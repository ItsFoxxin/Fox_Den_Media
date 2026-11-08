# Fox Den Media 1.0 — release and artifact publishing design

> **DESIGN ONLY — not an approved release or deployment.** No workflow, repository ruleset, tag, package, NAS state, or production environment is changed by this document. Release implementation requires separate maintainer approval and implementation PRs.

Repository: `ItsFoxxin/Fox_Den_Media`. Integration: `dev`. Stable: `main`. Intended milestone: `v1.0.0`. Snapshot refreshed: 2026-11-07, `dev` `bc1e0f1e2f127bb56409848223fbab0a0639cbf8` (VERSION `0.9.5`), `main` VERSION `0.9.1`. Reverify branch SHAs at every future gate.

## 1. Current state and ownership boundaries

- PRs #29 (Dependabot), #30 (CI architecture), #31 (Phase 1), and #32 (advisory Dependency Review) are merged into `dev`.
- PR #33 **merged**: Phase 2 Migration/Jellyfin dependency gating is implemented. Do not duplicate its graph changes or weaken the strict gate. PR #60 **merged**: Phase 3 removes duplicate feature/security push triggers, without changing required PR checks. PR #41 also merged, advancing current `dev` release metadata.
- PRs #34 and #35 are **closed, unmerged disposable probes**; never use their branch heads for a release.
- PR #36 **merged** into `main`: reviewed Dependabot and advisory Dependency Review configuration is present on the default branch. Dependabot is active, evidenced by its update PRs; routine PRs target `dev`, security PRs target `main` and require reviewed back-sync. PR #36 was **not** an application release promotion.
- Current `dev` `VERSION` is `0.9.5`, while `main` `VERSION` remains `0.9.1`. Re-evaluate exact commit ancestry and main-only security configuration before any eventual full application promotion; the development milestone is not a published release.
- Active workflows: `.github/workflows/monorepo.yml`, `codeql.yml`, `dependency-review.yml`. Phase 2 and 3 CI optimizations are merged, with pull-request validation preserved. None of these workflows publishes GHCR packages or deploys. PR #61 is an **independent, open** Phase 3 documentation closeout; it describes future Trivy/SBOM/security-hardening work that this design must reuse rather than duplicate.
- Existing `Monorepo strict gate` requires successful Validation, Music 3.12/3.13, Portal/Movies, pip-audit, Bandit, synthetic migration/rollback, isolated Jellyfin, and integrated container/synthetic VPN checks. Independent CodeQL Python and JavaScript/TypeScript are required. Dependency Review is `warn-only: true`, not a security release veto.
- Active branch rulesets require PRs, strict up-to-date required checks, review-thread resolution, and non-rewrite protections. They currently require **zero formal approving reviews**: a separate documented human release sign-off must not be presented as an already enforced GitHub requirement.
- `scripts/check_release.py` checks SemVer syntax, Compose Media version, README bold version, dated changelog header, and Media Dockerfile `VERSION` copy. Its `--base` stable-branch version-increase and `--reports` JUnit gates exist but are not invoked by active CI. `scripts/check_version_policy.py` runs on PRs, constrains one-step version increments and one-issue patch fixes. Root version policy is separate from a published release.
- Only the Firefox and qBittorrent Compose defaults are digest-pinned. Nginx, Jellyfin and Gluetun defaults are mutable tags. Portal, Music/worker and Media build locally and do not have GHCR publication. Three first-party Dockerfiles use `python:3.12.13-slim-bookworm` without a base-image digest. Record and resolve these before claiming immutable deployment.
- Existing docs `docs/release-1.0-checklist.md`, `docs/production-readiness.md`, `docs/recovery.md` hold mandatory NAS and rollback acceptance gates. These are **not** satisfied by synthetic CI.

## 2. Proposed lifecycle and separate approvals

