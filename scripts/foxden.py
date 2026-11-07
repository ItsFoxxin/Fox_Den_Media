#!/usr/bin/env python3
"""Validated, environment-driven entry point for Fox Den Media deployments."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import stat
import subprocess
import sys
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "compose.yaml"
GATEWAY_TEMPLATE = ROOT / "infra" / "gateway" / "portal-ingress.conf"

MODES = {
    "music": {"profiles": ("music",), "modules": {"music"}},
    "media": {"profiles": ("media",), "modules": {"media"}},
    "jellyfin": {"profiles": ("jellyfin",), "modules": set()},
    "full-external": {"profiles": ("music", "media"), "modules": {"music", "media"}},
    "full-managed": {"profiles": ("music", "media", "managed"), "modules": {"music", "media"}},
}
CORE_PATHS = ("FOXDEN_SECRETS_DIR", "FOXDEN_RUNTIME_DIR", "PORTAL_CONFIG_PATH")
MUSIC_PATHS = ("MUSIC_CONFIG_PATH", "MUSIC_STAGING_PATH", "MUSIC_DOWNLOAD_PATH", "MUSIC_LIBRARY_PATH")
MEDIA_PATHS = ("MEDIA_CONFIG_PATH", "MEDIA_LIBRARY_PATH", "TORRENT_DATA_PATH")
MANAGED_PATHS = ("QBIT_CONFIG_PATH", "GLUETUN_CONFIG_PATH")
JELLYFIN_PATHS = ("JELLYFIN_CONFIG_PATH", "JELLYFIN_CACHE_PATH", "JELLYFIN_MEDIA_PATH")
SECRET_FILES = ("portal-secret", "portal-bootstrap", "ingress-auth", "identity-private.pem", "identity-public.json")
MUSIC_SECRET_FILES = ("music-csrf",)
MEDIA_SECRET_FILES = ("media-app-token", "qbit-password")


class ConfigError(RuntimeError):
    pass


def _write_private_text(path: Path, value: str, *, exclusive: bool = False) -> None:
    """Create a private text file without a world-readable creation window."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            descriptor = -1
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ConfigError(f"Environment file does not exist: {path}")
    values: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigError(f"{path}:{line_number}: expected NAME=value")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value.startswith(("'", '"')):
            value = value[1:-1]
        if not key.replace("_", "").isalnum() or key[:1].isdigit():
            raise ConfigError(f"{path}:{line_number}: invalid variable name")
        values[key] = value
    return values


