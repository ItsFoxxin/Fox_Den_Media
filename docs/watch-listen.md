# Fox Den Watch & Listen 0.7

Watch & Listen is the user-facing media surface at `/watch/`. It is separate
from Music acquisition and Movies/TV administration. A Portal user may browse
only the libraries returned by that user's own Jellyfin session.

## Security and data flow

1. The user first authenticates to Portal through local or OIDC login.
2. The user explicitly connects their Jellyfin account. The password is sent
   server-to-server to `POST /Users/AuthenticateByName` and is never stored.
3. Portal encrypts the returned *user* access token before storing it in the
   Portal database. It never uses or exposes a Jellyfin administrator API key.
4. Every library, item, search, artwork, and resume request carries that user's
   token. Jellyfin remains the authorization authority for library visibility.
5. Fox Den returns a deliberately reduced object model. Paths, media sources,
   credentials, provider data, and administrator fields are excluded.

The encryption secret uses `PORTAL_JELLYFIN_TOKEN_SECRET[_FILE]`. The standard
Compose deployment reuses the protected Portal secret file; changing it
requires users to reconnect their Jellyfin accounts. Portal logout does not
destroy the link, while **Disconnect** revokes the Jellyfin session when the
server is reachable and always removes the local encrypted token.

## Deployment modes

- **Disabled:** omit `JELLYFIN_INTERNAL_URL`. `/watch/` presents a disabled
  state and no Jellyfin request is made.
- **External:** set the public client URL and a Portal-reachable internal URL.
- **Managed:** use `JELLYFIN_INTERNAL_URL=http://jellyfin:8096` with the
  optional Jellyfin profile.

Jellyfin failure never changes Portal, Music, or Movies/TV health.

## Versioned API

Browser pages and future clients share the server-side adapter. Implemented
read-only endpoints are:

- `GET /api/watch/v1/session`
- `GET /api/watch/v1/home`
- `GET /api/watch/v1/search?q=`
- `GET /api/watch/v1/browse/{movies|shows|artists|albums|songs|playlists}`
- `GET /api/watch/v1/items/{item_id}`
- `GET /api/watch/v1/artwork/{item_id}`

All metadata endpoints require an authenticated Portal session and a connected
Jellyfin user. The current web client uses secure Portal cookies. A future
mobile authorization-code/device flow will mint a revocable Fox Den client
session; it must not receive the Portal signing key, Jellyfin administrator
credentials, or another user's Jellyfin token.

## Playback boundary

This milestone provides a **Play in Jellyfin** handoff. Embedded Fox Den
playback is not claimed as complete. It requires a separately reviewed
user-scoped streaming contract, direct-play/transcode negotiation, session
reporting, seek/progress updates, and token delivery that cannot leak through
URLs, logs, referrers, or third-party players.

Jellyfin Web and native clients remain fully supported through the dedicated
Jellyfin hostname and their normal authentication. The Midnight CSS overlay is
the transitional branded player/browser.

## Failure behavior

- invalid credentials: generic failure plus rate limiting;
- expired/revoked Jellyfin token: reconnect prompt;
- server timeout/offline: unavailable state without internal host details;
- invalid artwork or oversized response: rejected;
- missing Portal session: `401` API response or login redirect;
- disabled module: explicit disabled state without startup failure.
