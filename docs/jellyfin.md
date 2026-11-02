# Optional Jellyfin module

Fox Den Media 0.6.0 can run the official `jellyfin/jellyfin` image as an optional,
independently restartable service. It is disabled unless the `jellyfin` mode,
`--jellyfin`, or `--jellyfin-hwaccel` is selected. Existing external Jellyfin
refresh support remains available through `JELLYFIN_URL` and does not start this
service.

The defaults follow the official [container documentation](https://jellyfin.org/docs/general/installation/container/):
separate persistent `/config` and `/cache`, a configurable non-root UID/GID,
read-only media, the image's built-in health check, and a pinned minor image tag.

## Routing decision: dedicated hostname

Use a dedicated hostname such as `jellyfin.example.net`, not `/jellyfin/`.
Jellyfin supports a base URL, but a hostname avoids subpath rewrites and is more
reliable for television, mobile, and desktop clients. The existing Nginx ingress
selects Jellyfin by the `Host` header, forwards WebSockets and proxy headers, and
disables request-path access logging because Jellyfin can place API keys in URLs.

Jellyfin requests do **not** pass through Portal `auth_request`. Jellyfin native
clients must authenticate directly to Jellyfin. Fox Den identity headers and
Authentik forward-auth headers are stripped before proxying. Configure the Nginx
container/network as a Known Proxy in Jellyfin before trusting forwarded client
addresses. See Jellyfin's [reverse-proxy guidance](https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/).

For Caddy, preserve the original Host header and proxy the Jellyfin hostname to
the same Fox Den ingress listener used by the Portal. TLS remains terminated by
Caddy. Do not add Authentik forward-auth in front of this hostname: native clients
cannot complete that browser-only flow.

## Configuration

| Variable | Required when enabled | Purpose |
|---|---:|---|
| `JELLYFIN_IMAGE` | yes | Official image and pinned tag; default `jellyfin/jellyfin:12.4` |
| `JELLYFIN_PUBLIC_URL` | yes | Client-facing URL and ingress hostname |
| `JELLYFIN_PUID`, `JELLYFIN_PGID` | yes | Container process UID/GID |
| `JELLYFIN_CONFIG_PATH` | yes | Persistent database, configuration, plugins, and metadata |
| `JELLYFIN_CACHE_PATH` | yes | Persistent cache/transcode working data |
| `JELLYFIN_MEDIA_PATH` | yes | Host media root mounted read-only |
| `JELLYFIN_MEDIA_CONTAINER_PATH` | yes | Stable in-container media root, default `/media` |
| `JELLYFIN_MEMORY_LIMIT`, `JELLYFIN_CPUS` | no | Container resource limits |
| `JELLYFIN_DRI_DEVICE` | hardware only | Verified host device or directory, commonly `/dev/dri` |
| `JELLYFIN_RENDER_GID`, `JELLYFIN_VIDEO_GID` | hardware only | Host supplemental group IDs |

Keep `JELLYFIN_MEDIA_CONTAINER_PATH` identical to the old container path during
migration. Jellyfin records library paths in its database.

```bash
cp deploy/examples/jellyfin.env.example .env.jellyfin
python scripts/foxden.py init --env .env.jellyfin --create-paths
python scripts/foxden.py validate jellyfin --env .env.jellyfin
python scripts/foxden.py deploy jellyfin --env .env.jellyfin
# Review the dry-run command, then explicitly repeat with --execute.
```

Add `--jellyfin` to `music`, `media`, `full-external`, or `full-managed` to add
the service. This never puts Jellyfin in Gluetun's network namespace.

## Intel N100 hardware transcoding

The N100 supports Intel Quick Sync/VA-API, but the host device path and group IDs
vary. Inventory them on the Linux Docker host before enabling anything:

```bash
ls -la /dev/dri
getent group render
getent group video
```

Set the three hardware variables, run validation, and use
`--jellyfin-hwaccel`. That flag adds `deploy/compose.jellyfin-hwaccel.yaml`; the
normal service has no device access. After startup, select Intel QSV or VA-API
in Jellyfin and perform a controlled transcode while reviewing the FFmpeg log.
Direct play does not prove transcoding works. Official hardware guidance is at
[Jellyfin Hardware Acceleration](https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/).

## Authentication decision

Native Jellyfin authentication is the production-safe default and recovery path.
It works with browser, television, mobile, and desktop clients.

If directory authentication is later approved, the best-supported Authentik path
is the Jellyfin LDAP Authentication plugin with an Authentik LDAP provider and
outpost. Jellyfin does not currently provide native external OIDC for every
client. Browser-oriented SSO plugins are not a replacement for native-client
login. Follow the [Authentik Jellyfin integration guide](https://integrations.goauthentik.io/media/jellyfin/)
and install only a plugin version compatible with the inventoried Jellyfin
version. Keep one tested local Jellyfin administrator for recovery.

- `foxden-jellyfin-users`: may authenticate; library access is still assigned in Jellyfin.
- `foxden-jellyfin-admins`: eligibility only; administrator assignment remains explicit.
- Portal administrators do not automatically become Jellyfin administrators.
- LDAP auto-provisioning must not auto-grant every library or administrator role.
- Logging out of Portal does not revoke a Jellyfin session, and vice versa.

## Fox Den Midnight theme

The official image is not modified. Nginx exposes the versioned CSS and mascot on
the Jellyfin hostname. In Jellyfin Web, open **Dashboard > Branding > Custom CSS**
and add:

```css
@import url('/foxden-theme.css');
```

The customization is isolated in `apps/portal/src/foxden_portal/static/jellyfin-midnight.css`.
It affects Jellyfin Web only; native applications retain their supported UI.
Remove the import to roll back the theme without changing the container.

## Backup boundary

Back up both `JELLYFIN_CONFIG_PATH` and `JELLYFIN_CACHE_PATH`; configuration and
the database are the critical set. Media is independently backed up according to
the storage policy. Never mount live config into two Jellyfin processes. Use
[the migration runbook](jellyfin-migration.md) before pointing this profile at
existing state.
