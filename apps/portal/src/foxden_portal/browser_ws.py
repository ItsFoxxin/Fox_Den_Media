"""Session-bound WebSocket relay for the optional Firefox/noVNC desktop.

Nginx still performs its existing Portal auth_request at the handshake.  This
relay enforces authorization *after* HTTP 101, which Nginx alone cannot do.
Only fixed noVNC websockify paths may reach the internal Firefox container.
"""
from __future__ import annotations

import asyncio
import re
from time import monotonic
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket
from websockets.asyncio.client import connect

RECHECK_INTERVAL_SECONDS = 15.0
MAX_CONNECTION_SECONDS = 3600.0
MAX_FRAME_BYTES = 32 * 1024 * 1024
WEBSOCKIFY_PATH = re.compile(r"websockify(?:-[a-z0-9-]{1,48})?\Z")
UPSTREAM_ORIGIN = "ws://download-browser:5800"


def _authorized(store, token: str | None) -> bool:
    """Never cache authorization: session expiry, logout and account changes matter."""
    try:
        record = store.session(token)
        return bool(record and record["role"] == "admin")
    except Exception:
        # A database error must not prolong desktop access.
        return False


def register_browser_websockets(app: FastAPI, store, public_url: str) -> None:
    expected_origin = public_url.rstrip("/")
    parsed = urlsplit(expected_origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
        raise ValueError("Portal public URL must be an HTTP(S) origin.")

    @app.websocket("/{browser_socket_path:path}")
    async def guarded_browser_socket(websocket: WebSocket, browser_socket_path: str):
        # Nginx routes /server-browser/ Upgrade requests here after stripping
        # the prefix; ordinary browser HTTP always remains on Firefox:5800.
        # Do not turn this into an open WebSocket proxy.
        if not WEBSOCKIFY_PATH.fullmatch(browser_socket_path):
            await websocket.close(code=1008)
            return
        if websocket.headers.get("origin") != expected_origin:
            await websocket.close(code=1008)
            return
        token = websocket.cookies.get("foxden_portal_session")
        if not _authorized(store, token):
            await websocket.close(code=1008)
            return

        query = websocket.scope.get("query_string", b"")
        if len(query) > 2048:
            await websocket.close(code=1008)
            return
        upstream_url = f"{UPSTREAM_ORIGIN}/{browser_socket_path}"
        if query:
            upstream_url += "?" + query.decode("ascii", errors="strict")
        # noVNC's optional 'binary' subprotocol is forwarded, including on audio.
        offered = websocket.scope.get("subprotocols", [])
        protocols = ["binary"] if "binary" in offered else None
        try:
            upstream = await connect(
                upstream_url, subprotocols=protocols, open_timeout=5,
                close_timeout=2, max_size=MAX_FRAME_BYTES,
            )
        except (OSError, TimeoutError, ValueError, Exception) as exc:
            # No stack trace, query string or user session data in error logs.
            await websocket.close(code=1013)
            return

        await websocket.accept(subprotocol=upstream.subprotocol)
        connected_at = monotonic()

        async def client_to_browser():
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return "client_disconnect"
                if message.get("bytes") is not None:
                    if len(message["bytes"]) > MAX_FRAME_BYTES:
                        return "oversize"
                    await upstream.send(message["bytes"])
                elif message.get("text") is not None:
                    if len(message["text"].encode("utf-8")) > MAX_FRAME_BYTES:
                        return "oversize"
                    await upstream.send(message["text"])

        async def browser_to_client():
            while True:
                payload = await upstream.recv()
                if isinstance(payload, bytes):
                    await websocket.send_bytes(payload)
                else:
                    await websocket.send_text(payload)

        async def watch_authorization():
            while True:
                remaining = MAX_CONNECTION_SECONDS - (monotonic() - connected_at)
                if remaining <= 0:
                    return "maximum_lifetime"
                await asyncio.sleep(min(RECHECK_INTERVAL_SECONDS, remaining))
                if not await asyncio.to_thread(_authorized, store, token):
                    return "authorization_revoked"

        tasks = [
            asyncio.create_task(client_to_browser()),
            asyncio.create_task(browser_to_client()),
            asyncio.create_task(watch_authorization()),
        ]
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            # An authorization watcher completion must close the connection.
            # Other completion (disconnect, upstream error) also closes safely.
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await upstream.close()
            try:
                await websocket.close(code=1008)
            except (OSError, RuntimeError):
                pass
