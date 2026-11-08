"""Synthetic offline R1/R2 positive and negative tests (no GHCR or NAS)."""
import hashlib
import json
from pathlib import Path
import pytest
import yaml
from scripts.release_lock import (
    ReleaseLockError, SERVICE_IMAGE, FIRST_PARTY, UPSTREAM,
    selected_services, validate_lock,
)
from scripts.release_metadata import ReleaseMetadataError, validate_metadata

SRC = "a" * 40
DIGEST = "b" * 64
COMPOSE = b"services:\n  portal: {}\n"

def make_lock(profiles=("music", "media", "managed", "browser", "jellyfin")):
    services = selected_services(set(profiles))
    images = set(SERVICE_IMAGE[s] for s in services)
    return {
        "schema_version": 1,
        "version": "1.0.0",
        "source_sha": SRC,
        "compose_sha256": hashlib.sha256(COMPOSE).hexdigest(),
        "platform": "linux/amd64",
        "profiles": list(profiles),
        "services": {s: SERVICE_IMAGE[s] for s in sorted(services)},
        "images": {
            name: {
                "ref": f"{({**FIRST_PARTY, **UPSTREAM})[name]}@sha256:{DIGEST}",
                "platform": "linux/amd64", "platform_digest": "c" * 64,
                "source_sha": SRC if name in FIRST_PARTY else None,
            } for name in images
        },
        "rollback": {"version": "0.9.1", "lock_sha256": "d" * 64},
        "publisher": {"workflow": "ghcr-candidates.yml", "run_id": 12345, "source_sha": SRC},
    }

def render(data):
    return {"services": {
        s: {"image": data["images"][name]["ref"]}
        for s, name in data["services"].items()
    }}

def test_complete_lock_and_same_music_digest():
    data = make_lock()
    assert data["services"]["music"] == data["services"]["music-worker"]
    validate_lock(data, compose=COMPOSE, rendered=render(data), expected_source=SRC)

@pytest.mark.parametrize("mutation", [
    lambda d: d.update(source_sha="f" * 40),
    lambda d: d.update(compose_sha256="f" * 64),
    lambda d: d.update(platform="linux/arm64"),
    lambda d: d["profiles"].append("unknown"),
    lambda d: d["services"].update({"rogue": "portal"}),
    lambda d: d["services"].update({"music-worker": "portal"}),
    lambda d: d["images"]["music"].update(ref="ghcr.io/itsfoxxin/fox-den-media-music:latest"),
    lambda d: d["images"]["music"].update(ref=f"ghcr.io/itsfoxxin/fox-den-media-music:sha-{SRC}@sha256:{DIGEST}"),
    lambda d: d["images"]["media"].update(ref=f"ghcr.io/attacker/fox-den-media-media@sha256:{DIGEST}"),
    lambda d: d["images"]["portal"].update(source_sha="f" * 40),
    lambda d: d["images"]["portal"].update(platform_digest="bad"),
    lambda d: d["images"]["nginx"].update(source_sha=SRC),
    lambda d: d["publisher"].update(source_sha="f" * 40),
    lambda d: d["rollback"].update(lock_sha256=""),
    lambda d: d.update(secrets={"TOKEN": "not allowed"}),
])
def test_bad_lock_fails_closed(mutation):
    data = make_lock()
    mutation(data)
    with pytest.raises(ReleaseLockError):
        validate_lock(data, compose=COMPOSE, expected_source=SRC)

def test_wrong_source_and_compose_rejected():
    with pytest.raises(ReleaseLockError, match="Wrong approved"):
        validate_lock(make_lock(), expected_source="f" * 40)
    with pytest.raises(ReleaseLockError, match="Compose hash"):
        validate_lock(make_lock(), compose=b"changed")

def test_worker_must_use_exact_music_digest_and_no_build():
    data = make_lock()
    config = render(data)
    config["services"]["music-worker"]["image"] = (
        f"ghcr.io/itsfoxxin/fox-den-media-music@sha256:{'e' * 64}"
    )
    with pytest.raises(ReleaseLockError, match="digest mismatch"):
        validate_lock(data, rendered=config)
    config = render(data)
    config["services"]["portal"]["build"] = {"context": "apps/portal"}
    with pytest.raises(ReleaseLockError, match="rebuild"):
        validate_lock(data, rendered=config)

def test_missing_image_or_profile_fails():
    data = make_lock()
    del data["images"]["media"]
    with pytest.raises(ReleaseLockError, match="Missing/unused"):
        validate_lock(data)
    with pytest.raises(ReleaseLockError, match="Browser requires Music"):
        validate_lock(make_lock(("browser",)))

