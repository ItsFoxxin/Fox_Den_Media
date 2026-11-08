# Configuration

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

Configuration is mode-specific. Copy a current [mode environment example](https://github.com/ItsFoxxin/Fox_Den_Media/tree/dev/deploy/examples/) to an **untracked private** `.env`; the root `.env.example` is reference material, not a full mode installer.

## Important settings

| Name | Purpose |
| --- | --- |
| `FOXDEN_PUBLIC_ORIGIN` | Browser origin and HTTPS scheme |
| `FOXDEN_BIND_IP`, `FOXDEN_PORT` | Ingress host bind (loopback by default) |
| `COMPOSE_PROJECT_NAME` | Distinct project identity for side-by-side tests |
| `FOXDEN_PUID`, `FOXDEN_PGID` | Numeric container account |
| `PORTAL_AUTH_MODE` | `local`, `oidc` or `hybrid` |
| `PORTAL_COOKIE_SECURE` | Enable for remotely available HTTPS |
| `FOXDEN_SECRETS_DIR` | Restricted file-mounted secret directory |
| `PORTAL_CONFIG_PATH`, `FOXDEN_RUNTIME_DIR` | Persistent Portal and private generated proxy data |
| `MUSICBRAINZ_CONTACT` | Required administrative contact in Music modes |

Each optional component adds its own storage paths, application settings and secret requirements. For example, Gluetun requires a private WireGuard key file and Jellyfin may require separate native-client routing.

## Safety rules

- Store private credentials in dedicated **secret files** (private files typically `0600`) with correct container-accessible ownership, not public docs or Git.
- Verify non-overlapping writable host directories; do not share live SQLite/config state between two stacks.
- Avoid copying secret-bearing expanded Compose outputs or container environments to public issues.
- `validate` and `config` render a private proxy configuration; they are not completely read-only operations.

**Authoritative specifications:** [settings and secrets](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md), [Compose](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/deploy/compose.yaml), [deployment controller](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/scripts/foxden.py) and [authorization boundaries](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/permissions.md).