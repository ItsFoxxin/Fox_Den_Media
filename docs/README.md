# Fox Den Media documentation

This index is the maintained entry point for **0.9.1**, an isolated-deployment and copied-state rehearsal candidate. **Production cutover remains blocked** pending the [readiness assessment](production-readiness.md).

## Start and operate

| Need | Guide |
| --- | --- |
| Get started, choose a mode, install, update, view logs | [Deployment](deployment.md) |
| Environment variables, persistent mounts, secrets | [Configuration](configuration.md) |
| Ugreen UGOS Docker project or CLI | [Ugreen NAS](ugreen-nas.md) |
| Keep production alongside a test stack | [Side-by-side migration](side-by-side-migration.md) |
| Diagnose startup, login, media and VPN issues | [Troubleshooting](troubleshooting.md) |
| Restore previous service state | [Recovery and rollback](recovery.md) |

## Architecture and security

- [Runtime architecture](architecture.md), [permissions and role boundaries](permissions.md), [security controls and gaps](security.md)
- [Bundled qBittorrent/Gluetun](torrent-vpn.md), [Gluetun validation](gluetun-validation.md), [qBittorrent recovery](qbittorrent-recovery.md)
- [Music file permissions / CodeQL alerts #11–15](security/media-file-permissions.md)
- [Jellyfin architecture](jellyfin.md), [Jellyfin copied-state migration](jellyfin-migration.md), [Authentik/AD/Jellyfin identity](authentik-jellyfin-auth.md)
- [Movie/TV request lifecycle](requests.md), [Watch & Listen](watch-listen.md), [versioned contracts](../contracts/v1/README.md)
- [Architecture decision records](adr/0002-modular-monorepo-and-portal.md) (with [superseded ADR 0001](adr/0001-versioned-modular-architecture.md)), [ingress ADR](adr/0003-nginx-ingress-and-independent-portal.md), [Jellyfin ADR](adr/0004-optional-jellyfin-native-client-boundary.md)

## Validation, development and releases

- [CI and development workflow](ci.md), [validation evidence](validation.md), [documentation audit](documentation-audit.md)
- [Production-readiness decision](production-readiness.md), [0.9.0 compatibility report](production-compatibility-0.9.md), [0.9.1 security review](security-0.9.1.md)
- [NAS inventory checklist](nas-inventory-checklist.md), [production rehearsal](production-migration-rehearsal.md), [cutover runbook](migration-runbook.md), [N100 hardware validation](n100-hardware-validation.md)
- [0.9.0 release-candidate checklist](release-0.9-checklist.md), [1.0.0 acceptance checklist](release-1.0-checklist.md)
- [Product roadmap](ROADMAP_TO_3.0.0.md), [mobile roadmap](mobile-media-roadmap.md), [remaining work](../next-steps.md)

## Design and historical records

- [Fox Den Midnight / DenKit](denkit-v0.1.md); [approved future branding spec](MEDIA_BRANDING_SPEC.md) (implementation deferred)
- [Consolidation/provenance](consolidation/README.md), [historical migration checklist](github-migration-checklist.md)
- [Phase 0 plans](phase-0/README.md), [Phase 1A planning](phase-1a/README.md), [Phase 1B integration notes](phase-1b/README.md)
- [Music component docs](../apps/music/README.md), [Music backend docs](../apps/music/backend/README.md), [Portal docs](../apps/portal/README.md)

Older phase documents, component version notes and ADRs are retained as evidence of *when* decisions were made. They are **not** current deployment instructions. Start with [deployment](deployment.md) and the actual CLI/Compose files for operational work.
