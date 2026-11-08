# Fox Den Media v1.0.0 — R5 controlled publication

**Status: implementation proposal, not release authorization.** The artifact-first order was adopted in PR #63. Source promotion, release publication and NAS production remain independent, explicitly recorded approvals. This R5 PR changes no production system.

## Audited prerequisites

At the latest R5 synchronization, `dev` remained 0.9.6 and `main` remained 0.9.1; the 1.0 blocker register #18 and other release-blocker issues remained open. No GitHub Release was present. PR #79's R1/R2 validators **are merged into `dev`**, but no separately authorized `main` 1.0.0 promotion has occurred. R3/R4 PR #81 and the digest-security producer PR #84 remain drafts: advisory Trivy PR #72 has since **merged into `dev`** (advisory image scans and CycloneDX SBOMs), and successor PR #74 has also **merged into `dev`** (PR-reporting and trusted advisory baselines). Dependency Review blocking issue #70, critical/high findings issue #76, and actual R3/R4 release-verification implementation remain outstanding. **Advisory scans are not the R3 digest-pinned publisher or R4 blocking release-verification gate.** Their work is **not duplicated** here.

R5 is deliberately **fail closed** until approved R3 image publication and approved R4 security/evidence verification are available.

**Cross-PR contract audit (2026-11-08):** PR #79 is merged into dev and its component-keyed R2 release lock is authoritative. The R5 reader now uses that schema and invokes its validator with the **required** sanitized rendered Compose. PR #81 at head `6e2af6b24b4a7e1f1186e485cde093eda06883bf` validates its R4 inputs but **does not produce** a release-ready artifact. R5 now requires a versioned `release-ready.json` root manifest, cryptographically attested by the exact R4 workflow on the approved main SHA, plus an exact byte-hash map that seals every file. No actual R4 artifact or signature is yet available. This is an implementation interface, not release authorization.

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
3. Include the **already merged PR #79 R1/R2** validators in the approved main release source and validate the immutable lock against sanitized rendered Compose. Synthetic tests are not a substitute for 1.0 candidate images.
4. Authorize R3 `.github/workflows/ghcr-candidates.yml` to build first-party Portal, Music (shared web/worker) and Media exactly once from the approved main SHA and publish **commit-identified candidate digests**, not a release tag.
5. Implement/approve R4 `.github/workflows/ghcr-verify.yml` using the **shared** Trivy/SBOM/vulnerability policy. It must verify real published digests, upstream images, SBOM, trusted provenance, security findings, expiring exceptions, and no-rebuild integration. An R4 workflow-dispatch run against exact main SHA must complete `success`.
6. Configure GitHub environment `release-publication` separately, restricting to `main` and requiring human reviewer(s), and set **environment-only** secret `RELEASE_PUBLICATION_ARMED` to `enabled`. Never set this secret at repository scope. **GitHub environment protections depend on repository visibility/plan; if required reviewers are unsupported, do not arm publication** until an equivalent separately reviewed control is available. This PR does not configure any repository settings.
7. **After R4 success**, create a *dedicated release approval issue* and record an exact comment authored by repository owner `ItsFoxxin`, newer than the R4 verification, identifying the main SHA, lock checksum and R4 run:

   `APPROVE_FOXDEN_RELEASE v1.0.0 main=<40-character-main-sha> lock_sha256=<64-character-sha256> r4_run_id=<run-id>`

   Owner approval does **not** replace environment required-reviewer approval, nor does it authorize NAS production.

## R4 → R5 evidence contract (required producer handoff)

**R5 now consumes the authoritative R2 versioned, component-keyed release lock**, not the former list-shaped draft. Both the read-only preflight and separately protected publication job invoke `scripts/release_lock.py` against the actual source Compose after R5 checks the R4 bundle. That authoritative R2 validator must be present in the approved `main` tree before R5 can run. A fixture-only R2 pass does not authorize publication.

A trusted R4 run must belong to `ItsFoxxin/Fox_Den_Media`, path `.github/workflows/ghcr-verify.yml`, manual dispatch on `main`, exact approved source SHA, and `conclusion=success`. The R4 run itself must be authenticated independently through the GitHub Actions API; an attestation signed by another run is not permission to skip the run check. A green run **without** the required immutable `foxden-r4-release-ready-v1.0.0` artifact is a failure. The artifact must contain exactly the files listed in the signed root manifest, with no symlinks or extra files:

