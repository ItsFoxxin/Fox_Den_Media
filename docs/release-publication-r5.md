# Fox Den Media v1.0.0 — R5 controlled publication

**Status: implementation proposal, not release authorization.** The artifact-first order was adopted in PR #63. Source promotion, release publication and NAS production remain independent, explicitly recorded approvals. This R5 PR changes no production system.

## Audited prerequisites

At the latest R5 synchronization, `dev` remained 0.9.6 and `main` remained 0.9.1; the 1.0 blocker register #18 and other release-blocker issues remained open. No GitHub Release was present. R1–R4 release-image and digest-lock workflows are not yet integrated into `dev`: advisory Trivy PR #72 has since **merged into `dev`** (advisory image scans and CycloneDX SBOMs), and successor PR #74 has also **merged into `dev`** (PR-reporting and trusted advisory baselines). Dependency Review blocking issue #70, critical/high findings issue #76, and actual R3/R4 release-verification implementation remain outstanding. **Advisory scans are not the R3 digest-pinned publisher or R4 blocking release-verification gate.** Their work is **not duplicated** here.

R5 is deliberately **fail closed** until approved R3 image publication and approved R4 security/evidence verification are available.

**Cross-PR contract audit (2026-11-08):** PR #81 uses `.github/workflows/ghcr-candidates.yml` and `.github/workflows/ghcr-verify.yml`; R5's trusted source identities now match these paths. However, the current R4 verifier **does not upload** `foxden-r4-release-ready-v1.0.0`, which R5 requires. PR #79's authoritative R2 lock schema defines `images` as a **component-keyed object** (with `services` and `publisher`), while the existing R5 draft `validate_bundle()` expects an **array** of image entries plus additional inline security properties. These are **blocking integration incompatibilities**, not passing release checks; merging R5 infrastructure into `dev` must not be mistaken for enabling publication. A green general CI run is not equivalent to R4 release artifacts.

## Included

- `.github/workflows/release-publish.yml`: manually dispatched, main-only R5 workflow. No automatic push, tag, registry or Release triggers.
- `scripts/release_publication.py`: current main/CI/blocker/R4/asset/registry validations, owner approval and digest-based release assets.
- `tests/platform/test_release_publication.py`: offline failure fixtures, included in existing monorepo platform CI.
- `docs/release-notes-1.0-template.md`: professional editable release-notes outline.
- `docs/production-publication-boundary.md`: future R6 architecture without production credentials or deploy jobs.

**Workflow-dispatch prerequisite:** GitHub normally requires a workflow to exist on the **default branch (`main`)** to offer manual dispatch. Merging this R5 infrastructure into `dev` allows review and tests; executing it later requires a **separately approved selective infrastructure promotion to `main`**. That is not a promotion of 1.0 application code or permission to publish.

## Conditions for actual publication (all mandatory)

1. PR #63's adopted checklist remains authoritative. Resolve issue #18 and **all** open `release-blocker` issues with redacted real copied-state NAS, restore, VPN/auth/browser/Jellyfin and rollback evidence. No fixture can replace these.
2. Approve application source promotion independently, review the exact `dev`→`main` diff and preserve main-only security changes. The promoted SHA must carry synchronized `VERSION=1.0.0`, README, Compose, Media version and changelog.
3. Implement/test R1 metadata and R2 release-lock schema validators. Their fixtures **do not** require 1.0 candidate images.
4. Authorize R3 `.github/workflows/ghcr-candidates.yml` to build first-party Portal, Music (shared web/worker) and Media exactly once from the approved main SHA and publish **commit-identified candidate digests**, not a release tag.
5. Implement/approve R4 `.github/workflows/ghcr-verify.yml` using the **shared** Trivy/SBOM/vulnerability policy. It must verify real published digests, upstream images, SBOM, trusted provenance, security findings, expiring exceptions, and no-rebuild integration. An R4 workflow-dispatch run against exact main SHA must complete `success`.
6. Configure GitHub environment `release-publication` separately, restricting to `main` and requiring human reviewer(s), and set **environment-only** secret `RELEASE_PUBLICATION_ARMED` to `enabled`. Never set this secret at repository scope. **GitHub environment protections depend on repository visibility/plan; if required reviewers are unsupported, do not arm publication** until an equivalent separately reviewed control is available. This PR does not configure any repository settings.
7. **After R4 success**, create a *dedicated release approval issue* and record an exact comment authored by repository owner `ItsFoxxin`, newer than the R4 verification, identifying the main SHA, lock checksum and R4 run:

   `APPROVE_FOXDEN_RELEASE v1.0.0 main=<40-character-main-sha> lock_sha256=<64-character-sha256> r4_run_id=<run-id>`

   Owner approval does **not** replace environment required-reviewer approval, nor does it authorize NAS production.

