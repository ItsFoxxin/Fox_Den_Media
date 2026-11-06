# Fox Den Media 1.0.0 release acceptance checklist

**Status: NOT RELEASED / PRODUCTION CUTOVER BLOCKED.** This is an open acceptance checklist, not authorization to tag, deploy, promote, delete branches or modify the NAS.

## Repository and code freeze

- [ ] Record exact reviewed `dev` head, source/version/changelog alignment and green required GitHub checks (including CodeQL and **Monorepo strict gate**).
- [ ] Verify protected `main` and `dev`, the intended `dev` → `main` promotion, commit ancestry and imported history. Do not rewrite provenance.
- [ ] Freeze Compose profiles, images/digests, environment schema, names, ports, mounts, UIDs/GIDs and dependencies.
- [ ] Review all security findings, dependencies, image provenance and remaining non-root/browser risks.
- [ ] Back up repository bundles and document supported rollback refs.

The earlier stacked PR/rename steps are retained for provenance in [historical migration checklist](github-migration-checklist.md); they are **not** pending release instructions.

## Copied-state and NAS acceptance

- [ ] Complete authorized read-only NAS inventory and review all discovered mutable paths and external systems.
- [ ] Verify every application writer's consistent backup, external large-data snapshot, SHA-256 manifests, and an empty-target restore.
- [ ] Rehearse Portal local login, OIDC/group mapping, administrator module identity, Music/Media databases, reviewed imports, permission boundaries, and exception/rollback paths.
- [ ] Test actual qBittorrent resume pairs and payload path mapping, live *staging* VPN DNS/HTTPS/kill-switch failure, port forwarding and no independent downloader egress.
- [ ] Confirm Jellyfin version/schema/plugins, all user/history/library/streaming interactions, browser/TV/mobile clients and N100 hardware if enabled.
- [ ] Confirm reverse-proxy HTTPS headers, WebSocket behavior, cookies, directory ownership/ACLs, device permissions and outage behavior.
- [ ] Produce a readiness report tied to an exact source SHA with no missing evidence gates; retain time-stamped, redacted proof.

## Production change approval

- [ ] Obtain an explicit maintenance window, owner approval, operator runbook and rollback owner.
- [ ] Stop prior writers and prove exclusive mutable-state ownership before the **final** backup.
- [ ] Verify pre-cutover archive and data snapshots; keep prior images/config/state recoverable.
- [ ] Cut over one route/state boundary at a time and validate auth, modules, VPN, torrent seeding, media clients and storage.
- [ ] Complete stabilization observation and a successful restoration rehearsal.
- [ ] Only then approve a `dev` → `main` promotion and consider the `1.0.0` tag/release.

Failing any critical condition means **NO GO**. Do not silently mark a checkbox complete because a fixture/CI job succeeded. See [production readiness](production-readiness.md), [compatibility report](production-compatibility-0.9.md), [migration](side-by-side-migration.md), [cutover](migration-runbook.md), and [recovery](recovery.md).
