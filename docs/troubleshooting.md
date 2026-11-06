# Troubleshooting

Use these checks on a **test or explicitly authorized** deployment. For a production NAS, record the current state and obtain the appropriate change approval before restarting, editing files or rotating credentials. Start with [deployment](deployment.md) and [configuration](configuration.md).

## A safe first pass

```bash
python scripts/foxden.py validate music --env .env
docker compose --env-file .env -f deploy/compose.yaml --profile music ps
docker compose --env-file .env -f deploy/compose.yaml --profile music logs --tail=100
```

Replace `music` with the actual mode and matching profiles. These commands assume `.env` already exists and dependencies are installed. `validate` writes the rendered runtime gateway file even though it does not start containers. Logs may expose URL tokens or paths; redact before sharing.

## Symptoms

| Symptom | Check | Safe next step |
| --- | --- | --- |
| `init` fails generating keys | Python environment and installed `apps/portal` package/dependencies | Recreate local virtual environment; preserve existing keys |
| `validate` rejects path | Absolute path, existence, access, no overlap, container UID/GID/ACLs | Correct **test** paths/ownership; do not chmod a live production tree broadly |
| Required secret missing/empty | Secret basename from validator, file `0600`, actual consumer UID | Populate only approved provider secret through secure editor; leave unrelated keys untouched |
| `PORTAL_MODULES_JSON` error | Exact selected `music`/`media` IDs in mode example | Copy correct example; validate JSON, not a comma-separated string |
| Login redirect loop | Public scheme/host, secure-cookie setting, reverse-proxy headers, OIDC redirect | Test local auth first; don't disable HTTPS in production |
| `/setup` refuses first admin | Bootstrap secret file, already-used flag and expiration | Follow Portal recovery design; never reset live SQLite to rerun setup |
| Music or Media unavailable/503 | Compose profile selected, container health, bind mount permission, Portal auth | Inspect scoped service logs without exposing backend ports |
| Download browser denied | Music mode and `--browser`, Portal administrator session | Check route and roles; don't bypass ingress |
| qBittorrent API fails | External `QBIT_URL` versus managed `http://gluetun:8080`, credentials, VPN health | Rehearse with copied client state; avoid restarting production Gluetun |
| Gluetun `unhealthy` | DNS/HTTPS versus ICMP probe, tunnel, host DNS, device, logs | See [Gluetun validation](gluetun-validation.md); never turn firewall off to make it healthy |
| Jellyfin shows wrong/missing media | Container library root, UID/GID/ACL, read-only mount, version/schema | Inspect copied state; never attach live config to two Jellyfin containers |
| No hardware transcoding | `/dev/dri`, video/render groups, override selected, actual FFmpeg log | [N100 hardware procedure](n100-hardware-validation.md); direct play is not proof |
| Restore fails | Archive manifest/checksum, empty target, writer shutdown | Stop the rehearsal, preserve evidence, consult [recovery](recovery.md) |

## Docker/Compose checks

The authoritative Compose file is `deploy/compose.yaml`, not legacy Compose under `deploy/legacy/` or Music's standalone files. Mode profile flags are **not optional** for targeted application services. `config --quiet` checks YAML resolution, not network access, host storage permissions or runtime secrets.

Run `docker compose version` to ensure Compose v2. The project name is declared as `foxden-media`; explicitly isolate the project identity for side-by-side rehearsal, not just ports. Confirm `PORTAL_CONFIG_PATH`, `FOXDEN_SECRETS_DIR` and other mounts point to the expected safe roots. Beware that a change to a named/host config directory can appear to fix startup while actually starting a blank application.

## When to stop

Stop the proposed change if you see any external qBittorrent route bypassing the VPN, unexpected mutable mounts, missing backups, a production port collision, loss of admin recovery, broken native Jellyfin clients or unknown database-version behavior. Do not attempt an ad-hoc production rollback; use [migration runbook](migration-runbook.md) and [recovery](recovery.md).

Read [security](security.md) for the intended control boundaries and [readiness](production-readiness.md) for unresolved operational checks.
