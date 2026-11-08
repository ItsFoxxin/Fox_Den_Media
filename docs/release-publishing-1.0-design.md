# Fox Den Media 1.0 — release and artifact publishing design

> **Historical design reference, not release/deployment approval.** Artifact-first release-order policy was subsequently approved in PR #63; the operative [release checklist](release-1.0-checklist.md) is authoritative. This design does not authorize source promotion, tagging, image publication or NAS deployment. Implementation and each later action require separate approvals.

Repository: `ItsFoxxin/Fox_Den_Media`. Integration: `dev`. Stable: `main`. Intended milestone: `v1.0.0`. Historical audit snapshot: 2026-11-07, `dev` was `7dfbafa` (VERSION `0.9.5`) and `main` was `0.9.1`. These are **historical**; reverify current SHAs and versions for any future approval. In the subsequent audit, `dev` advanced to `0.9.6` and release-order policy PR #63 merged.

## 1. Current state and ownership boundaries

- PRs #29 (Dependabot), #30 (CI architecture), #31 (Phase 1), and #32 (advisory Dependency Review) are merged into `dev`.
- PR #33 **merged**: Phase 2 Migration/Jellyfin dependency gating is implemented. Do not duplicate its graph changes or weaken the strict gate. PR #60 **merged**: Phase 3 removes duplicate feature/security push triggers, without changing required PR checks. PR #41 also merged, advancing current `dev` release metadata.
- PRs #34 and #35 are **closed, unmerged disposable probes**; never use their branch heads for a release.
- PR #36 **merged** into `main`: reviewed Dependabot and advisory Dependency Review configuration is present on the default branch. Dependabot is active, evidenced by its update PRs; routine PRs target `dev`, security PRs target `main` and require reviewed back-sync. PR #36 was **not** an application release promotion.
- Current `dev` `VERSION` is `0.9.5`, while `main` `VERSION` remains `0.9.1`. Re-evaluate exact commit ancestry and main-only security configuration before any eventual full application promotion; the development milestone is not a published release.
- Active workflows: `.github/workflows/monorepo.yml`, `codeql.yml`, `dependency-review.yml`. Phase 2 and 3 CI optimizations are merged, with pull-request validation preserved. None of these workflows publishes GHCR packages or deploys. PR #61 has **merged** as the Phase 3 documentation closeout; it describes future Trivy/SBOM/security-hardening work that this design must reuse rather than duplicate.
- Existing `Monorepo strict gate` requires successful Validation, Music 3.12/3.13, Portal/Movies, pip-audit, Bandit, synthetic migration/rollback, isolated Jellyfin, and integrated container/synthetic VPN checks. Independent CodeQL Python and JavaScript/TypeScript are required. Dependency Review is `warn-only: true`, not a security release veto.
- Active branch rulesets require PRs, strict up-to-date required checks, review-thread resolution, and non-rewrite protections. They currently require **zero formal approving reviews**: a separate documented human release sign-off must not be presented as an already enforced GitHub requirement.
- `scripts/check_release.py` checks SemVer syntax, Compose Media version, README bold version, dated changelog header, and Media Dockerfile `VERSION` copy. Its `--base` stable-branch version-increase and `--reports` JUnit gates exist but are not invoked by active CI. `scripts/check_version_policy.py` runs on PRs, constrains one-step version increments and one-issue patch fixes. Root version policy is separate from a published release.
- Only the Firefox and qBittorrent Compose defaults are digest-pinned. Nginx, Jellyfin and Gluetun defaults are mutable tags. Portal, Music/worker and Media build locally and do not have GHCR publication. Three first-party Dockerfiles use `python:3.12.13-slim-bookworm` without a base-image digest. Record and resolve these before claiming immutable deployment.
- Existing docs `docs/release-1.0-checklist.md`, `docs/production-readiness.md`, `docs/recovery.md` hold mandatory NAS and rollback acceptance gates. These are **not** satisfied by synthetic CI.

## 2. Artifact-first lifecycle and separate approvals (policy adopted in PR #63)

