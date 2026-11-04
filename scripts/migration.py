#!/usr/bin/env python3
"""Fail-closed inventory, backup, restore, and migration-rehearsal tooling."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from foxden import ConfigError, load_env, validate

PLATFORM_VERSION = "0.9.1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_ENV = {"PUID", "PGID", "UID", "GID", "TZ", "UMASK", "UMASK_SET"}

PATH_ROLES = {
    "foxden-secrets": "FOXDEN_SECRETS_DIR",
    "portal-config": "PORTAL_CONFIG_PATH",
    "music-config": "MUSIC_CONFIG_PATH",
    "music-staging": "MUSIC_STAGING_PATH",
    "music-downloads": "MUSIC_DOWNLOAD_PATH",
    "music-library": "MUSIC_LIBRARY_PATH",
    "media-config": "MEDIA_CONFIG_PATH",
    "media-library": "MEDIA_LIBRARY_PATH",
    "torrent-data": "TORRENT_DATA_PATH",
    "qbittorrent-config": "QBIT_CONFIG_PATH",
    "gluetun-config": "GLUETUN_CONFIG_PATH",
    "jellyfin-config": "JELLYFIN_CONFIG_PATH",
    "jellyfin-cache": "JELLYFIN_CACHE_PATH",
    "jellyfin-media": "JELLYFIN_MEDIA_PATH",
}
BACKUP_ROLES = {
    "foxden-secrets", "portal-config", "music-config", "music-staging",
    "music-downloads", "media-config", "qbittorrent-config",
    "gluetun-config", "jellyfin-config", "jellyfin-cache",
}
LARGE_DATA_ROLES = {"music-library", "media-library", "torrent-data", "jellyfin-media"}

MODE_INVENTORY_ROLES = {
    "music": {"foxden-secrets", "portal-config", "music-config", "music-staging",
              "music-downloads", "music-library"},
    "media": {"foxden-secrets", "portal-config", "media-config", "media-library",
              "torrent-data"},
    "jellyfin": {"foxden-secrets", "portal-config", "jellyfin-config", "jellyfin-cache",
                 "jellyfin-media"},
    "full-external": {"foxden-secrets", "portal-config", "music-config", "music-staging",
                      "music-downloads", "music-library", "media-config", "media-library",
                      "torrent-data"},
    "full-managed": set(PATH_ROLES) - {"jellyfin-config", "jellyfin-cache", "jellyfin-media"},
}

GATE_DEFINITIONS = {
    "hosted_ci_passed": ("hosted CI passed for the exact release commit", {"ci"}),
    "inventory_reviewed": ("read-only production inventory reviewed", {"nas"}),
    "writers_stopped": ("production writers stopped", {"nas"}),
    "final_backup_verified": ("final consistent backup verified", {"nas"}),
    "restore_rehearsal_passed": ("isolated restore rehearsal passed", {"isolated-staging", "nas"}),
    "portal_rehearsal_passed": ("Portal identity and database rehearsal passed", {"isolated-staging", "nas"}),
    "music_rehearsal_passed": ("Music database, worker, imports, and tagging rehearsal passed", {"isolated-staging", "nas"}),
    "media_rehearsal_passed": ("Movies/TV state, paths, and duplicate controls passed", {"isolated-staging", "nas"}),
    "torrent_vpn_rehearsal_passed": ("qBittorrent resume and VPN fail-closed rehearsal passed", {"isolated-staging", "nas"}),
    "jellyfin_rehearsal_passed": ("Jellyfin users, libraries, history, and playback rehearsal passed", {"isolated-staging", "nas"}),
    "client_validation_passed": ("browser and native-client validation passed", {"nas"}),
    "rollback_confirmed": ("rollback rehearsal passed", {"isolated-staging", "nas"}),
    "cutover_approved": ("operator approved the reviewed cutover", {"nas"}),
}
EVIDENCE_GATES = {key: value[0] for key, value in GATE_DEFINITIONS.items()}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, data: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(path, 0o600)


def _path_entry(role: str, variable: str, path: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {"role": role, "variable": variable, "path": str(path), "exists": path.exists()}
    if not path.exists():
        return entry
    details = path.stat()
    usage = shutil.disk_usage(path)
    entry.update({
        "mode": stat.filemode(details.st_mode), "uid": getattr(details, "st_uid", None),
        "gid": getattr(details, "st_gid", None), "device": details.st_dev,
        "capacity_bytes": usage.total, "free_bytes": usage.free,
    })
    if path.is_dir() and role not in LARGE_DATA_ROLES:
        files, bytes_total = 0, 0
        for root, dirs, names in os.walk(path, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
            for name in names:
                candidate = Path(root) / name
                try:
                    if candidate.is_file() and not candidate.is_symlink():
                        files += 1
                        bytes_total += candidate.stat().st_size
                except OSError:
                    entry["scan_warning"] = "One or more entries could not be inspected."
        entry.update(files=files, bytes=bytes_total)
    elif path.is_dir():
        entry["content_scan"] = "skipped-large-data-root"
    return entry


def inventory(values: dict[str, str], required_roles: set[str] | None = None) -> dict[str, Any]:
    entries = []
    for role, key in PATH_ROLES.items():
        raw = values.get(key, "").strip()
        if raw:
            entries.append(_path_entry(role, key, Path(raw).expanduser()))
    configured = {item["role"] for item in entries}
    required = required_roles or set()
    missing_required = sorted(required - configured)
    warnings = []
    if not entries:
        warnings.append("No application storage paths were configured; Docker metadata alone is not migration inventory.")
    if missing_required:
        warnings.append("Required storage roles are absent: " + ", ".join(missing_required))
    return {
        "schema": 2, "generated_at": _utc(), "read_only": True, "entries": entries,
        "configured_roles": sorted(configured), "missing_required_roles": missing_required,
        "complete": bool(entries) and not missing_required, "warnings": warnings,
        "notes": [
            "Secret contents, authentication databases, tokens, and VPN keys were not inspected.",
            "Container state and SQLite consistency require the sanitized host inventory and quiesce gate.",
        ],
    }


def require_complete_inventory(report: dict[str, Any]) -> None:
    if not report.get("complete"):
        details = "; ".join(report.get("warnings") or ["inventory is incomplete"])
        raise ConfigError(f"Refusing incomplete production inventory: {details}")


class _BencodeReader:
    """Small bounded decoder for offline qBittorrent recovery inspection."""

    def __init__(self, data: bytes):
        if len(data) > 64 * 1024 * 1024:
            raise ConfigError("Bencoded recovery file exceeds the 64 MiB inspection limit.")
        self.data = data
        self.position = 0

    def parse(self, depth: int = 0) -> Any:
        if depth > 64 or self.position >= len(self.data):
            raise ConfigError("Bencoded recovery data is malformed or too deeply nested.")
        marker = self.data[self.position:self.position + 1]
        if marker == b"i":
            self.position += 1
            end = self.data.find(b"e", self.position)
            if end < 0:
                raise ConfigError("Bencoded integer is unterminated.")
            raw = self.data[self.position:end]
            if not re.fullmatch(rb"-?(?:0|[1-9][0-9]*)", raw):
                raise ConfigError("Bencoded integer is invalid.")
            self.position = end + 1
            return int(raw)
        if marker in {b"l", b"d"}:
            self.position += 1
            if marker == b"l":
                output = []
                while self.data[self.position:self.position + 1] != b"e":
                    output.append(self.parse(depth + 1))
                self.position += 1
                return output
            output = {}
            while self.data[self.position:self.position + 1] != b"e":
                key = self.parse(depth + 1)
                if not isinstance(key, bytes):
                    raise ConfigError("Bencoded dictionary key is not bytes.")
                if key in output:
                    raise ConfigError("Bencoded dictionary contains a duplicate key.")
                output[key] = self.parse(depth + 1)
            self.position += 1
            return output
        if marker.isdigit():
            colon = self.data.find(b":", self.position)
            if colon < 0:
                raise ConfigError("Bencoded byte string length is missing.")
            raw_length = self.data[self.position:colon]
            if not raw_length.isdigit() or (len(raw_length) > 1 and raw_length.startswith(b"0")):
                raise ConfigError("Bencoded byte string length is invalid.")
            length = int(raw_length)
            start, end = colon + 1, colon + 1 + length
            if end > len(self.data):
                raise ConfigError("Bencoded byte string is truncated.")
            self.position = end
            return self.data[start:end]
        raise ConfigError("Bencoded recovery data contains an unsupported marker.")

    def complete(self) -> Any:
        value = self.parse()
        if self.position != len(self.data):
            raise ConfigError("Bencoded recovery data contains trailing bytes.")
        return value


def _decode_recovery_value(value: Any) -> str | None:
    if not isinstance(value, bytes) or len(value) > 4096:
        return None
    return value.decode("utf-8", errors="replace")


def _encode_bencode(value: Any) -> bytes:
    if isinstance(value, int):
        return b"i" + str(value).encode("ascii") + b"e"
    if isinstance(value, bytes):
        return str(len(value)).encode("ascii") + b":" + value
    if isinstance(value, list):
        return b"l" + b"".join(_encode_bencode(item) for item in value) + b"e"
    if isinstance(value, dict):
        return b"d" + b"".join(_encode_bencode(key) + _encode_bencode(value[key])
                                for key in sorted(value)) + b"e"
    raise ConfigError("Decoded recovery data cannot be canonically re-encoded.")


def _resume_metadata(value: Any) -> dict[str, Any]:
    wanted = {b"save_path", b"qBt-savePath", b"qBt-tempPath", b"qBt-contentPath",
              b"qBt-category", b"qBt-tags"}
    found: dict[str, Any] = {}

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key in wanted:
                    decoded = _decode_recovery_value(child)
                    if decoded is not None:
                        found[key.decode("ascii")] = decoded
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return found


def _read_bencoded(path: Path) -> Any:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ConfigError("Bencoded recovery file exceeds the 64 MiB inspection limit.")
    return _BencodeReader(path.read_bytes()).complete()


def discover_qbittorrent_state(config_root: Path) -> dict[str, Any]:
    """Inspect copied qBittorrent state without starting qBittorrent or using the network."""
    config_root = config_root.expanduser().resolve()
    candidates = [config_root / "qBittorrent" / "BT_backup", config_root / "BT_backup"]
    backup_root = next((path for path in candidates if path.is_dir()), None)
    if backup_root is None:
        raise ConfigError("qBittorrent BT_backup was not found under the supplied copied config root.")
    torrents = {path.stem: path for path in backup_root.glob("*.torrent") if path.is_file()}
    resumes = {path.stem: path for path in backup_root.glob("*.fastresume") if path.is_file()}
    records = []
    for torrent_hash in sorted(set(torrents) | set(resumes)):
        torrent, resume = torrents.get(torrent_hash), resumes.get(torrent_hash)
        record: dict[str, Any] = {
            "torrent_hash": torrent_hash, "torrent_present": torrent is not None,
            "fastresume_present": resume is not None, "paired": torrent is not None and resume is not None,
        }
        if torrent:
            record["torrent_sha256"] = _sha256(torrent)
            try:
                decoded_torrent = _read_bencoded(torrent)
                record["torrent_bencode_valid"] = isinstance(decoded_torrent, dict) and b"info" in decoded_torrent
                if record["torrent_bencode_valid"]:
                    encoded_info = _encode_bencode(decoded_torrent[b"info"])
                    algorithm = "sha1" if len(torrent_hash) == 40 else "sha256" if len(torrent_hash) == 64 else None
                    if algorithm:
                        computed = hashlib.new(algorithm, encoded_info).hexdigest()
                        record["computed_info_hash"] = computed
                        record["hash_matches_filename"] = computed.lower() == torrent_hash.lower()
                    else:
                        record["hash_matches_filename"] = False
            except ConfigError as exc:
                record["torrent_bencode_valid"] = False
                record["torrent_error"] = str(exc)
        if resume:
            record["fastresume_sha256"] = _sha256(resume)
            try:
                decoded_resume = _read_bencoded(resume)
                record["fastresume_bencode_valid"] = isinstance(decoded_resume, dict)
                record["resume_metadata"] = _resume_metadata(decoded_resume)
                record["absolute_paths"] = sorted({value for key, value in record["resume_metadata"].items()
                                                   if "path" in key.lower() and
                                                   (PurePosixPath(value).is_absolute() or
                                                    re.match(r"^[A-Za-z]:[\\/]", value))})
            except ConfigError as exc:
                record["fastresume_bencode_valid"] = False
                record["fastresume_error"] = str(exc)
        records.append(record)
    complete = bool(records) and all(item.get("paired") and item.get("torrent_bencode_valid")
                                     and item.get("hash_matches_filename")
                                     and item.get("fastresume_bencode_valid") for item in records)
    return {
        "schema": 1, "generated_at": _utc(), "read_only": True, "offline": True,
        "config_root": str(config_root), "bt_backup": str(backup_root),
        "torrent_files": len(torrents), "fastresume_files": len(resumes),
        "pair_count": sum(1 for item in records if item["paired"]), "complete_pairs": complete,
        "records": records,
        "warning": "This proves structural readability only; payload presence, client-version compatibility, trackers, peers and seeding are not tested.",
    }


def discover_sqlite_state(state_root: Path) -> dict[str, Any]:
    """Inspect SQLite files in a copied state tree using immutable read-only connections."""
    state_root = state_root.expanduser().resolve()
    if not state_root.is_dir():
        raise ConfigError("Copied application state root does not exist.")
    records = []
    for path in sorted(state_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
            continue
        record: dict[str, Any] = {"path": path.relative_to(state_root).as_posix(),
                                  "size": path.stat().st_size, "sha256": _sha256(path)}
        try:
            uri = f"file:{path.as_posix()}?mode=ro&immutable=1"
            with sqlite3.connect(uri, uri=True) as connection:
                record["quick_check"] = connection.execute("PRAGMA quick_check").fetchone()[0]
                record["user_version"] = connection.execute("PRAGMA user_version").fetchone()[0]
                record["tables"] = sorted(row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        except sqlite3.Error as exc:
            record["quick_check"] = "error"
            record["error"] = str(exc)[:300]
        records.append(record)
    return {"schema": 1, "generated_at": _utc(), "read_only": True, "immutable": True,
            "state_root": str(state_root), "databases": records,
            "structurally_readable": bool(records) and all(item.get("quick_check") == "ok" for item in records),
            "warning": "Structural SQLite readability is not application-schema compatibility; run the matching application against a disposable restored copy."}


def _docker_json(command: list[str], runner: Callable[..., Any]) -> Any:
    try:
        result = runner(command, capture_output=True, text=True, check=True, timeout=30)
        return json.loads(result.stdout or "[]")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ConfigError(f"Read-only Docker inventory failed for {' '.join(command[:3])}.") from exc


def _safe_container(container: dict[str, Any], image: dict[str, Any] | None) -> dict[str, Any]:
    config, host, state = container.get("Config") or {}, container.get("HostConfig") or {}, container.get("State") or {}
    labels = config.get("Labels") or {}
    safe_env = {}
    for item in config.get("Env") or []:
        key, _, value = item.partition("=")
        if key in SAFE_ID_ENV:
            safe_env[key] = value
    health = config.get("Healthcheck") or {}
    return {
        "name": str(container.get("Name", "")).lstrip("/"), "id": str(container.get("Id", ""))[:12],
        "image_reference": config.get("Image"), "image_id": container.get("Image"),
        "image_digests": sorted((image or {}).get("RepoDigests") or []),
        "compose": {key.removeprefix("com.docker.compose."): labels[key]
                    for key in ("com.docker.compose.project", "com.docker.compose.service") if key in labels},
        "state": {"status": state.get("Status"), "health": (state.get("Health") or {}).get("Status")},
        "user": config.get("User") or None, "identity_environment": safe_env,
        "restart_policy": (host.get("RestartPolicy") or {}).get("Name") or "no",
        "published_ports": container.get("NetworkSettings", {}).get("Ports") or {},
        "networks": sorted((container.get("NetworkSettings", {}).get("Networks") or {}).keys()),
        "mounts": [{"type": item.get("Type"), "source": item.get("Source"),
                    "destination": item.get("Destination"), "read_write": bool(item.get("RW")),
                    "name": item.get("Name")} for item in container.get("Mounts") or []],
        "healthcheck": {"configured": bool(health), "interval": health.get("Interval"),
                        "timeout": health.get("Timeout"), "retries": health.get("Retries"),
                        "start_period": health.get("StartPeriod")},
        "devices": [{"host": item.get("PathOnHost"), "container": item.get("PathInContainer"),
                     "permissions": item.get("CgroupPermissions")} for item in host.get("Devices") or []],
        "reverse_proxy_label_keys": sorted(
            key for key in labels if key.lower().startswith(("traefik.", "caddy", "nginx."))),
    }


def docker_inventory(runner: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    version = _docker_json(["docker", "version", "--format", "{{json .Server}}"], runner)
    try:
        listed = runner(["docker", "ps", "-a", "--no-trunc", "--format", "{{.ID}}"],
                        capture_output=True, text=True, check=True, timeout=30)
        ids = [value for value in listed.stdout.splitlines() if value.strip()]
        containers = _docker_json(["docker", "inspect", *ids], runner) if ids else []
        image_ids = sorted({item.get("Image") for item in containers if item.get("Image")})
        images = _docker_json(["docker", "image", "inspect", *image_ids], runner) if image_ids else []
        by_id = {item.get("Id"): item for item in images}
        volume_names = runner(["docker", "volume", "ls", "-q"], capture_output=True, text=True,
                              check=True, timeout=30).stdout.split()
        volumes = _docker_json(["docker", "volume", "inspect", *volume_names], runner) if volume_names else []
        network_ids = runner(["docker", "network", "ls", "-q"], capture_output=True, text=True,
                             check=True, timeout=30).stdout.split()
        networks = _docker_json(["docker", "network", "inspect", *network_ids], runner) if network_ids else []
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ConfigError("Read-only Docker inventory failed.") from exc
    return {
        "schema": 1, "generated_at": _utc(), "read_only": True,
        "docker_server": {"version": version.get("Version"), "api_version": version.get("ApiVersion"),
                          "os": version.get("Os"), "architecture": version.get("Arch")},
        "containers": [_safe_container(item, by_id.get(item.get("Image"))) for item in containers],
        "volumes": [{"name": item.get("Name"), "driver": item.get("Driver"),
                     "mountpoint": item.get("Mountpoint"),
                     "compose_project": (item.get("Labels") or {}).get("com.docker.compose.project")}
                    for item in volumes],
        "networks": [{"name": item.get("Name"), "id": str(item.get("Id", ""))[:12],
                      "driver": item.get("Driver"), "scope": item.get("Scope"),
                      "internal": bool(item.get("Internal")), "attachable": bool(item.get("Attachable"))}
                     for item in networks],
        "redaction": "Non-identity environment values, health commands, label values, credentials, and tokens were omitted.",
    }


def backup_sources(values: dict[str, str]) -> dict[str, Path]:
    sources = {}
    for role, key in PATH_ROLES.items():
        if role in BACKUP_ROLES and values.get(key, "").strip():
            path = Path(values[key]).expanduser().resolve()
            if path.exists():
                sources[role] = path
    return sources


def _source_manifest(sources: dict[str, Path], source_commit: str) -> dict[str, Any]:
    files, roles = [], []
    for role, source in sorted(sources.items()):
        count, size = 0, 0
        for candidate in sorted(source.rglob("*")):
            if candidate.is_symlink():
                raise ConfigError(f"Backup source contains a symlink; review it explicitly: {role}/{candidate.relative_to(source)}")
            if not candidate.is_file():
                continue
            details = candidate.stat()
            files.append({"role": role, "path": candidate.relative_to(source).as_posix(),
                          "size": details.st_size, "sha256": _sha256(candidate),
                          "mode": stat.S_IMODE(details.st_mode), "uid": getattr(details, "st_uid", None),
                          "gid": getattr(details, "st_gid", None), "mtime_ns": details.st_mtime_ns})
            count, size = count + 1, size + details.st_size
        source_details = source.stat()
        roles.append({"role": role, "files": count, "bytes": size,
                      "mode": stat.S_IMODE(source_details.st_mode),
                      "uid": getattr(source_details, "st_uid", None),
                      "gid": getattr(source_details, "st_gid", None),
                      "mtime_ns": source_details.st_mtime_ns})
    return {"schema": 2, "platform_version": PLATFORM_VERSION, "source_commit": source_commit,
            "created_at": _utc(), "consistency": "writers-stopped", "roles": roles, "files": files}


def create_backup(values: dict[str, str], destination: Path, *, execute: bool,
                  writers_stopped: bool, source_commit: str = "unknown") -> Path | None:
    sources = backup_sources(values)
    if not sources:
        raise ConfigError("No existing state directories were configured.")
    destination = destination.expanduser().resolve()
    for source in sources.values():
        if destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
            raise ConfigError("Backup destination must not overlap a source directory.")
    print("Backup source plan (contents are not printed):")
    for role, source in sources.items():
        print(f"  {role}: {source}")
    if not execute:
        print("Dry run only. Quiesce all writers and repeat with --writers-stopped --execute.")
        return None
    if not writers_stopped:
        raise ConfigError("Refusing backup without --writers-stopped confirmation; live SQLite copying is unsafe.")
    manifest = _source_manifest(sources, source_commit)
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = destination / f"foxden-state-{stamp}.tar.gz"
    with tarfile.open(archive, "x:gz", format=tarfile.PAX_FORMAT) as bundle:
        info = tarfile.TarInfo("backup-manifest.json")
        info.size, info.mode, info.mtime = len(manifest_bytes), 0o600, int(datetime.now().timestamp())
        bundle.addfile(info, io.BytesIO(manifest_bytes))
        for role, source in sorted(sources.items()):
            directory = tarfile.TarInfo(role)
            directory.type, directory.mode, directory.mtime = tarfile.DIRTYPE, 0o700, int(source.stat().st_mtime)
            bundle.addfile(directory)
            for item in (value for value in manifest["files"] if value["role"] == role):
                bundle.add(source / item["path"], arcname=f"{role}/{item['path']}", recursive=False)
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{_sha256(archive)}  {archive.name}\n", encoding="ascii")
    _write_json(archive.with_suffix(archive.suffix + ".manifest.json"), manifest, private=True)
    verify_backup(archive)
    print(f"Created and verified consistent backup archive {archive}")
    return archive


def _manifest_from_archive(bundle: tarfile.TarFile) -> tuple[dict[str, Any], bytes]:
    try:
        stream = bundle.extractfile("backup-manifest.json")
        raw = stream.read() if stream else b""
        manifest = json.loads(raw)
    except (KeyError, json.JSONDecodeError) as exc:
        raise ConfigError("Backup manifest is missing or invalid.") from exc
    if manifest.get("schema") != 2 or not isinstance(manifest.get("files"), list):
        raise ConfigError("Backup manifest schema is unsupported.")
    return manifest, raw


def verify_backup(archive: Path) -> bool:
    archive = archive.resolve()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    external_manifest = archive.with_suffix(archive.suffix + ".manifest.json")
    if not archive.is_file() or not checksum.is_file() or not external_manifest.is_file():
        raise ConfigError("Archive, checksum, or external manifest is missing.")
    expected = checksum.read_text(encoding="ascii").split()[0]
    if not SHA256_RE.fullmatch(expected) or _sha256(archive) != expected:
        raise ConfigError("Backup checksum does not match.")
    with tarfile.open(archive, "r:gz") as bundle:
        manifest, raw_manifest = _manifest_from_archive(bundle)
        if json.loads(external_manifest.read_text(encoding="utf-8")) != manifest:
            raise ConfigError("External and embedded backup manifests do not match.")
        canonical = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        if hashlib.sha256(raw_manifest).digest() != hashlib.sha256(canonical).digest():
            raise ConfigError("Embedded backup manifest is not canonical.")
        expected_members = {"backup-manifest.json"}
        for item in manifest["files"]:
            if not SHA256_RE.fullmatch(str(item.get("sha256", ""))):
                raise ConfigError("Backup manifest contains an invalid file record.")
            name = f"{item['role']}/{item['path']}"
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ConfigError("Backup contains an unsafe path.")
            expected_members.add(name)
            try:
                member = bundle.getmember(name)
            except KeyError as exc:
                raise ConfigError(f"Backup is incomplete: {name}") from exc
            if not member.isfile() or member.issym() or member.islnk():
                raise ConfigError(f"Backup contains an unsupported member: {name}")
            stream = bundle.extractfile(member)
            digest, size = hashlib.sha256(), 0
            for block in iter(lambda: stream.read(1024 * 1024), b"") if stream else ():
                digest.update(block)
                size += len(block)
            if digest.hexdigest() != item["sha256"] or size != item["size"]:
                raise ConfigError(f"Backup file verification failed: {name}")
        for member in bundle.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise ConfigError("Backup contains an unsafe member.")
            if member.isfile() and member.name not in expected_members:
                raise ConfigError(f"Backup contains an unmanifested file: {member.name}")
    print(f"Backup verified: {archive.name} ({len(manifest['files'])} files)")
    return True


def _restore(archive: Path, destination: Path, *, apply_ownership: bool = False) -> dict[str, Any]:
    if apply_ownership and (not hasattr(os, "geteuid") or os.geteuid() != 0):
        raise ConfigError("Applying recorded numeric ownership requires root on a POSIX rehearsal host.")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as bundle:
        manifest, _ = _manifest_from_archive(bundle)
        for role in manifest["roles"]:
            role_path = destination / role["role"]
            role_path.mkdir(mode=int(role["mode"]), parents=True, exist_ok=True)
            os.chmod(role_path, int(role["mode"]))
            if apply_ownership and role.get("uid") is not None and role.get("gid") is not None:
                os.chown(role_path, int(role["uid"]), int(role["gid"]))
        for item in manifest["files"]:
            target = destination / item["role"] / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = bundle.extractfile(f"{item['role']}/{item['path']}")
            if stream is None:
                raise ConfigError("Backup file disappeared during restore.")
            with target.open("xb") as output:
                shutil.copyfileobj(stream, output)
            os.chmod(target, int(item["mode"]))
            if apply_ownership and item.get("uid") is not None and item.get("gid") is not None:
                os.chown(target, int(item["uid"]), int(item["gid"]))
            os.utime(target, ns=(int(item["mtime_ns"]), int(item["mtime_ns"])))
    failures = []
    for item in manifest["files"]:
        target = destination / item["role"] / item["path"]
        if not target.is_file() or target.stat().st_size != item["size"] or _sha256(target) != item["sha256"]:
            failures.append(f"{item['role']}/{item['path']}")
    return {"schema": 1, "generated_at": _utc(), "archive": archive.name,
            "archive_sha256": _sha256(archive), "destination": str(destination),
            "files_verified": len(manifest["files"]) - len(failures), "failures": failures,
            "result": "pass" if not failures else "fail",
            "ownership_applied": apply_ownership,
            "ownership_note": "Numeric ownership is recorded in the manifest; apply it only during operator-reviewed production restore."}


def restore_rehearsal(archive: Path, destination: Path, *, execute: bool,
                      report_path: Path | None = None,
                      apply_ownership: bool = False) -> dict[str, Any] | None:
    verify_backup(archive)
    destination = destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ConfigError("Restore destination must be empty.")
    print(f"Restore target: {destination}")
    if not execute:
        print("Dry run only. Repeat with --execute to restore into this isolated destination.")
        return None
    report = _restore(archive.resolve(), destination, apply_ownership=apply_ownership)
    if report_path:
        _write_json(report_path, report)
    if report["result"] != "pass":
        raise ConfigError("Restore verification failed.")
    print("Restore rehearsal completed and verified. This does not authorize a production cutover.")
    return report


def rollback_rehearsal(archive: Path, destination: Path, *, execute: bool,
                       report_path: Path | None = None,
                       apply_ownership: bool = False) -> dict[str, Any] | None:
    report = restore_rehearsal(archive, destination, execute=execute,
                               apply_ownership=apply_ownership)
    if report is None:
        return None
    report.update(kind="rollback-rehearsal", recovery_source="immutable-pre-migration-backup",
                  old_binary_database_rule="never-use-a-database-modified-by-a-newer-incompatible-version")
    if report_path:
        _write_json(report_path, report)
    print("Rollback state restored into an isolated target; application startup remains a separate gate.")
    return report


def prepare_rehearsal(archive: Path, destination: Path, values: dict[str, str], output_env: Path,
                      *, execute: bool) -> dict[str, Any] | None:
    """Restore copied state and write a deliberately non-production environment."""
    verify_backup(archive)
    destination = destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ConfigError("Rehearsal destination must be empty.")
    if not execute:
        print(f"Dry run only. Rehearsal state would be restored under {destination}.")
        return None
    restore_report = _restore(archive.resolve(), destination)
    if restore_report["result"] != "pass":
        raise ConfigError("Rehearsal restore verification failed.")
    rehearsal = dict(values)
    rehearsal.update({
        "COMPOSE_PROJECT_NAME": "foxden-rehearsal", "FOXDEN_REHEARSAL": "true",
        "FOXDEN_PUBLIC_ORIGIN": "http://127.0.0.1:18080", "FOXDEN_PORT": "18080",
        "FOXDEN_RUNTIME_DIR": str(destination / "runtime"), "PORTAL_AUTH_MODE": "local",
        "PORTAL_OIDC_ISSUER": "", "PORTAL_OIDC_CLIENT_ID": "",
        "QBIT_URL": "http://127.0.0.1:1",
        "WIREGUARD_ADDRESSES": "CHANGE_ME_REHEARSAL_WIREGUARD_ADDRESSES",
        "WIREGUARD_PUBLIC_KEY": "CHANGE_ME_REHEARSAL_WIREGUARD_PUBLIC_KEY",
        "WIREGUARD_ENDPOINT_IP": "CHANGE_ME_REHEARSAL_WIREGUARD_ENDPOINT",
        "JELLYFIN_PUBLIC_URL": "http://127.0.0.1:18096",
        "JELLYFIN_INTERNAL_URL": "http://jellyfin:8096",
    })
    for role, variable in PATH_ROLES.items():
        restored = destination / role
        if restored.is_dir() and role not in LARGE_DATA_ROLES:
            rehearsal[variable] = str(restored)
    synthetic_media = destination / "synthetic-media"
    for path in (destination / "runtime", destination / "browser", destination / "synthetic-torrents",
                 synthetic_media / "music", synthetic_media / "video"):
        path.mkdir(parents=True, exist_ok=True)
    rehearsal.update({
        "MUSIC_LIBRARY_PATH": str(synthetic_media / "music"),
        "MEDIA_LIBRARY_PATH": str(synthetic_media / "video"),
        "JELLYFIN_MEDIA_PATH": str(synthetic_media),
        "TORRENT_DATA_PATH": str(destination / "synthetic-torrents"),
        "BROWSER_CONFIG_PATH": str(destination / "browser"),
    })
    output_env.parent.mkdir(parents=True, exist_ok=True)
    output_env.write_text("\n".join(
        f"{key}={json.dumps(str(value))}" for key, value in sorted(rehearsal.items())) + "\n", encoding="utf-8")
    os.chmod(output_env, 0o600)
    report = {
        "schema": 1, "generated_at": _utc(), "result": "pass",
        "archive_sha256": _sha256(archive), "destination": str(destination),
        "environment_file": str(output_env), "compose_project": "foxden-rehearsal",
        "production_paths_reused": False, "network_ready": False,
        "blocking_placeholders": ["WIREGUARD_ADDRESSES", "WIREGUARD_PUBLIC_KEY", "WIREGUARD_ENDPOINT_IP"],
        "note": "Add only separately approved staging network credentials; never production VPN credentials in CI.",
    }
    print(f"Prepared isolated rehearsal state and private environment file at {output_env}.")
    return report


def load_evidence(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "schema" not in data:
        if set(data) - set(GATE_DEFINITIONS) or any(not isinstance(value, bool) for value in data.values()):
            raise ConfigError("Legacy evidence contains an unknown gate or non-boolean value.")
        return [{"test_name": key, "timestamp": _utc(), "environment": "legacy",
                 "source_version": "unknown", "source_commit": "unknown", "artifact_id": "legacy-boolean",
                 "result": "pass" if value else "fail", "checksums": {},
                 "operator_approval_required": True, "operator_approved": False,
                 "failure_details": None if value else "Legacy gate recorded false.", "critical": True}
                for key, value in data.items()]
    if not isinstance(data, dict) or data.get("schema") != 2 or not isinstance(data.get("records"), list):
        raise ConfigError("Evidence must use schema 2 with a records array.")
    required = {"test_name", "timestamp", "environment", "source_version", "source_commit", "artifact_id",
                "result", "checksums", "operator_approval_required", "operator_approved", "failure_details", "critical"}
    for record in data["records"]:
        if not isinstance(record, dict) or not required <= set(record):
            raise ConfigError("Every evidence record must contain the documented provenance fields.")
        if record["test_name"] not in GATE_DEFINITIONS or record["result"] not in {"pass", "fail", "pending"}:
            raise ConfigError("Evidence contains an unknown test or result.")
        if record["environment"] not in {"ci", "isolated-staging", "nas"}:
            raise ConfigError("Evidence environment must be ci, isolated-staging, or nas.")
        try:
            datetime.fromisoformat(str(record["timestamp"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ConfigError("Evidence timestamp must be ISO-8601.") from exc
        if not isinstance(record["checksums"], dict) or any(
                not SHA256_RE.fullmatch(str(value)) for value in record["checksums"].values()):
            raise ConfigError("Evidence checksums must be SHA-256 values.")
        if any(not isinstance(record[key], bool) for key in
               ("operator_approval_required", "operator_approved", "critical")):
            raise ConfigError("Evidence approval and critical fields must be booleans.")
    return data["records"]


def readiness(values: dict[str, str], mode: str, evidence: list[dict[str, Any]] | None = None,
              *, source_version: str = PLATFORM_VERSION, source_commit: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        validate(mode, values)
        checks.append({"name": "configuration", "status": "pass"})
    except (ConfigError, OSError, ValueError) as exc:
        checks.append({"name": "configuration", "status": "fail", "detail": str(exc)})
    path_report = inventory(values)
    missing = [str(item["role"]) for item in path_report["entries"] if not item["exists"]]
    checks.append({"name": "configured-paths", "status": "pass" if not missing else "fail",
                   "detail": "all configured paths exist" if not missing else "missing: " + ", ".join(missing)})
    records = evidence or []
    for key, (label, allowed_environments) in GATE_DEFINITIONS.items():
        candidates = [item for item in records if item["test_name"] == key]
        passing = [item for item in candidates if item["result"] == "pass"
                   and item["environment"] in allowed_environments
                   and item["source_version"] == source_version
                   and (not source_commit or item["source_commit"] == source_commit)]
        if not candidates:
            status, detail = "missing", "No evidence record was supplied."
        elif not passing:
            status, detail = "fail", "No passing record matches the required environment and exact release source."
        else:
            newest = passing[-1]
            if newest["operator_approval_required"] and not newest["operator_approved"]:
                status, detail = "manual-approval-required", "Evidence passed but operator approval is absent."
            else:
                status, detail = "pass", f"artifact={newest['artifact_id']} environment={newest['environment']}"
        checks.append({"name": label, "evidence_key": key, "status": status, "detail": detail})
    ready = all(item["status"] == "pass" for item in checks)
    return {"schema": 2, "generated_at": _utc(), "mode": mode, "source_version": source_version,
            "source_commit": source_commit, "decision": "CUTOVER_READY" if ready else "BLOCKED",
            "ready_for_cutover": ready, "checks": checks, "inventory": path_report,
            "warning": "CI or fixture evidence alone never authorizes a production cutover."}


def human_readiness(report: dict[str, Any]) -> str:
    lines = [f"# Fox Den Media {report['source_version']} migration readiness", "",
             f"Decision: **{report['decision']}**", "", "| Gate | Status | Detail |", "|---|---|---|"]
    for item in report["checks"]:
        lines.append(f"| {item['name']} | {item['status']} | {item.get('detail', '')} |")
    return "\n".join(lines + ["", "> CI success alone does not grant production approval.", ""])


def hardware_inventory(device_root: Path = Path("/dev/dri"),
                       runner: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    devices = []
    if device_root.is_dir():
        for device in sorted(device_root.iterdir()):
            details = device.stat()
            devices.append({"path": str(device), "mode": stat.filemode(details.st_mode),
                            "uid": getattr(details, "st_uid", None), "gid": getattr(details, "st_gid", None),
                            "character_device": stat.S_ISCHR(details.st_mode)})
    probes: dict[str, Any] = {}
    for name, command in {"ffmpeg_hwaccels": ["ffmpeg", "-hide_banner", "-hwaccels"],
                          "vainfo": ["vainfo", "--display", "drm"]}.items():
        try:
            result = runner(command, capture_output=True, text=True, timeout=20, check=False)
            safe_lines = [line[:300] for line in (result.stdout + result.stderr).splitlines()
                          if any(word in line.lower() for word in ("vaapi", "qsv", "intel", "driver", "render"))]
            probes[name] = {"available": True, "exit_code": result.returncode, "summary": safe_lines[:50]}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            probes[name] = {"available": False}
    return {"schema": 1, "generated_at": _utc(), "read_only": True, "device_root": str(device_root),
            "devices": devices, "probes": probes, "transcode_proven": False,
            "note": "Device discovery is not proof of hardware transcoding; run the isolated synthetic transcode gate."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fox Den Media migration rehearsal tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--env", type=Path, required=True)
    inv.add_argument("--output", type=Path, required=True)
    host = sub.add_parser("host-inventory")
    host.add_argument("--env", type=Path, required=True)
    host.add_argument("--output", type=Path, required=True)
    host.add_argument("--expected-mode", choices=tuple(sorted(MODE_INVENTORY_ROLES)), required=True)
    host.add_argument("--allow-partial", action="store_true",
                      help="write an explicitly incomplete report instead of failing on missing storage roles")
    hardware = sub.add_parser("hardware-inventory")
    hardware.add_argument("--output", type=Path, required=True)
    qbit = sub.add_parser("qbit-discovery")
    qbit.add_argument("--config-root", type=Path, required=True,
                      help="copied qBittorrent appdata root; never point CI at live production state")
    qbit.add_argument("--output", type=Path, required=True)
    sqlite = sub.add_parser("sqlite-discovery")
    sqlite.add_argument("--state-root", type=Path, required=True,
                        help="copied Music or Jellyfin state root")
    sqlite.add_argument("--output", type=Path, required=True)
    ready = sub.add_parser("readiness")
    ready.add_argument("--env", type=Path, required=True)
    ready.add_argument("--mode", choices=("music", "media", "jellyfin", "full-external", "full-managed"), required=True)
    ready.add_argument("--output", type=Path, required=True)
    ready.add_argument("--human-output", type=Path)
    ready.add_argument("--evidence", type=Path)
    ready.add_argument("--source-version", default=PLATFORM_VERSION)
    ready.add_argument("--source-commit")
    backup = sub.add_parser("backup")
    backup.add_argument("--env", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True)
    backup.add_argument("--source-commit", default="unknown")
    backup.add_argument("--writers-stopped", action="store_true")
    backup.add_argument("--execute", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    prepare = sub.add_parser("prepare-rehearsal")
    prepare.add_argument("archive", type=Path)
    prepare.add_argument("--env", type=Path, required=True)
    prepare.add_argument("--destination", type=Path, required=True)
    prepare.add_argument("--output-env", type=Path, required=True)
    prepare.add_argument("--report", type=Path)
    prepare.add_argument("--execute", action="store_true")
    for name in ("restore-rehearsal", "rollback-rehearsal"):
        restore = sub.add_parser(name)
        restore.add_argument("archive", type=Path)
        restore.add_argument("--destination", type=Path, required=True)
        restore.add_argument("--report", type=Path)
        restore.add_argument("--apply-ownership", action="store_true",
                             help="apply recorded numeric UID/GID; requires root and explicit review")
        restore.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            _write_json(args.output, inventory(load_env(args.env.resolve())))
        elif args.command == "host-inventory":
            report = inventory(load_env(args.env.resolve()), MODE_INVENTORY_ROLES[args.expected_mode])
            report["docker"] = docker_inventory()
            _write_json(args.output, report, private=True)
            if not args.allow_partial:
                require_complete_inventory(report)
        elif args.command == "hardware-inventory":
            _write_json(args.output, hardware_inventory())
        elif args.command == "qbit-discovery":
            _write_json(args.output, discover_qbittorrent_state(args.config_root), private=True)
        elif args.command == "sqlite-discovery":
            _write_json(args.output, discover_sqlite_state(args.state_root), private=True)
        elif args.command == "readiness":
            report = readiness(load_env(args.env.resolve()), args.mode, load_evidence(args.evidence),
                               source_version=args.source_version, source_commit=args.source_commit)
            _write_json(args.output, report)
            if args.human_output:
                args.human_output.parent.mkdir(parents=True, exist_ok=True)
                args.human_output.write_text(human_readiness(report), encoding="utf-8")
        elif args.command == "backup":
            create_backup(load_env(args.env.resolve()), args.destination, execute=args.execute,
                          writers_stopped=args.writers_stopped, source_commit=args.source_commit)
        elif args.command == "verify":
            verify_backup(args.archive)
        elif args.command == "prepare-rehearsal":
            report = prepare_rehearsal(args.archive, args.destination, load_env(args.env.resolve()),
                                       args.output_env, execute=args.execute)
            if report and args.report:
                _write_json(args.report, report)
        elif args.command == "restore-rehearsal":
            restore_rehearsal(args.archive, args.destination, execute=args.execute,
                              report_path=args.report, apply_ownership=args.apply_ownership)
        else:
            rollback_rehearsal(args.archive, args.destination, execute=args.execute,
                               report_path=args.report, apply_ownership=args.apply_ownership)
        return 0
    except (ConfigError, OSError, tarfile.TarError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Migration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
