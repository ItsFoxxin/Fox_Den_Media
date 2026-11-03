# Fox Den Media 0.8.0 production migration rehearsal

This procedure prepares evidence; it does not authorize access to or changes on
the NAS. Run production commands only during a separately approved inventory or
maintenance window.

## Safety model

- Inventory commands are read-only and deliberately omit environment secrets,
  health-check commands, reverse-proxy label values, tokens, and VPN keys.
- A backup cannot run until the operator confirms every writer is stopped.
- Archives contain an embedded and external per-file SHA-256 manifest plus an
  archive checksum. Verification reads every archived file.
- Restore and rollback targets must be empty. Production paths are never
  overwritten by rehearsal commands.
- Prepared rehearsal environments use copied state, a unique Compose project,
  synthetic payload roots, local-only URLs, and unusable VPN placeholders.
- CI evidence can never satisfy NAS inventory, real-client, final-backup, or
  operator-approval gates.

## 1. Separately authorized read-only inventory

On the Docker host, copy the code and a private environment file but do not start
or stop anything:

```bash
python scripts/migration.py host-inventory \
  --env production.env \
  --output private-reports/host-inventory.json
python scripts/migration.py hardware-inventory \
  --output private-reports/n100-hardware.json
```

The host report records image tags/digests, Compose project/service, ports,
networks, bind mounts and volumes, UID/GID, capacity/free space, restart policy,
health status/configuration, proxy-label names, and device maps. Treat the report
as private because host paths and topology are operationally sensitive.

Before approval, the operator must also record:

- Ugreen model/OS, Docker Engine and Compose versions;
- actual Compose files/project names and reverse-proxy hostnames;
- filesystem type, ownership and ACL behavior for every bind mount;
- current Jellyfin version, image digest, plugins/providers, container media
  paths, users, clients, and `/dev/dri` mapping;
- qBittorrent version, categories/tags, torrent count, save/incomplete paths,
  seeding state and Gluetun namespace/routing;
- free space at the backup target and on every source filesystem.

Never paste `.env`, container environment output, Authentik secrets, qBittorrent
credentials, Jellyfin tokens, or WireGuard private keys into tickets or logs.

## 2. Consistent backup

SQLite databases must not be copied while their writers are active. Stop Portal,
Music web/worker, Movies/TV and Jellyfin before copying their state. Stop
qBittorrent before copying its appdata/BT_backup, and stop Gluetun only after
qBittorrent. Confirm no second container uses the same writable path.

First review the plan:

```bash
python scripts/migration.py backup --env production.env --destination /backup/foxden
```

Only after writer shutdown is independently confirmed:

```bash
python scripts/migration.py backup \
  --env production.env \
  --destination /backup/foxden \
  --source-commit EXACT_APPROVED_SHA \
  --writers-stopped --execute
python scripts/migration.py verify /backup/foxden/foxden-state-TIMESTAMP.tar.gz
```

The small-state archive covers Fox Den secrets, Portal, Music, Movies/TV,
qBittorrent, Gluetun and Jellyfin configuration/cache roots configured in the
environment. Music/video libraries and torrent payloads remain inventory-only;
protect them with host storage snapshots or existing backups instead of copying
terabytes through this archive. Preserve internal container media paths.

## 3. Isolated restore and rehearsal layout

Use copied state on a different empty root:

```bash
python scripts/migration.py restore-rehearsal \
  /backup/foxden/foxden-state-TIMESTAMP.tar.gz \
  --destination /rehearsal/restore \
  --report /rehearsal/reports/restore.json --execute

python scripts/migration.py prepare-rehearsal \
  /backup/foxden/foxden-state-TIMESTAMP.tar.gz \
  --env production.env \
  --destination /rehearsal/stack \
  --output-env /rehearsal/private/rehearsal.env \
  --report /rehearsal/reports/layout.json --execute
```

Review `rehearsal.env`. It is intentionally not network-ready. Supply only
separately approved staging qBittorrent/VPN/OIDC values. Never connect CI or a
synthetic torrent fixture to production trackers, Authentik, or VPN credentials.

Validate the selected mode before starting containers:

```bash
python scripts/foxden.py validate full-managed \
  --env /rehearsal/private/rehearsal.env --jellyfin
```

Validation must initially fail on the deliberate network placeholders. That is
the expected fail-closed behavior.

## 4. Rehearsal acceptance matrix

| Area | Fixture/isolated checks | Operational checks still required |
|---|---|---|
| Portal | schema migration, local login, roles, Ed25519 assertions, encrypted token restart | real Authentik OIDC and emergency-admin recovery |
| Music | DB startup, worker, single song, album completeness, duplicates, tagging | real library permissions and Jellyfin refresh |
| Movies/TV | request/import state, path mapping, duplicate controls | staging qBittorrent connectivity and final media ownership |
| qBittorrent/Gluetun | restored config shape, synthetic resume data, shared namespace, kill-switch fixture | real torrent counts, seeding continuity, DNS/egress and port forwarding |
| Jellyfin | copied config startup, path compatibility, user-scoped API, search/artwork/handoff | users/history/plugins, browser/TV/mobile playback, subtitles and seeking |
| Intel N100 | device/group discovery and synthetic transcode procedure | observed QSV/VA-API transcode with CPU/GPU evidence |

Mocks and synthetic files prove control logic only. They do not prove real
accounts, media, VPN connectivity, seeding, hardware transcoding, or clients.

## 5. Readiness evidence

Copy `deploy/examples/migration-evidence.example.json`. Every record requires a
timestamp, environment, exact version/commit, artifact identifier, result,
checksums, approval state and failure details. Generate both reports:

```bash
python scripts/migration.py readiness \
  --env production.env --mode full-managed \
  --source-version 0.8.0 --source-commit EXACT_APPROVED_SHA \
  --evidence migration-evidence.json \
  --output private-reports/readiness.json \
  --human-output private-reports/readiness.md
```

The only successful decision is `CUTOVER_READY`. Missing records, wrong source
commit, fixture evidence where NAS evidence is required, failures, or missing
human approval produce `BLOCKED`.

## 6. Rollback rehearsal

Restore the immutable pre-migration archive to another empty root:

```bash
python scripts/migration.py rollback-rehearsal \
  /backup/foxden/foxden-state-TIMESTAMP.tar.gz \
  --destination /rehearsal/rollback \
  --report /rehearsal/reports/rollback.json --execute
```

Start prior application versions only against the restored pre-migration copy.
Never point an older version at a database already changed by a newer version.