| Stage | Trigger, identity and outcome | Gate |
| --- | --- | --- |
| A. Prepare | Reconfirm merged CI/security foundations, latest dev changes, open release blockers and copied-state readiness. Finish independent security/release blocker work and copied-state rehearsals. | Existing `dev` CI + CodeQL, explicit owner decisions. No release side effects. |
| B. Freeze candidate | Record exact `dev` SHA, close/accept blockers, inventory versions, R2 schema/plan (not completed candidate-image lock), rollback readiness and redacted NAS evidence. Propose `1.0.0` metadata in a dedicated source PR against `dev` after readiness. | Operator signs release eligibility against issue #18 and `release-1.0-checklist.md`. Missing critical evidence = NO GO. |
| C. Promote source | Open a distinct `dev` → `main` PR (after main-only commits are reconciled and the full diff reviewed). Merge manually; do not reuse #36. | All existing `main` required statuses on the actual promotion head, no unresolved review threads, explicit maintainer merge approval, no force push. |
| D. Verify stable commit | Recheck the resulting **main SHA**, root version and release metadata, any release-specific report policy and all required post-merge CI/security statuses. Do not infer green from old `dev` runs. | Failure or unknown = stop; no tag. |
| E. R3 build candidate artifacts | **After** approved source promotion and required post-merge CI, build the three first-party images from exact immutable `main` SHA; publish commit-identified GHCR candidates, capture digests and populate R2-schema release-lock entries. | Only after main acceptance; scan/publish candidate stage does **not** tag `v1.0.0`, create GitHub Release or touch NAS. |
| F. R4 validate artifact identities | Consume **actual R3-published** digests, verify trusted provenance, shared Trivy/SBOM/security policy and pinned upstream identities, perform **no-rebuild integration** and only then finalize the verified release lock and rollback artifact identities. | No critical/high unaccepted findings; all artifacts match source SHA, required architectures and expected services. Signed, expiring exceptions require owner sign-off. |
| G. Publish release | **Separate human release-publish approval** binds `v1.0.0` to that verified SHA. Create protected annotated tag; attach existing tested image digests to `1.0.0` tags without rebuilding; verify tags still resolve to the identical digests; publish immutable GitHub Release with changelog, manifest, hashes, reports and release notes. | Rerun idempotent identity checks; no tag move, force retag or release rewrite on failure. Tag/Release creation cannot authorize NAS access. |
| H. NAS deployment | Future separately authorized **manual production** change, never a consequence of merge, tag, image push or GitHub Release. | Independent go/no-go, operator, maintenance window, exact digests, pre-cutover verified backup/restore, real VPN/auth/browser/client tests, rollback plan; see `production-nas` boundary below. |

**Policy reconciliation completed in PR #63:** pre-promotion copied-state acceptance occurs before source-promotion approval; after the approved `main` merge, R3 builds digests and R4 verifies the immutable artifact set. R5 release publication requires separate approval; any later NAS cutover requires a third independent production GO, with post-cutover stabilization. No stage is authorized merely because this policy was merged.


### 2.1 Historical release-order conflict — resolved by PR #63

**Before PR #63**, the 1.0 checklist contained these two superseded lines (shown for change-history context, **not current instructions**):

> - [ ] Complete stabilization observation and a successful restoration rehearsal.
> - [ ] Only then approve a `dev` → `main` promotion and consider the `1.0.0` tag/release.

**Resolution:** PR #63 approved and merged the artifact-first policy into `dev`. The [current checklist](release-1.0-checklist.md), not the superseded text quoted above, defines the release sequence. All actual NAS acceptance, source-promotion, release-publication and production approvals remain outstanding until separately demonstrated and authorized.

### 2.2 Historical amendment text — adopted in PR #63