| Stage | Trigger, identity and outcome | Gate |
| --- | --- | --- |
| A. Prepare | Reconfirm merged CI/security foundations, latest dev changes, open release blockers and copied-state readiness. Finish independent security/release blocker work and copied-state rehearsals. | Existing `dev` CI + CodeQL, explicit owner decisions. No release side effects. |
| B. Freeze candidate | Record exact `dev` SHA, close/accept blockers, inventory versions, generated release lock plan, rollback and redacted NAS evidence. Propose `1.0.0` metadata in a dedicated source PR against `dev` after readiness. | Operator signs release eligibility against issue #18 and `release-1.0-checklist.md`. Missing critical evidence = NO GO. |
| C. Promote source | Open a distinct `dev` → `main` PR (after main-only commits are reconciled and the full diff reviewed). Merge manually; do not reuse #36. | All existing `main` required statuses on the actual promotion head, no unresolved review threads, explicit maintainer merge approval, no force push. |
| D. Verify stable commit | Recheck the resulting **main SHA**, root version and release metadata, any release-specific report policy and all required post-merge CI/security statuses. Do not infer green from old `dev` runs. | Failure or unknown = stop; no tag. |
| E. Build candidate artifacts | From an explicitly approved immutable `main` SHA, a trusted, manually dispatched release-candidate workflow builds first-party images to GHCR with `sha-<full-commit>` candidate tags. | Only after main acceptance; scan/publish candidate stage does **not** tag `v1.0.0`, create GitHub Release or touch NAS. |
| F. Validate artifacts | Record index digests, provenance, SPDX SBOMs, vulnerability reports, pinned upstream image identities, compatibility smoke tests and a full release lock manifest. | No critical/high unaccepted findings; all artifacts match source SHA, required architectures and expected services. Signed, expiring exceptions require owner sign-off. |
| G. Publish release | **Separate human release-publish approval** binds `v1.0.0` to that verified SHA. Create protected annotated tag; attach existing tested image digests to `1.0.0` tags without rebuilding; verify tags still resolve to the identical digests; publish immutable GitHub Release with changelog, manifest, hashes, reports and release notes. | Rerun idempotent identity checks; no tag move, force retag or release rewrite on failure. Tag/Release creation cannot authorize NAS access. |
| H. NAS deployment | Future separately authorized **manual production** change, never a consequence of merge, tag, image push or GitHub Release. | Independent go/no-go, operator, maintenance window, exact digests, pre-cutover verified backup/restore, real VPN/auth/browser/client tests, rollback plan; see `production-nas` boundary below. |

**Policy reconciliation required:** Existing `docs/release-1.0-checklist.md` says to consider tagging only after successful production stabilization. Artifact-first reproducible deployment requires releasable images *before* deployment. Seek a separate owner decision to clarify: complete copied-state acceptance before release publication; use a separately approved publication event; deploy only after an **additional** production approval. Until this is accepted, follow the more restrictive existing checklist and do not create a tag.


### 2.1 Explicit conflict with the current acceptance policy — unresolved

The exact current [1.0 acceptance checklist](release-1.0-checklist.md) says:

> - [ ] Complete stabilization observation and a successful restoration rehearsal.
> - [ ] Only then approve a `dev` → `main` promotion and consider the `1.0.0` tag/release.

**Those statements are currently authoritative.** They require production stabilization **before** the application promotion/tag, whereas proposed stages C–H above promote, publish, and then perform a separately approved NAS production cutover. This is a **genuine release-order conflict**, not a documentation typo and not an implicitly approved exception. Even if this design PR were merged, its artifact-first lifecycle would remain **BLOCKED**. No image publication, application promotion, release tag or NAS deployment is authorized on the strength of this document.

### 2.2 Proposed precise amendment (separate PR and explicit owner approval required)

Recommend replacing **only the two quoted checkboxes** in the checklist's `Production change approval` section with these four, **in a future independent policy PR** — do **not** change that file in PR #38:

> - [ ] **Before source promotion or publication:** Complete approved copied-state and isolated NAS acceptance, genuine staging VPN fail-closed/auth/browser/Jellyfin checks, all blocker dispositions, writer-quiesced backup and empty-target restore rehearsal, digest-exact candidate and rollback evidence, and a signed release-readiness report. Missing critical acceptance evidence means NO GO.
> - [ ] **Source and publication decisions:** Separately approve a reviewed `dev` → `main` promotion after exact required CI/CodeQL checks, and then separately approve `v1.0.0` tag, GHCR image digests and GitHub Release publication from that immutable `main` SHA. These decisions **do not** authorize production deployment.
> - [ ] **Production decision:** Before any NAS cutover, obtain a **new, independent manual GO** bound to the exact release-lock digest, operator, destination environment, maintenance window, recent backup/restore proof, exclusive-writer plan and tested rollback. Never deploy automatically because an image was built, tagged, or released.
> - [ ] **Post-cutover closeout:** After authorized production cutover, observe stabilization; verify authentication/roles, Music/Media, Jellyfin, browser, torrent/VPN isolation, storage and state consistency; record success or stop writers and execute the approved rollback before declaring production acceptance complete.

