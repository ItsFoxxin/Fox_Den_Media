from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import foxden


def configured(tmp_path: Path, mode: str) -> dict[str, str]:
    modules = foxden.MODES[mode]["modules"]
    values = {
        "FOXDEN_PUBLIC_ORIGIN": "http://127.0.0.1:18080",
        "FOXDEN_PUID": "10001",
        "FOXDEN_PGID": "10001",
        "FOXDEN_PORT": "18080",
        "FOXDEN_SECRETS_DIR": str(tmp_path / "secrets"),
        "FOXDEN_RUNTIME_DIR": str(tmp_path / "runtime"),
        "PORTAL_CONFIG_PATH": str(tmp_path / "portal"),
        "PORTAL_AUTH_MODE": "local",
        "JELLYFIN_PUBLIC_URL": "https://jellyfin.example.invalid",
        "JELLYFIN_INTERNAL_URL": "http://jellyfin:8096",
        "JELLYFIN_PUID": "10001",
        "JELLYFIN_PGID": "10001",
        "JELLYFIN_MEDIA_CONTAINER_PATH": "/media",
        "PORTAL_MODULES_JSON": json.dumps([
            {"id": item, "name": item.title(), "base_url": f"http://{item}:8000", "navigation_path": f"/{item}/"}
            for item in sorted(modules)
        ]),
        "MUSICBRAINZ_CONTACT": "test@example.invalid",
        "QBIT_URL": "http://192.0.2.1:8080",
        "WIREGUARD_ADDRESSES": "10.2.0.2/32",
        "WIREGUARD_PUBLIC_KEY": "test-public-key",
        "WIREGUARD_ENDPOINT_IP": "192.0.2.2",
    }
    for key in (*foxden.MUSIC_PATHS, *foxden.MEDIA_PATHS, *foxden.MANAGED_PATHS,
                *foxden.JELLYFIN_PATHS, "BROWSER_CONFIG_PATH"):
        values[key] = str(tmp_path / key.lower())
    for key in (*foxden.CORE_PATHS, *foxden.MUSIC_PATHS, *foxden.MEDIA_PATHS,
                *foxden.MANAGED_PATHS, *foxden.JELLYFIN_PATHS):
        if key in values:
            Path(values[key]).mkdir(parents=True, exist_ok=True)
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    secret_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        *foxden.SECRET_FILES,
        *foxden.MUSIC_SECRET_FILES,
        *foxden.MEDIA_SECRET_FILES,
        "wireguard-private-key",
        "oidc-client-secret",
    ):
        target = secret_dir / name
        target.write_text("x" * 40, encoding="utf-8")
        target.chmod(0o644 if name == "identity-public.json" else 0o600)
    return values


@pytest.mark.parametrize("mode", sorted(foxden.MODES))
def test_each_mode_validates_independently(tmp_path: Path, mode: str) -> None:
    values = configured(tmp_path, mode)
    foxden.validate(mode, values)


