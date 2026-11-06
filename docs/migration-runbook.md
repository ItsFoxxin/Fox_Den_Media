# Production cutover runbook

This runbook is operator-reviewed and intentionally non-executable as a whole.
Every state-changing step requires separate production approval. Use
`production-migration-rehearsal.md` to generate the prerequisite evidence.

## Preconditions

- Exact release commit, image tags and digests recorded.
- Sanitized NAS inventory reviewed; mount ownership, free space, reverse proxy,
  `/dev/dri`, qBittorrent/Gluetun, Jellyfin and Authentik dependencies known.
- Initial consistent backup and isolated restore/rehearsal passed.
- Final path map preserves existing large media/torrent payloads in place where
  possible and preserves Jellyfin container media paths.
- Rollback archive, prior images/Compose/environment and recovery operator are available.
- Machine and human readiness reports say `CUTOVER_READY` for the exact commit.

## Cutover sequence

1. Confirm the approved production inventory has not drifted.
2. Confirm backup destination availability, ownership and free space.
3. Verify the earlier consistent backup and copied-state rehearsal artifacts.
4. Resolve every compatibility issue; do not waive failed critical evidence.
5. Record final approval, operators, timestamps, release SHA and rollback trigger.
6. Begin the maintenance window; disable acquisition/import submissions.
7. Stop Music worker/web and Movies/TV writers, then Portal.
8. Reconfirm no qBittorrent process/container exists. If that has changed, stop it
   and confirm resume data is flushed before stopping Gluetun. Preserve the
   discovered orphaned appdata without initializing it.
9. Stop Jellyfin and confirm no process has its database/config open.
10. Verify old and new stacks cannot simultaneously mount any writable database,
    qBittorrent appdata, Jellyfin config, staging directory or final publish root.
11. Capture and verify the final consistent backup and storage snapshot.
12. Start the approved Fox Den ingress/Portal and enabled application modules.
13. Validate local emergency login, Authentik if enabled, roles, signed identities,
    module health, redirects, assets, uploads and WebSockets.
14. Start Gluetun, validate tunnel/firewall/DNS/port-forward behavior, then start
    qBittorrent and verify counts, paths, resume and seeding state.
15. Start Jellyfin; validate users, plugins, libraries, history, artwork, search,
    Watch & Listen and browser/TV/mobile playback.
16. Confirm Liquidsoap/Icecast still read the unchanged Music library and port
    18080 remains available; Radio stays external for the initial migration.
17. Switch production routing only after direct service validation.
18. Observe logs, health, storage growth, queues, VPN and playback for the
    approved stabilization period. Keep the previous deployment stopped but intact.
19. Declare acceptance separately. Do not tag 1.0.0 merely because containers started.

## Abort and rollback triggers

Rollback instead of improvising when authentication recovery is unavailable,
database migration fails, Jellyfin loses users/history/libraries, qBittorrent
resume/seeding diverges, VPN fail-closed behavior is uncertain, permissions cause
writes under the wrong identity, or ingress cannot be restored quickly.

The rollback procedure is in `recovery.md`. Never use a database modified by an
incompatible newer application as an older-version recovery source.