This preserves every substantive readiness/restore/stabilization obligation while ordering **pre-production rehearsal → reviewed main promotion → immutable release publication → separately approved production cutover → stabilization**. It is a recommendation **only**, not an amended rule, accepted exception, checklist change, or permission to proceed. If rejected, R5/R6 remain blocked and any alternative sequence needs an equally explicit policy decision.

### 2.3 Independent approvals under the proposed policy

Three positive owner decisions must be distinct and audit-linked to exact immutable identities: **(1) application source promotion** (reviewed diff and exact main SHA), **(2) release publication** (tag/SHA plus all digests, SBOMs, provenance and risk disposition), and **(3) NAS production deployment** (release-lock digest, environment, operator and maintenance window). A fourth, **policy amendment approval**, is a prerequisite for using this order. Missing, rejected or expired approvals stop the respective action; approval is never inherited from earlier stages.


## 3. Proposed image/artifact inventory

Publish **three** first-party images, with Git repository linkage, OCI revision/version/source labels and explicitly checked linux/amd64 support:

| Runtime | Candidate GHCR image repository | Source build context |
| --- | --- | --- |
| Portal | `ghcr.io/itsfoxxin/fox-den-media-portal` | `apps/portal` |
| Music web + worker (same digest) | `ghcr.io/itsfoxxin/fox-den-media-music` | `apps/music/backend` |
| Movies/TV | `ghcr.io/itsfoxxin/fox-den-media-media` | repository root; `apps/media/Dockerfile` |

Proposed human-friendly tags are `:1.0.0` and `:sha-<40-character-source-SHA>`. Do not deploy `:latest` or assume tags are immutable. All deployments must select `name@sha256:<digest>`; capture manifest/index digest *and* platform-specific digest where useful. First-party image metadata must identify the exact **main commit**, not just the version string. Music worker must resolve to the **same digest** as Music web.

Non-FoxDen images (Nginx, Firefox, Jellyfin, Gluetun, qBittorrent) remain upstream images, **not silently copied into Fox Den GHCR**. Resolve/tag+digest for every enabled profile in the lock manifest, including those currently tag-only. Test upstream architecture, expected ports and mount/UID semantics. Report upstream provenance/SBOM gaps honestly rather than asserting FoxDen-built attestations cover third parties.

For each first-party image, publish/retain: OCI digest, OCI labels, GitHub provenance attestation, an SPDX JSON SBOM with its attestation, vulnerability report (scanner version/db timestamp), checksum material, GitHub Actions run ID, source SHA, build platform and policy decision. Prefer `docker/build-push-action` BuildKit `provenance: mode=max` and `sbom: true` plus a separately verifiable GitHub provenance/SBOM attestation for the image digest. Do not put secrets in build args or attestation-visible metadata. Confirm how the registry retains attached attestation references and how consumers verify them.

A machine-readable versioned `release-lock.json` and corresponding nonsecret `release-images.env` should include:
- release `1.0.0`, exact source commit, release workflow/run, Compose file hash and schema version;
- **all enabled** first-party and upstream image names+digests, platform and profile/mode selections;
- SBOM/attestation references, vulnerability decisions and scanner/database versions;
- release evidence/checksum references and rollback release lock/digest set;
- **no** secrets, tokens, real NAS mount paths or private environment values.

## 4. Release validation gates

### Automated — every release candidate must pass

