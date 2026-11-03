import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from foxden_portal.app import create_app
from foxden_portal.config import ConfigError, Settings
from foxden_portal.contracts import ActivityFeed, CONTRACT_VERSION, ModuleSummary

from conftest import bootstrap_admin, settings


def test_checked_in_module_schema_matches_runtime_contract():
    schema_path = Path(__file__).parents[3] / "contracts" / "v1" / "module-summary.schema.json"
    checked_in = json.loads(schema_path.read_text(encoding="utf-8"))
    runtime = ModuleSummary.model_json_schema()
    assert checked_in["properties"]["contract_version"]["const"] == CONTRACT_VERSION
    assert set(checked_in["required"]) == set(runtime["required"])
    assert checked_in["properties"]["capabilities"]["maxItems"] == 50
    assert checked_in["properties"]["activity"]["maxItems"] == 20
    activity_path = Path(__file__).parents[3] / "contracts" / "v1" / "activity.schema.json"
    activity = json.loads(activity_path.read_text(encoding="utf-8"))
    assert set(activity["required"]) == set(ActivityFeed.model_json_schema()["required"])
    assert activity["properties"]["activity"]["maxItems"] == 20
    watch_path = Path(__file__).parents[3] / "contracts" / "v1" / "watch-listen.schema.json"
    watch = json.loads(watch_path.read_text(encoding="utf-8"))
    assert watch["properties"]["contract_version"]["const"] == "1.0"
    assert {"libraries", "recent_video", "recent_audio", "continue_watching"} <= set(watch["required"])


def test_config_validation_and_redaction(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_COOKIE_SECURE", "false")
    monkeypatch.setenv("PORTAL_JELLYFIN_URL", "https://jellyfin.example.invalid")
    monkeypatch.setenv("PORTAL_MODULES_JSON", json.dumps([{
        "id": "music", "name": "Music", "base_url": "http://music:8000", "navigation_path": "/music/"
    }]))
    configured = Settings.from_env()
    redacted = configured.redacted()
    assert redacted["bootstrap_configured"] is True
    assert "secret" not in json.dumps(redacted).lower()
    assert configured.modules[0].module_id == "music"
    assert configured.jellyfin_public_url == "https://jellyfin.example.invalid"
    assert redacted["jellyfin_link_configured"] is True
    assert redacted["watch_listen_enabled"] is False


def test_watch_config_requires_complete_server_side_boundary(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_JELLYFIN_INTERNAL_URL", "http://jellyfin:8096")
    with pytest.raises(ConfigError, match="Watch & Listen requires"):
        Settings.from_env()
    monkeypatch.setenv("PORTAL_JELLYFIN_URL", "https://jellyfin.example.invalid")
    monkeypatch.setenv("PORTAL_JELLYFIN_TOKEN_SECRET", "jellyfin-token-encryption-secret-123456")
    configured = Settings.from_env()
    assert configured.watch_enabled
    assert "jellyfin-token-encryption-secret" not in json.dumps(configured.redacted())


def test_config_rejects_credentials_in_module_url(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_MODULES_JSON", '[{"id":"music","name":"Music","base_url":"http://user:pass@music:8000","navigation_path":"/music/"}]')
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_config_rejects_credentials_in_jellyfin_url(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_JELLYFIN_URL", "https://user:password@jellyfin.example.invalid")
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_config_rejects_query_or_fragment_in_jellyfin_url(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_JELLYFIN_URL", "https://jellyfin.example.invalid/?token=must-not-be-here")
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_local_mode_requires_no_oidc(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_AUTH_MODE", "local")
    configured = Settings.from_env()
    assert configured.local_enabled and not configured.oidc_enabled


def test_responsive_navigation_and_state_styles_exist(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        page = client.get("/")
        css = client.get("/static/portal.css")
        denkit = client.get("/static/denkit.css")
        jellyfin_theme = client.get("/static/jellyfin-midnight.css")
        mascot = client.get("/static/fox-den-mascot.png")
        assert 'name="viewport"' in page.text
        assert 'aria-label="Platform"' in page.text
        assert "/static/denkit.css" in page.text
        assert denkit.status_code == 200
        assert "--den-midnight" in denkit.text
        assert jellyfin_theme.status_code == 200 and "--den-coral" in jellyfin_theme.text
        assert mascot.status_code == 200 and mascot.headers["content-type"] == "image/png"
        assert "@media(max-width:680px)" in css.text
        assert "@media (max-width: 760px)" in denkit.text
        assert ".media-grid" in denkit.text and ".watch-hero" in denkit.text
        for state in ("healthy", "unhealthy", "offline"):
            assert f"state-{state}" in css.text
