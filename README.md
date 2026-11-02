# Fox Den Media

Fox Den Media is a modular self-hosted media platform with one Portal, one
ingress boundary, and independently deployable Music and Movies/TV modules.
The repository preserves Fox Den Music as its canonical Git lineage and imports
the non-Music history from Media Downloader.

This branch is a production-readiness candidate. It does not deploy to a NAS or
modify existing application state.

Current platform milestone: **0.6.0**.

![Fox Den Midnight Portal with optional Jellyfin entry](docs/foxden-midnight-portal-desktop.png)

## Deployment modes

Copy the matching example from `deploy/examples`, replace every placeholder,
then validate before starting anything:

```bash
python scripts/foxden.py init --env .env
python scripts/foxden.py validate music --env .env
python scripts/foxden.py deploy music --env .env
```

Supported modes are `music`, `media`, `jellyfin`, `full-external`, and
`full-managed`. Add `--browser` for contained Firefox, `--jellyfin` to add the
official Jellyfin service to another mode, or `--jellyfin-hwaccel` only after
inventorying the host render device. `deploy`
prints the exact Compose command unless `--execute` is supplied.

See [deployment](docs/deployment.md), [Jellyfin architecture](docs/jellyfin.md),
[Jellyfin migration](docs/jellyfin-migration.md), [permissions](docs/permissions.md),
and the [production-readiness assessment](docs/production-readiness.md).

## Safety boundary

- Portal and ingress start independently of optional modules.
- Music and Movies/TV keep separate processes and databases.
- qBittorrent shares Gluetun's network namespace in managed mode.
- No application container receives the Docker socket.
- Jellyfin remains external until its optional profile passes a copied-state rehearsal.
- Production cutover requires a separate approval after backup and rollback
  evidence is reviewed.

The existing external Jellyfin integration is preserved: configure `JELLYFIN_URL` and
store its API key in `FOXDEN_SECRETS_DIR/jellyfin-api-key`. The Music worker
continues to request a library refresh after a successful import. The new managed
profile is disabled by default and must never share live config with the existing
instance. Native Jellyfin login remains independent for television and mobile clients.