The following wording was originally proposed in the design review and subsequently adopted, with chronological formatting, in merged [PR #63](https://github.com/ItsFoxxin/Fox_Den_Media/pull/63). Refer to the **current** checklist for operative steps. These historical quotations are not unchecked new policy proposals:

> - [ ] **Before source promotion:** Complete approved copied-state NAS inventory, writer-quiesced backup, isolated empty-target restore rehearsals, real staging VPN fail-closed, authentication, browser, Jellyfin and client checks; disposition release blockers, record version, reviewed `dev` SHA and Compose/rollback readiness, and sign the source-bound readiness report. **Do not require final GHCR 1.0 candidate image digests, SBOMs or finalized release lock here; these are generated only after source promotion.**
> - [ ] **After independent source-promotion approval:** Review and merge the application source into `main` with required CI/CodeQL, verify its exact resulting SHA, and repeat affected staging acceptance if the merged content materially differs. Build commit-identified GHCR candidates from that SHA, capture immutable digests, verify shared Trivy/SBOM/provenance/vulnerability results and no-rebuild integration, finalize the release lock and rollback artifact identities, and obtain a **separate release-publication approval** before any `v1.0.0` tag, version image tags or GitHub Release.
> - [ ] **Before NAS production cutover:** Obtain a **new independent manual production GO** bound to exact validated release-lock digest, NAS target, operator and maintenance window. Reconfirm exclusive writers, final verified backups/snapshots, restore and rollback evidence. Neither source promotion nor image/Release publication grants NAS access or deployment permission.
> - [ ] **After authorized cutover:** Observe production stabilization, authentication, Music/Media, Jellyfin, browser/clients, torrents/VPN and state integrity; complete rollback/restoration assurance. If any critical verification fails, stop writers and follow the approved rollback before marking production accepted.

PR #63 changed **ordering only**, not the acceptance, backup, restore, rollback or security obligations. The policy is adopted, but no application release promotion, GHCR candidate publication, release tag or NAS deployment is authorized without its own independent approval. This historical design does not modify the authoritative checklist.

### 2.3 Independent approvals under the proposed policy

Three positive owner decisions must be distinct and audit-linked to exact immutable identities: **(1) application source promotion** (reviewed diff and exact main SHA), **(2) release publication** (tag/SHA plus all digests, SBOMs, provenance and risk disposition), and **(3) NAS production deployment** (release-lock digest, environment, operator and maintenance window). The fourth, **policy amendment approval**, was completed with PR #63; the three remaining operational decisions are still separate and must be explicitly recorded. Missing, rejected or expired approvals stop the respective action; approval is never inherited from earlier stages.


### 2.4 Non-circular lifecycle and evidence boundaries

**Pre-promotion evidence** (before the separate source GO) consists of real copied-state NAS acceptance, isolated restore and staging VPN/auth/browser/Jellyfin tests, blockers, reviewed `dev` SHA, version/Compose inputs and rollback readiness. This stage deliberately does **not** demand first-party GHCR release-image digests, post-publish SBOMs or a final lock.

**Post-promotion evidence** is tied to the verified, approved `main` SHA: R3 builds and publishes commit-identified first-party candidates and captures their real digests; R4 checks SBOM/provenance/shared Trivy policy, no-rebuild integration and exact source/digest identity; only then is the release lock finalized with real images and rollback artifact references. A separate owner GO is required before R5 releases any version/tag.

The four independent positive decisions are: **(1) release-order adopted policy, (2) source promotion, (3) release publication, (4) NAS production deployment**. An approval cannot be inferred from green CI or automatically inherited. R1/R2 implementation tests using fixtures do not constitute source/release/production authorization.

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

**R2 defines and tests the release-lock schema and no-build Compose validator using fixtures or already-available images; it never requires first-party 1.0 GHCR candidates to exist. R3 populates actual image digests, and R4 validates/finalizes the production-eligible lock.** A machine-readable versioned `release-lock.json` and nonsecret `release-images.env` should include:
- release `1.0.0`, exact source commit, release workflow/run, Compose file hash and schema version;
- **all enabled** first-party and upstream image names+digests, platform and profile/mode selections;
- SBOM/attestation references, vulnerability decisions and scanner/database versions;
- release evidence/checksum references and rollback release lock/digest set;
- **no** secrets, tokens, real NAS mount paths or private environment values.

## 4. Release validation gates

### Automated — every release candidate must pass

1. Before R5, confirm `VERSION=1.0.0`, exact approved `main` SHA and no conflicting existing `v1.0.0` tag/release. **Do not require the tag to exist in R1–R4.** Only after separate R5 publication approval create/verify annotated `v1.0.0` bound to that same SHA; no overwrite or races.
2. `scripts/check_release.py` plus a release-specific invocation of its `--base` and `--reports` options where appropriate; validate the one-step `0.9.x → 1.0.0` transition and exact dated changelog, README and Compose metadata. Validate `apps/media/VERSION` equals root `VERSION` (a current check gap). Enforce release notes and no duplicate version sections.
3. All currently required `Monorepo strict gate` + `CodeQL (python)` + `CodeQL (javascript-typescript)` + `CodeQL` on the actual `main` release commit. No stale, pending, skipped or cancelled results accepted. Do not change required check names as part of publishing.
4. Required application suites, coverage, JavaScript/Python syntax, actionlint, full-history secret scan, Compose profiles, pip-audit, Bandit, synthetic migration/restore/rollback, synthetic VPN fail-closed and Jellyfin all pass. Existing advisory Dependency Review remains visibility, not a substitute for artifact vulnerability scanning.
5. Build once for the intended source SHA, push candidate images to GHCR using **only** release-specific minimal `packages: write` and read/attestation/OIDC permissions on trusted refs. No image push on PR, arbitrary branch, `dev` merge, or Dependabot event. Never run privileged publisher logic via `pull_request_target`.
6. R4 scans **R3's published digest**, including OS and Python packages, via the separate **reusable Trivy/SBOM/vulnerability-policy security workstream**, not a second scanner. Fail on unresolved high/critical findings by default; require expiring, issue-linked, explicit maintainer acceptance for exceptions. Keep findings non-public where exploit detail is sensitive.
7. Generate, retain and verify digest-bound provenance and SPDX SBOMs. Verify source/ref/repo/workflow identity and digest, not just whether a signature exists. Review package/registry visibility, read access, and permissions before publishing.
8. Smoke pull by digest, verify image labels/architecture and run integration with exactly the three pushed images **without rebuilding**, plus pinned enabled upstream images. Check a generated Compose config resolves no unexpected image, profile, mutable tag or missing digest. Test failure on missing/swapped digest and invalid provenance.
9. Release publication is blocked until every manifest reference is resolvable and the tag-to-digest identity test passes for all first-party images. Preserve the verified candidate digests on retry; reject divergence.
10. Store image manifest, SBOMs, attestations, scan results, release metadata and checksums as GitHub Release assets (and optionally a mirrored NAS backup *after* separate authorization). CI artifact retention of 14–30 days is not adequate as the only durable release evidence.

### Human — separate decisions

- **Source merge**: maintainer reviews full promotion PR, branch divergence, changed security gates and complete CI.
- **Release publish**: maintainer reviews release checklist, open blockers, scan exceptions, migration evidence, actual image digests and rollback release. Record decision and links in release issue; publication is manual only.
- **NAS production**: a new, independent operator approval after release publication, tied to the release lock digest SHA and actual target environment/maintenance window. Approval for a GitHub Release is expressly **not** permission to deploy.


### Shared security workstream contract — mandatory reuse

[CI Phase 3 closeout PR #61](https://github.com/ItsFoxxin/Fox_Den_Media/pull/61) (merged; its successor security implementation is still a separate, unapproved workstream) identifies **Trivy image scanning, SBOM inputs, fixability/severity policy, expiring exceptions and digest-to-release linkage** as an independent successor security-hardening workstream. **Do not create a second Trivy installation, SBOM generator, severity policy or exception ledger in R4.** The security workstream owns a reusable, versioned scan/policy interface; release gates consume its exact outputs and record its policy version. Its separately approved implementation must be complete before a blocking image-release security gate is accepted.

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

## 6. R1–R6 dependency order and acceptance (future implementation only)

**Implementation sequence:** R1 metadata → **R2 lock schema/validator using fixtures** → R3 GHCR publisher implementation → R4 integration consuming the *separately owned* reusable Trivy/SBOM/security-policy implementation → R5 release publisher → optional later R6 deployment. Implementing/testing these PRs is not permission to execute a release. R3's **actual** 1.0 image publication requires the independently approved checklist amendment, completed pre-promotion copied-state/staging acceptance, manual source-promotion GO, reviewed `main` SHA and post-merge CI. R4's actual security gate needs R3's images.

**Required sequence under the adopted policy (no step yet authorized):** pre-promotion NAS/staging acceptance → source-promotion GO → `dev`→`main` promotion/CI → R3 GHCR candidate build and **actual R2-format lock population** → R4 verifiable digest-bound SBOM/provenance/Trivy/no-rebuild integration and **final lock** → separate release-publication GO → R5 release tag/GitHub Release → independent NAS production GO → future R6 deployment → post-cutover stabilization. No GHCR 1.0 release-image digest is needed to authorize source promotion.

| Future PR | Prerequisite and positive acceptance | Mandatory negative tests on disposable fixtures |
| --- | --- | --- |
| **R1 — release metadata** | Read-only validation of exact source, version/changelog/Media/README/Compose, JUnit and existing required checks. No real artifact needed; before R5 check conflicting tag *absence*, after R5 verify created tag identity. | Wrong SemVer, duplicate/missing changelog, failed/missing/skipped/stale checks, bad JUnit, metadata mismatch, reused tag must fail without publication. |
| **R2 — release-lock architecture** | R1; versioned schema, digest/Compose/profile/platform validator, vetted upstream policy, no-build rendering and rollback layout tested with **fixtures or already available images**. **Do not demand actual GHCR 1.0 candidate images.** | Missing/mutable digest, wrong arch, unexpected local build, unknown upstream, omitted profile, mismatched Music web/worker digest or secrets in lock must fail. |
| **R3 — GHCR candidate publisher** | R1+R2 schema and explicit implementation approval. **At execution**, adopted PR #63 policy + full copied-state acceptance + manual source promotion + green `main` CI. Build three first-party images once from exact authorized `main` SHA, publish **commit-identified candidates only**, record immutable index/platform digests and **populate R2-format release lock**; Music web/worker share digest. No `v1.0.0` tag/Release/NAS. | PR/fork/Dependabot/`dev` publish attempt, bad SHA/ref, excess permissions, missing/altered image, tag/digest retarget, failed build or worker/web mismatch must stop. |
| **R4 — supply-chain and artifact verification** | **Actual R3 digests** and separate reusable Trivy/SBOM/policy implementation. Verify trusted repo/ref/workflow/SHA, provenance/SBOM scan subject, high/critical policy and expiring exceptions; scan vetted upstream images, perform **no-rebuild integration**; freeze validated release lock and rollback identities. No duplicate scanner/exception ledger. | Wrong/missing digests/attestations/SBOM, unscanned image, critical/high unaccepted finding, expired exception, scanner/DB outage, changed source or rebuild attempt must **block R5**. |
| **R5 — release publication** | R1–R4 real evidence, adopted PR #63 policy, verified promoted `main` source and **independent publication GO**. Create annotated `v1.0.0` and GitHub Release; version-tags reference *identical scanned candidate digests*, never rebuild; attach lock and checksums. | Wrong/occupied tag, digest drift, missing approval, scanner policy mismatch or partial publication must fail closed without force rewrite. |
| **R6 — future NAS production** | Separate automation approval plus **new manual production GO** for exact lock digest, target, window, owner, backup/restore/rollback and exclusive writers; deploy only digest-selected images with post-cutover checks. | Missing/rejected approval, wrong target/digest, bad backup/restore, real VPN failure, GHCR/tag/Release event or untrusted runner must not deploy or access NAS secrets. |

**Release events are never production triggers.** No push to `main`, GHCR image event, tag, GitHub Release, required-check success or earlier manual approval may invoke R6 or unlock `production-nas` credentials. Preserve per-job least privilege, exact image SHA/digest identity, approved expiring security exceptions, fail-closed unknown status and compatible backup/restore rollback.

## 7. Release-day decision record template

- Independently approved **policy-amendment** PR (absent = existing checklist governs):
- **Pre-source-promotion** version/`dev` SHA/Compose, copied-state staging/restore/VPN/auth/browser/Jellyfin acceptance, blocker and rollback evidence:
- **Separate source-promotion GO** and verified `main` SHA/CI:
- PRs and main required-run URLs:
- Unresolved release blockers (#18, #23, #27 and current follow-ups) and signed exceptions:
- Copied-state / actual browser / auth / real VPN / Jellyfin / permission / backup-restore evidence:
- **Post-source-promotion R3** image digests, build identity and populated R2 schema/arch/upstream lock:
- **R4-verified final lock** and no-rebuild integration/rollback identities:
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