def test_music_does_not_require_torrent_or_vpn_configuration(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    for key in (*foxden.MEDIA_PATHS, *foxden.MANAGED_PATHS, "QBIT_URL", "WIREGUARD_PUBLIC_KEY", "WIREGUARD_ENDPOINT_IP"):
        values.pop(key, None)
    foxden.validate("music", values)
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    for name in foxden.MEDIA_SECRET_FILES:
        (secret_dir / name).unlink()
    foxden.validate("music", values)


def test_existing_modes_do_not_require_jellyfin_configuration(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    for key in (*foxden.JELLYFIN_PATHS, "JELLYFIN_PUBLIC_URL", "JELLYFIN_INTERNAL_URL", "JELLYFIN_PUID",
                "JELLYFIN_PGID", "JELLYFIN_MEDIA_CONTAINER_PATH"):
        values.pop(key, None)
    foxden.validate("music", values)


def test_jellyfin_profile_requires_only_core_and_jellyfin_configuration(tmp_path: Path) -> None:
    values = configured(tmp_path, "jellyfin")
    for key in (*foxden.MUSIC_PATHS, *foxden.MEDIA_PATHS, *foxden.MANAGED_PATHS,
                "MUSICBRAINZ_CONTACT", "QBIT_URL"):
        values.pop(key, None)
    foxden.validate("jellyfin", values)
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    for name in (*foxden.MUSIC_SECRET_FILES, *foxden.MEDIA_SECRET_FILES):
        (secret_dir / name).unlink()
    foxden.validate("jellyfin", values)


def test_media_does_not_require_music_configuration(tmp_path: Path) -> None:
    values = configured(tmp_path, "media")
    for key in (*foxden.MUSIC_PATHS, "MUSICBRAINZ_CONTACT"):
        values.pop(key, None)
    foxden.validate("media", values)
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    for name in foxden.MUSIC_SECRET_FILES:
        (secret_dir / name).unlink()
    foxden.validate("media", values)


def test_managed_mode_requires_vpn_configuration(tmp_path: Path) -> None:
    values = configured(tmp_path, "full-managed")
    values["WIREGUARD_PUBLIC_KEY"] = ""
    with pytest.raises(foxden.ConfigError, match="WIREGUARD_PUBLIC_KEY"):
        foxden.validate("full-managed", values)


def test_service_specific_numeric_ids_are_independent_and_validated(tmp_path: Path) -> None:
    values = configured(tmp_path, "full-managed")
    values.update(MUSIC_PUID="1000005", MUSIC_PGID="1000004", MEDIA_PUID="10001",
                  MEDIA_PGID="10001", QBIT_PUID="1000", QBIT_PGID="1000")
    foxden.validate("full-managed", values)
    values["MUSIC_PUID"] = "not-a-number"
    with pytest.raises(foxden.ConfigError, match="MUSIC_PUID"):
        foxden.validate("full-managed", values)


def test_gluetun_dns_small_check_is_supported_on_3411(tmp_path: Path) -> None:
    values = configured(tmp_path, "full-managed")
    values["GLUETUN_IMAGE"] = "qmcgaw/gluetun:v3.41.1"
    values["GLUETUN_HEALTH_SMALL_CHECK_TYPE"] = "dns"
    foxden.validate("full-managed", values)
    values["GLUETUN_HEALTH_SMALL_CHECK_TYPE"] = "icmp"
    foxden.validate("full-managed", values)
    values["GLUETUN_HEALTH_SMALL_CHECK_TYPE"] = "tcp"
    with pytest.raises(foxden.ConfigError, match="must be dns or icmp"):
        foxden.validate("full-managed", values)


def test_unprefixed_gluetun_small_check_is_rejected(tmp_path: Path) -> None:
    values = configured(tmp_path, "full-managed")
    values["HEALTH_SMALL_CHECK_TYPE"] = "dns"
    with pytest.raises(foxden.ConfigError, match="Use GLUETUN_HEALTH_SMALL_CHECK_TYPE"):
        foxden.validate("full-managed", values)


def test_latest_image_tags_are_rejected(tmp_path: Path) -> None:
    values = configured(tmp_path, "full-managed")
    values["QBIT_IMAGE"] = "lscr.io/linuxserver/qbittorrent:latest"
    with pytest.raises(foxden.ConfigError, match="pinned"):
        foxden.validate("full-managed", values)

    values = configured(tmp_path, "jellyfin")
    values["JELLYFIN_IMAGE"] = "jellyfin/jellyfin:latest"
    with pytest.raises(foxden.ConfigError, match="pinned"):
        foxden.validate("jellyfin", values)


def test_invalid_resource_limits_are_rejected(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    values["FOXDEN_APP_MEMORY_LIMIT"] = "unlimited"
    with pytest.raises(foxden.ConfigError, match="memory"):
        foxden.validate("music", values)


def test_overlapping_storage_roles_are_rejected(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    nested = Path(values["MUSIC_CONFIG_PATH"]) / "staging"
    nested.mkdir()
    values["MUSIC_STAGING_PATH"] = str(nested)
    with pytest.raises(foxden.ConfigError, match="non-overlapping"):
        foxden.validate("music", values)


def test_compose_profiles_select_only_requested_modules(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    command = foxden.compose_command("full-managed", env, browser=True, action="config")
    assert command.count("--profile") == 4
    assert all(profile in command for profile in ("music", "media", "managed", "browser"))


def test_jellyfin_profile_and_hardware_override_are_explicit(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    disabled = foxden.compose_command("music", env, browser=False, action="config")
    assert "jellyfin" not in disabled
    enabled = foxden.compose_command("music", env, browser=False, action="config", jellyfin=True)
    assert enabled[enabled.index("--profile") + 1] == "music"
    assert "jellyfin" in enabled
    hardware = foxden.compose_command("jellyfin", env, browser=False, action="config",
                                      jellyfin_hwaccel=True)
    assert str(foxden.ROOT / "deploy" / "compose.jellyfin-hwaccel.yaml") in hardware


def test_jellyfin_is_off_vpn_and_media_is_read_only() -> None:
    import yaml
    compose = yaml.safe_load((ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8"))
    jellyfin = compose["services"]["jellyfin"]
    assert jellyfin["profiles"] == ["jellyfin"]
    assert jellyfin["image"].startswith("${JELLYFIN_IMAGE:-jellyfin/jellyfin:")
    assert jellyfin["networks"] == ["platform", "outbound"]
    assert "network_mode" not in jellyfin and "gluetun" not in str(jellyfin).lower()
    mounts = {item["target"]: item for item in jellyfin["volumes"]}
    media_mount = next(item for item in jellyfin["volumes"] if item.get("read_only"))
    assert media_mount["read_only"] is True
    assert mounts["/config"].get("read_only") is not True
    assert mounts["/cache"].get("read_only") is not True


def test_gateway_render_keeps_secret_out_of_return_value(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    secret = (Path(values["FOXDEN_SECRETS_DIR"]) / "ingress-auth").read_text(encoding="utf-8")
    target = foxden.render_gateway(values)
    assert target.name == "nginx.conf"
    assert secret in target.read_text(encoding="utf-8")
    assert secret not in str(target)


def test_initialization_generates_identity_and_does_not_overwrite_secrets(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    for item in secret_dir.iterdir():
        item.unlink()
    foxden.initialize(values, create_paths=False)
    original = (secret_dir / "portal-secret").read_text(encoding="utf-8")
    foxden.initialize(values, create_paths=False)
    assert (secret_dir / "portal-secret").read_text(encoding="utf-8") == original
    assert "BEGIN PRIVATE KEY" in (secret_dir / "identity-private.pem").read_text(encoding="utf-8")
    assert json.loads((secret_dir / "identity-public.json").read_text(encoding="utf-8"))["keys"][0]["kty"] == "OKP"


def test_managed_compose_forces_qbittorrent_through_gluetun() -> None:
    compose = (ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8")
    qbit = compose.split("  qbittorrent:", 1)[1]
    assert "network_mode: service:gluetun" in qbit
    assert "gluetun: {condition: service_healthy}" in qbit
    assert "ports:" not in qbit.split("networks:", 1)[0]
    assert "FIREWALL: \"on\"" in compose
    assert "platform: {internal: true}" in compose
    assert "outbound: {}" in compose
    gluetun = compose.split("  gluetun:", 1)[1].split("  qbittorrent:", 1)[0]
    assert "networks: [platform, outbound]" in gluetun
    assert 'HEALTH_SMALL_CHECK_TYPE: "${GLUETUN_HEALTH_SMALL_CHECK_TYPE:-dns}"' in gluetun
    assert 'HEALTH_TARGET_ADDRESSES: "${GLUETUN_HEALTH_TARGET_ADDRESSES' in gluetun


def test_compose_supports_distinct_service_identities() -> None:
    compose = (ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8")
    assert 'user: "${MUSIC_PUID:-10001}:${MUSIC_PGID:-10001}"' in compose
    assert 'user: "${MEDIA_PUID:-10001}:${MEDIA_PGID:-10001}"' in compose
    assert 'PUID: "${QBIT_PUID:-10001}"' in compose
    assert 'PGID: "${QBIT_PGID:-10001}"' in compose



def test_deployment_tmpfs_entries_are_single_mount_specifications() -> None:
    import yaml

    compose = yaml.safe_load((ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8"))
    targets = (
        (compose["x-hardening"], 256),
        (compose["services"]["ingress"], 64),
        (compose["services"]["jellyfin"], 512),
    )
    for service, size in targets:
        entries = service["tmpfs"]
        assert len(entries) == 1
        assert entries[0].startswith("/tmp:rw,")
        assert f"size={size}m" in entries[0]
        assert "mode=1777" in entries[0]


def test_media_dockerfile_normalizes_nas_source_file_permissions() -> None:
    dockerfile = (ROOT / "apps" / "media" / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.index("COPY apps/media/VERSION ./VERSION") < dockerfile.index("RUN chmod -R a+rX /app")
    assert dockerfile.index("RUN chmod -R a+rX /app") < dockerfile.index("USER foxden:foxden")


def test_movies_tv_ci_uses_existing_ffmpeg_or_bounded_package_install() -> None:
    workflow = (ROOT / ".github" / "workflows" / "monorepo.yml").read_text(encoding="utf-8")
    applications = workflow.split("  applications:", 1)[1].split("\n  audit:", 1)[0]
    assert "command -v ffmpeg" in applications
    assert "command -v ffprobe" in applications
    assert "timeout 300s" in applications
    assert "Acquire::Retries=3" in applications
    assert "DPkg::Lock::Timeout=60" in applications
    assert "sudo apt-get update && sudo apt-get install -y ffmpeg" not in applications


def test_qbittorrent_s6_init_compatible_with_vpn_kill_switch() -> None:
    import yaml

    compose = yaml.safe_load((ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8"))
    qbit = compose["services"]["qbittorrent"]
    vpn = compose["services"]["gluetun"]
    assert qbit["network_mode"] == "service:gluetun"
    assert qbit["depends_on"]["gluetun"]["condition"] == "service_healthy"
    assert "security_opt" not in qbit  # s6 privilege drop requires no_new_privileges to be unset
    assert "ports" not in qbit
    assert "NET_ADMIN" in vpn["cap_add"]
    assert vpn["environment"]["FIREWALL"] == "on"
