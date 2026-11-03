from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from foxden import ConfigError
from migration import (EVIDENCE_GATES, create_backup, docker_inventory, hardware_inventory,
                       inventory, load_evidence, prepare_rehearsal, readiness, restore_rehearsal,
                       rollback_rehearsal, verify_backup)


def fixture_values(tmp_path: Path) -> dict[str, str]:
    music = tmp_path / "live-fixture" / "music-config"
    qbit = tmp_path / "live-fixture" / "qbittorrent-config"
    music.mkdir(parents=True)
    qbit.mkdir(parents=True)
    (music / "foxden-music.db").write_bytes(b"synthetic-sqlite-state")
    (qbit / "BT_backup").mkdir()
    (qbit / "BT_backup" / "example.fastresume").write_bytes(b"synthetic-resume-state")
    return {"MUSIC_CONFIG_PATH": str(music), "QBIT_CONFIG_PATH": str(qbit)}


def test_inventory_is_read_only_and_excludes_contents(tmp_path: Path) -> None:
    report = inventory(fixture_values(tmp_path))
    assert report["read_only"] is True
    assert {entry["role"] for entry in report["entries"]} == {"music-config", "qbittorrent-config"}
    assert "synthetic-sqlite-state" not in str(report)


def test_backup_requires_writer_stop_confirmation(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="writers-stopped"):
        create_backup(fixture_values(tmp_path), tmp_path / "backups", execute=True, writers_stopped=False)


