"""Explicit, fail-closed host permission provisioning for rootful Docker deployments.

Never walk or recursively chown copied NAS data. The caller must explicitly opt
in using init --apply-permissions, running with host root privileges.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path


class PermissionSetupError(RuntimeError):
    pass


# The identities consuming each *individual read-only bind-mounted* file.
# Gluetun runs as root in the current Compose file; its key remains root-only.
SECRET_ROLES = {
    "portal-secret": "FOXDEN",
    "portal-bootstrap": "FOXDEN",
    "ingress-auth": "FOXDEN",
    "identity-private.pem": "FOXDEN",
    "oidc-client-secret": "FOXDEN",
    "music-csrf": "MUSIC",
    "jellyfin-api-key": "MUSIC",
    "media-app-token": "MEDIA",
    "qbit-password": "MEDIA",
    "wireguard-private-key": "ROOT",
}
PUBLIC_FILES = {"identity-public.json"}

# Exact leaf paths only. Never follow children or attempt to repair copied state.
DIRECTORY_ROLES = {
    "PORTAL_CONFIG_PATH": "FOXDEN",
    "MUSIC_CONFIG_PATH": "MUSIC",
    "MUSIC_STAGING_PATH": "MUSIC",
    "MUSIC_LIBRARY_PATH": "MUSIC",
    "MEDIA_CONFIG_PATH": "MEDIA",
    "MEDIA_LIBRARY_PATH": "MEDIA",
    "QBIT_CONFIG_PATH": "QBIT",
    "GLUETUN_CONFIG_PATH": "ROOT",
    "JELLYFIN_CONFIG_PATH": "JELLYFIN",
    "JELLYFIN_CACHE_PATH": "JELLYFIN",
    "BROWSER_CONFIG_PATH": "FOXDEN",
}
# Shared or external paths such as MUSIC_DOWNLOAD_PATH, TORRENT_DATA_PATH and JELLYFIN_MEDIA_PATH
# are deliberately excluded. The operator must audit existing ACLs separately.


def role_identity(values: dict[str, str], role: str) -> tuple[int, int]:
    if role == "ROOT":
        return 0, 0
    fallback_uid = values["FOXDEN_PUID"]
    fallback_gid = values["FOXDEN_PGID"]
    try:
        uid = int(values.get(f"{role}_PUID", fallback_uid))
        gid = int(values.get(f"{role}_PGID", fallback_gid))
    except (TypeError, ValueError) as exc:
        raise PermissionSetupError(f"Invalid numeric identity for {role}.") from exc
    if uid <= 0 or gid <= 0:
        raise PermissionSetupError(f"{role} requires a positive UID and GID.")
    return uid, gid


def _safe_file(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise PermissionSetupError(f"Refusing non-regular, linked or unsafe file: {path.name}")


def _safe_directory(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
        raise PermissionSetupError(f"Refusing non-directory or symlink: {path}")


def inspect_secret_owners(values: dict[str, str], *, names: set[str]) -> None:
    """Check ownership as well as 0600; the caller's own UID is not sufficient."""
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    _safe_directory(secret_dir)
    for name in sorted(names & SECRET_ROLES.keys()):
        target = secret_dir / name
        _safe_file(target)
        uid, gid = role_identity(values, SECRET_ROLES[name])
        info = target.stat()
        if (info.st_uid, info.st_gid) != (uid, gid) or stat.S_IMODE(info.st_mode) != 0o600:
            raise PermissionSetupError(
                f"{name} must be owned by container identity {uid}:{gid}, mode 0600; "
                "run init --apply-permissions using host root on an approved isolated copy."
            )


def provision_permissions(values: dict[str, str], *, created_directories: set[Path]) -> None:
    """Reconcile only known individual secrets and newly created or empty leaves.

    Requires host root. No recursive operations and no changes to nonempty
    copied-state directories. Does not read or display the secret contents.
    """
    if os.name != "posix" or os.geteuid() != 0:
        raise PermissionSetupError(
            "Permission provisioning requires host root (sudo); this is not a "
            "runtime container operation. Do not run it against live NAS paths."
        )
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    runtime_dir = Path(values["FOXDEN_RUNTIME_DIR"])
    _safe_directory(secret_dir)
    _safe_directory(runtime_dir)

    planned: list[tuple[Path, tuple[int, int], int]] = []
    for name, role in SECRET_ROLES.items():
        path = secret_dir / name
        if not path.exists() and not path.is_symlink():
            continue
        _safe_file(path)
        planned.append((path, role_identity(values, role), 0o600))
    for name in PUBLIC_FILES:
        path = secret_dir / name
        if path.exists() or path.is_symlink():
            _safe_file(path)
            planned.append((path, role_identity(values, "FOXDEN"), 0o644))

    # Only created paths and empty pre-existing configuration directories may
    # be retargeted. Preserve imported data and its existing ownership.
    for key, role in DIRECTORY_ROLES.items():
        raw = values.get(key, "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute() or not path.exists():
            continue
        _safe_directory(path)
        if path not in created_directories and any(path.iterdir()):
            continue
        mode = 0o700
        planned.append((path, role_identity(values, role), mode))

    # Preflight is complete before any metadata mutation. Keep host directories
    # private; Docker daemon resolves the per-file source bind mounts.
    os.chown(secret_dir, 0, 0, follow_symlinks=False)
    os.chmod(secret_dir, 0o700, follow_symlinks=False)
    os.chown(runtime_dir, 0, 0, follow_symlinks=False)
    os.chmod(runtime_dir, 0o700, follow_symlinks=False)
    for path, (uid, gid), mode in planned:
        if path.is_dir():
            os.chown(path, uid, gid, follow_symlinks=False)
            os.chmod(path, mode, follow_symlinks=False)
            continue
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PermissionSetupError(f"Refusing unsafe secret: {path.name}")
            os.fchown(fd, uid, gid)
            os.fchmod(fd, mode)
        finally:
            os.close(fd)
