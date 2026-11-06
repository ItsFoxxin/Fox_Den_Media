# Installation and operations

This is the maintained deployment entry point for Fox Den Media **0.9.1**, a copied-state rehearsal candidate. **Do not substitute it for the production cutover approvals** in [readiness](production-readiness.md) and [migration](side-by-side-migration.md). The authoritative files are [deployment CLI](../scripts/foxden.py), [Compose](../deploy/compose.yaml) and [mode examples](../deploy/examples/).

## Prerequisites and version selection

1. Use a Linux/compatible NAS host with Docker Engine, Docker Compose **v2** (`docker compose version`), Docker permissions and free disk space for source builds and the chosen media roots.
2. Install Python 3 and the Portal project's Python dependencies in a virtual environment. CI uses Python **3.12**. Confirm `python -m pip install -e apps/portal` completes before `init`, which generates an Ed25519 keypair.
3. Plan UIDs/GIDs, writable config/staging and read-only shared data. Set up separate backups before creating a working deployment; **do not point this candidate at mutable existing-production state**.
4. Arrange HTTPS reverse proxying for any non-local access. Gluetun/WireGuard and Jellyfin hardware prerequisites depend on the mode.

```bash
git clone https://github.com/ItsFoxxin/Fox_Den_Media.git
cd Fox_Den_Media
git switch dev        # current integration code
git rev-parse HEAD    # record exact tested commit
docker compose version
python -m venv .venv
. .venv/bin/activate
python -m pip install -e apps/portal
```

Prefer a human-reviewed, immutable tag/commit for a future production release; repository `VERSION` alone is not a release. `main` is default/stable, `dev` integration.

## Mode selection

| CLI mode | Compose profiles | Example |
| --- | --- | --- |
| `music` | `music` | `deploy/examples/music.env.example` |
| `media` | `media` | `deploy/examples/media.env.example` |
| `jellyfin` | `jellyfin` | `deploy/examples/jellyfin.env.example` |
| `full-external` | `music`, `media` | `deploy/examples/full-external.env.example` |
| `full-managed` | `music`, `media`, `managed` | `deploy/examples/full-managed.env.example` |

Optional `--browser` requires Music; `--jellyfin` enables the official Jellyfin service in another mode; `--jellyfin-hwaccel` also loads `deploy/compose.jellyfin-hwaccel.yaml` after device/group inspection. `ingress` and `portal` have no profile and always start.

## Initialize a new, isolated installation

The following uses Music. Substitute the corresponding example, mode and flags when needed.

```bash
cp deploy/examples/music.env.example .env
# Edit .env: choose new absolute host directories, valid numeric IDs, public origin,
# mode-specific values and actual MusicBrainz contact. Do not copy existing live DBs.
python scripts/foxden.py init --env .env --create-paths
python scripts/foxden.py validate music --env .env
python scripts/foxden.py config music --env .env
python scripts/foxden.py deploy music --env .env
```

The first command makes private random Portal/identity/CSRF values, creates **empty** optional secret files, and leaves existing secrets intact. Keep the secret directory private (individual secret files mode `0600`; public verification key intentionally may be `0644`). Provide the additional real secret files appropriate to the selected mode and fix permissions for the actual numeric container identities. `validate` and `config` perform preflight **and write a rendered Nginx config** under `FOXDEN_RUNTIME_DIR`; do not treat them as byte-for-byte read-only operations.

Review the dry-run Compose command and configuration without publishing secret-bearing output. Then explicitly start:

```bash
python scripts/foxden.py deploy music --env .env --execute
docker compose --env-file .env -f deploy/compose.yaml --profile music ps
docker compose --env-file .env -f deploy/compose.yaml --profile music logs --tail=100
```

For the initial local administrator, visit `/setup` on the configured origin, use the private `portal-bootstrap` secret **locally**, and create a strong administrator login. The bootstrap secret expires according to Portal settings; keep it out of screenshots, shell history and messages. Use TLS before exposing login remotely. See [Portal OIDC setup](phase-1a/authentik-oidc-setup.md) if enabling Authentik.

For an explicit build/pull inspection before first startup, these are equivalent scoped examples (the CLI `deploy --execute` invokes Compose `up -d` and builds services as required):

```bash
docker compose --env-file .env -f deploy/compose.yaml --profile music config --quiet
docker compose --env-file .env -f deploy/compose.yaml --profile music build portal music music-worker
docker compose --env-file .env -f deploy/compose.yaml --profile music pull ingress
```

Do not blindly pull newer tag-based images during a migration rehearsal; record/review image digests. Docker's `config` without `--quiet` may expose substituted settings, so review privately.

## Health and day-two operations

- Use the scoped `ps` and `logs` commands above; append a service name (`portal`, `music`, `music-worker`, `media`, `gluetun`) to limit logs. Avoid sharing raw logs containing sensitive URLs.
- The main ingress health check probes `127.0.0.1:8080` inside the container. Portal and Music have their own health checks. Gluetun health does **not** itself prove VPN fail-closed behavior.
- Verify Portal login/logout, module permissions, test imports, persistent state across a **rehearsal** restart, and (where enabled) Jellyfin native clients. Use [troubleshooting](troubleshooting.md) and [validation](validation.md).
- With a local reverse proxy, retain `FOXDEN_BIND_IP=127.0.0.1`, set the public `https://` origin and `PORTAL_COOKIE_SECURE=true`. Avoid direct exposure of backends and qBittorrent.

## Updates and rollback

1. Record the running commit and image digests. Read the new `CHANGELOG.md`, migration notes and relevant CVEs; freeze target versions.
2. Capture *consistent* state backups with all writers quiesced and verify the archive **and** large media/torrent data backups. See [rehearsal](production-migration-rehearsal.md). Keep separate prior images/config.
3. Test upgrades against a **copied** environment first. Never mount the same writable SQLite/portal/Jellyfin/qBittorrent directories into concurrent stacks.
4. On the approved stack only, fetch the reviewed ref, validate/configure, review dry-run, then repeat `deploy MODE --env FILE --execute`. Confirm health, access, media, VPN isolation and clients before routing changes.
5. For an authorized shutdown, first review `python scripts/foxden.py stop MODE --env FILE`; `--execute` invokes Compose `down`. It does **not** delete volumes, but it does stop the selected project's services. Do not run against production as part of rehearsal.
6. On failed migration, stop **all new writers** and follow [recovery](recovery.md) with the *verified pre-upgrade* state; do not point an old image at a database already upgraded by the new image.

Never use `docker compose down -v`, volume prune, or unreviewed image upgrades as a rollback technique.

## Additional installation paths

- [Configuration, all variables and secret handling](configuration.md)
- [Ugreen NAS CLI and GUI limitations](ugreen-nas.md)
- [Isolated side-by-side migration and rollback](side-by-side-migration.md)
- [Jellyfin](jellyfin.md), [VPN isolation](torrent-vpn.md), [security](security.md)

Docker references: [Compose CLI](https://docs.docker.com/reference/cli/docker/compose/), [profiles](https://docs.docker.com/compose/how-tos/profiles/), [config --quiet](https://docs.docker.com/reference/cli/docker/compose/config/).
