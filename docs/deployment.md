# Modular deployment

Fox Den uses one Compose model with profiles selected by `scripts/foxden.py`.
Users configure host-specific values only through an environment file and
secret files.

| Mode | Profiles | Services |
|---|---|---|
| `music` | `music` | ingress, Portal, Music web, Music worker |
| `media` | `media` | ingress, Portal, Movies/TV |
| `jellyfin` | `jellyfin` | ingress, Portal, official Jellyfin server |
| `full-external` | `music`, `media` | both modules with external qBittorrent and optional external Jellyfin |
| `full-managed` | `music`, `media`, `managed` | both modules, qBittorrent, and Gluetun |

`--browser` adds the contained browser. `--jellyfin` adds Jellyfin to another
mode. `--jellyfin-hwaccel` also loads the explicit `/dev/dri` override. Disabled profiles do not make
their configuration mandatory.

Application containers join a private internal module network plus a separate
outbound network for metadata providers, external qBittorrent/Jellyfin, and
OIDC. They publish no backend ports. Ingress is the only public route. Managed
qBittorrent shares Gluetun's network namespace and cannot attach to an
independent network.

## Initial configuration

1. Copy the matching file from `deploy/examples` to an untracked `.env`.
2. Replace example paths, public origin, IDs, and provider values.
3. Run `python scripts/foxden.py init --env .env --create-paths`.
4. Put the real qBittorrent password and, for managed mode, WireGuard private
   key into the generated secret files. If Jellyfin or OIDC is enabled, fill
   `jellyfin-api-key` or `oidc-client-secret` respectively. The command never
   prints them.
5. Run `python scripts/foxden.py validate MODE --env .env`.
6. Review `python scripts/foxden.py deploy MODE --env .env`.
7. Only after approval, repeat with `--execute`.

The gateway configuration is rendered from a tracked template into the runtime
directory with the ingress authentication secret. It is never committed.

## Reverse proxies and Authentik

Bind ingress to loopback when Caddy terminates TLS. Set `FOXDEN_PUBLIC_ORIGIN`
to the external HTTPS origin and keep `PORTAL_COOKIE_SECURE=true`. Authentik is
optional; set Portal to `oidc` or `hybrid` and configure issuer, client ID,
client-secret file, redirect URI, and group mappings. Caddy or forward-auth
headers are not accepted as module identity; Portal mints separate Ed25519
assertions after authentication.

## Jellyfin boundary

`JELLYFIN_URL` and the generated `jellyfin-api-key` secret remain the separate
Music-worker library-refresh integration; only that worker sees the API key.
Leave the URL blank when refresh is not wanted.

Watch & Listen uses `JELLYFIN_PUBLIC_URL` for browser/native-client links and
`JELLYFIN_INTERNAL_URL` for Portal's server-side adapter. Use
`http://jellyfin:8096` for managed Jellyfin or a Portal-reachable address for
an external server. It authenticates each person as their own Jellyfin user and
never consumes the worker API key. The existing `portal-secret` encrypts those
user tokens; changing it requires users to reconnect, so it must be backed up
with Portal state.

The optional managed profile is documented in [jellyfin.md](jellyfin.md). It
must use copied state until the [Jellyfin migration runbook](jellyfin-migration.md)
and machine-readable evidence gates pass.
