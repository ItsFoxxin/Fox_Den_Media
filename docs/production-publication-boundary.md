# Fox Den Media — R6 production approval boundary (future design)

**DESIGN ONLY. Not implemented or authorized by R5.** This document defines a future independent production change-control interface. No NAS workflow, network route, secret, runner, deployment action or automation is added.

## Fundamental separation

- **R5 publishes software**: verified main SHA, immutable GitHub tag/Release, candidate GHCR image digests and security evidence.
- **R6 deploys to production, if separately approved later**: operator selects the exact R5 release lock and target, proves real NAS readiness, and obtains a **new independent manual GO**. A release-publication approval cannot be reused as deployment authorization.
- **Never auto-deploy:** GitHub pushes, PR merges, release tags, GitHub Release creation, GHCR events and successful CI checks are not deployment triggers. No tag or package event may start a job with NAS credentials.
- This repository currently has **no R6 production workflow**. Adding one requires a new, narrow, separately reviewed implementation PR and operator-approved infrastructure changes.

## Proposed future production request fields

| Field | Gate |
| --- | --- |
| Released Git tag and **full main SHA** | Resolve to immutable, attested R5 publication; reject moved/conflicting tag |
| **SHA-256 of verified final release lock** | Resolve release asset and validate integrity, image manifests/platforms and profiles |
| **Approved NAS target ID** | Pre-registered private target identifier, not an arbitrary host or SSH string from untrusted user input |
| Operator and rollback owner | Named, independently accountable approvers |
| Maintenance window | Explicit bounded time in the NAS local timezone; reject expired windows |
| Writer ownership and outage plan | Exclusive mutable-state ownership, coordinated stop of prior writers |
| Backup and isolated restore evidence | Fresh writer-quiesced archives/snapshots, SHA-256 manifests, empty-target restore proof and verified rollback |
| Real staging validation | Gluetun fail-closed / DNS HTTPS, qBittorrent resume+seeding, Authentik and local emergency login, Firefox/noVNC, Music/Media/Jellyfin/clients |
| Human **production** approval | New protected environment review bound to target, lock digest and window; never inherited from R5 |
| Post-cutover evidence | Separate operator sign-off for health, stabilization, identity, storage and client behavior |

## Future protected job architecture

1. **Read-only preflight:** fetch R5 Release and assets; cryptographically validate source, image digests, SBOM/provenance and lock hash; check source/version, known blockers, environment/target selection and approval request. No production credentials, network access or writer mutation.
2. **Independent human production gate:** proposed protected environment `production-nas` with specific trusted-ref policy and reviewers. Require separate owner authorization and maintenance window. Restrict environment secrets to the post-approval job. Verify actual supported GitHub environment protections **before enabling**; never assume an unconfigured environment is protected.
3. **Privileged operator execution (only if a later PR is approved):** use a private/pull-based controller or narrow private-network credentials. No public Docker socket, broad host SSH key, privileged PR runner or secrets at repository scope. Digest-pinned image pull, exclusive writer quiescence, final backup and validated staged state precede routing changes.
4. **Independent stabilization:** verify service routes and security, data integrity, qBittorrent tunnel isolation, playback clients and rollback readiness. On failure stop new writers, preserve evidence and execute the *approved* compatible restore/rollback; do not point older images at migrated databases.
5. **Immutable audit trail:** record owner approval, exact SHA and lock digest, window, backup hashes, command/step results, health metrics, operator and rollback evidence with secrets redacted.

## Non-negotiable negative tests for any future R6 PR

- No / rejected / expired production reviewer decision → **zero NAS access and zero state changes**.
- Tag, GitHub Release or GHCR package event → **no deployment job**.
- Missing/mismatched release-lock digest or wrong image architecture → reject.
- Wrong, unapproved or user-supplied arbitrary NAS target → reject before acquiring credentials.
- Stale/missing backup, failed isolated restore, simultaneous writers → fail closed.
- VPN kill-switch / DNS / managed qBittorrent leak or failed authentication → NO GO.
- Missing maintenance window/operator or expired change approval → refuse.
- Partial deployment, failed health or data migration → controlled stop and approved rollback without forced registry retagging.

## Decisions intentionally deferred

- Whether to use a private pull agent or a short-lived private-network executor.
- Specific required-reviewer configuration and availability for the repository's GitHub plan.
- NAS target registry, service-account identity, ACL, backup retention and rollback authority.
- State migration/cutover runbook for exact v1.0.0 release and approved images.

All remain **release/production implementation blockers**, not evidence that production is authorized today. [R5 publishing](release-publication-r5.md) can be merged and tested as infrastructure with this boundary unchanged.
