"""Browser WebSocket authorization regression tests (mocked Firefox transport).

End-to-end pinned jlesage/firefox image and Nginx ingress are manual release gates.
"""
from __future__ import annotations

import asyncio
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from foxden_portal import browser_ws
from foxden_portal.app import create_app

from conftest import bootstrap_admin, settings


ORIGIN = {"origin": "http://testserver"}


class EchoBrowser:
    subprotocol = "binary"

    def __init__(self, subprotocol=None):
        self.subprotocol = subprotocol
        self.inbox = asyncio.Queue()
        self.closed = False

    async def recv(self):
        return await self.inbox.get()

    async def send(self, value):
        await self.inbox.put(value)

    async def close(self):
        self.closed = True


@pytest.fixture
def mock_browser(monkeypatch):
    connections = []

    async def fake_connect(url, **kwargs):
        browser = EchoBrowser("binary" if kwargs.get("subprotocols") else None)
        connections.append((url, kwargs, browser))
        return browser

    monkeypatch.setattr(browser_ws, "connect", fake_connect)
    monkeypatch.setattr(browser_ws, "RECHECK_INTERVAL_SECONDS", 0.025)
    monkeypatch.setattr(browser_ws, "MAX_CONNECTION_SECONDS", 2.0)
    return connections


def test_authorized_admin_can_exchange_novnc_text_and_binary(tmp_path, mock_browser):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        with client.websocket_connect("/websockify", headers=ORIGIN, subprotocols=["binary"]) as socket:
            socket.send_text("rfb-check")
            assert socket.receive_text() == "rfb-check"
            socket.send_bytes(b"\x00\x01novnc")
            assert socket.receive_bytes() == b"\x00\x01novnc"
        assert len(mock_browser) == 1
        assert mock_browser[0][0] == "ws://download-browser:5800/websockify"
        assert mock_browser[0][1]["subprotocols"] == ["binary"]


@pytest.mark.parametrize("state", ["logout", "expiry", "disabled", "role_revoked"])
def test_connected_browser_closes_when_portal_authority_changes(tmp_path, mock_browser, state):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        session_token = client.cookies.get("foxden_portal_session")
        with client.websocket_connect("/websockify", headers=ORIGIN, subprotocols=["binary"]) as socket:
            socket.send_text("connected")
            assert socket.receive_text() == "connected"
            if state == "logout":
                csrf = client.cookies.get("foxden_portal_csrf")
                logout = client.post("/logout", data={"csrf": csrf}, follow_redirects=False)
                assert logout.status_code == 303
            elif state == "expiry":
                with client.app.state.store.connection() as db:
                    db.execute("UPDATE sessions SET expires_at = 0")
            elif state == "disabled":
                with client.app.state.store.connection() as db:
                    db.execute("UPDATE users SET active = 0 WHERE username = 'admin'")
            else:
                with client.app.state.store.connection() as db:
                    db.execute("UPDATE users SET role = 'user' WHERE username = 'admin'")
            with pytest.raises(WebSocketDisconnect) as rejected:
                socket.receive_text()
            assert rejected.value.code == 1008
        assert mock_browser[0][2].closed is True
        assert not browser_ws._authorized(client.app.state.store, session_token) or state == "logout"


def test_existing_socket_enforces_absolute_connection_lifetime(tmp_path, mock_browser, monkeypatch):
    monkeypatch.setattr(browser_ws, "MAX_CONNECTION_SECONDS", 0.09)
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        with client.websocket_connect("/websockify", headers=ORIGIN) as socket:
            with pytest.raises(WebSocketDisconnect) as rejected:
                socket.receive_text()
            assert rejected.value.code == 1008


