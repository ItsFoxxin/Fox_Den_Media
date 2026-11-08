# Quick Start — Isolated Local Test

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

**Audience:** Evaluators on a disposable Linux host or separate test deployment. This is **not** a production installation or NAS migration procedure.

## Prerequisites

Docker Engine, Docker Compose v2, Python 3 and enough free storage for a new, isolated test state. See [[System Requirements|System-Requirements]].

## Music-only example

~~~bash
git clone https://github.com/ItsFoxxin/Fox_Den_Media.git
cd Fox_Den_Media
git switch dev                      # integration code, NOT a stable release
git rev-parse HEAD                  # record tested SHA
python -m venv .venv
. .venv/bin/activate
python -m pip install -e apps/portal
cp deploy/examples/music.env.example .env
~~~

Edit the *untracked* `.env`: choose **new test-only absolute directories**, safe numeric UID/GID, an origin appropriate to the local test, and a genuine `MUSICBRAINZ_CONTACT`. For loopback HTTP only, keep `FOXDEN_BIND_IP=127.0.0.1` and `PORTAL_COOKIE_SECURE=false`. Do **not** make this HTTP example Internet-facing.

~~~bash
python scripts/foxden.py init --env .env --create-paths
python scripts/foxden.py validate music --env .env
python scripts/foxden.py deploy music --env .env
~~~

The last line is a **dry run**. `init` generates some secrets and empty optional placeholders; verify the actual container user can read required files. `validate` updates private generated Nginx configuration; it does not start services.

Only after reviewing paths, secrets, mounts and the dry-run on an **authorized isolated test host**:

~~~bash
python scripts/foxden.py deploy music --env .env --execute
docker compose --env-file .env -f deploy/compose.yaml --profile music ps
~~~

Create the first local Portal administrator at `/setup` using the private, expiring `portal-bootstrap` secret. Never share it.

## Next steps

Read the full [deployment runbook](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/deployment.md), [configuration guide](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md) and [troubleshooting reference](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/troubleshooting.md). For an existing NAS, start with [side-by-side migration](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/side-by-side-migration.md) instead of pointing this stack at live state.