1. `VERSION` is exactly `1.0.0`; the annotated tag is exactly `v1.0.0` and points at the chosen `main` SHA. No existing tag or release identity can be overwritten. No race with another promotion.
2. `scripts/check_release.py` plus a release-specific invocation of its `--base` and `--reports` options where appropriate; validate the one-step `0.9.x → 1.0.0` transition and exact dated changelog, README and Compose metadata. Validate `apps/media/VERSION` equals root `VERSION` (a current check gap). Enforce release notes and no duplicate version sections.
3. All currently required `Monorepo strict gate` + `CodeQL (python)` + `CodeQL (javascript-typescript)` + `CodeQL` on the actual `main` release commit. No stale, pending, skipped or cancelled results accepted. Do not change required check names as part of publishing.
4. Required application suites, coverage, JavaScript/Python syntax, actionlint, full-history secret scan, Compose profiles, pip-audit, Bandit, synthetic migration/restore/rollback, synthetic VPN fail-closed and Jellyfin all pass. Existing advisory Dependency Review remains visibility, not a substitute for artifact vulnerability scanning.
5. Build once for the intended source SHA, push candidate images to GHCR using **only** release-specific minimal `packages: write` and read/attestation/OIDC permissions on trusted refs. No image push on PR, arbitrary branch, `dev` merge, or Dependabot event. Never run privileged publisher logic via `pull_request_target`.
6. Scan **the published digest**, including OS and Python packages, with a versioned image scanner (e.g. Trivy or Grype). Fail on unresolved high/critical findings by default; require expiring, issue-linked, explicit maintainer acceptance for exceptions. Keep findings non-public where exploit detail is sensitive.
7. Generate, retain and verify digest-bound provenance and SPDX SBOMs. Verify source/ref/repo/workflow identity and digest, not just whether a signature exists. Review package/registry visibility, read access, and permissions before publishing.
8. Smoke pull by digest, verify image labels/architecture and run integration with exactly the three pushed images **without rebuilding**, plus pinned enabled upstream images. Check a generated Compose config resolves no unexpected image, profile, mutable tag or missing digest. Test failure on missing/swapped digest and invalid provenance.
9. Release publication is blocked until every manifest reference is resolvable and the tag-to-digest identity test passes for all first-party images. Preserve the verified candidate digests on retry; reject divergence.
10. Store image manifest, SBOMs, attestations, scan results, release metadata and checksums as GitHub Release assets (and optionally a mirrored NAS backup *after* separate authorization). CI artifact retention of 14–30 days is not adequate as the only durable release evidence.

### Human — separate decisions

- **Source merge**: maintainer reviews full promotion PR, branch divergence, changed security gates and complete CI.
- **Release publish**: maintainer reviews release checklist, open blockers, scan exceptions, migration evidence, actual image digests and rollback release. Record decision and links in release issue; publication is manual only.
- **NAS production**: a new, independent operator approval after release publication, tied to the release lock digest SHA and actual target environment/maintenance window. Approval for a GitHub Release is expressly **not** permission to deploy.


### Shared security workstream contract — mandatory reuse