def test_r1_metadata_validation_fixture(tmp_path):
    for directory in ("apps/media", "deploy"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "VERSION").write_text("1.0.0\n")
    (tmp_path / "apps/media/VERSION").write_text("1.0.0\n")
    (tmp_path / "apps/media/Dockerfile").write_text("COPY apps/media/VERSION ./VERSION\n")
    (tmp_path / "README.md").write_text("Current source milestone: **1.0.0**.\n")
    (tmp_path / "CHANGELOG.md").write_text("## 1.0.0 - 2026-11-07\n")
    (tmp_path / "deploy/compose.yaml").write_text('image: "${MEDIA_IMAGE:-fox-den-media:1.0.0}"\n')
    validate_metadata(tmp_path, SRC, SRC)
    with pytest.raises(ReleaseMetadataError, match="main HEAD"):
        validate_metadata(tmp_path, SRC, "f" * 40)
    (tmp_path / "CHANGELOG.md").write_text("## 1.0.0 - 2026-11-07\n## 1.0.0 - 2026-11-08\n")
    with pytest.raises(ReleaseMetadataError, match="exactly one"):
        validate_metadata(tmp_path, SRC, SRC)
    (tmp_path / "CHANGELOG.md").write_text("## 1.0.0 - 2026-11-07\n")
    (tmp_path / "apps/media/VERSION").write_text("0.9.6\n")
    with pytest.raises(ReleaseMetadataError, match="Media VERSION"):
        validate_metadata(tmp_path, SRC, SRC)

ROOT = Path(__file__).resolve().parents[2]

def test_deployed_compose_service_and_profile_contract():
    """Catch Compose inventory drift before the release lock is approved."""
    compose = yaml.safe_load((ROOT / "deploy/compose.yaml").read_text())
    services = compose["services"]
    assert set(services) == set(SERVICE_IMAGE)
    expected = {
        "ingress": set(), "portal": set(),
        "music": {"music"}, "music-worker": {"music"},
        "media": {"media"}, "download-browser": {"browser"},
        "jellyfin": {"jellyfin"}, "gluetun": {"managed"},
        "qbittorrent": {"managed"},
    }
    for name, profiles in expected.items():
        assert set(services[name].get("profiles", [])) == profiles
        assert ("build" in services[name]) == (name in {"portal", "music", "music-worker", "media"})
    assert services["music"]["image"] == services["music-worker"]["image"]
    assert services["music"]["build"] == services["music-worker"]["build"]
    assert services["media"]["build"]["dockerfile"] == "apps/media/Dockerfile"
    assert services["portal"]["build"]["context"] == "../apps/portal"

def test_versioned_json_schema_matches_runtime_contract():
    """Schema metadata must not drift away from the enforcing Python validator."""
    from scripts.release_lock import ROOT_KEYS, IMAGE_KEYS
    schema = json.loads((ROOT / "docs/release-lock-v1.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == ROOT_KEYS == set(schema["properties"])
    image_schema = schema["properties"]["images"]["additionalProperties"]
    assert set(image_schema["required"]) == IMAGE_KEYS == set(image_schema["properties"])
    assert schema["properties"]["platform"]["const"] == "linux/amd64"

@pytest.mark.parametrize("profile_set", [
    (), ("music",), ("media",), ("jellyfin",),
    ("music", "browser"), ("music", "media", "managed", "jellyfin"),
])
def test_supported_profile_release_locks(profile_set):
    candidate = make_lock(profile_set)
    validate_lock(candidate, compose=COMPOSE, rendered=render(candidate), expected_source=SRC)

@pytest.mark.parametrize("rollback", ["1.0.0", "1.0.1", "2.0.0"])
def test_reject_current_or_future_rollback(rollback):
    candidate = make_lock()
    candidate["rollback"]["version"] = rollback
    with pytest.raises(ReleaseLockError, match="Rollback must precede"):
        validate_lock(candidate)

def test_r1_rejects_fake_or_malformed_metadata(tmp_path):
    for directory in ("apps/media", "deploy"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "VERSION").write_text("1.0.0\n")
    (tmp_path / "apps/media/VERSION").write_text("1.0.0\n")
    (tmp_path / "apps/media/Dockerfile").write_text("COPY apps/media/VERSION ./VERSION\n")
    (tmp_path / "README.md").write_text("Not the milestone: **1.0.0**\n")
    (tmp_path / "CHANGELOG.md").write_text("## 1.0.0 - 2026-11-08\n")
    (tmp_path / "deploy/compose.yaml").write_text('image: "${MEDIA_IMAGE:-fox-den-media:1.0.0}"\n')
    with pytest.raises(ReleaseMetadataError, match="README current source milestone"):
        validate_metadata(tmp_path, SRC, SRC)
    (tmp_path / "README.md").write_text("Current source milestone: **1.0.0**.\n")
    (tmp_path / "CHANGELOG.md").write_text("## 1.0.0 - 2026-02-30\n")
    with pytest.raises(ReleaseMetadataError, match="calendar date"):
        validate_metadata(tmp_path, SRC, SRC)
    (tmp_path / "CHANGELOG.md").write_text("## 1.0.0 - 2026-11-08\n")
    (tmp_path / "deploy/compose.yaml").write_text("image: random:1.0.0\n")
    with pytest.raises(ReleaseMetadataError, match="Compose version"):
        validate_metadata(tmp_path, SRC, SRC)
