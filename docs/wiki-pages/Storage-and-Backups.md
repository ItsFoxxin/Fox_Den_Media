# Storage and Backups

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Fox Den Media persists **separate state per component**: Portal, Music, Movies/TV, optional Firefox/Jellyfin/qBittorrent/Gluetun and media library directories.

## Design for recovery

- Assign distinct persistent paths, appropriate numeric owners, and read-only library mounts where applicable.
- Keep secrets under `FOXDEN_SECRETS_DIR` with restricted file and directory permissions. Include them in encrypted, controlled recovery backups.
- Back up application databases/configuration **consistently with writers quiesced**.
- Back up **large media and torrent payloads separately**: small-state archives do not cover all content.
- Verify archive/file hashes and rehearse recovery into an **empty isolated target**.
- Preserve the prior compatible application images/configuration and rollback procedure.

**Never** attach one writable application database/config path to an old and a new stack concurrently. Never post actual NAS paths or inventory reports to the public Wiki.

Read [storage map](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md), [backup and restore rehearsal](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/production-migration-rehearsal.md), [recovery procedure](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/recovery.md) and [copy-state migration](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/side-by-side-migration.md).