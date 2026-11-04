# Ugreen NAS inventory checklist

This is an operator-controlled, read-only checklist for the authorized inventory
phase. It does not grant permission to connect to the NAS, restart containers, or
copy production databases. Record secret names and locations, never secret values.

## Host and storage

- [ ] NAS model, OS version, Docker Engine and Compose versions.
- [ ] CPU architecture, total memory, timezone, and NTP status.
- [ ] `/dev/dri` entries and the numeric render/video group IDs, if GPU validation is desired.
- [ ] Filesystem type, total/free space for every state and media mount.
- [ ] UID/GID, mode and ownership expectations for bind mounts.

## Docker deployment

- [ ] Container names, images, versions and immutable image digests.
- [ ] Compose project/service names, restart policies and health states.
- [ ] Published ports, private networks, bind mounts, named volumes and device mappings.
- [ ] Reverse-proxy dependencies and public hostnames without credentials or tokens.

Run the sanitized collector only after reviewing its output destination:

```bash
python scripts/migration.py host-inventory \
  --env production-paths.env \
  --expected-mode full-managed \
  --output private-reports/nas-host-inventory.json
```

The command fails if required storage roles are absent. Use `--allow-partial`
only to capture an explicitly incomplete diagnostic report. The collector reads
Docker metadata and host capacity only. It omits container
environment values, health-check commands, label values, credentials, private
keys, tokens and application database contents.

## Application state locations

- [ ] Portal database, secret files, signing/encryption keys and configuration.
- [ ] Music database, import history, staging/download roots, library and configuration.
- [ ] Movies/TV database, state, download mappings, media roots and configuration.
- [ ] qBittorrent appdata, `BT_backup`, incomplete/completed roots, categories and save paths.
- [ ] Gluetun appdata and the locations of WireGuard/VPN and port-forwarding configuration.
- [ ] Jellyfin config, data/database, plugins, metadata, cache and media mounts.
- [ ] Browser profiles and any other stateful optional-module paths.

For each path, record whether it is read-only media, writable application state,
large payload data, or a secret location. Preserve existing container-side media
paths where Jellyfin or qBittorrent stores them in database state.

## Authentication and routing

- [ ] Authentik issuer and application/provider names; do not export client secrets.
- [ ] AD/LDAP provider and group-mapping configuration names.
- [ ] Caddy/Nginx route map, TLS ownership, WebSocket behavior and trusted proxy ranges.
- [ ] Local emergency administrator recovery procedure and required secret-file dependencies.
- [ ] Jellyfin authentication providers/plugins and their installed versions.

## Operator evidence required before rehearsal

- [ ] Inventory artifact reviewed for accidental secret disclosure.
- [ ] Exact source commit and proposed image digests recorded.
- [ ] Writer/quiescence plan approved for each SQLite-backed service.
- [ ] Backup and restore destinations confirmed not to overlap production paths.
- [ ] Rehearsal networks, ports and Compose project name confirmed isolated.
- [ ] Rollback start commands for the existing stack recorded and tested syntactically.

The first authorized NAS phase should collect this inventory only. Production
backup, copied-state rehearsal and cutover are separate approval gates.
