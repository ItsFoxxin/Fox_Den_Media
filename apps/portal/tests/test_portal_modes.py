from dataclasses import replace
from html.parser import HTMLParser

from fastapi.testclient import TestClient
import httpx

from foxden_portal.app import create_app
from foxden_portal.config import ModuleConfig
from foxden_portal.modules import ModuleClient

from conftest import bootstrap_admin, module_summary, module_transport, settings


class _LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attributes = dict(attrs)
            if "href" in attributes:
                self.hrefs.append(attributes["href"])


def configured_modules(*ids: str):
    return tuple(ModuleConfig(item, "Music" if item == "music" else "Movies & TV",
                              f"http://{item}.test", f"/{item}/", True) for item in ids)


def test_zero_modules_starts_and_shows_coherent_empty_state(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        page = client.get("/")
        assert page.status_code == 200
        assert "No media modules are enabled" in page.text
        assert client.get("/health").json()["status"] == "healthy"


def test_music_only_hides_movies(tmp_path):
    modules = configured_modules("music")
    transport = module_transport({"music.test": module_summary("music")})
    with TestClient(create_app(settings(tmp_path, modules), ModuleClient(.2, transport))) as client:
        bootstrap_admin(client)
        page = client.get("/")
        assert "Music" in page.text
        assert "Movies &amp; TV" not in page.text
        assert "state-healthy" in page.text


def test_movies_only_hides_music(tmp_path):
    modules = configured_modules("media")
    transport = module_transport({"media.test": module_summary("media")})
    with TestClient(create_app(settings(tmp_path, modules), ModuleClient(.2, transport))) as client:
        bootstrap_admin(client)
        page = client.get("/")
        assert "Movies &amp; TV" in page.text
        assert ">Music<" not in page.text


def test_full_configuration_withholds_unauthenticated_summary_activity(tmp_path):
    modules = configured_modules("music", "media")
    transport = module_transport({"music.test": module_summary("music"), "media.test": module_summary("media")})
    with TestClient(create_app(settings(tmp_path, modules), ModuleClient(.2, transport))) as client:
        bootstrap_admin(client)
        page = client.get("/")
        assert "music item" not in page.text and "media item" not in page.text
        data = client.get("/api/platform/v1/status").json()
        assert {item["id"] for item in data["modules"]} == {"music", "media"}
        assert data["activity"] == []


def test_offline_timeout_invalid_and_unhealthy_are_differentiated(tmp_path):
    modules = configured_modules("music", "media") + (
        ModuleConfig("invalid", "Invalid", "http://invalid.test", "/invalid/", True),
        ModuleConfig("slow", "Slow", "http://slow.test", "/slow/", True),
    )
    transport = module_transport({
        "music.test": httpx.ConnectError("private detail"),
        "media.test": module_summary("media", "unhealthy"),
        "invalid.test": {"secret_path": "/mnt/private", "token": "do-not-show"},
        "slow.test": httpx.ReadTimeout("private endpoint"),
    })
    with TestClient(create_app(settings(tmp_path, modules), ModuleClient(.2, transport))) as client:
        bootstrap_admin(client)
        page = client.get("/")
        assert page.text.count("state-offline") == 2
        assert page.text.count("state-unhealthy") == 2
        assert "/mnt/private" not in page.text and "do-not-show" not in page.text
        assert "private endpoint" not in page.text and "private detail" not in page.text


def test_module_recovers_on_next_snapshot(tmp_path):
    modules = configured_modules("music")
    transport = module_transport({"music.test": [httpx.ConnectError("down"), module_summary("music")]})
    with TestClient(create_app(settings(tmp_path, modules), ModuleClient(.2, transport))) as client:
        bootstrap_admin(client)
        assert "state-offline" in client.get("/").text
        assert "state-healthy" in client.get("/").text


def test_disabled_module_is_not_contacted_or_rendered(tmp_path):
    modules = (ModuleConfig("music", "Music", "http://music.test", "/music/", False),)
    with TestClient(create_app(settings(tmp_path, modules), ModuleClient(.2, module_transport({})))) as client:
        bootstrap_admin(client)
        page = client.get("/")
        assert "No media modules are enabled" in page.text


def test_general_user_sees_jellyfin_but_not_admin_modules_or_activity(tmp_path):
    modules = configured_modules("music", "media")
    configured = replace(settings(tmp_path, modules), jellyfin_public_url="https://jellyfin.example.invalid")
    transport = module_transport({"music.test": module_summary("music"), "media.test": module_summary("media")})
    with TestClient(create_app(configured, ModuleClient(.2, transport))) as client:
        bootstrap_admin(client)
        with client.app.state.store.connection() as db:
            password_hash = db.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()[0]
        viewer = client.app.state.store.create_local_user("viewer", "Viewer", password_hash, "user")
        token, token_csrf = client.app.state.store.create_session(viewer["id"], "local", 3600)
        client.cookies.set("foxden_portal_session", token)
        client.cookies.set("foxden_portal_csrf", token_csrf)
        page = client.get("/")
        links = _LinkCollector()
        links.feed(page.text)
        assert configured.jellyfin_public_url in links.hrefs
        assert "Media access only" in page.text
        assert "state-healthy" not in page.text and "Recent activity" not in page.text
        assert client.get("/api/platform/v1/status").status_code == 403
