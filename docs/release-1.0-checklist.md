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
- [ ] **Before source promotion:** Complete approved copied-state NAS inventory, writer-quiesced backup, isolated empty-target restore rehearsals, real staging VPN fail-closed, authentication, browser, Jellyfin and client checks; disposition release blockers, record version, reviewed `dev` SHA and Compose/rollback readiness, and sign the source-bound readiness report. **Do not require final GHCR 1.0 candidate image digests, SBOMs or finalized release lock here; these are generated only after source promotion.**
- [ ] **After independent source-promotion approval:** Review and merge the application source into `main` with required CI/CodeQL, verify its exact resulting SHA, and repeat affected staging acceptance if the merged content materially differs. Build commit-identified GHCR candidates from that SHA, capture immutable digests, verify shared Trivy/SBOM/provenance/vulnerability results and no-rebuild integration, finalize the release lock and rollback artifact identities, and obtain a **separate release-publication approval** before any `v1.0.0` tag, version image tags or GitHub Release.
- [ ] **Before NAS production cutover:** Obtain a **new independent manual production GO** bound to exact validated release-lock digest, NAS target, operator and maintenance window. Reconfirm exclusive writers, final verified backups/snapshots, restore and rollback evidence. Neither source promotion nor image/Release publication grants NAS access or deployment permission.
- [ ] **After authorized cutover:** Observe production stabilization, authentication, Music/Media, Jellyfin, browser/clients, torrents/VPN and state integrity; complete rollback/restoration assurance. If any critical verification fails, stop writers and follow the approved rollback before marking production accepted.

Failing any critical condition means **NO GO**. Do not silently mark a checkbox complete because a fixture/CI job succeeded. See [production readiness](production-readiness.md), [compatibility report](production-compatibility-0.9.md), [migration](side-by-side-migration.md), [cutover](migration-runbook.md), and [recovery](recovery.md).
