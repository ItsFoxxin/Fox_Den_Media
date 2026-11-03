from __future__ import annotations

import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken

from .database import PortalStore
from .jellyfin import JellyfinSession


class WatchSessionError(RuntimeError):
    pass


class WatchSessionStore:
    """Encrypt Jellyfin user tokens before they reach Portal-owned SQLite."""

    def __init__(self, store: PortalStore, secret: str):
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self.fernet = Fernet(key)
        self.store = store

    def save(self, portal_user_id: str, server_url: str, session: JellyfinSession) -> None:
        ciphertext = self.fernet.encrypt(session.access_token.encode("utf-8"))
        self.store.save_jellyfin_link(
            portal_user_id, server_url, session.user_id, session.username, ciphertext, session.device_id,
        )

    def load(self, portal_user_id: str, server_url: str) -> JellyfinSession | None:
        link = self.store.jellyfin_link(portal_user_id)
        if not link:
            return None
        if not secrets.compare_digest(link["server_url"], server_url):
            raise WatchSessionError("The saved Jellyfin connection belongs to a different server.")
        try:
            token = self.fernet.decrypt(bytes(link["token_ciphertext"])).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError):
            raise WatchSessionError("The saved Jellyfin connection cannot be decrypted. Reconnect your account.") from None
        return JellyfinSession(
            user_id=link["jellyfin_user_id"], username=link["username"],
            access_token=token, device_id=link["device_id"],
        )

    def delete(self, portal_user_id: str) -> None:
        self.store.delete_jellyfin_link(portal_user_id)