## R4 → R5 verified evidence contract (proposed v1)

The actual R4 run must belong to `ItsFoxxin/Fox_Den_Media`, path `.github/workflows/ghcr-verify.yml`, event `workflow_dispatch` on `main`, head SHA equal to approved main SHA, conclusion `success`. It must upload exactly one complete artifact named `foxden-r4-release-ready-v1.0.0`, containing:

- `release-lock.json` — schema_version=1, version=1.0.0, source_sha, r3_run_id, r4_run_id, 64-hex Compose SHA-256, supported `profiles` list, `music_worker_digest`, verified `rollback.lock_sha256`, and `images`.
- `verification.json` — schema_version=1, version=1.0.0, source_sha, r3_run_id, r4_run_id, `decision=pass`, **`source_promotion_approval` (independent owner-approved source decision, exact main SHA and GitHub record URL)**, `security_policy_result=pass`, `no_rebuild_integration=passed`, `high_critical_unaccepted=0`, **`github_security_review=pass` and `unapproved_security_findings=0`** covering native CodeQL/Dependabot/secret alerts, nonempty `security_policy_version`, approved nonexpired `exceptions`, and a `files` map from relative evidence paths to SHA-256 checksums (excluding the verification file itself).
- `release-notes.md` — complete headings from the release-notes template, the exact main SHA, SHA-256 checksum of release-lock.json and all first-party `name@sha256:...` image references.
- Referenced, checksum-bound SBOMs, provenance and vulnerability reports (plus other explicitly recorded evidence files). No symlinks, path traversal or untracked extras.

Each `images` entry contains kind (`first-party` or `upstream`), component, name, digest (`sha256:<64hex>`), architecture (`linux/amd64`) and `security_decision=pass`. First-party entries must be **exactly**:

| Component | Required immutable image repository |
| --- | --- |
| portal | `ghcr.io/itsfoxxin/fox-den-media-portal` |
| music | `ghcr.io/itsfoxxin/fox-den-media-music` |
| media | `ghcr.io/itsfoxxin/fox-den-media-media` |

First-party entries additionally require `source_sha`, `candidate_tag=sha-<source-sha>`, and paths for `sbom`, `provenance` and `vulnerability_report`. Music worker digest must equal the Music image digest. Every enabled upstream image must be present in the lock with `kind=upstream` and `approved_upstream=true`. R4 owns verification of **all enabled** profile/image coverage, approved risk exceptions and source-to-digest mapping. R4 also records the separately reviewed disposition of GitHub's native security alerts; a successful CodeQL run is not evidence that all alerts are cleared. R5 does not implement another scanner or policy database.

R5 requires `gh` CLI **2.102.0 or newer** before any attestation-verification step (to avoid older prefix-matching of `--signer-workflow`). The preflight and independently approved publication job both fail closed if the runner's CLI version is older; a reviewed, integrity-pinned CLI installation may be required in a later PR before actual publication. R5 verifies each image digest is fetchable, and that a first-party SHA candidate tag still resolves to the identical digest. It cryptographically verifies the first-party provenance and SPDX SBOM attestations using GitHub CLI, binding expected signer `.github/workflows/ghcr-candidates.yml`, repository, main ref and source SHA. The signer path and contract must be coordinated with the independently implemented R3/R4 workflows before enabling publication.

**No actual release image digests or R4 evidence currently exist in this workstream.** Do not mistake test fixture data for deployable artifacts.

## Manual runbook — when all dependencies are complete