def test_unauthenticated_wrong_origin_and_unexpected_paths_do_not_reach_firefox(
    tmp_path, mock_browser
):
    with TestClient(create_app(settings(tmp_path))) as client:
        for path, headers in [
            ("/websockify", ORIGIN),
            ("/websockify", {"origin": "http://attacker.invalid"}),
            ("/unrelated-socket", ORIGIN),
        ]:
            if headers["origin"] == "http://attacker.invalid":
                # The malicious Origin must be rejected *with* a valid admin cookie.
                bootstrap_admin(client)
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(path, headers=headers):
                    pass
        assert mock_browser == []


def test_non_admin_and_offline_upstream_fail_closed(tmp_path, mock_browser, monkeypatch):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        with client.app.state.store.connection() as db:
            db.execute("UPDATE users SET role = 'user' WHERE username = 'admin'")
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/websockify", headers=ORIGIN):
                pass
        assert mock_browser == []

    async def down(*args, **kwargs):
        raise OSError("internal details not disclosed")

    monkeypatch.setattr(browser_ws, "connect", down)
    offline = tmp_path / "offline"
    offline.mkdir()
    with TestClient(create_app(settings(offline))) as client:
        bootstrap_admin(client)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/websockify", headers=ORIGIN):
                pass


def test_audio_and_malformed_upgrade_paths(tmp_path, mock_browser):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        with client.websocket_connect("/websockify-audio", headers=ORIGIN, subprotocols=["binary"]) as socket:
            socket.send_bytes(b"pcm")
            assert socket.receive_bytes() == b"pcm"
        for path in ("/websockify/other", "/ws-other"):
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(path, headers=ORIGIN):
                    pass
        assert len(mock_browser) == 1

class RoleChangingOIDC:
    """Simulates two verified OIDC callbacks; no live IdP polling is implied."""

    def __init__(self):
        self.groups = ["foxden-admins"]

    async def finish(self, state, code):
        claims = {
            "sub": "browser-oidc-subject",
            "preferred_username": "oidc-browser-admin",
            "name": "Browser Admin",
            "groups": list(self.groups),
        }
        return claims, {"return_to": "/"}

    def authorize_claims(self, claims):
        role = "admin" if "foxden-admins" in claims["groups"] else "user"
        return (
            claims["sub"], claims["preferred_username"], claims["name"],
            claims["groups"], role,
        )


def test_verified_oidc_role_change_revokes_existing_websocket(tmp_path, mock_browser):
    identity = RoleChangingOIDC()
    with TestClient(create_app(settings(tmp_path, auth_mode="hybrid"), oidc_client=identity)) as client:
        bootstrap_admin(client)
        first = client.get("/auth/oidc/callback?state=first&code=test", follow_redirects=False)
        assert first.status_code == 303
        previous_token = client.cookies.get("foxden_portal_session")
        with client.websocket_connect("/websockify", headers=ORIGIN) as socket:
            socket.send_bytes(b"connected")
            assert socket.receive_bytes() == b"connected"
            identity.groups = []
            next_login = client.get(
                "/auth/oidc/callback?state=second&code=test", follow_redirects=False,
            )
            assert next_login.status_code == 303
            assert client.app.state.store.session(previous_token) is None
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_bytes()
            assert closed.value.code == 1008
        assert mock_browser[0][2].closed


def test_session_database_failure_terminates_active_socket(tmp_path, mock_browser, monkeypatch):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        with client.websocket_connect("/websockify", headers=ORIGIN) as socket:
            socket.send_text("connected")
            assert socket.receive_text() == "connected"
            def database_unavailable(token):
                raise OSError("simulated outage")
            monkeypatch.setattr(client.app.state.store, "session", database_unavailable)
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_text()
            assert closed.value.code == 1008
        assert mock_browser[0][2].closed


def test_session_database_failure_rejects_handshake(tmp_path, mock_browser, monkeypatch):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        def database_unavailable(token):
            raise OSError("simulated outage")
        monkeypatch.setattr(client.app.state.store, "session", database_unavailable)
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect("/websockify", headers=ORIGIN):
                pass
        assert closed.value.code == 1008
        assert mock_browser == []
