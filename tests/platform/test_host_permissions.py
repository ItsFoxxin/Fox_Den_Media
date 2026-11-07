"""Host permission provisioning: security and idempotence tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts import host_permissions as p


def test_role_uid_gid_are_independent():
    values = {
        "FOXDEN_PUID": "10001", "FOXDEN_PGID": "10002",
        "MUSIC_PUID": "1000005", "MUSIC_PGID": "1000004",
        "MEDIA_PUID": "11111", "MEDIA_PGID": "11112",
        "QBIT_PUID": "1000", "QBIT_PGID": "1000",
    }
    assert p.role_identity(values, "FOXDEN") == (10001, 10002)
    assert p.role_identity(values, "MUSIC") == (1000005, 1000004)
    assert p.role_identity(values, "MEDIA") == (11111, 11112)
    assert p.role_identity(values, "QBIT") == (1000, 1000)
    assert p.role_identity(values, "ROOT") == (0, 0)
    values["MEDIA_PUID"] = "invalid"
    with pytest.raises(p.PermissionSetupError, match="Invalid numeric"):
        p.role_identity(values, "MEDIA")


def test_each_secret_has_only_intended_service_reader():
    assert p.SECRET_ROLES["identity-private.pem"] == "FOXDEN"
    assert p.SECRET_ROLES["portal-secret"] == "FOXDEN"
    assert p.SECRET_ROLES["music-csrf"] == "MUSIC"
    assert p.SECRET_ROLES["media-app-token"] == "MEDIA"
    assert p.SECRET_ROLES["qbit-password"] == "MEDIA"
    assert p.SECRET_ROLES["jellyfin-api-key"] == "MUSIC"
    assert p.SECRET_ROLES["wireguard-private-key"] == "ROOT"
    assert "MUSIC_DOWNLOAD_PATH" not in p.DIRECTORY_ROLES
    assert "TORRENT_DATA_PATH" not in p.DIRECTORY_ROLES
    assert "JELLYFIN_MEDIA_PATH" not in p.DIRECTORY_ROLES


def test_inspection_fails_closed_when_host_owner_is_not_service_uid(tmp_path: Path):
    root = tmp_path / "secrets"
    root.mkdir()
    file = root / "portal-secret"
    file.write_text("synthetic-not-live")
    file.chmod(0o600)
    target_uid = 10001 if os.getuid() != 10001 else 10002
    values = {"FOXDEN_SECRETS_DIR": str(root), "FOXDEN_PUID": str(target_uid),
              "FOXDEN_PGID": "10001"}
    with pytest.raises(p.PermissionSetupError, match="container identity"):
        p.inspect_secret_owners(values, names={"portal-secret"})


def test_inspection_rejects_symlink_and_hardlink(tmp_path: Path):
    root = tmp_path / "secrets"
    root.mkdir()
    base = tmp_path / "base"
    base.write_text("test")
    (root / "portal-secret").symlink_to(base)
    values = {"FOXDEN_SECRETS_DIR": str(root), "FOXDEN_PUID": "10001",
              "FOXDEN_PGID": "10001"}
    with pytest.raises(p.PermissionSetupError, match="unsafe"):
        p.inspect_secret_owners(values, names={"portal-secret"})
    (root / "portal-secret").unlink()
    os.link(base, root / "portal-secret")
    with pytest.raises(p.PermissionSetupError, match="unsafe"):
        p.inspect_secret_owners(values, names={"portal-secret"})


def test_provision_without_root_fails_before_changing_files(tmp_path: Path, monkeypatch):
    secret_dir, runtime_dir = tmp_path / "secrets", tmp_path / "runtime"
    secret_dir.mkdir()
    runtime_dir.mkdir()
    monkeypatch.setattr(p.os, "geteuid", lambda: 1000)
    with pytest.raises(p.PermissionSetupError, match="requires host root"):
        p.provision_permissions({
            "FOXDEN_SECRETS_DIR": str(secret_dir),
            "FOXDEN_RUNTIME_DIR": str(runtime_dir),
        }, created_directories=set())


def test_provision_is_idempotent_and_skips_populated_existing_dirs(tmp_path: Path, monkeypatch):
    root, runtime = tmp_path / "secrets", tmp_path / "runtime"
    root.mkdir()
    runtime.mkdir()
    portal = root / "portal-secret"
    portal.write_text("must-preserve-secret")
    portal.chmod(0o600)
    populated = tmp_path / "copied"
    populated.mkdir()
    (populated / "existing.db").write_text("must-preserve-db")
    empty = tmp_path / "empty-config"
    empty.mkdir()
    values = {
        "FOXDEN_SECRETS_DIR": str(root),
        "FOXDEN_RUNTIME_DIR": str(runtime),
        "FOXDEN_PUID": "10001", "FOXDEN_PGID": "10001",
        "PORTAL_CONFIG_PATH": str(empty), "MUSIC_CONFIG_PATH": str(populated),
    }
    monkeypatch.setattr(p.os, "geteuid", lambda: 0)
    seen = []
    monkeypatch.setattr(p.os, "chown", lambda path, uid, gid, **kw: seen.append((str(path), uid, gid)))
    monkeypatch.setattr(p.os, "fchown", lambda fd, uid, gid: seen.append(("secret", uid, gid)))
    monkeypatch.setattr(p.os, "fchmod", lambda fd, mode: seen.append(("file-mode", mode)))
    monkeypatch.setattr(p.os, "chmod", lambda path, mode, **kw: seen.append(("directory-mode", str(path), mode)))
    for _ in range(2):
        p.provision_permissions(values, created_directories=set())
    assert portal.read_text() == "must-preserve-secret"
    assert (populated / "existing.db").read_text() == "must-preserve-db"
    assert all(call[0] != str(populated) for call in seen)
    assert ("secret", 10001, 10001) in seen
    assert (str(empty), 10001, 10001) in seen
    assert ("directory-mode", str(empty), 0o700) in seen


def test_preflight_rejects_unsafe_file_before_mutation(tmp_path: Path, monkeypatch):
    secrets, runtime = tmp_path / "secrets", tmp_path / "runtime"
    secrets.mkdir()
    runtime.mkdir()
    (secrets / "portal-secret").symlink_to(tmp_path / "target")
    monkeypatch.setattr(p.os, "geteuid", lambda: 0)
    monkeypatch.setattr(p.os, "chown", lambda *args, **kwargs: pytest.fail("mutation before preflight"))
    with pytest.raises(p.PermissionSetupError, match="unsafe"):
        p.provision_permissions({
            "FOXDEN_SECRETS_DIR": str(secrets),
            "FOXDEN_RUNTIME_DIR": str(runtime),
            "FOXDEN_PUID": "10001", "FOXDEN_PGID": "10001",
        }, created_directories=set())
