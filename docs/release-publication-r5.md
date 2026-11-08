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

## R4 → R5 evidence contract (required producer handoff)

**R5 now consumes the authoritative R2 versioned, component-keyed release lock**, not the former list-shaped draft. Both the read-only preflight and separately protected publication job invoke `scripts/release_lock.py` against the actual source Compose after R5 checks the R4 bundle. That authoritative R2 validator must be present in the approved `main` tree before R5 can run. A fixture-only R2 pass does not authorize publication.

A trusted R4 run must belong to `ItsFoxxin/Fox_Den_Media`, path `.github/workflows/ghcr-verify.yml`, manual dispatch on `main`, exact approved source SHA, and `conclusion=success`. A green run **without** the required immutable `foxden-r4-release-ready-v1.0.0` artifact is a failure. The artifact must contain:

- **`release-lock.json`:** strict R2 v1 root keys `schema_version`, `version`, `source_sha`, `compose_sha256`, `platform`, `profiles`, `images`, `services`, `rollback`, `publisher`. Its `images` is a **component-keyed object**, each entry containing only `ref=name@sha256:<digest>`, `platform=linux/amd64`, `platform_digest` (64-hex), and `source_sha` (approved commit for first party, null for upstream). The `publisher` must identify `ghcr-candidates.yml`, R3 run ID and matching source SHA; Music web and worker map to the same component. `rollback` contains the previous version and lock hash. Do **not** add inline vulnerability/attestation fields to this strict schema.
- **`verification.json`:** separate schema-versioned R4 evidence bound to exact `source_sha`, `r3_run_id`, and `r4_run_id`, with `decision=pass`, `security_policy_result=pass`, `no_rebuild_integration=passed`, `rollback_verified=true`, nonempty `security_policy_version`, `high_critical_unaccepted=0`, independently approved source-promotion record, `github_security_review=pass`, `unapproved_security_findings=0`, explicit approved/unexpired `exceptions`, component-keyed `image_evidence`, and a `files` path-to-SHA256 map.
- **`image_evidence`:** one entry for every enabled R2 image: all require `security_decision=pass`, an `sbom` path and `vulnerability_report` path. Each first-party entry also requires `provenance` and `candidate_tag=sha-<full-approved-SHA>`; each upstream image requires `approved_upstream=true`. Each reference must be included in the checksum map and be public-safe. The Music web/worker must share the same locked image reference.
- **`release-notes.md`:** all final required sections, immutable image name@digest references, exact approved main SHA and SHA-256 checksum of the finalized release lock. Unfilled editorial placeholders or private information fail.
- The **actual** checksum-bound SPDX SBOMs, trusted provenance and vulnerability reports for all enabled first-party and upstream images (plus supported synthetic no-rebuild evidence). No symlinks, hidden extra files, secrets or private NAS paths.

R5 validates the complete evidence set and its subject hashes, verifies each first-party GHCR manifest and SHA-tag resolve to the same immutable digest, and verifies trusted provenance/SPDX attestations using `gh` **2.102.0 or newer** with exact `ghcr-candidates.yml` signing identity. R4 owns genuine security verification, signed policy disposition, actual source-to-digest linkage and full enabled-profile coverage; R5 must not reinvent Trivy or claim a green advisory scan is sufficient.

**Current hard blockers:** PR #79 R2 tooling is not yet merged into approved `main`, and PR #81 R4 currently **does not create** this release-ready artifact. Its R3 implementation creates BuildKit SBOM and default GitHub image provenance; the independently signed SPDX attestation or equivalent verified trust mechanism still needs an explicitly approved contract. No valid R4 evidence or source-promotion/release approval is available, and R5 therefore remains fail-closed.

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

## Remaining R2–R4 prerequisites (not yet satisfied)

- Merge/approve PR #79's R2 validator into the intended `main` release source; this R5 consumer now uses the keyed R2 lock shape and its fixture tests cover that shape.
- PR #81, or a separately approved narrow integration change, must produce the **real**, verified `foxden-r4-release-ready-v1.0.0` artifact with the exact schema defined above, signed/verifiable evidence and genuine immutable digests. R5 cannot manufacture the missing R4 verification outputs.
- Agree on and test the cryptographically verifiable SPDX attestation trust chain; do not equate a BuildKit SBOM attachment with an independently verified GitHub SPDX attestation without proving that verification.
- Obtain documented source-promotion and publication decisions, clear master issue #18 and all open release-blocker issues, and configure a reviewed, supported protected GitHub publication environment. All remain independent of R5 implementation CI.

A fully green infrastructure PR is **not** authorization to release `v1.0.0`, publish packages, or access NAS production.
