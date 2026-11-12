# Docker Installation

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

Fox Den Media uses Docker Compose v2 with a first-party deployment controller; the maintained manifest is [deploy/compose.yaml](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/deploy/compose.yaml).

1. Install Docker Engine and the Compose plugin for your Linux/NAS distribution; verify `docker version` and `docker compose version`.
2. Select a [[Deployment Mode|Deployment-Modes]]; copy its matching [environment example](https://github.com/ItsFoxxin/Fox_Den_Media/tree/dev/deploy/examples/).
3. Create private, **new** host directories and confirm container UID/GID ownership. Keep secrets in file mounts, not committed env files.
4. Use `scripts/foxden.py init`, then `validate`, review the dry-run, and only then run `deploy … --execute` on an authorized test host.
5. Inspect containers and logs; check Portal setup and module access, including negative permission tests.

**Do not** use legacy `deploy/legacy/` or old standalone Compose examples as the current monorepo installer. Do not run `down -v`, prune volumes or mount existing production writable databases into a test stack.

Use the tested command sequence on [[Quick Start|Quick-Start]], followed by [detailed installation/operations](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/deployment.md) and [Ugreen NAS notes](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/ugreen-nas.md).