def test_backup_verify_and_isolated_restore_round_trip(tmp_path: Path) -> None:
    archive = create_backup(fixture_values(tmp_path), tmp_path / "backups", execute=True,
                            writers_stopped=True, source_commit="a" * 40)
    assert archive is not None and verify_backup(archive)
    manifest = json.loads(archive.with_suffix(archive.suffix + ".manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_commit"] == "a" * 40
    assert all(item["sha256"] for item in manifest["files"])
    restore = tmp_path / "restore"
    report = restore_rehearsal(archive, restore, execute=True)
    assert report and report["result"] == "pass"
    assert (restore / "music-config" / "foxden-music.db").read_bytes() == b"synthetic-sqlite-state"
    assert (restore / "qbittorrent-config" / "BT_backup" / "example.fastresume").exists()


def test_restore_refuses_nonempty_destination(tmp_path: Path) -> None:
    archive = create_backup(fixture_values(tmp_path), tmp_path / "backups", execute=True, writers_stopped=True)
    destination = tmp_path / "restore"
    destination.mkdir()
    (destination / "keep.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(ConfigError, match="empty"):
        restore_rehearsal(archive, destination, execute=True)


def test_backup_verification_rejects_manifest_tampering(tmp_path: Path) -> None:
    archive = create_backup(fixture_values(tmp_path), tmp_path / "backups", execute=True, writers_stopped=True)
    manifest_path = archive.with_suffix(archive.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ConfigError, match="manifests do not match"):
        verify_backup(archive)


def test_rollback_rehearsal_restores_only_to_empty_isolated_target(tmp_path: Path) -> None:
    archive = create_backup(fixture_values(tmp_path), tmp_path / "backups", execute=True, writers_stopped=True)
    report = rollback_rehearsal(archive, tmp_path / "rollback", execute=True)
    assert report and report["kind"] == "rollback-rehearsal"
    assert report["result"] == "pass"


def test_prepare_rehearsal_uses_copied_state_and_synthetic_payload_roots(tmp_path: Path) -> None:
    values = fixture_values(tmp_path)
    archive = create_backup(values, tmp_path / "backups", execute=True, writers_stopped=True)
    output_env = tmp_path / "private" / "rehearsal.env"
    report = prepare_rehearsal(archive, tmp_path / "rehearsal", values, output_env, execute=True)
    rendered = output_env.read_text(encoding="utf-8")
    assert report and report["production_paths_reused"] is False
    assert report["network_ready"] is False
    assert "live-fixture" not in rendered
    assert 'COMPOSE_PROJECT_NAME="foxden-rehearsal"' in rendered
    assert "CHANGE_ME_REHEARSAL_WIREGUARD" in rendered
    assert (tmp_path / "rehearsal" / "synthetic-media" / "music").is_dir()


def test_large_data_roots_are_inventory_only_and_not_backed_up(tmp_path: Path) -> None:
    values = fixture_values(tmp_path)
    library = tmp_path / "media-library"
    library.mkdir()
    (library / "large-placeholder.mkv").write_bytes(b"fixture")
    values["MEDIA_LIBRARY_PATH"] = str(library)

    report = inventory(values)
    media = next(entry for entry in report["entries"] if entry["role"] == "media-library")
    assert media["content_scan"] == "skipped-large-data-root"
    archive = create_backup(values, tmp_path / "backups", execute=True, writers_stopped=True)
    assert archive is not None
    restore = tmp_path / "restore-large"
    restore_rehearsal(archive, restore, execute=True)
    assert not (restore / "media-library").exists()


def test_jellyfin_state_is_backed_up_but_media_is_inventory_only(tmp_path: Path) -> None:
    values = fixture_values(tmp_path)
    config = tmp_path / "jellyfin" / "config"
    cache = tmp_path / "jellyfin" / "cache"
    media = tmp_path / "jellyfin" / "media"
    for path in (config, cache, media):
        path.mkdir(parents=True)
    (config / "jellyfin.db").write_bytes(b"synthetic-jellyfin-database")
    (cache / "image.cache").write_bytes(b"synthetic-cache")
    (media / "movie.mkv").write_bytes(b"synthetic-media")
    values.update(JELLYFIN_CONFIG_PATH=str(config), JELLYFIN_CACHE_PATH=str(cache), JELLYFIN_MEDIA_PATH=str(media))
    report = inventory(values)
    assert next(item for item in report["entries"] if item["role"] == "jellyfin-media")["content_scan"] == "skipped-large-data-root"
    archive = create_backup(values, tmp_path / "backups", execute=True, writers_stopped=True)
    restore = tmp_path / "restore-jellyfin"
    restore_rehearsal(archive, restore, execute=True)
    assert (restore / "jellyfin-config" / "jellyfin.db").exists()
    assert (restore / "jellyfin-cache" / "image.cache").exists()
    assert not (restore / "jellyfin-media").exists()


def test_readiness_stays_closed_until_every_evidence_gate_passes(tmp_path: Path) -> None:
    from test_deployment import configured
    values = configured(tmp_path, "music")
    pending = readiness(values, "music")
    assert pending["ready_for_cutover"] is False
    assert pending["decision"] == "BLOCKED"
    assert any(item["status"] == "missing" for item in pending["checks"])

    commit = "b" * 40
    nas = {"inventory_reviewed", "writers_stopped", "final_backup_verified",
           "client_validation_passed", "cutover_approved"}
    evidence = [{
        "test_name": key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": "ci" if key == "hosted_ci_passed" else ("nas" if key in nas else "isolated-staging"),
        "source_version": "0.8.0", "source_commit": commit, "artifact_id": f"artifact-{key}",
        "result": "pass", "checksums": {"report": "c" * 64},
        "operator_approval_required": key == "cutover_approved",
        "operator_approved": key == "cutover_approved", "failure_details": None, "critical": True,
    } for key in EVIDENCE_GATES]
    passed = readiness(values, "music", evidence, source_commit=commit)
    assert passed["ready_for_cutover"] is True
    assert passed["decision"] == "CUTOVER_READY"
    assert all(item["status"] == "pass" for item in passed["checks"])

    next(item for item in evidence if item["test_name"] == "rollback_confirmed")["result"] = "fail"
    assert readiness(values, "music", evidence, source_commit=commit)["ready_for_cutover"] is False


def test_legacy_boolean_evidence_can_never_authorize_cutover(tmp_path: Path) -> None:
    from test_deployment import configured
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({key: True for key in EVIDENCE_GATES}), encoding="utf-8")
    report = readiness(configured(tmp_path, "music"), "music", load_evidence(path))
    assert report["decision"] == "BLOCKED"


def test_evidence_parser_rejects_unknown_or_non_boolean_values(tmp_path: Path) -> None:
    bad = tmp_path / "bad-evidence.json"
    bad.write_text('{"inventory_reviewed": "yes", "secret": true}', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_evidence(bad)


def test_docker_inventory_redacts_secrets_and_health_commands() -> None:
    container = {
        "Id": "1" * 64, "Image": "sha256:image", "Name": "/foxden-portal",
        "Config": {"Image": "foxden-portal:0.8.0", "User": "1000:1000",
                   "Env": ["PUID=1000", "PGID=1000", "TOKEN=must-not-leak"],
                   "Labels": {"com.docker.compose.project": "foxden", "com.docker.compose.service": "portal",
                              "traefik.http.middlewares.secret.basicauth.users": "must-not-leak"},
                   "Healthcheck": {"Test": ["CMD", "curl", "?token=must-not-leak"], "Retries": 3}},
        "HostConfig": {"RestartPolicy": {"Name": "unless-stopped"}, "Devices": []},
        "State": {"Status": "running", "Health": {"Status": "healthy"}},
        "NetworkSettings": {"Ports": {"8020/tcp": [{"HostPort": "8020"}]}, "Networks": {"platform": {}}},
        "Mounts": [{"Type": "bind", "Source": "/srv/portal", "Destination": "/config", "RW": True}],
    }

    def runner(command, **_kwargs):
        if command[:2] == ["docker", "version"]:
            output = json.dumps({"Version": "29", "ApiVersion": "1.52", "Os": "linux", "Arch": "amd64"})
        elif command[:3] == ["docker", "ps", "-a"]:
            output = "1" * 64 + "\n"
        elif command[:2] == ["docker", "inspect"]:
            output = json.dumps([container])
        elif command[:3] == ["docker", "image", "inspect"]:
            output = json.dumps([{"Id": "sha256:image", "RepoDigests": ["foxden@sha256:" + "d" * 64]}])
        elif command[:3] == ["docker", "volume", "ls"] or command[:3] == ["docker", "network", "ls"]:
            output = ""
        else:
            raise AssertionError(command)
        return SimpleNamespace(stdout=output, stderr="", returncode=0)

    report = docker_inventory(runner)
    serialized = json.dumps(report)
    assert "must-not-leak" not in serialized
    assert report["containers"][0]["identity_environment"] == {"PUID": "1000", "PGID": "1000"}
    assert report["containers"][0]["healthcheck"]["configured"] is True
    assert report["containers"][0]["compose"]["project"] == "foxden"


def test_hardware_inventory_never_claims_transcoding_from_device_discovery(tmp_path: Path) -> None:
    report = hardware_inventory(tmp_path / "missing-dri", runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    assert report["read_only"] is True
    assert report["transcode_proven"] is False