[CI Phase 3 closeout PR #61](https://github.com/ItsFoxxin/Fox_Den_Media/pull/61) (still separate and open) identifies **Trivy image scanning, SBOM inputs, fixability/severity policy, expiring exceptions and digest-to-release linkage** as an independent successor security-hardening workstream. **Do not create a second Trivy installation, SBOM generator, severity policy or exception ledger in R4.** The security workstream owns a reusable, versioned scan/policy interface; release gates consume its exact outputs and record its policy version. Its separately approved implementation must be complete before a blocking image-release security gate is accepted.

Minimum shared interface:

- Input: immutable `name@sha256:<digest>` and actual platform manifest, source SHA and trusted build identity (for first-party images), and upstream identity where available.
- Output: reproducible SPDX SBOM, Trivy machine-readable finding report, pinned scanner version, vulnerability database timestamp, report subject digest/platform, severity/fixability policy version, exception IDs with expiration and owner, and explicit pass/fail/unknown result.
- Validation: verify provenance attestation's repository/ref/workflow/source SHA and **subject digest**; compare the scan, SBOM, no-rebuild smoke image and release lock to **the same** published digest. Report upstream provenance gaps rather than impersonating upstream attestations.
- Policy: run advisory discovery/noise tests first, then separately approve the release-blocking high/critical threshold and exception procedure. Failed scanner, unavailable DB, missing SBOM, wrong digest, outdated exception or unknown status **fail closed for release publication**. Sensitive findings should not be printed into public release assets.
- Retention: keep digest-bound SBOM, attestation, decision record and scan metadata retrievable after normal short-lived CI artifacts expire. R4 performs *release integration only*, not scanner implementation.

### Per-job minimal permissions and trust

| Proposed stage | Minimum permission boundary | Forbidden trigger/effect |
| --- | --- | --- |
| R1 metadata and R2 lock validations | `contents: read` with no registry/write/deployment secrets | PR checks never tag, publish or deploy |
| R3 local build verification | `contents: read`; disposable ephemeral containers, no token with package write | No publication from untrusted PR/fork/Dependabot |
| R3 approved GHCR candidate publisher | Isolated trusted `main` SHA dispatch; `contents: read`, `packages: write` **only for publisher job**; `id-token: write` and `attestations: write` only for attestation jobs that actually require them | Never `pull_request_target`, never untrusted PR code with registry credentials, never an automatic stable version/tag |
| Shared Trivy/SBOM scans + R4 evidence consumer | Registry/package read and `contents: read`; no package write for read-only scanning; separately scoped attestation write only if generating attestations | No second image scan implementation or hidden acceptance of unverified reports |
| R5 release-publishing job | `contents: write` only for authorized tag/Release operation; separate, narrowly scoped `packages: write` if promoting a verified image tag; no rebuild | Reject existing conflicting tags/releases, no force-retagging or deployment |
| Future R6 production | Dedicated protected `production-nas` environment with release/ref restrictions, reviewer, short-lived scoped credential; zero production secrets outside the approved job | No automatic trigger on merge, package push or tag; no NAS access before independent GO |

Default workflow identity remains read-only; elevate **per job**, and verify effective GitHub Actions token permissions. Keep release tag protection/release immutability changes as independently reviewed future settings decisions, not changes in this design PR.


## 5. Manual NAS boundary (future implementation only)

No current workflow should run on or connect to the NAS. If NAS deployment automation is **later** separately approved:

- Gate the deployment job on a GitHub environment such as `production-nas` with required reviewer(s), restriction to trusted `main` release ref, and no repository-level production secret exposure before approval. Never add a self-hosted NAS runner to jobs running untrusted PR code.
- For a solo maintainer, use an explicit required-review step without `prevent self-review` (otherwise the initiator may be unable to approve); record the risk of single-person approval. Consider dual control when another trusted reviewer is available. Do not claim the environment protection already exists.
- Prefer a private, pull-based deployment agent that accepts only a verified release-lock digest after a separate manual go/no-go, or scoped access over an established private network. No public SSH/Docker socket, no mutable tag pulls, and no auto-updates triggered by `main`.
- Require a recent writer-quiesced backup, backup checksum and isolated restore evidence, explicit ownership of state, copied-state success, direct verification of VPN fail-closed and auth/session behavior, and tested rollback. Stop all new writers before state restoration; do not point old images at migrated DB files.
- A rejected/missing approval means **zero** production side effects. Record deployment SHA/digests, check results, operator and rollback outcome in the release issue.

## 6. R1–R6 prerequisites and negative acceptance (future PRs; no implementation authorized)

**Ordering:** R0 design review → R1 metadata → R2 digest-lock → R3 GHCR candidate publisher → R4 security/evidence integration → R5 publish tag/Release → R6 separately authorized NAS deployment. The **separate Trivy/SBOM/security policy** must exist before R4 can claim release-blocking verification. The **separate checklist amendment** is mandatory before proposed application promotion and R5 release actions; R6 needs its **own** production-automation approval and operator GO. R1/R2 read-only design/test work can proceed without approving the new release order. PRs #33/#36/#60 are complete and must not be modified.

| Incremental PR | Entry prerequisite, authorized scope and positive evidence | Mandatory negative tests on disposable refs/fixtures |
| --- | --- | --- |
| **R1 — metadata / release preflight** | Read-only; version and single-issue patch policy preserved; `--base` / `--reports` tested, `apps/media/VERSION`, README, changelog, Compose align; exact required checks on candidate merge/main SHA. | Wrong SemVer step, missing or duplicate dated changelog, mismatched Media/root version, reused release identity, failed/skipped JUnit, missing/stale/skipped/cancelled required check and wrong branch all **fail** without publication. |
| **R2 — digest-lock / no-build deployment plan** | R1 validation contract; declare supported modes/architectures; schema pins all enabled first-party and upstream images, Compose SHA, source, OCI platform, rollback lock and evidence; resolve by digest and render without local rebuild. | Missing or tag-only image, wrong platform, changed image tag resolving to another digest, omitted optional profile, mismatched Music web/worker digest, secret-containing manifest and unreviewed upstream digest **fail**. |
| **R3 — candidate GHCR build** | R1+R2, **explicit separate implementation approval**, restricted trusted `main` commit dispatch, scoped publisher/attestation credentials; build Portal, Music/worker and Media exactly once with OCI revision labels and record index+platform digests. SHA-candidate tags only; **no** release tag or NAS. | PR/fork/Dependabot/`dev` trigger cannot publish; wrong SHA/ref/repository, incomplete/altered build, missing permission, tag race and duplicate mutable candidate identity **stop**; no stable image promotion. |
| **R4 — shared supply-chain policy integration** | R2+R3 and separately approved security workstream's versioned Trivy/SBOM/report/exception contract. Verify image digest, source/attestation trust, scan policy, SPDX and integration smoke on **published digest without rebuild**. | High/critical unaccepted finding, missing/altered SBOM, wrong provenance subject/ref, stale exception, unreachable scanner DB, omitted third-party scan, wrong platform or vulnerability-policy downgrade **block** release. |
| **R5 — manual tag/GitHub Release** | R1–R4 green; **policy amendment separately approved**; reviewed `dev`→`main` and source-promotion sign-off; **new independent publication approval**. Tag `v1.0.0` at verified main SHA; apply version tag only to already scanned digests; include release lock, checksums, notes and durable SBOM/provenance evidence. | Conflicting/reused tag, digest drift, rebuilt image, duplicate different Release, missing permission, stale status, absent approval, failed attestation or partial push **refuse to overwrite**; idempotent retry preserves same immutable identities. |
| **R6 — production runbook / future deployment boundary** | **Another explicit approval to implement production automation**; approved production environment reviewer, independent operator GO for exact release-lock digest/NAS/window, fresh writer-quiesced backup and isolated restore, real VPN/auth/Jellyfin/browser acceptance, tested rollback. | No/rejected/expired approval, wrong digest or target, shared mutable state, missing/corrupt backup, VPN leak, untrusted runner or unknown health **cause no unauthorized NAS write**; after an authorized cutover, stop writers and follow controlled rollback on failure. |

No step allows **R3 candidate publication** to become **R5 stable release publication**, or R5 to become **R6 NAS deployment**, merely because the preceding CI succeeded. Never point production at mutable version tags or assume GHCR immutability: verify `name@sha256:...` identities at build, scan, release and deployment boundaries. Record tag-to-digest checks at both publication and future pull time. The Music worker and web must use the same published digest. Use protected or immutable release settings only after separate authorization.

### Additional failure-propagation policy

Unknown is **not** pass. Fail closed when required check context is absent or pending, release lock and scan digest differ, an image lacks attestation, a published artifact is partially updated, the candidate source is not the approved main SHA, or any of the required human approvals are absent. No rollback may move a Git tag or reuse a migrated database with an older image; restore only from verified pre-upgrade state under operator control.


## 7. Release-day decision record template

- Proposed version and exact `dev`/`main`/tag SHAs:
- PRs and main required-run URLs:
- Unresolved release blockers (#18, #23, #27 and current follow-ups) and signed exceptions:
- Copied-state / actual browser / auth / real VPN / Jellyfin / permission / backup-restore evidence:
- First-party and third-party digest lock + arch checks:
- SBOM, provenance and vulnerability verification links:
- Changelog/release notes and manual publication approval:
- Prior compatible release digest set, backup IDs and rollback owner:
- **Separate** production approval (operator / time window / target / GO or NO GO):
- Final outcome, observation, and redacted evidence links:

## References

- [Current monorepo workflow](../.github/workflows/monorepo.yml), [CodeQL](../.github/workflows/codeql.yml), [Dependency Review](../.github/workflows/dependency-review.yml)
- [CI design](ci-execution-redesign.md), [Dependabot](dependabot.md), [version/bug policy](versioning-and-bug-tracking.md)
- [Release acceptance](release-1.0-checklist.md), [production readiness](production-readiness.md), [recovery](recovery.md), [browser image](browser-image-1.0-review.md)
- [GitHub image publishing](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations), [deployment environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [immutable releases](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes), [Docker SBOM/provenance](https://docs.docker.com/build/ci/github-actions/attestations/)
