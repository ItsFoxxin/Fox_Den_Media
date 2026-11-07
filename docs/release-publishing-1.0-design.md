# Fox Den Media 1.0 — release and artifact publishing design

> **DESIGN ONLY — not an approved release or deployment.** No workflow, repository ruleset, tag, package, NAS state, or production environment is changed by this document. Release implementation requires separate maintainer approval and implementation PRs.

Repository: `ItsFoxxin/Fox_Den_Media`. Integration: `dev`. Stable: `main`. Intended milestone: `v1.0.0`. Snapshot reviewed: 2026-11-07, `dev` `60cce4e7e4cd73ca20f467af3f9f9e4b84f524f6`, `main` `3aec6e646add9f0956130a3b2874ed27e6d6d845`.

## 1. Current state and ownership boundaries

- PRs #29 (Dependabot), #30 (CI architecture), #31 (Phase 1), and #32 (advisory Dependency Review) are merged into `dev`.
- PR #33 is **open**: it alone owns Phase 2 migration/Jellyfin job ordering. Do not touch its branch or duplicate its graph changes.
- PRs #34 and #35 are **closed, unmerged disposable probes**; never use their branch heads for a release.
- PR #36 is **open against `main`**, promoting only the already-reviewed Dependabot and advisory Dependency Review foundations; it is **not** application promotion. Dependabot schedule activation on the default branch depends on that separately approved merge.
- Current `dev` `VERSION` is `0.9.3`, `main` `VERSION` is `0.9.1`. Branches have diverged; evaluate the final merge base and main-only commits before a full promotion. No release tags or GitHub Releases were found by the read-only API review.
- Active workflows: `.github/workflows/monorepo.yml`, `codeql.yml`, `dependency-review.yml`. They do **not** publish packages or deploy anything.
- Existing `Monorepo strict gate` requires successful Validation, Music 3.12/3.13, Portal/Movies, pip-audit, Bandit, synthetic migration/rollback, isolated Jellyfin, and integrated container/synthetic VPN checks. Independent CodeQL Python and JavaScript/TypeScript are required. Dependency Review is `warn-only: true`, not a security release veto.
- Active branch rulesets require PRs, strict up-to-date required checks, review-thread resolution, and non-rewrite protections. They currently require **zero formal approving reviews**: a separate documented human release sign-off must not be presented as an already enforced GitHub requirement.
- `scripts/check_release.py` checks SemVer syntax, Compose Media version, README bold version, dated changelog header, and Media Dockerfile `VERSION` copy. Its `--base` stable-branch version-increase and `--reports` JUnit gates exist but are not invoked by active CI. `scripts/check_version_policy.py` runs on PRs, constrains one-step version increments and one-issue patch fixes. Root version policy is separate from a published release.
- Only the Firefox and qBittorrent Compose defaults are digest-pinned. Nginx, Jellyfin and Gluetun defaults are mutable tags. Portal, Music/worker and Media build locally and do not have GHCR publication. Three first-party Dockerfiles use `python:3.12.13-slim-bookworm` without a base-image digest. Record and resolve these before claiming immutable deployment.
- Existing docs `docs/release-1.0-checklist.md`, `docs/production-readiness.md`, `docs/recovery.md` hold mandatory NAS and rollback acceptance gates. These are **not** satisfied by synthetic CI.

## 2. Proposed lifecycle and separate approvals

| Stage | Trigger, identity and outcome | Gate |
| --- | --- | --- |
| A. Prepare | Merge independent security promotion #36 after its own review; complete #33 as separate Phase 2 work. Finish release-blocking bug PRs and copied-state rehearsals. | Existing `dev` CI + CodeQL, explicit owner decisions. No release side effects. |
| B. Freeze candidate | Record exact `dev` SHA, close/accept blockers, inventory versions, generated release lock plan, rollback and redacted NAS evidence. Propose `1.0.0` metadata in a dedicated source PR against `dev` after readiness. | Operator signs release eligibility against issue #18 and `release-1.0-checklist.md`. Missing critical evidence = NO GO. |
| C. Promote source | Open a distinct `dev` → `main` PR (after main-only commits are reconciled and the full diff reviewed). Merge manually; do not reuse #36. | All existing `main` required statuses on the actual promotion head, no unresolved review threads, explicit maintainer merge approval, no force push. |
| D. Verify stable commit | Recheck the resulting **main SHA**, root version and release metadata, any release-specific report policy and all required post-merge CI/security statuses. Do not infer green from old `dev` runs. | Failure or unknown = stop; no tag. |
| E. Build candidate artifacts | From an explicitly approved immutable `main` SHA, a trusted, manually dispatched release-candidate workflow builds first-party images to GHCR with `sha-<full-commit>` candidate tags. | Only after main acceptance; scan/publish candidate stage does **not** tag `v1.0.0`, create GitHub Release or touch NAS. |
| F. Validate artifacts | Record index digests, provenance, SPDX SBOMs, vulnerability reports, pinned upstream image identities, compatibility smoke tests and a full release lock manifest. | No critical/high unaccepted findings; all artifacts match source SHA, required architectures and expected services. Signed, expiring exceptions require owner sign-off. |
| G. Publish release | **Separate human release-publish approval** binds `v1.0.0` to that verified SHA. Create protected annotated tag; attach existing tested image digests to `1.0.0` tags without rebuilding; verify tags still resolve to the identical digests; publish immutable GitHub Release with changelog, manifest, hashes, reports and release notes. | Rerun idempotent identity checks; no tag move, force retag or release rewrite on failure. Tag/Release creation cannot authorize NAS access. |
| H. NAS deployment | Future separately authorized **manual production** change, never a consequence of merge, tag, image push or GitHub Release. | Independent go/no-go, operator, maintenance window, exact digests, pre-cutover verified backup/restore, real VPN/auth/browser/client tests, rollback plan; see `production-nas` boundary below. |

