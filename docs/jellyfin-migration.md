# Existing Jellyfin migration and rollback

This is a runbook, not authorization to change the NAS. No production Jellyfin
state was inspected or migrated while preparing it.

## Read-only inventory

Record without changing the running service:

- exact Jellyfin server version and image tag/digest;
- container name, Compose project, restart policy, networks, published ports,
  environment, UID/GID, supplemental groups, and device mappings;
- host paths mounted at `/config`, `/cache`, and every media path;
- the exact in-container path used by every library;
- config/database sizes, filesystem type, ownership, permissions, and free space;
- installed plugins and their versions;
- reverse proxy hostname, TLS termination, Known Proxies, and WebSocket behavior;
- current users, administrators, library grants, playback restrictions, and
  authentication provider for each account;
- active sessions, scheduled tasks, and hardware-transcoding configuration.

Do not print API keys, tokens, passwords, or full environment dumps into tickets.

## Backup gate

1. Confirm a tested backup destination with enough free space.
2. Record the current image digest and deployment files.
3. Stop the old Jellyfin container for a consistent database/config snapshot.
4. Copy config and cache with ownership, permissions, timestamps, symlinks, and
   extended attributes preserved where supported.
5. Produce a file inventory and checksums for the backup.
6. Restart the old service and confirm it is healthy.
7. Restore the backup into a new, isolated test directory and verify checksums.

Jellyfin 12 includes database migrations that can prevent a downgrade. Never use
an upgraded test copy as a rollback source; retain the untouched pre-upgrade
backup and old image. See Jellyfin's official [migration guidance](https://jellyfin.org/docs/general/administration/migrate/).

## Isolated rehearsal

1. Use the same Jellyfin version as production first. Do not combine migration
   and a major-version upgrade in one untested step.
2. Point `JELLYFIN_CONFIG_PATH` and `JELLYFIN_CACHE_PATH` at the restored copy.
3. Mount media read-only using the exact old in-container paths.
4. Use a temporary hostname and do not advertise it to normal users.
5. Ensure the old and rehearsal containers never share config/cache paths.
6. Validate users, libraries, watch history, progress, metadata, artwork,
   collections, plugins, playback preferences, direct play, subtitles, seeking,
   transcode playback, WebSockets, and native clients.
7. Apply the Midnight CSS import only after functional validation.
8. Record results and obtain explicit cutover approval.

## Cutover

1. Announce downtime and stop writes/scheduled scans.
2. Stop old Jellyfin and confirm no process has the config/database open.
3. Take and verify a final consistent backup.
4. Confirm the new profile uses the approved image and exact media mount targets.
5. Start only the new Jellyfin service, then validate health locally.
6. Switch Caddy/DNS to the dedicated hostname and validate WebSockets and client IPs.
7. Test one administrator, one general user, one browser client, and one native client.
8. Test direct play and a controlled hardware transcode.
9. Keep the old container stopped but intact through the observation window.

## Machine-readable go/no-go report

The migration tool cannot infer human validation. Copy the schema-2
`deploy/examples/migration-evidence.example.json` and replace each template
record with timestamped, checksummed evidence for the exact release commit:

```bash
python scripts/migration.py readiness --env production.env --mode jellyfin \
  --source-version 0.8.0 --source-commit EXACT_APPROVED_SHA \
  --evidence migration-evidence.json --output readiness.json \
  --human-output readiness.md
```

The decision remains `BLOCKED` when configuration or paths fail, evidence is
missing/failed, the source commit or environment is wrong, or operator approval
is absent. A `CUTOVER_READY` report records reviewed evidence; it does not stop
containers, alter routing, or independently authorize deployment.

## Rollback

1. Stop the new service immediately; do not run both writers.
2. Restore proxy/DNS routing to the old endpoint.
3. If the old config was never modified, restart the old pinned image.
4. If it was modified or upgraded, restore the pre-cutover backup before starting
   the old image.
5. Validate users, libraries, playback progress, and a representative stream.
6. Preserve new logs and the failed test copy for diagnosis; do not overwrite the
   last known-good backup.
