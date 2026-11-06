from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from foxden import load_env


def test_ugreen_rehearsal_template_preserves_verified_versions_and_ids() -> None:
    values = load_env(ROOT / "deploy" / "examples" / "ugreen-rehearsal.env.example")
    assert values["MUSIC_PUID"] == "1000005"
    assert values["MUSIC_PGID"] == "1000004"
    assert values["JELLYFIN_PUID"] == "1004"
    assert values["JELLYFIN_PGID"] == "100"
    assert values["JELLYFIN_VIDEO_GID"] == "44"
    assert values["JELLYFIN_RENDER_GID"] == "105"
    assert values["JELLYFIN_MEDIA_CONTAINER_PATH"] == "/media"
    assert "jellyfin/jellyfin:10.11@sha256:" in values["JELLYFIN_IMAGE"]
    assert "qmcgaw/gluetun:v3.41.1@sha256:" in values["GLUETUN_IMAGE"]
    assert values["TORRENT_DATA_PATH"].startswith("/CHANGE_ME_")
    assert not any(path in "\n".join(values.values()) for path in (
        "/volume2/jellyfin/config", "/volume2/docker/torrent-vpn/appdata/qbittorrent",
        "/volume2/docker/fox-den-music/Fox-Den-Music/data/config",
    ))


def test_hardware_override_uses_explicit_numeric_groups() -> None:
    override = yaml.safe_load((ROOT / "deploy" / "compose.jellyfin-hwaccel.yaml").read_text(encoding="utf-8"))
    jellyfin = override["services"]["jellyfin"]
    assert jellyfin["group_add"] == [
        "${JELLYFIN_RENDER_GID:?Set JELLYFIN_RENDER_GID to the host render group ID}",
        "${JELLYFIN_VIDEO_GID:?Set JELLYFIN_VIDEO_GID to the host video group ID}",
    ]


def test_managed_networking_has_no_qbittorrent_bypass() -> None:
    compose = yaml.safe_load((ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8"))
    qbit = compose["services"]["qbittorrent"]
    gluetun = compose["services"]["gluetun"]
    assert qbit["network_mode"] == "service:gluetun"
    assert "ports" not in qbit and "networks" not in qbit
    assert qbit["depends_on"]["gluetun"]["condition"] == "service_healthy"
    assert gluetun["environment"]["FIREWALL"] == "on"
    assert gluetun["environment"]["HEALTH_SMALL_CHECK_TYPE"] == "${GLUETUN_HEALTH_SMALL_CHECK_TYPE:-dns}"


def test_compatibility_report_records_verified_production_paths() -> None:
    report = (ROOT / "docs" / "production-compatibility-0.9.md").read_text(encoding="utf-8")
    for expected in (
        "/volume2/jellyfin/config", "/volume2/jellyfin/cache", "/mnt/@usb/sdc2/Media",
        "/volume2/docker/torrent-vpn/appdata/qbittorrent", "1000005:1000004", "1004:100",
    ):
        assert expected in report
