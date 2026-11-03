from dataclasses import replace
import json
import sqlite3

from fastapi.testclient import TestClient
import httpx

from foxden_portal.app import create_app
from foxden_portal.jellyfin import JellyfinAdapter

from conftest import bootstrap_admin, csrf, settings


TOKEN = "user-scoped-jellyfin-token-never-an-admin-key"
ITEM = {
    "Id": "video-1", "Name": "Midnight Movie", "Type": "Movie", "ProductionYear": 2026,
    "Path": "/private/media/Midnight Movie.mkv", "MediaSources": [{"Path": "/private/media"}],
    "UserData": {"Played": False, "PlaybackPositionTicks": 1200},
}
AUDIO = {
    "Id": "audio-1", "Name": "Café Song", "Type": "Audio", "AlbumArtist": "Fox Artist",
    "Artists": ["Fox Artist"], "UserData": {"IsFavorite": True},
}


def watch_settings(tmp_path):
    return replace(
        settings(tmp_path), jellyfin_public_url="https://media.example.invalid",
        jellyfin_internal_url="http://jellyfin.test",
        jellyfin_token_secret="watch-token-secret-for-tests-123456789",
    )


def transport(requests: list[httpx.Request], *, unavailable: bool = False):
    def handler(request: httpx.Request):
        requests.append(request)
        if unavailable:
            raise httpx.ConnectError("secret internal host detail")
        if request.url.path == "/Users/AuthenticateByName":
            data = json.loads(request.content)
            if data.get("Pw") != "jellyfin-password":
                return httpx.Response(401)
            return httpx.Response(200, json={
                "AccessToken": TOKEN, "User": {"Id": "jf-user-1", "Name": data["Username"]},
            })
        assert f'Token="{TOKEN}"' in request.headers.get("Authorization", "")
        if request.url.path == "/Users/Me":
            return httpx.Response(200, json={"Id": "jf-user-1", "Name": "viewer"})
        if request.url.path == "/UserViews":
            return httpx.Response(200, json={"Items": [{"Id": "library-1", "Name": "Movies", "Type": "CollectionFolder"}]})
        if request.url.path == "/UserItems/Resume":
            return httpx.Response(200, json={"Items": [ITEM]})
        if request.url.path == "/Items" and request.url.params.get("searchTerm"):
            return httpx.Response(200, json={"Items": [ITEM, AUDIO]})
        if request.url.path == "/Items":
            kinds = request.url.params.get("includeItemTypes", "")
            music_kinds = {"MusicArtist", "MusicAlbum", "Audio", "Playlist"}
            return httpx.Response(200, json={
                "Items": [AUDIO if music_kinds.intersection(kinds.split(",")) else ITEM],
            })
        if request.url.path == "/Items/video-1":
            return httpx.Response(200, json={**ITEM, "Overview": "A safe synthetic movie.", "Genres": ["Cozy"]})
        if request.url.path == "/Items/video-1/Images/Primary":
            return httpx.Response(200, content=b"synthetic-jpeg", headers={"content-type": "image/jpeg"})
        if request.url.path == "/Sessions/Logout":
            return httpx.Response(204)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_disabled_module_does_not_affect_portal(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        assert client.get("/api/watch/v1/session").json() == {
            "contract_version": "1.0", "state": "disabled", "connected": False,
        }
        page = client.get("/watch/")
        assert page.status_code == 200 and "Watch &amp; Listen is resting" in page.text


def test_user_scoped_browsing_search_artwork_and_disconnect(tmp_path):
    requests: list[httpx.Request] = []
    configured = watch_settings(tmp_path)
    adapter = JellyfinAdapter(configured.jellyfin_internal_url, configured.jellyfin_public_url,
                               transport=transport(requests))
    with TestClient(create_app(configured, jellyfin_adapter=adapter)) as client:
        bootstrap_admin(client)
        page = client.get("/watch/")
        connected = client.post("/watch/connect", data={
            "csrf": csrf(page.text), "username": "viewer", "password": "jellyfin-password",
        }, follow_redirects=False)
        assert connected.status_code == 303
        with client.app.state.store.connection() as db:
            row = db.execute("SELECT token_ciphertext FROM jellyfin_links").fetchone()
        assert row and TOKEN.encode() not in bytes(row[0])

        page = client.get("/watch/")
        assert page.status_code == 200
        assert "Midnight Movie" in page.text and "Café Song" in page.text
        assert "/private/media" not in page.text and TOKEN not in page.text

        home = client.get("/api/watch/v1/home")
        assert home.status_code == 200
        assert "recent_video" in home.text and "recent_audio" in home.text
        assert "/private/media" not in home.text and TOKEN not in home.text
        search = client.get("/api/watch/v1/search", params={"q": "midnight"})
        assert search.status_code == 200 and len(search.json()["items"]) == 2
        browse = client.get("/api/watch/v1/browse/albums")
        assert browse.status_code == 200 and browse.json()["kind"] == "albums"
        assert "Café Song" in client.get("/watch/browse/albums").text
        assert client.get("/api/watch/v1/browse/not-a-kind").status_code == 400
        assert client.get("/api/watch/v1/search", params={"q": ""}).status_code == 400
        assert client.get("/api/watch/v1/items/not%20valid").status_code == 400
        detail = client.get("/api/watch/v1/items/video-1")
        assert detail.status_code == 200
        assert detail.json()["item"]["jellyfin_url"].startswith("https://media.example.invalid/")
        artwork = client.get("/api/watch/v1/artwork/video-1")
        assert artwork.status_code == 200 and artwork.headers["content-type"] == "image/jpeg"

        page = client.get("/watch/")
        response = client.post("/watch/disconnect", data={"csrf": csrf(page.text)}, follow_redirects=False)
        assert response.status_code == 303
        assert client.get("/api/watch/v1/session").json()["connected"] is False


def test_watch_requires_both_portal_and_jellyfin_authorization(tmp_path):
    configured = watch_settings(tmp_path)
    adapter = JellyfinAdapter(configured.jellyfin_internal_url, configured.jellyfin_public_url,
                               transport=transport([]))
    with TestClient(create_app(configured, jellyfin_adapter=adapter)) as client:
        assert client.get("/api/watch/v1/home").status_code == 401
        bootstrap_admin(client)
        assert client.get("/api/watch/v1/home").status_code == 409
        assert client.post("/watch/connect", data={
            "username": "viewer", "password": "jellyfin-password",
        }).status_code == 403
        page = client.get("/watch/")
        failed = client.post("/watch/connect", data={
            "csrf": csrf(page.text), "username": "viewer", "password": "wrong",
        })
        assert failed.status_code == 401 and TOKEN not in failed.text


def test_general_portal_user_can_consume_media_without_admin_access(tmp_path):
    configured = watch_settings(tmp_path)
    adapter = JellyfinAdapter(configured.jellyfin_internal_url, configured.jellyfin_public_url,
                               transport=transport([]))
    with TestClient(create_app(configured, jellyfin_adapter=adapter)) as client:
        bootstrap_admin(client)
        with client.app.state.store.connection() as db:
            password_hash = db.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()[0]
        viewer = client.app.state.store.create_local_user("viewer", "Viewer", password_hash, "user")
        token, token_csrf = client.app.state.store.create_session(viewer["id"], "local", 3600)
        client.cookies.set("foxden_portal_session", token)
        client.cookies.set("foxden_portal_csrf", token_csrf)
        page = client.get("/watch/")
        assert page.status_code == 200 and "Connect your Jellyfin account" in page.text
        assert client.get("/api/platform/v1/status").status_code == 403


def test_jellyfin_outage_is_isolated_and_redacted(tmp_path):
    configured = watch_settings(tmp_path)
    adapter = JellyfinAdapter(configured.jellyfin_internal_url, configured.jellyfin_public_url,
                               transport=transport([], unavailable=True))
    with TestClient(create_app(configured, jellyfin_adapter=adapter)) as client:
        bootstrap_admin(client)
        page = client.get("/watch/")
        failed = client.post("/watch/connect", data={
            "csrf": csrf(page.text), "username": "viewer", "password": "jellyfin-password",
        })
        assert failed.status_code == 503
        assert "secret internal host detail" not in failed.text
        assert client.get("/").status_code == 200


def test_v1_database_migrates_without_losing_accounts(tmp_path):
    configured = settings(tmp_path)
    with TestClient(create_app(configured)) as client:
        bootstrap_admin(client)
    with sqlite3.connect(configured.database_path) as db:
        db.execute("UPDATE portal_metadata SET value='1' WHERE key='schema_version'")
        db.execute("DROP TABLE jellyfin_links")
    with TestClient(create_app(configured)) as client:
        assert client.app.state.store.user_by_username("admin") is not None
        with client.app.state.store.connection() as db:
            assert db.execute("SELECT value FROM portal_metadata WHERE key='schema_version'").fetchone()[0] == "2"
            assert db.execute("SELECT name FROM sqlite_master WHERE name='jellyfin_links'").fetchone()