def _required(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value or value.startswith("CHANGE_ME"):
        raise ConfigError(f"Set {key} in the environment file.")
    return value


def _url(values: dict[str, str], key: str, *, https_only: bool = False) -> None:
    parsed = urlparse(_required(values, key))
    allowed = {"https"} if https_only else {"http", "https"}
    if parsed.scheme not in allowed or not parsed.netloc or parsed.username or parsed.password:
        raise ConfigError(f"{key} must be a valid {'HTTPS' if https_only else 'HTTP(S)'} URL without credentials.")


def _resources(values: dict[str, str]) -> None:
    for key, value in values.items():
        if key.endswith("_CPUS") and value.strip():
            try:
                if float(value) <= 0:
                    raise ValueError
            except ValueError as exc:
                raise ConfigError(f"{key} must be a positive CPU count.") from exc
        if key.endswith("_MEMORY_LIMIT") and value.strip():
            if not re.fullmatch(r"[1-9][0-9]*(?:[kKmMgGtT](?:[bB])?)?", value.strip()):
                raise ConfigError(f"{key} must be a positive Docker memory value such as 512m or 2g.")


def _paths(values: dict[str, str], keys: tuple[str, ...], *, create: bool = False) -> list[Path]:
    resolved: list[Path] = []
    for key in keys:
        path = Path(_required(values, key)).expanduser()
        if not path.is_absolute():
            raise ConfigError(f"{key} must be an absolute host path: {path}")
        if create:
            path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise ConfigError(f"{key} is not an existing directory: {path}")
        required_access = os.R_OK | os.X_OK
        if key not in {"TORRENT_DATA_PATH", "JELLYFIN_MEDIA_PATH"}:
            required_access |= os.W_OK
        if not os.access(path, required_access):
            expectation = "readable" if key in {"TORRENT_DATA_PATH", "JELLYFIN_MEDIA_PATH"} else "readable and writable"
            raise ConfigError(f"{key} must be {expectation} by the deployment UID/GID: {path}")
        resolved.append(path.resolve())
    if len(set(resolved)) != len(resolved):
        raise ConfigError("Configured storage roles must use distinct directories.")
    return resolved


def _secret(path: Path, *, allow_empty: bool = False, private: bool = True) -> None:
    if not path.is_file():
        raise ConfigError(f"Required secret file is missing: {path.name}")
    if not allow_empty and not path.read_bytes().strip():
        raise ConfigError(f"Required secret file is empty: {path.name}")
    if private and os.name != "nt" and path.stat().st_mode & 0o077:
        raise ConfigError(f"Secret file permissions are too broad; require mode 0600: {path.name}")


def validate(mode: str, values: dict[str, str], *, browser: bool = False, jellyfin: bool = False,
             jellyfin_hwaccel: bool = False, create_paths: bool = False) -> None:
    definition = MODES[mode]
    jellyfin = jellyfin or mode == "jellyfin" or jellyfin_hwaccel
    _resources(values)
    _url(values, "FOXDEN_PUBLIC_ORIGIN")
    for key in ("FOXDEN_PUID", "FOXDEN_PGID", "FOXDEN_PORT"):
        value = int(_required(values, key))
        if value <= 0 or (key == "FOXDEN_PORT" and value > 65535):
            raise ConfigError(f"{key} is outside its valid range.")
    for key in ("MUSIC_PUID", "MUSIC_PGID", "MEDIA_PUID", "MEDIA_PGID", "QBIT_PUID", "QBIT_PGID"):
        if values.get(key, "").strip():
            try:
                if int(values[key]) <= 0:
                    raise ValueError
            except ValueError as exc:
                raise ConfigError(f"{key} must be a positive numeric ID.") from exc
    all_paths = _paths(values, CORE_PATHS, create=create_paths)
    if "music" in definition["modules"]:
        all_paths += _paths(values, MUSIC_PATHS, create=create_paths)
        _required(values, "MUSICBRAINZ_CONTACT")
    if "media" in definition["modules"]:
        all_paths += _paths(values, MEDIA_PATHS, create=create_paths)
    if mode == "full-managed":
        all_paths += _paths(values, MANAGED_PATHS, create=create_paths)
        for key in ("WIREGUARD_ADDRESSES", "WIREGUARD_PUBLIC_KEY", "WIREGUARD_ENDPOINT_IP"):
            _required(values, key)
        small_check = values.get("GLUETUN_HEALTH_SMALL_CHECK_TYPE", "dns").strip().lower()
        if small_check not in {"dns", "icmp"}:
            raise ConfigError("GLUETUN_HEALTH_SMALL_CHECK_TYPE must be dns or icmp.")
        if values.get("HEALTH_SMALL_CHECK_TYPE", "").strip():
            raise ConfigError("Use GLUETUN_HEALTH_SMALL_CHECK_TYPE for managed Compose, not HEALTH_SMALL_CHECK_TYPE.")
    elif "media" in definition["modules"]:
        _url(values, "QBIT_URL")
    if jellyfin:
        jellyfin_paths = _paths(values, JELLYFIN_PATHS, create=create_paths)
        # The read-only Jellyfin media root may intentionally contain the Music
        # and Movies/TV library roots. Its writable config/cache must not overlap.
        all_paths += jellyfin_paths[:2]
        _url(values, "JELLYFIN_PUBLIC_URL")
        _url(values, "JELLYFIN_INTERNAL_URL")
        for key in ("JELLYFIN_PUID", "JELLYFIN_PGID"):
            if int(_required(values, key)) <= 0:
                raise ConfigError(f"{key} must be a positive numeric ID.")
        container_path = _required(values, "JELLYFIN_MEDIA_CONTAINER_PATH")
        if not container_path.startswith("/") or ".." in Path(container_path).parts:
            raise ConfigError("JELLYFIN_MEDIA_CONTAINER_PATH must be a safe absolute container path.")
    if jellyfin_hwaccel:
        device = Path(_required(values, "JELLYFIN_DRI_DEVICE"))
        if not device.is_absolute():
            raise ConfigError("JELLYFIN_DRI_DEVICE must be an absolute host device path.")
        if not device.exists():
            raise ConfigError(f"JELLYFIN_DRI_DEVICE does not exist on this host: {device}")
        for key in ("JELLYFIN_RENDER_GID", "JELLYFIN_VIDEO_GID"):
            if int(_required(values, key)) < 0:
                raise ConfigError(f"{key} must be a non-negative group ID.")
    if values.get("JELLYFIN_URL", "").strip():
        _url(values, "JELLYFIN_URL")
    if values.get("JELLYFIN_INTERNAL_URL", "").strip():
        _url(values, "JELLYFIN_INTERNAL_URL")
        _url(values, "JELLYFIN_PUBLIC_URL")
    if browser:
        all_paths += _paths(values, ("BROWSER_CONFIG_PATH",), create=create_paths)
        if "music" not in definition["modules"]:
            raise ConfigError("The contained browser currently requires a Music deployment mode.")
    for index, first in enumerate(all_paths):
        for second in all_paths[index + 1:]:
            if first == second or first in second.parents or second in first.parents:
                raise ConfigError("Host storage roles must be distinct, non-overlapping directories.")

    secret_dir = Path(values["FOXDEN_SECRETS_DIR"]).resolve()
    for name in SECRET_FILES:
        _secret(secret_dir / name, private=name != "identity-public.json")
    if "music" in definition["modules"]:
        for name in MUSIC_SECRET_FILES:
            _secret(secret_dir / name)
        if values.get("JELLYFIN_URL", "").strip():
            _secret(secret_dir / "jellyfin-api-key")
    if "media" in definition["modules"]:
        for name in MEDIA_SECRET_FILES:
            _secret(secret_dir / name)
    if mode == "full-managed":
        _secret(secret_dir / "wireguard-private-key")

    try:
        modules = json.loads(_required(values, "PORTAL_MODULES_JSON"))
    except json.JSONDecodeError as exc:
        raise ConfigError("PORTAL_MODULES_JSON must be valid JSON.") from exc
    ids = {item.get("id") for item in modules if isinstance(item, dict)}
    if ids != definition["modules"]:
        raise ConfigError(f"PORTAL_MODULES_JSON must enable exactly: {sorted(definition['modules'])}")

    auth_mode = values.get("PORTAL_AUTH_MODE", "local").strip().lower()
    if auth_mode not in {"local", "oidc", "hybrid"}:
        raise ConfigError("PORTAL_AUTH_MODE must be local, oidc, or hybrid.")
    if auth_mode in {"oidc", "hybrid"}:
        _url(values, "PORTAL_OIDC_ISSUER", https_only=True)
        _required(values, "PORTAL_OIDC_CLIENT_ID")
        _secret(secret_dir / "oidc-client-secret")

    for key, value in values.items():
        if key.endswith("_IMAGE") and (value.endswith(":latest") or value == "latest"):
            raise ConfigError(f"{key} must use a pinned tag or digest, not latest.")


def initialize(values: dict[str, str], *, create_paths: bool) -> None:
    secret_dir = Path(_required(values, "FOXDEN_SECRETS_DIR")).expanduser()
    runtime_dir = Path(_required(values, "FOXDEN_RUNTIME_DIR")).expanduser()
    if not secret_dir.is_absolute() or not runtime_dir.is_absolute():
        raise ConfigError("Secret and runtime directories must be absolute paths.")
    secret_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for name in ("portal-secret", "portal-bootstrap", "ingress-auth", "music-csrf", "media-app-token"):
        target = secret_dir / name
        if not target.exists():
            try:
                _write_private_text(target, secrets.token_urlsafe(48), exclusive=True)
            except FileExistsError:
                # Another initializer won the exclusive-create race. Preserve it.
                pass
    sys.path.insert(0, str(ROOT / "apps" / "portal" / "src"))
    from foxden_identity import generate_key_files
    private = secret_dir / "identity-private.pem"
    public = secret_dir / "identity-public.json"
    if private.exists() != public.exists():
        raise ConfigError("Identity private/public files must either both exist or both be absent.")
    if not private.exists():
        generate_key_files(private, public, kid=values.get("PORTAL_IDENTITY_SIGNING_KID", "foxden-portal-1"))
        os.chmod(private, 0o600)
        # This is a public verification key by design. It contains no private
        # signing material and must be readable by independently running modules.
        os.chmod(public, 0o644)
    for optional in ("qbit-password", "wireguard-private-key", "jellyfin-api-key", "oidc-client-secret"):
        target = secret_dir / optional
        if not target.exists():
            target.touch(mode=0o600)
    if create_paths:
        keys = (list(CORE_PATHS[2:]) + list(MUSIC_PATHS) + list(MEDIA_PATHS)
                + list(MANAGED_PATHS) + list(JELLYFIN_PATHS) + ["BROWSER_CONFIG_PATH"])
        for key in keys:
            raw = values.get(key, "").strip()
            if raw:
                path = Path(raw).expanduser()
                if not path.is_absolute():
                    raise ConfigError(f"{key} must be absolute before it can be created.")
                path.mkdir(parents=True, exist_ok=True)
    print(f"Initialized secret and runtime material under {secret_dir.parent}; secret values were not printed.")


def render_gateway(values: dict[str, str]) -> Path:
    """Atomically render the private ingress config for the configured UID.

    A rename replaces the inode behind Docker file bind mounts. An operator
    must explicitly recreate ingress after any changed render.
    """
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"]).resolve()
    runtime_dir = Path(values["FOXDEN_RUNTIME_DIR"]).expanduser()
    if not runtime_dir.is_absolute() or runtime_dir.is_symlink():
        raise ConfigError("FOXDEN_RUNTIME_DIR must be an absolute, non-symlink directory.")
    try:
        ingress_uid = int(_required(values, "FOXDEN_PUID"))
        ingress_gid = int(_required(values, "FOXDEN_PGID"))
    except ValueError as exc:
        raise ConfigError("FOXDEN_PUID/PGID must be numeric.") from exc
    if ingress_uid <= 0 or ingress_gid <= 0:
        raise ConfigError("Ingress UID/GID must be positive.")
    ingress_secret = (secret_dir / "ingress-auth").read_text(encoding="utf-8").strip()
    if len(ingress_secret) < 32:
        raise ConfigError("ingress-auth must contain at least 32 characters.")
    jellyfin_host = "jellyfin.invalid"
    if values.get("JELLYFIN_PUBLIC_URL", "").strip():
        parsed = urlparse(values["JELLYFIN_PUBLIC_URL"].strip())
        if not parsed.hostname:
            raise ConfigError("JELLYFIN_PUBLIC_URL must include a hostname.")
        jellyfin_host = parsed.hostname
    rendered = (GATEWAY_TEMPLATE.read_text(encoding="utf-8")
                .replace("__PORTAL_INGRESS_AUTH_SECRET__", ingress_secret)
                .replace("__JELLYFIN_PUBLIC_HOST__", jellyfin_host))
    if ingress_secret not in rendered:
        raise ConfigError("Gateway template did not contain the expected secret placeholder.")
    if "__JELLYFIN_PUBLIC_HOST__" in rendered:
        raise ConfigError("Gateway template did not render the Jellyfin hostname.")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    target = runtime_dir / "nginx.conf"
    if target.is_symlink():
        raise ConfigError("Refusing symlink nginx.conf target.")
    if target.exists():
        info = target.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ConfigError("Refusing unsafe nginx.conf target.")
        if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (ingress_uid, ingress_gid, 0o600):
            if target.read_text(encoding="utf-8") == rendered:
                return target  # No unnecessary inode replacement.
    descriptor, temporary_name = tempfile.mkstemp(prefix=".nginx.conf.", dir=runtime_dir, text=True)
    temporary = Path(temporary_name)
    try:
        try:
            if hasattr(os, "fchown"):
                os.fchown(descriptor, ingress_uid, ingress_gid)
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, 0o600)
        except PermissionError as exc:
            raise ConfigError(
                f"Cannot set ingress nginx.conf ownership to {ingress_uid}:{ingress_gid}; "
                "render using an authorized host administrator with chown privileges."
            ) from exc
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            descriptor = -1
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    return target

