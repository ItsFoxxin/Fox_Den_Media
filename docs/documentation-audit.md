# Documentation modernization audit

Scope: `dev` initial inventory `eab8fc9`, updated against `09e673d` (additional Music file-permission hardening), source version **0.9.1**. This report accompanies the documentation-only modernization PR. The repository initially contained **50 Markdown files under `docs/`** plus component docs, root README/changelog/next steps and historical plans. The deployment CLI, Compose, examples, tests and workflows—not old prose—were used as the operational source of truth.

## Inventory and disposition

| Surface | Before | Disposition |
| --- | --- | --- |
| Root `README.md` | Short status/mode description, limited onboarding | Rewritten for features, modes, requirements, safe quick start, auth, VPN, storage, lifecycle and roadmap |
| `docs/deployment.md` | Profile map and brief install | Replaced with CLI, dependencies, dry-run, health, first admin, build/pull, update/backup/rollback steps |
| `docs/architecture.md` | Obsolete gateway path/ports, obsolete seven-service assertion, old staging names | Corrected from `deploy/compose.yaml` and ingress template |
| `docs/ci.md` | Former `master` and `CI gate` language, mismatched workflow schedule/checks | Rewritten against current workflows and **Monorepo strict gate** |
| NAS installation | Read-only inventory, hardware and rehearsal runbooks only | Added `ugreen-nas.md` covering scoped CLI and GUI verification |
| Configuration/secrets | Distributed between Compose examples and topic guides | Added `configuration.md`; examples remain authoritative |
| Security | Strong historical 0.9.1 review, no unified operator summary | Added `security.md` with verified controls, gaps and operational rules |
| `docs/torrent-vpn.md` | Referred to missing legacy Compose files, direct passwords and automatic VPN startup | Rewritten for managed profile, file secrets, current path names and fail-closed tests |
| Migration | Comprehensive specialized cutover/restore docs but no new-user safe path | Added `side-by-side-migration.md` and linked existing runbooks |
| Navigation and support | README long cross-links but no docs hub | Added `docs/README.md` and `troubleshooting.md` |
| `next-steps.md` and release checklist | Historical branch/rename and old token/auth assumptions | Corrected current work queue and 1.0.0 gate, preserving provenance |
| `docs/github-migration-checklist.md` | Valid historical instructions presented as if still active | Added historical-only notice; preserved original numbered migration sequence |
| `docs/denkit-v0.1.md`, `docs/MEDIA_BRANDING_SPEC.md` | Current token/spec docs, proposed future placement | Retained with implementation-deferred boundary |
| `docs/ROADMAP_TO_3.0.0.md`, `docs/jellyfin.md` | Old canonical-repo status; Jellyfin health-check assumption | Added current-source status and explicit Jellyfin readiness caveat |
| Phase 0/1 notes, ADRs, import map, component version notes | Decision and migration chronology | Retained, indexed as historical rather than rewritten retroactively |
| `apps/music/README.md` | Legacy standalone deployment/CI directions and four broken backend-doc links | Marked historical; corrected all four relative targets without rewriting component history |
| Music CodeQL file-permission report added on latest `dev` | New `docs/security/media-file-permissions.md` | Linked from index/security; open alert #13 remains subject to NAS ACL verification |
| `deploy/compose.yaml`, `deploy/examples/`, `scripts/`, `.github/workflows/` | Operational code/config | **Inspected, not edited** |

## Critical corrections

1. The current gateway is Nginx **ingress :8080** routing to independent **Portal :8020**, Music :8000, Media :8010 and optionally Firefox :5800/Jellyfin :8096. The older architecture document conflated it with a prior gateway and misdescribed mounts.
2. `main` is default/stable and `dev` is integration; no new `master` branch or repository rename is pending as a task here.
3. Five CLI modes and optional profile flags are implemented; Compose validation and deployment *must* match the selected mode.
4. The current GitHub aggregate job is **Monorepo strict gate** and CodeQL is a separate workflow. Both Python 3.12 and 3.13 are used for Music regressions.
5. `init` may leave optional provider secret files **empty**; `validate` generates a runtime gateway config; `deploy` is dry-run without `--execute`.
6. Managed qBittorrent must remain in Gluetun's namespace; real VPN, NAS and copied-state Jellyfin validation remain outstanding despite passing fixtures.
7. Version **0.9.1** is the source milestone, not an independently verified public release or a production approval.
8. `scripts/check_compose.py` is an older helper that still expects the prior `gateway`/`web` service model; it is **not** called by the current monorepo workflow. Do not use it as a deployment validator; the current checks use `docker compose config --quiet` and platform tests. This task does not rewrite the historical helper.

## Validation evidence and limits

The PR should contain only documentation changes. Review `git diff --check`, relative Markdown references, example path/service/profile names, CLI help, version/release checks, and Compose syntax rendering. These prove documentation consistency, **not** production safety. Live Ugreen GUI controls, application startup, VPN credentials/egress and real Jellyfin clients cannot be validated from this source-only audit.

## Owner confirmation still required

- Exact Ugreen model, UGOS firmware version and supported Docker GUI features for `--env-file`, profiles, builds and multi-Compose override.
- Exact rehearsal filesystem roots, UID/GID/ACL mappings, chosen spare port(s), backup target, storage headroom and unique project identity.
- Real external service addresses (if using external qBittorrent/Jellyfin/OIDC), TLS hostname/proxy policy and initial administrator recovery process.
- Approved image digests and compatibility pinning for existing Jellyfin, qBittorrent and Gluetun before any copied-state rehearsal.
- Authorized test VPN endpoint/credentials, kill-switch evidence, qBittorrent resume/seeding acceptance and whether port forwarding is in scope.
- Real Jellyfin plugin/provider/client behavior, library paths, N100 group mappings and hardware transcode evidence.
- Signed-off restoration rehearsal, maintenance window, final backup and explicit production cutover decision.

**Nothing in this documentation task changes production services, GitHub settings, application versions, executable scripts, Docker Compose configuration or historical Git ancestry.**
