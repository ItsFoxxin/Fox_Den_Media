# qBittorrent recovery rehearsal

Production currently has no qBittorrent container or process. One `.torrent`
and one `.fastresume` survive under
`/volume2/docker/torrent-vpn/appdata/qbittorrent/qBittorrent/BT_backup`.

1. Copy the entire qBittorrent appdata tree while no qBittorrent writer exists.
2. Hash the copy and retain the original read-only.
3. Run `migration.py qbit-discovery` against the copy. It validates bencoding,
   pair completeness, checksums, and allowlisted stored path/category/tag fields.
4. Locate and copy the payload path referenced by the report. Map that same
   path to `/downloads` or document a reviewed path rewrite.
5. Start the pinned rehearsal qBittorrent only after Gluetun is healthy and its
   fail-closed fixture passes. Block tracker/peer traffic in the first offline run.
6. Verify torrent hash, category, tags, save path, completion, resume percentage,
   and seeding state without rechecking or moving production files.
7. Stop the rehearsal and verify the immutable source copy is unchanged.

Rollback deletes only the disposable rehearsal copy and restarts nothing. The
original appdata and payload remain untouched. Never initialize the production
appdata with a newer qBittorrent version before its copy has passed recovery.

qBittorrent documents `--relative-fastresume` for portable profile migrations,
but this release does not rewrite resume records automatically. Absolute stored
paths require operator review because an incorrect rewrite can reset progress or
make payloads appear missing.