def compose_command(mode: str, env_path: Path, *, browser: bool, action: str,
                    jellyfin: bool = False, jellyfin_hwaccel: bool = False) -> list[str]:
    profiles = list(MODES[mode]["profiles"])
    if browser:
        profiles.append("browser")
    if jellyfin or jellyfin_hwaccel:
        profiles.append("jellyfin")
    command = ["docker", "compose", "--env-file", str(env_path), "-f", str(COMPOSE)]
    if jellyfin_hwaccel:
        command += ["-f", str(ROOT / "deploy" / "compose.jellyfin-hwaccel.yaml")]
    for profile in dict.fromkeys(profiles):
        command += ["--profile", profile]
    command.append(action)
    if action == "up":
        command.append("-d")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(prog="foxden", description="Fox Den Media deployment control")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create local secret material without overwriting existing files")
    init.add_argument("--env", type=Path, required=True)
    init.add_argument("--create-paths", action="store_true")
    for name in ("validate", "config", "deploy", "stop"):
        command = sub.add_parser(name)
        command.add_argument("mode", choices=MODES)
        command.add_argument("--env", type=Path, required=True)
        command.add_argument("--browser", action="store_true")
        command.add_argument("--jellyfin", action="store_true", help="enable the optional Jellyfin profile")
        command.add_argument("--jellyfin-hwaccel", action="store_true",
                             help="enable Jellyfin and the reviewed /dev/dri override")
        if name in {"deploy", "stop"}:
            command.add_argument("--execute", action="store_true", help="actually invoke Docker Compose")
    args = parser.parse_args()
    try:
        values = load_env(args.env.resolve())
        if args.command == "init":
            initialize(values, create_paths=args.create_paths)
            return 0
        validate(args.mode, values, browser=args.browser, jellyfin=args.jellyfin,
                 jellyfin_hwaccel=args.jellyfin_hwaccel)
        # Preflight and dry-run commands must not mutate active configuration.
        should_render = args.command == "config" or (args.command == "deploy" and args.execute)
        gateway = render_gateway(values) if should_render else None
        action = {"validate": "config", "config": "config", "deploy": "up", "stop": "down"}[args.command]
        command = compose_command(args.mode, args.env.resolve(), browser=args.browser, action=action,
                                  jellyfin=args.jellyfin, jellyfin_hwaccel=args.jellyfin_hwaccel)
        redacted = " ".join(command)
        if gateway is None:
            print(f"Configuration valid for {args.mode}; gateway was not regenerated.")
        else:
            print(f"Configuration valid for {args.mode}; rendered gateway at {gateway}.")
            print("If ingress is already running, a changed nginx.conf requires an explicit ingress recreation: Docker file bind mounts can retain the old inode.")
        print(redacted)
        if args.command in {"deploy", "stop"} and not args.execute:
            print("Dry run only. Repeat with --execute after reviewing the command and migration gate.")
            return 0
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except (ConfigError, ValueError, OSError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
