# Architecture (current deployment model)

This describes the **0.9.1** source in [`deploy/compose.yaml`](../deploy/compose.yaml) and [`infra/gateway/portal-ingress.conf`](../infra/gateway/portal-ingress.conf), not the older `deploy/legacy/` or standalone Music Compose variants. Refer to [configuration](configuration.md) for required host paths and secrets.

```text
HTTPS client -> external TLS reverse proxy (optional)
                              |
                              v
Host 127.0.0.1:8080 -> Nginx ingress :8080 [edge + platform]
                            | -> Portal :8020 (unprofiled)
                            | -> Music :8000 [music] -> Music worker [music]
                            | -> Media :8010 [media]
                            | -> Firefox :5800 [browser]
Jellyfin hostname ----------| -> Jellyfin :8096 [jellyfin]

Media -> qBittorrent API -> qBittorrent [managed; namespace of Gluetun]
                                |
                    Gluetun [managed; WireGuard + firewall]
```

| Network | Purpose | Attachment |
| --- | --- | --- |
| `edge` | Host-facing ingress only | Nginx |
| `platform` (`internal: true`) | Backend routing, Portal assertion verification | Nginx, Portal, app services, browser, Jellyfin, Gluetun |
| `outbound` | Explicit upstream access for metadata, OIDC, providers | App services, browser, Jellyfin, Gluetun; **not** a separate qBittorrent interface |

The unprofiled `ingress` and `portal` are always present. Only ingress publishes an application UI by default (host loopback `FOXDEN_BIND_IP:FOXDEN_PORT`). Gluetun additionally publishes a **loopback-bound** qBittorrent Web UI for managed mode. Music, Media, Jellyfin and Firefox use Docker `expose` only. Managed qBittorrent has `network_mode: service:gluetun` and is blocked on Gluetun health; it has **no** independent port/network definition.

## Trust boundaries

Nginx validates Portal sessions through a protected auth subrequest and removes client-supplied Fox Den/Authentik identity headers. Portal is the only holder of the Ed25519 private signing key. It issues short-lived audience-bound assertions; modules verify the published public keys, roles, scopes and request identity. General Portal accounts can link and browse their own Jellyfin libraries through Watch & Listen but do not gain acquisition access. Music, Media and Firefox routes require Portal administrator privileges. See [permissions](permissions.md), [identity key management](phase-1b/identity-key-management.md), and [security](security.md).

Jellyfin keeps its native login independently of Portal and Authentik. Its dedicated hostname is routed by ingress without browser-only forward auth so TVs/mobile clients continue to work. The worker's optional `JELLYFIN_URL` + API key for library refresh is **separate** from Portal's user-scoped Watch & Listen integration (`JELLYFIN_INTERNAL_URL`, `JELLYFIN_PUBLIC_URL`).

## Application state and paths

- Portal: `PORTAL_CONFIG_PATH` with Portal SQLite state; secrets and signing keys under `FOXDEN_SECRETS_DIR`.
- Music web and worker: separate processes sharing `MUSIC_CONFIG_PATH` SQLite/config, staging and inbox; the worker alone writes `MUSIC_LIBRARY_PATH`.
- Media: `MEDIA_CONFIG_PATH` SQLite and `MEDIA_LIBRARY_PATH`; `TORRENT_DATA_PATH` mounted **read-only** in the Media container at `/downloads`, while qBittorrent can write that root in managed mode.
- qBittorrent: separate `QBIT_CONFIG_PATH`, shared Gluetun network namespace, media-visible torrent data.
- Jellyfin: independent `JELLYFIN_CONFIG_PATH` and `JELLYFIN_CACHE_PATH`, read-only `JELLYFIN_MEDIA_PATH` mounted at `JELLYFIN_MEDIA_CONTAINER_PATH`.
- Firefox: its own `BROWSER_CONFIG_PATH`, Music download inbox shared as required.

Media import jobs validate source paths and content, then copy into a unique hidden `.imports` staging path under the destination library, validate checksums and publish without overwriting an existing name. An interrupted operation may need manual review; the source torrent payload remains intact. The application needs a compatible local filesystem for atomic no-replace publication. See [requests](requests.md) and [0.9.1 review](security-0.9.1.md).

The platform is **not** a hostile multi-tenant filesystem sandbox; only trusted operators should be able to mutate host storage roots. The browser image has different upstream hardening constraints than first-party app images.

## Evolution and evidence

Older phase documents and ADRs deliberately show earlier routes, stack names and plans. They are historical, not competing deployment instructions. **Current configuration is authoritative.** Unit/integration tests do not prove real NAS permissions, real VPN kill switch, Jellyfin plugin compatibility or production cutover. See [readiness](production-readiness.md).