**Policy reconciliation required:** Existing `docs/release-1.0-checklist.md` says to consider tagging only after successful production stabilization. Artifact-first reproducible deployment requires releasable images *before* deployment. Seek a separate owner decision to clarify: complete copied-state acceptance before release publication; use a separately approved publication event; deploy only after an **additional** production approval. Until this is accepted, follow the more restrictive existing checklist and do not create a tag.

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

## 5. Manual NAS boundary (future implementation only)

No current workflow should run on or connect to the NAS. If NAS deployment automation is **later** separately approved:

- Gate the deployment job on a GitHub environment such as `production-nas` with required reviewer(s), restriction to trusted `main` release ref, and no repository-level production secret exposure before approval. Never add a self-hosted NAS runner to jobs running untrusted PR code.
- For a solo maintainer, use an explicit required-review step without `prevent self-review` (otherwise the initiator may be unable to approve); record the risk of single-person approval. Consider dual control when another trusted reviewer is available. Do not claim the environment protection already exists.
- Prefer a private, pull-based deployment agent that accepts only a verified release-lock digest after a separate manual go/no-go, or scoped access over an established private network. No public SSH/Docker socket, no mutable tag pulls, and no auto-updates triggered by `main`.
- Require a recent writer-quiesced backup, backup checksum and isolated restore evidence, explicit ownership of state, copied-state success, direct verification of VPN fail-closed and auth/session behavior, and tested rollback. Stop all new writers before state restoration; do not point old images at migrated DB files.
- A rejected/missing approval means **zero** production side effects. Record deployment SHA/digests, check results, operator and rollback outcome in the release issue.

## 6. Exact proposed acceptance checks

| Deliverable / owner | Acceptance criteria |
| --- | --- |
| Design PR (this document) | Only this markdown file added on a short-lived docs branch against `dev`. Zero workflow, app, VERSION, protections, registry or NAS modifications. Maintainer review before merge. |
| Release metadata gate | Disposable PR tests fail for bad tag/version, missing/mismatched dated changelog, stale/read-only base, duplicate release, Media VERSION mismatch, skipped/failed JUnit, and succeed on valid `1.0.0` source. Existing version/bug policy remains unchanged. |
| Immutable upstream lock + deployment dry-run | All enabled Compose images use verified digest references; fail on missing digest, wrong platform, unauthorized tag and accidental local build. All supported modes remain renderable. No secret-bearing config artifact upload. |
| GHCR candidate builder | Only explicit main-SHA release dispatch publishes three candidate images; Music/worker one image; no PR or dev publication. Build contexts, OCI labels, digest outputs, permissions and scan attachment are verified on disposable version tags. |
| Supply-chain release gate | The image tested is the exact image published. Every digest has verifiable repository/SHA provenance, SPDX SBOM and a passing or explicitly accepted vulnerability assessment. Negative tamper tests reject missing/altered digest or wrong source. |
| Release publication | Annotated `v1.0.0` tag matches `main` SHA and root VERSION, all three `:1.0.0` tags still resolve to the scanned digests, notes derive from approved changelog and have links, attached manifest/checksums verified. A retry cannot silently overwrite artifacts. Enable/review GitHub release immutability in a **separate settings change**, not this design. |
| Release rollback package | Release includes previous known-good digest set, compatible-state/migration warning, backup+restore runbook, tested stop/start ordering and reverse proxy/VPN checks. An isolated rollback works without re-resolving mutable tags. |
| Production boundary | On absent/rejected authorization, **no deployment job or NAS write occurs**. Future authorized dry-run checks exact lock/backup/rollback/permissions before a *second* explicit execute step; recorded approver and target release are auditable. |

## 7. Suggested small PR sequence (no implementation authorized yet)

- **PR R0 — design:** this docs-only PR. It must not block or modify PR #33 or PR #36.
- **PR R1 — release metadata validation:** separate read-only release-preflight workflow / tests; enforce `--base`, `--reports` and `apps/media/VERSION` alignment. Review independently from Phase 2 DAG; preserve existing required check contexts.
- **PR R2 — release lock and upstream digest policy:** add nonsecret manifest schema, generator/validator and isolated Compose rendering/no-build tests. Keep third-party image ownership explicit; no NAS or required-check settings.
- **PR R3 — candidate GHCR image builds:** explicitly dispatched, main-commit-only, three images, read/build provenance and GitHub package permissions. Include dry-run/testing strategy before allowing real pushes. This PR requires explicit implementation approval.
- **PR R4 — attestations, SBOM, image scanning and promotion gate:** verify identities and negative fixtures, implement digest promotion; **no GitHub Release or NAS action** until independently reviewed.
- **PR R5 — manual tag + GitHub Release publisher:** release-publish sign-off, immutable version policy, manifest and notes. Handle partial failure and idempotency with no forced re-tag.
- **PR R6 — future NAS runbook/approval integration:** **separate later decision** after actual copied-state acceptance and a human review of credential/network/runner design. No automatic production deployment may be introduced in R1–R5.

**Dependencies:** R0 review → finish #33 and separately decide #36 → R1 → R2 → R3 → R4 → R5. R6 follows only after a second explicit implementation/deployment authorization. R1/R2 can be drafted independently, but GHCR publishing must not preempt the accepted `main`/release identity policy.

## 8. Release-day decision record template

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
