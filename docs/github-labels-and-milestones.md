# GitHub labels, milestones and issue/PR organization

This guide defines Fox Den Media's GitHub **Issue and pull-request metadata**, not Git tags or application versions. The canonical release-readiness register is [Issue #18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18), together with [the 1.0 checklist](release-1.0-checklist.md). A merged change is **not** proof of NAS/production acceptance.

## Label conventions

Apply **exactly one primary type** and **at most one priority** to each active Issue or PR. Component labels may be combined for genuinely cross-component work. Workflow labels describe remaining work, not GitHub's native draft/review/mergeable state. Never infer a P0 incident solely from the fact that work blocks a release.

### Primary type (one only)

| Label | Hex color | Apply when |
|---|---|---|
| type: bug | D73A4A | Confirmed defect or incorrect behavior |
| type: feature | 238636 | New functionality |
| type: enhancement | 2DA44E | Improvement to existing functionality |
| type: security | B60205 | Security defect or hardening |
| type: documentation | 6B7280 | Documentation-only change |
| type: maintenance | 8B949E | Dependencies, upkeep and cleanup |

Use **type: security** instead of simultaneously applying *type: security* and *type: bug* to a security defect. For a mixed PR, choose the primary reason for the work; split unrelated changes when possible.

### Components (multiple only when justified)

| Label | Hex color | Scope |
|---|---|---|
| area: portal | 0969DA | Portal interface, backend, accounts and sessions |
| area: music | 1F6FEB | Music requests, downloader, worker and processing |
| area: media | 1559B7 | Movies and TV application and media APIs |
| area: browser | 0E8A99 | Firefox, noVNC and embedded browser functionality |
| area: authentik | 087E8B | Authentik OIDC, LDAP and identity integration |
| area: jellyfin | 177E89 | Jellyfin integration, libraries, clients and playback |
| area: vpn | 0B7285 | Gluetun, qBittorrent, tunnel safety and network isolation |
| area: ingress | 2563EB | NGINX, reverse proxy, HTTPS and ingress routes |
| area: docker | 0086B3 | Compose, container builds and deployment configuration |
| area: ci-cd | 315CAA | GitHub Actions, CI validation and release automation |
| area: release | 395B94 | Release process, versioning and promotion approvals |

For example, a Firefox/noVNC request surfaced in Music may use **area: music** and **area: browser**. Portal-authenticated WebSocket relays may additionally require **area: portal** and **area: ingress**. Do not add every adjacent system label merely because an integration test touches it.

### Priority (at most one)

| Label | Hex color | Meaning |
|---|---|---|
| priority: p0 | B60205 | Critical active security, data-loss or production risk |
| priority: p1 | D93F0B | High-impact defect, important security or major functionality |
| priority: p2 | D4A017 | Normal planned development or maintenance priority |
| priority: p3 | E4C65E | Low-priority optional or future improvement |

Priority is an impact/urgency assessment, not an implementation status. A routine dependency update does not automatically merit P1 or P0; untriaged updates may have no priority label.

### Workflow and release

| Label | Hex color | Apply when |
|---|---|---|
| needs-triage | 8250DF | Diagnosis, reproduction or impact assessment required |
| needs-testing | 6F42C1 | Verification remains incomplete |
| blocked | 6B7280 | A documented external prerequisite prevents progress |
| release-blocker | B60205 | Must be resolved or formally dispositioned before release |
| release-testing | 9562E8 | Requires release-environment acceptance or runtime verification |
| breaking-change | D93F0B | Backward-incompatible behavior, API or configuration change |

**release-blocker** is an explicit go/no-go designation. **release-testing** identifies an acceptance activity; it may coexist with **needs-testing** and **release-blocker**. A green CI run or a merged PR removes neither NAS acceptance obligations nor release approvals. Remove testing labels only after the corresponding verified evidence is recorded. Reserve **blocked** for a specific unmet dependency recorded in the Issue; do not use it as a synonym for unfinished work.

Do not add **needs-review** or **ready-for-merge** labels initially; use GitHub's native PR state and required checks.

### Existing Dependabot ecosystem labels (retain)

| Label | Usage |
|---|---|
| dependencies | Dependency version/update work, including Dependabot PRs |
| docker | Dependabot Dockerfile/base-image ecosystem |
| python | Dependabot Python package ecosystem |
| github_actions | Dependabot GitHub Actions ecosystem |

These ecosystem labels are **not** component labels. In particular, **docker** means dependency ecosystem, while **area: docker** means container/Compose/deployment scope. Preserve the existing labels, colors, descriptions and automation. A routine Dependabot PR typically gets **type: maintenance**, its existing ecosystem label(s), and its true application component label. Do not automatically add **type: security**, **release-blocker**, a milestone, or a high priority without evidence. Dependabot updates remain reviewed; no auto-merge policy is introduced.

## Milestones (GitHub Issue/PR milestones, not Git version tags)

- **1.0.0 Release** — Mandatory security, copied-state NAS acceptance, restore/rollback and independent source-promotion, artifact-publication and production-cutover gates. Initially group #18, #23, #27, #37, #57 and #62. Keep #18 as the release blocker/acceptance register.
- **Post-1.0 Improvements** — Work intentionally deferred until after first stable release, initially #66 (controlled Python runtime upgrade).
- Do not create a vague Future Roadmap milestone until concrete roadmap Issues justify it.
- Assign the milestone primarily to the tracking Issue. A PR may share it when it is a direct delivery item, but merge alone must not complete the Issue's runtime gate.
- Newly created CI/security tracking Issues such as #70 and #71 require separate release-gate evaluation before adding a 1.0.0 milestone or declaring them blockers.

## Issue-to-PR lifecycle

1. Open an Issue describing one independently reproducible defect/root cause, affected source commit, impact and redacted evidence. The existing bug report template collects these details.
2. Apply a single type, the smallest meaningful set of components, and a grounded priority. Add **needs-triage** if reproduction/root cause is unknown.
3. Link the dedicated fix PR with a valid closing reference such as **Fixes #123**. Follow the repository's existing one-bug-per-patch policy, change logs and version-policy CI; this guide does not itself bump versions.
4. Once implementation is reviewed and the required checks pass, record its source SHA and automated evidence. If a real isolated NAS or release acceptance test remains, keep the tracking Issue open with **needs-testing** and **release-testing** (and **release-blocker** if required for 1.0.0).
5. Perform operational tests only in a separately approved disposable copied-state environment. Record evidence in #18 or the specific Issue. Merge to **dev** does not authorize NAS access, source promotion, GitHub Release publication or production cutover.
6. Clear **needs-triage**, **needs-testing**, **blocked** and **release-blocker** only when their specific conditions are demonstrably resolved or, for an acceptable release risk, explicitly dispositioned and documented with owner approval.

## Maintenance and automation

Repository label names, descriptions and exact hex colors are controlled by the approved taxonomy. Safely rename **bug** to **type: bug**, preserving its Issue/PR relationships; if both names already exist, migrate every association and verify the transfer before deleting the now-redundant old name. Never delete a useful label simply because it is unused.

For a reproducible initial installation, use the separate idempotent GitHub CLI bootstrap supplied with this organization task. It is **dry-run by default**; run **--apply** only after reviewing its report. It sets exact label metadata, preserves Dependabot ecosystem labels, creates only missing milestones and labels only explicitly scoped Issues/PRs. Re-running it should not create duplicates.

A file-based component labeler could be added later under a separate reviewed PR, mapping application directories to their component labels. Do not let automation assign severity, release-blocker, acceptance completion, or protected-branch approval. Preserve existing Monorepo strict gate, CodeQL and Dependency Review workflows.
