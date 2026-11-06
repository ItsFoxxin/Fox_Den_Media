# Ugreen NAS installation and copied-state rehearsal

Fox Den Media is designed to run on an appropriate Linux Ugreen NAS with Docker support. This guide documents **planning and isolated rehearsal**, not permission to modify the running NAS. Start with [deployment](deployment.md), [configuration](configuration.md), and [production readiness](production-readiness.md).

## Verify the NAS before installing

Record model, CPU architecture, UGOS version, available memory, filesystem/ACLs, snapshots, free capacity, Docker Engine/Compose versions, existing project/container names, ports and host-directory mounts. Confirm that the NAS supports building local images and that a backup target outside the tested project exists. On authorized SSH access:

```bash
docker version
docker compose version
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
docker compose ls
```

These commands inspect metadata, **not** secrets. Treat paths/ports as private operational information. Existing Jellyfin, Gluetun and qBittorrent may already occupy ports and writable state. Do not stop or replace them while preparing a test.

## Recommended: CLI workflow on the NAS

1. Use a dedicated project checkout and unique, non-production test directories. Example paths such as `/volume2/docker/foxden-media-rehearsal` in [the Ugreen template](../deploy/examples/ugreen-rehearsal.env.example) are *illustrative*, not automatically discovered paths.
2. Clone a reviewed commit on a storage location with sufficient build space, install the Python/Portal dependencies, and copy a mode-specific template. For rehearsal, the Ugreen template is designed for copied state and includes deliberate `CHANGE_ME` values.
3. Confirm numeric ownership/ACLs for each app and all secrets; imported files may need **copied-state** ownership mapping. Ensure separate library and torrent payload roots.
4. Run `python scripts/foxden.py init --env .env --create-paths`, then `validate MODE --env .env` (with the correct `--browser`/`--jellyfin` flags). **Expected failure** on unreplaced test VPN placeholders is a safety control.
5. Review `deploy MODE --env .env` (dry run), confirm port conflicts and image digests, then start only the approved *isolated* mode with `--execute`.
6. Monitor `docker compose --env-file .env -f deploy/compose.yaml --profile music ps` and scoped `logs --tail=100` for a Music rehearsal, changing profiles for other modes.

For a full managed **rehearsal**, do not substitute real production WireGuard keys into the provided placeholder environment. Obtain separate authorized test credentials and test egress/fail-closed behavior before allowing torrent activity. The historical Ugreen template pins a Jellyfin 10.11 image and Gluetun 3.41.1 digest for copied-state compatibility: these are **not** blanket recommendations to downgrade or upgrade an existing NAS.

## UGOS Docker GUI / Compose Project workflow

UGREEN's [Docker/Compose guide](https://ai.ugreen.com/blogs/knowledge/docker-docker-compose-ugreen-nas) documents a **Docker > Project > Create** workflow on supported UGOS versions. Check the installed firmware's menus; they can change.

1. Prepare the checked-out repository, mode-specific private env file, generated secrets, directories and rendered ingress config **via CLI first**. The project's Compose file has relative `build.context` references to `../apps/` and a bind mount to a runtime-generated Nginx configuration; uploading only the YAML to a GUI loses those dependencies.
2. In **Docker > Project > Create** where present, select a project directory that retains the full repository tree and configure a Compose file pointing at `deploy/compose.yaml`. Verify that this firmware's UI supports build contexts, environment-file interpolation, multiple profiles and the optional Jellyfin override. **If any are missing or cannot be confirmed, use the CLI**.
3. Keep the project name distinct from production projects; the Compose file declares `name: foxden-media`. A private rehearsal env file can set `COMPOSE_PROJECT_NAME=foxden-media-rehearsal` for CLI use, but the GUI's environment and project-name override support must be confirmed. Changing the GUI display label alone may **not** isolate containers. Verify the effective project name before starting.
4. Confirm loopback binds, unique ports, bind mounts and actual UID/GID permissions. Preview the resolved Compose config without publishing credentials. Create/launch only after test-mode configuration passes.
5. Use the GUI's container status/log views if exposed; verify health and then run CLI checks as needed. Do not assume a GUI button implements the custom `foxden.py` validation or backup gates.

**GUI limitations needing confirmation on the target NAS:** exact UGOS firmware UI controls; `--env-file` equivalent; `--profile` selection; multi-file Compose overrides; build-context resolution; and preserving the declared project name. A GUI that cannot express these must not be used to start the managed stack without a separately reviewed adaptation.

## Ports, storage and safety boundaries

| Exposure | Default | Rehearsal consideration |
| --- | --- | --- |
| Fox Den ingress | `127.0.0.1:8080` | `FOXDEN_BIND_IP`, `FOXDEN_PORT`: use unique test port such as `18080` |
| Managed qBittorrent Web UI | `127.0.0.1:8081` (via Gluetun) | `QBIT_BIND_IP`, `QBIT_WEB_PORT`: unique local-only port |
| Portal/Music/Movies/Firefox/Jellyfin | Docker-internal `expose` | Do **not** publish module ports directly |

If testing from another machine, an SSH/Tailscale tunnel or separately authenticated HTTPS reverse proxy is preferable to changing every service bind to `0.0.0.0`. Verify NAS firewall and VLAN access.

For existing production state, follow [side-by-side migration](side-by-side-migration.md) and [production rehearsal](production-migration-rehearsal.md). Never run two Jellyfin/Portal/SQLite/qBittorrent instances against the same mutable config tree. `JELLYFIN_MEDIA_PATH` is read-only to the candidate; the *config* and *cache* must be separate.

## Validate the rehearsal

- Confirm image architecture, health, local login, roles, media/torrent path mapping, and restart persistence with **copied or synthetic** state.
- Verify the new stack's ingress, Jellyfin login/client handoff, existing deployment isolation, backup verification and rollback.
- For managed mode, validate DNS/HTTPS VPN egress, default-drop/firewall, no client bypass, a controlled tunnel-loss test and recovery. CI's synthetic fixture is not equivalent to a real NAS VPN test.
- For N100 hardware transcoding, follow [hardware validation](n100-hardware-validation.md), inspect `/dev/dri` and groups, and prove an actual QSV/VA-API transcode.

Stop here until every outstanding operator/compatibility gate is reviewed. A safe test does **not** approve production cutover.
