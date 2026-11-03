# Recovery and rollback

Rollback always begins by stopping **every new writer**. Preserve the failed
state for diagnosis, then restore only from the immutable verified pre-migration
backup and storage snapshot. Never use `docker compose down -v`, prune volumes,
or point an older image at a database modified by an incompatible newer version.

## Tested fixture boundary

`scripts/migration.py rollback-rehearsal` verifies the archive, restores it only
to an empty isolated target and validates every file checksum. CI proves this
mechanism using synthetic state. It does not prove NAS paths, ownership, plugins,
torrents, VPN routing, clients, or prior images until an authorized rehearsal.

## Failure matrix

| Failure | Immediate action | Recovery validation |
|---|---|---|
| Container startup | Stop new project; preserve logs/config | Start prior Compose against restored copy; check health and mounts |
| Database migration | Stop that application and all related workers | Restore pre-migration DB plus WAL/SHM/config; use prior image only |
| Authentik/OIDC | Keep Portal local emergency access; stop routing changes | Validate issuer/client/redirect/groups and local recovery before retry |
| Jellyfin plugin/provider | Stop new Jellyfin; do not let another instance use config | Restore config/database/plugins, prior image and exact media paths; test users/history |
| Jellyfin library/history | Stop writes immediately | Restore database/metadata snapshot; validate counts, progress, artwork and clients |
| qBittorrent resume/seeding | Stop qBittorrent, then Gluetun | Restore appdata/BT_backup, exact save paths and prior versions; compare torrent states |
| VPN tunnel/firewall | Stop qBittorrent first | Start prior Gluetun, verify tunnel/DNS/kill switch, then prior qBittorrent |
| Media permissions | Stop publishers/importers | Restore recorded UID/GID/mode/ACL and validate synthetic write/rename before reopening |
| Reverse proxy | Revert routing while direct services remain private | Validate prior Caddy config, TLS, WebSockets, cookies and module routes |

## Rollback order

1. Close ingress to state-changing operations.
2. Stop new Music/Movies workers, qBittorrent, Jellyfin, Portal and related writers.
3. Confirm no new process holds the affected state roots.
4. Preserve the failed deployment and logs separately.
5. Verify the immutable pre-migration archive and snapshot checksums.
6. Restore into the approved prior paths with recorded numeric ownership/modes.
7. Start prior Gluetun and validate it before prior qBittorrent.
8. Start prior databases/applications only after their exact state is restored.
9. Start prior Jellyfin against its restored config and unchanged internal media paths.
10. Validate authentication, counts, history, queues, seeding, VPN and clients.