1. Select the R5 workflow on `main` and enter **full source SHA**, trusted `r4_run_id` and dedicated approval issue. Set `publish=false` to perform read-only evidence preflight.
2. Verify the exact main SHA has successful **Monorepo strict gate**, **CodeQL (python)**, **CodeQL (javascript-typescript)** and **CodeQL** checks; no open release-blocker issues; successful trusted R4 run; approved shared security policy; complete checksum-bound evidence.
3. Review supported architecture, no-rebuild integration, all real GHCR/upstream digests, provenance/SBOM verifications, final rollback identities, release notes and public sensitivity.
4. Record the **separate owner release-publication approval** comment after R4 completes. Dispatch again with `publish=true` and `confirmation=PUBLISH v1.0.0`. Wait for human environment reviewer approval.
5. The guarded publisher rechecks **live** main SHA, CI, blocker issues, R4 run, evidence, owner comment, registry digests and attestations before creating an annotated `v1.0.0` tag and GitHub Release with `--verify-tag`. It uploads locked release references, evidence and `assets.sha256`. It never rebuilds or retags GHCR images.
6. If a tag or Release already exists, publication **fails without overwrite**. A partial tagged-but-unpublished result needs separately reviewed manual recovery, not an automatic retry. Read-only preview/verifier checks are repeatable.

**Idempotent read-only verification after publication:** given the preserved trusted R4 artifact at `release-evidence/`, run `python scripts/release_publication.py published --source-sha <approved-main-sha> --r4-run-id <r4-run-id>` with read-only GitHub access. This verifies the existing annotated `v1.0.0` tag's peeled commit SHA, public non-draft/non-prerelease Release identity, complete expected asset set and each GitHub asset SHA-256. It performs **no upload, tag move, update or new publication**; repeating it has the same result. Missing GitHub asset digests fail closed rather than claiming unverifiable integrity.

Release assets must not contain private NAS configuration, credentials, private paths or topology, privileged tokens or sensitive exploit detail. Unfinished release notes are rejected.

## Test and security boundaries

The monorepo fixture tests simulate missing/failed CI, untrusted R4 workflow/branch, wrong SHA, blockers, missing independent approval, altered digests, missing artifacts, stale SBOM/security evidence, high/critical exceptions, invalid provenance, incompatible image/platform, mismatched Music worker, invalid rollback data and unapproved upstream images. The **real** GHCR integration cannot be tested until R3/R4 exists.

Publication has no production environment, production secrets, NAS runner, SSH/Docker-socket access or deploy steps. Merge/tag/Release/package events **cannot trigger** a NAS deployment. See the separate [R6 boundary](production-publication-boundary.md), [authoritative acceptance checklist](release-1.0-checklist.md) and [release design](release-publishing-1.0-design.md).

## Final R2–R4 integration prerequisites (not yet satisfied)

Before publication can be armed, merge or approve the single authoritative R2 versioned lock schema from PR #79, and implement an **explicit** R4→R5 evidence adapter that consumes its keyed `images`, `services`, `publisher`, `rollback` and `platform` fields. Never put unrecognized security fields into that strict R2 lock; keep security findings, approvals, hashes and attestation subject identity in separately checked verification evidence.

PR #81 or an independently reviewed follow-up must produce a **single signed/checksum-bound R4 release-ready artifact** named `foxden-r4-release-ready-v1.0.0`. It must contain the final actual (not fixture) lock and verified R3 publisher identities, all first-party/upstream scan coverage, SBOMs, signed provenance, expiration-aware policy decisions, independent source approval evidence, no-rebuild integration proof and public-safe release notes. R5 must validate its **exact** agreed schema and verify trust, never merely accept a green R4 job.

The existing R5 fixtures represent a draft list-shaped contract, **not** the final R2/R4 API. PR #81's R3 currently produces a default GitHub image provenance attestation and BuildKit SBOM; R5 requires a **cryptographically verifiable SPDX attestation** as well. The worker teams must agree whether R3/its shared security producer will attest SPDX in GitHub or whether R5 should verify the trusted registry-attached SBOM with a different strict mechanism. Do not silently treat `--sbom=true` alone as a GitHub-signed SPDX attestation. Add interoperability fixtures for the actual R2 lock and trusted R4 bundle and require a successful read-only preflight before treating R5 as ready to publish. This is an explicit **blocker**; do not fabricate a `verification.json` or weaken the checks as a workaround.
