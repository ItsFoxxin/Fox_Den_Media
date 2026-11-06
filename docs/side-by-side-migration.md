# Side-by-side migration without touching production

The existing NAS may already run Jellyfin, qBittorrent and Gluetun. The new Fox Den Media stack must initially be a **separate, reversible experiment**. This is an operator procedure to **plan and rehearse**, not a live-migration instruction or authorization.

## 1. Inventory, without mutation

On the approved host, record project/container/image names, exact image digests, volumes, mounts, port binds, UID/GID, ACLs, filesystem types, free space, Caddy/Authentik/Jellyfin endpoints, qBittorrent resume paths and current VPN health. Use [NAS inventory checklist](nas-inventory-checklist.md) and [0.9 compatibility report](production-compatibility-0.9.md). The repository's sanitizing `scripts/migration.py host-inventory` requires `--env`, `--expected-mode` and `--output`; review its [runbook](production-migration-rehearsal.md). Keep resulting reports private.

Existing production version/configuration must be captured **before** comparing to any default in `deploy/compose.yaml`. Do not infer compatibility because an image boots on synthetic CI data.

## 2. Back up and prove recovery

Back up immutable copies of all application state (Portal, Music SQLite/WAL, Jellyfin config/plugins/database, qBittorrent `BT_backup`/resume data, Gluetun config, secrets), and separately protect large libraries and torrent payloads. Obtain an application-consistent snapshot or explicitly quiesce every writer before archive creation. The migration tool requires `--writers-stopped --execute` before taking its state archive; it **excludes** large media/torrent payloads.

Verify archive SHA-256 and file manifests with `scripts/migration.py verify`; rehearse restore and rollback into **empty, isolated** directories. Keep former images and the old Compose configuration. See [production rehearsal](production-migration-rehearsal.md) and [recovery](recovery.md).

## 3. Build a separate candidate

- Use a fresh checkout pinned to the reviewed `dev` commit and a dedicated test path, e.g. `/volume2/docker/foxden-media-rehearsal` if that path exists on the NAS.
- Use a distinct Compose project name, separate test ingress/qBittorrent host ports, private env/secrets, and copied/synthetic databases, config and download roots. The base Compose model declares `name: foxden-media`; set `COMPOSE_PROJECT_NAME=foxden-media-rehearsal` in the **private rehearsal** env file and verify the effective project name before launching. Do not use the production project name.
- Do not mount production databases, Jellyfin config, Music/Media config, or qBittorrent appdata **read-write into both stacks**. Even if the old service is momentarily idle, the correct rehearsal source is a copy or verified snapshot.
- Use synthetic torrent data and isolated client accounts. Reuse of read-only public media requires ownership and confidentiality review; prefer test media first.
- Keep candidate VPN endpoints deliberately unusable until separately authorized staging credentials are provided. Do not use the production tunnel, live trackers or active seeding to prove test behavior.

The [Ugreen rehearsal example](../deploy/examples/ugreen-rehearsal.env.example) is intentionally incomplete. `foxden.py validate` must reject placeholder values until the operator provides staging evidence. There is **no** one-command migration of an existing NAS.

For example, after setting `COMPOSE_PROJECT_NAME` in `.env`, inspect the effective name without exposing the rest of the expanded configuration:

```bash
docker compose --env-file .env -f deploy/compose.yaml --profile music config --format json | python -c 'import json,sys; print(json.load(sys.stdin)["name"])'
```

## 4. Rehearsal acceptance matrix

| Area | Minimum copied-state checks |
| --- | --- |
| Portal | Initial/admin and local recovery login, admin-only modules, OIDC only with approved test provider |
| Music | SQLite/worker compatibility, new test download, staging and import integrity, Jellyfin refresh if enabled |
| Movies/TV | qBittorrent API permissions, reviewed import/checksum, path mapping and overwrite refusal |
| Torrent/VPN | Config/resume consistency, DNS + HTTPS egress via VPN, no direct leak under controlled tunnel loss, qBittorrent recovery |
| Jellyfin | Existing-version/schema/plugin compatibility, actual user library/history/artwork, browser/TV/mobile playback, subtitles and seeking |
| NAS | Numeric ownership/ACLs, restart persistence, free space, no production port/config interference, N100 transcode if selected |
| Recovery | Full verified restore and prior-image restart using **isolated** paths; timed rollback rehearsal |

Document each result with timestamp, exact code/image SHA/digest, redacted evidence and any failure. Hosted CI can establish logic, not NAS integration.

## 5. Prepare a controlled cutover — separate approval

Only after the [release checklist](release-1.0-checklist.md) and machine-readable readiness report are complete: schedule maintenance, stop old writers, take/verify a final consistent backup, lock target versions/digests, switch exactly one writable state owner, validate direct services before proxy/DNS changes, and monitor. Follow [cutover runbook](migration-runbook.md) rather than improvising.

Any unexplained VPN leak, database/plugin incompatibility, lost seeding state, missing user/history data, broken native client, failed backup, or inability to restore means **NO GO**.

## 6. Roll back

Close new ingress to writes, stop new workers/services (qBittorrent before Gluetun), retain failure evidence, restore verified *pre-cutover* state/ownership and former image/config, then validate the old stack before returning traffic. Never delete the old deployment/repo prematurely and never start an older image against state upgraded by the candidate.

See [recovery](recovery.md), [Jellyfin migration](jellyfin-migration.md), and [Gluetun validation](gluetun-validation.md).
