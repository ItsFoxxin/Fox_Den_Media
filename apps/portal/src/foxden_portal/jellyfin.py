from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit
import re

import httpx


ITEM_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
STATIC_API_PATHS = frozenset({
    "/Items", "/Sessions/Logout", "/UserItems/Resume", "/Users/AuthenticateByName",
    "/Users/Me", "/UserViews",
})
DYNAMIC_API_PATH = re.compile(r"^/Items/[A-Za-z0-9_-]{1,128}(?:/Images/Primary)?$")
HTTP_METHODS = frozenset({"GET", "POST"})


class JellyfinError(RuntimeError):
    """A safe, user-facing Jellyfin integration failure."""


class JellyfinInputError(JellyfinError):
    """The caller supplied an unsupported or malformed request."""


class JellyfinUnavailable(JellyfinError):
    pass


class JellyfinAuthenticationError(JellyfinError):
    pass


@dataclass(frozen=True)
class JellyfinSession:
    user_id: str
    username: str
    access_token: str
    device_id: str


class JellyfinAdapter:
    """Small, bounded adapter for the user-scoped Jellyfin API surface.

    Raw Jellyfin responses never leave this class. In particular, paths,
    media-source details, provider credentials, and administrator fields are
    not exposed through the Fox Den API.
    """

    def __init__(self, base_url: str, public_url: str, timeout: float = 4.0,
                 transport: httpx.AsyncBaseTransport | None = None):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment):
            raise JellyfinInputError("The configured Jellyfin service URL is invalid.")
        self.base_url = base_url.rstrip("/")
        self.public_url = public_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    @staticmethod
    def authorization(device_id: str, token: str | None = None) -> str:
        values = [
            'Client="Fox Den Media"', 'Device="Portal"',
            f'DeviceId="{device_id}"', 'Version="0.9.1"',
        ]
        if token:
            values.append(f'Token="{token}"')
        return "MediaBrowser " + ", ".join(values)

    async def authenticate(self, username: str, password: str, device_id: str) -> JellyfinSession:
        if not username or not password:
            raise JellyfinAuthenticationError("Enter your Jellyfin username and password.")
        response = await self._request(
            "POST", "/Users/AuthenticateByName", device_id=device_id,
            json={"Username": username, "Pw": password}, allow_auth_failure=True,
        )
        data = self._json(response)
        user = data.get("User") if isinstance(data, dict) else None
        token = data.get("AccessToken") if isinstance(data, dict) else None
        if not isinstance(user, dict) or not isinstance(user.get("Id"), str) or not isinstance(token, str):
            raise JellyfinAuthenticationError("Jellyfin returned an invalid login response.")
        return JellyfinSession(user["Id"], str(user.get("Name") or username), token, device_id)

    async def profile(self, session: JellyfinSession) -> dict[str, Any]:
        response = await self._request("GET", "/Users/Me", session=session)
        data = self._json(response)
        if not isinstance(data, dict) or str(data.get("Id", "")) != session.user_id:
            raise JellyfinAuthenticationError("The linked Jellyfin session is no longer valid.")
        return {"id": session.user_id, "name": str(data.get("Name") or session.username)}

    async def home(self, session: JellyfinSession) -> dict[str, Any]:
        await self.profile(session)
        views, recent_video, recent_audio, resume = await self._gather(
            self._items(session, "/UserViews", {"userId": session.user_id}),
            self._items(session, "/Items", {
                "userId": session.user_id, "recursive": "true", "includeItemTypes": "Movie,Series,Episode",
                "sortBy": "DateCreated", "sortOrder": "Descending", "limit": "18",
                "fields": "PrimaryImageAspectRatio,Overview,ProductionYear,RunTimeTicks,UserData",
            }),
            self._items(session, "/Items", {
                "userId": session.user_id, "recursive": "true", "includeItemTypes": "MusicAlbum,Audio,MusicArtist",
                "sortBy": "DateCreated", "sortOrder": "Descending", "limit": "18",
                "fields": "PrimaryImageAspectRatio,Overview,ProductionYear,RunTimeTicks,AlbumArtist,Artists,UserData",
            }),
            self._items(session, "/UserItems/Resume", {
                "userId": session.user_id, "limit": "18", "mediaTypes": "Video",
                "fields": "PrimaryImageAspectRatio,Overview,ProductionYear,RunTimeTicks,UserData",
            }),
        )
        return {
            "contract_version": "1.0", "state": "ready",
            "user": {"id": session.user_id, "name": session.username},
            "libraries": views, "recent_video": recent_video,
            "recent_audio": recent_audio, "continue_watching": resume,
        }

    async def search(self, session: JellyfinSession, query: str) -> dict[str, Any]:
        query = query.strip()
        if not query or len(query) > 200:
            raise JellyfinInputError("Search must contain between 1 and 200 characters.")
        items = await self._items(session, "/Items", {
            "userId": session.user_id, "recursive": "true", "searchTerm": query, "limit": "50",
            "includeItemTypes": "Movie,Series,Season,Episode,MusicArtist,MusicAlbum,Audio,Playlist",
            "fields": "PrimaryImageAspectRatio,Overview,ProductionYear,RunTimeTicks,AlbumArtist,Artists,UserData",
        })
        return {"contract_version": "1.0", "query": query, "items": items}

    async def browse(self, session: JellyfinSession, kind: str, start: int = 0, limit: int = 60) -> dict[str, Any]:
        kinds = {
            "movies": "Movie", "shows": "Series", "artists": "MusicArtist",
            "albums": "MusicAlbum", "songs": "Audio", "playlists": "Playlist",
        }
        if kind not in kinds:
            raise JellyfinInputError("That media collection is not supported.")
        start = max(0, start)
        limit = min(max(limit, 1), 100)
        items = await self._items(session, "/Items", {
            "userId": session.user_id, "recursive": "true", "includeItemTypes": kinds[kind],
            "sortBy": "SortName", "sortOrder": "Ascending", "startIndex": str(start), "limit": str(limit),
            "fields": "PrimaryImageAspectRatio,Overview,ProductionYear,RunTimeTicks,AlbumArtist,Artists,UserData",
        })
        return {"contract_version": "1.0", "kind": kind, "start": start, "limit": limit, "items": items}

    async def item(self, session: JellyfinSession, item_id: str) -> dict[str, Any]:
        self._validate_item_id(item_id)
        response = await self._request(
            "GET", f"/Items/{quote(item_id, safe='')}", session=session,
            params={"userId": session.user_id},
        )
        data = self._json(response)
        if not isinstance(data, dict):
            raise JellyfinError("Jellyfin returned invalid item metadata.")
        safe = self._safe_item(data, detailed=True)
        if safe["type"] in {"Series", "Season", "MusicAlbum", "MusicArtist", "Playlist"}:
            safe["children"] = await self._items(session, "/Items", {
                "userId": session.user_id, "parentId": item_id, "recursive": "false", "limit": "100",
                "sortBy": "ParentIndexNumber,IndexNumber,SortName", "sortOrder": "Ascending",
                "fields": "PrimaryImageAspectRatio,Overview,ProductionYear,RunTimeTicks,AlbumArtist,Artists,UserData",
            })
        else:
            safe["children"] = []
        return {"contract_version": "1.0", "item": safe}

    async def artwork(self, session: JellyfinSession, item_id: str, width: int = 640) -> tuple[bytes, str]:
        self._validate_item_id(item_id)
        # Confirm item visibility through the user's item endpoint before
        # proxying an image, even if a Jellyfin version serves images broadly.
        await self.item(session, item_id)
        width = min(max(width, 64), 1600)
        response = await self._request(
            "GET", f"/Items/{quote(item_id, safe='')}/Images/Primary", session=session,
            params={"maxWidth": str(width), "quality": "85"},
        )
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            raise JellyfinError("Jellyfin returned an unsupported artwork format.")
        if len(response.content) > 10 * 1024 * 1024:
            raise JellyfinError("Jellyfin artwork exceeded the size limit.")
        return response.content, content_type

    async def logout(self, session: JellyfinSession) -> None:
        try:
            await self._request("POST", "/Sessions/Logout", session=session)
        except JellyfinError:
            # Local unlinking must still work if Jellyfin is offline.
            return

    def web_item_url(self, item_id: str) -> str:
        self._validate_item_id(item_id)
        return f"{self.public_url}/web/#/details?id={quote(item_id, safe='')}"

    async def _items(self, session: JellyfinSession, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = await self._request("GET", path, session=session, params=params)
        data = self._json(response)
        raw = data.get("Items", []) if isinstance(data, dict) else []
        if not isinstance(raw, list):
            raise JellyfinError("Jellyfin returned an invalid item list.")
        return [self._safe_item(item) for item in raw if isinstance(item, dict) and isinstance(item.get("Id"), str)]

    async def _gather(self, *calls):
        import asyncio
        return await asyncio.gather(*calls)

    def _safe_item(self, item: dict[str, Any], detailed: bool = False) -> dict[str, Any]:
        item_id = str(item.get("Id", ""))
        self._validate_item_id(item_id)
        user_data = item.get("UserData") if isinstance(item.get("UserData"), dict) else {}
        artists = item.get("Artists") if isinstance(item.get("Artists"), list) else []
        result: dict[str, Any] = {
            "id": item_id,
            "name": str(item.get("Name") or "Untitled")[:300],
            "type": str(item.get("Type") or "Unknown")[:40],
            "year": item.get("ProductionYear") if isinstance(item.get("ProductionYear"), int) else None,
            "album_artist": str(item.get("AlbumArtist") or "")[:200] or None,
            "artists": [str(value)[:200] for value in artists[:10]],
            "runtime_ticks": item.get("RunTimeTicks") if isinstance(item.get("RunTimeTicks"), int) else None,
            "played": bool(user_data.get("Played", False)),
            "favorite": bool(user_data.get("IsFavorite", False)),
            "playback_position_ticks": user_data.get("PlaybackPositionTicks", 0)
            if isinstance(user_data.get("PlaybackPositionTicks", 0), int) else 0,
            "artwork_url": f"/api/watch/v1/artwork/{quote(item_id, safe='')}",
            "details_url": f"/watch/item/{quote(item_id, safe='')}",
        }
        if detailed:
            result["overview"] = str(item.get("Overview") or "")[:5000]
            result["genres"] = [str(value)[:100] for value in (item.get("Genres") or [])[:20]]
            result["jellyfin_url"] = self.web_item_url(item_id)
        return result

    async def _request(self, method: str, path: str, *, session: JellyfinSession | None = None,
                       device_id: str | None = None, allow_auth_failure: bool = False, **kwargs) -> httpx.Response:
        method, request_url = self._validated_request_target(method, path)
        active_device = session.device_id if session else (device_id or "foxden-portal")
        headers = {"Authorization": self.authorization(active_device, session.access_token if session else None),
                   "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False,
                                         transport=self.transport, trust_env=False) as client:
                response = await client.request(method, request_url, headers=headers, **kwargs)
        except httpx.RequestError:
            raise JellyfinUnavailable("Jellyfin is currently unavailable.") from None
        if response.status_code in {401, 403}:
            if allow_auth_failure:
                raise JellyfinAuthenticationError("Jellyfin did not accept those credentials.")
            raise JellyfinAuthenticationError("Your Jellyfin session has expired. Reconnect to continue.")
        if response.status_code == 404:
            raise JellyfinError("The requested Jellyfin item was not found.")
        if response.status_code < 200 or response.status_code >= 300:
            raise JellyfinError("Jellyfin could not complete the request.")
        maximum = 12 * 1024 * 1024 if "/Images/" in path else 5 * 1024 * 1024
        if len(response.content) > maximum:
            raise JellyfinError("Jellyfin returned a response larger than the allowed limit.")
        return response

    def _validated_request_target(self, method: str, path: str) -> tuple[str, str]:
        method = method.upper()
        if method not in HTTP_METHODS:
            raise JellyfinInputError("That Jellyfin request method is not supported.")
        if path not in STATIC_API_PATHS and not DYNAMIC_API_PATH.fullmatch(path):
            raise JellyfinInputError("That Jellyfin API path is not supported.")
        # Build from the operator-controlled base and a strictly allowlisted
        # relative API path. A caller cannot replace the configured origin with
        # an absolute or scheme-relative URL.
        request_url = self.base_url + path
        return method, request_url

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            raise JellyfinError("Jellyfin returned an invalid response.") from None

    @staticmethod
    def _validate_item_id(item_id: str) -> None:
        if not ITEM_ID.fullmatch(item_id):
            raise JellyfinInputError("The Jellyfin item identifier is invalid.")
