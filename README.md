# Fox Den Media

Fox Den Media is a modular self-hosted media platform with one Portal, one
ingress boundary, and independently deployable Music and Movies/TV modules.
The repository preserves Fox Den Music as its canonical Git lineage and imports
the non-Music history from Media Downloader.

This branch is a production-readiness candidate. It does not deploy to a NAS or
modify existing application state.

Current platform milestone: **0.9.1** security hardening.

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
[Watch & Listen](docs/watch-listen.md), [identity integration](docs/authentik-jellyfin-auth.md),
[product roadmap](docs/ROADMAP_TO_3.0.0.md), [mobile roadmap](docs/mobile-media-roadmap.md), and the
[production-readiness assessment](docs/production-readiness.md).

For migration work, start with the [0.9.0 production compatibility report](docs/production-compatibility-0.9.md),
[0.9.0 release checklist](docs/release-0.9-checklist.md),
[0.9.1 security review](docs/security-0.9.1.md),
[0.8.0 production rehearsal](docs/production-migration-rehearsal.md),
[Ugreen NAS inventory checklist](docs/nas-inventory-checklist.md),
[qBittorrent recovery](docs/qbittorrent-recovery.md), [Gluetun validation](docs/gluetun-validation.md),
[cutover runbook](docs/migration-runbook.md), [N100 hardware validation](docs/n100-hardware-validation.md),
and [1.0.0 release checklist](docs/release-1.0-checklist.md).

## Watch & Listen

When an external or managed Jellyfin server is configured, `/watch/` provides
real user-scoped movie, television, artist, album, song, library, search,
recently-added, and continue-watching views. Users connect their own Jellyfin
account; passwords are never stored and user tokens are encrypted in Portal
storage. Acquisition and administration remain separate administrator-only
capabilities.

This release hands playback to Jellyfin Web rather than pretending embedded
streaming is complete. The versioned `/api/watch/v1` adapter is the foundation
for later browser playback and Android clients.

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
