# 0.7.0 production readiness

## Implemented

- DenKit/Fox Den Midnight across Portal, Music, Movies/TV, and optional Jellyfin Web.
- Administrator-only ingress for acquisition and contained-browser routes.
- General-user Portal view limited to assigned media links.
- Optional official Jellyfin container with persistent state, read-only media,
  dedicated-host ingress, WebSockets, resource controls, and isolated hardware override.
- Existing external Jellyfin library-refresh integration remains intact.
- User-scoped Watch & Listen browsing with encrypted token storage and a tested
  Portal database migration from schema v1 to v2.
- Explicit machine-readable production evidence gates; incomplete evidence
  cannot produce a cutover-ready report.
- Migration, rollback, authentication, permissions, and theme procedures.

## Tested in source/CI fixtures

- configuration and profile selection with Jellyfin enabled and disabled;
- route/header/security invariants and WebSocket proxy configuration;
- Portal local/OIDC identity behavior and administrator boundary;
- DenKit tokens, theme asset packaging, and responsive Portal behavior;
- existing Music, Movies/TV, and signed-identity regression suites.

## Requires production configuration and isolated NAS rehearsal

- inventory the existing Jellyfin version, mounts, plugins, users, and device access;
- choose final `JELLYFIN_PUBLIC_URL` and configure Caddy/DNS/TLS;
- configure Jellyfin Known Proxies;
- make and verify consistent config/cache backups;
- test a restored copy without sharing live state;
- verify the N100 `/dev/dri` path and group IDs;
- validate native clients, playback, subtitles, seeking, and real transcodes;
- review LDAP plugin compatibility before connecting Authentik/AD.
- connect one disposable production-like Jellyfin user and verify that Watch &
  Listen exposes only that user's assigned libraries;
- confirm the dedicated public and container-reachable Jellyfin URLs.

## Not ready for automatic production cutover

The code is a migration candidate, not proof of the live NAS. Production remains
blocked on read-only inventory, tested backup/restore, isolated Jellyfin rehearsal,
full hosted CI, and explicit human approval. No repository merge or deployment
authorizes access to live Jellyfin configuration.