- **`release-ready.json` (canonical v1 manifest):** conforming to [r4-r5-release-ready-v1.schema.json](r4-r5-release-ready-v1.schema.json), with exactly `schema_version=foxden.r4.release-ready.v1`, `version=1.0.0`, `repository=ItsFoxxin/Fox_Den_Media`, `workflow=.github/workflows/ghcr-verify.yml`, exact `source_sha`, integer `r3_run_id`, integer `r4_run_id`, and `files` mapping every other artifact-relative path to the lowercase SHA-256 of its **raw bytes**. It includes `verification.json` but excludes itself, avoiding a self-referential hash. R4 must attest the **raw manifest bytes** with GitHub/Sigstore SLSA provenance from its approved workflow, `refs/heads/main`, exact source SHA. R5 calls `gh attestation verify --format json` with all three identity constraints, rejects missing/empty/malformed verification or wrong subject hash, and requires gh CLI >= 2.102.0. Neither an unsigned checksum map nor a status flag substitutes for this signature.
- **`release-lock.json`:** strict R2 v1 root keys `schema_version`, `version`, `source_sha`, `compose_sha256`, `platform`, `profiles`, `images`, `services`, `rollback`, `publisher`. Its `images` is a **component-keyed object**, each entry containing only `ref=name@sha256:<digest>`, `platform=linux/amd64`, `platform_digest` (64-hex), and `source_sha` (approved commit for first party, null for upstream). The `publisher` must identify `ghcr-candidates.yml`, R3 run ID and matching source SHA; Music web and worker map to the same component. `rollback` contains the previous version and lock hash. Do **not** add inline vulnerability/attestation fields to this strict schema.
- **`security-contract.json`, `scanner.json`, `rendered-release-compose.json`:** the **unchanged raw, separately attested inputs** from the trusted PR #84 security producer, already authenticated and policy-checked in R4. R5 carries their SHA-256 in the signed manifest; it does not re-run Trivy. The sanitized rendered Compose must be verified against the authoritative R2 validator in both R5 jobs using `--rendered release-evidence/rendered-release-compose.json`.
- **`verification.json`:** separate schema-versioned R4 evidence bound to exact `source_sha`, `r3_run_id`, and `r4_run_id`, with `decision=pass`, `security_policy_result=pass`, `no_rebuild_integration=passed`, `rollback_verified=true`, nonempty `security_policy_version`, `high_critical_unaccepted=0`, independently approved source-promotion record, `github_security_review=pass`, `unapproved_security_findings=0`, `exceptions=[]` (strict v1 disallows all exceptions), component-keyed `image_evidence`, and a `files` path-to-SHA256 map matching the signed root manifest except for `verification.json`. `security_policy_version` must be `v1:<64-char reviewed policy hash>`. Every declared claim must be backed by real verified evidence, never a synthetic or self-approved report.
- **`image_evidence`:** one entry for every enabled R2 image: all require `ref` exactly equal to the locked image URI, exact `platform_digest`, `security_decision=pass`, `sbom`, `vulnerability_report`, and `provenance` file paths (including separately verified upstream provenance). Each first-party entry also requires `candidate_tag=sha-<full-approved-SHA>`; each upstream image requires `approved_upstream=true`. Each reference must be included in the checksum map and be public-safe. The Music web/worker must share the same locked image reference.
- **`release-notes.md`:** all final required sections, immutable image name@digest references, exact approved main SHA and SHA-256 checksum of the finalized release lock. Unfilled editorial placeholders or private information fail.
- The **actual** checksum-bound `reports/<component>.sbom.spdx.json`, `reports/<component>.vuln.json`, `provenance/<component>.json` for each enabled first-party and upstream component, plus any verified `integration/*.json` reports. Reports must retain raw PR #84 bytes and exact digests, not rewritten or sanitized to create a pass. The signed root and `verification.files` must cover them.
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

- PR #79 is **merged into dev**; independently approve and promote the exact R2 validator and release code into the intended `main` release source. R5's workflows now pass its mandatory `--rendered` input.
- The PR #81 worker must add a **post-verification-only** R4 producer for the actual `foxden-r4-release-ready-v1.0.0` artifact, plus SLSA attestation of `release-ready.json` from the exact `ghcr-verify.yml` signer. The R4 job must receive narrowly scoped `id-token: write` and `attestations: write` to attest, with **no** package/tag/production writer permissions. It must copy the real signed PR #84 inputs, verified provenance and integration evidence, and produce verified source promotion/native security/rollback claims or stop without uploading. R5 consumes but cannot author or fabricate these claims. R5 cannot manufacture the missing R4 verification outputs.
- Agree on and test the cryptographically verifiable SPDX attestation trust chain; do not equate a BuildKit SBOM attachment with an independently verified GitHub SPDX attestation without proving that verification.
- Obtain documented source-promotion and publication decisions, clear master issue #18 and all open release-blocker issues, and configure a reviewed, supported protected GitHub publication environment. All remain independent of R5 implementation CI.

A fully green infrastructure PR is **not** authorization to release `v1.0.0`, publish packages, or access NAS production.
