# R4 trusted digest-security producer — v2 A/C (Issue #83, draft PR #84)

**Preparatory code only. No 1.0.0 release, real image assessment, protected merge, GHCR push or NAS authorization.** This PR owns the existing `trivy-digest-security.yml` workflow and `ghcr_digest_security.py`; it does not copy or edit the separately owned #93 / #81 / #80 branches. The authoritative independent verifier from merged PR #93 (head `437616f75c5b6d4c54d52d034c489dd5260bfa19`) is now present on protected `dev` at `61d282f71382c5e078ffdec39a19acefc7fd84c9`. PR #84 was reconciled with that protected base once; the independent code and schema are consumed unchanged. This source integration does not establish B artifact availability or live acceptance.

## Why two independent runs

A single v1 producer blocked on any HIGH/CRITICAL, making independent legitimate FIXED or NOT_AFFECTED review impossible. The new workflow accepts `stage: collect` (A) or `stage: finalize` (C) under separate, human-reviewed `ghcr-security` environment approvals. Between them, the merged PR #93 B workflow must perform independent Ed25519 human dispositions and GitHub OIDC attestation, but its separate submission uploader and owner-controlled trust are still outstanding.

1. **A — collect original evidence**: only manual approved `main` SHA with a real, successful same-source R3 run, three first-party candidates and owner-reviewed R2 lock. Authenticate R3, exact OCI digest, platform and upstream signer (never assume provenance); scan each distinct enabled image with checksum-verified Trivy 0.76.2. Retain unaltered unsuppressed `reports/*.vuln.json`, original SPDX and scanner JSON. Verify structure, image ID, hash, Trivy version, positive DB version, nonfuture <=14-day freshness, source/R3, lock and service coverage. **HIGH/CRITICAL/UNKNOWN are retained, not cleared or suppressed.** UNKNOWN blocks final security acceptance. Sign context, lock, rendered Compose, scanner and source exception policy with GitHub OIDC; upload `ghcr-security-contract-v2-inputs`. SUCCESS means evidence collected, **not security accepted**.
2. **B — separate independent human review**: separately owned `.github/workflows/security-disposition-review.yml` consumes signed A + independently authenticated `security-disposition-submission-v1`; validates every HIGH/CRITICAL occurrence from the unmodified reports, FIXED/NOT_AFFECTED proof and reviewer Ed25519 signature, additional owner Ed25519 concurrence for CRITICAL NOT_AFFECTED, and separately owner-signed fresh lifecycle. It emits signed `security-disposition-review-v1`, with `disposition-verification.json` plus dispositions, signatures and original proofs. This implementation and owner-managed reviewer submission are **not** in PR #84.
3. **C — finalize strict v2**: separately authorize another manual run on the **same approved SHA**. Fetch run-ID-specific successful R3/A/B artifacts, verify exact completed GitHub workflow/source identities and OIDC attestation on A and B, independently reconstruct R2/candidate/upstream identities and current report hashes, then **rerun the PR #93 CLI** using owner-managed current trust, separately signed latest lifecycle, the original source/lock/scanner/reports, review proof files and signatures. Require its regenerated `disposition-verification.json` bytes to match the signed B verification. Reject expired/revoked/superseded review, missing or duplicate HIGH/CRITICAL, UNKNOWN, wrong source/lock/manifest/platform, wrong signer or altered report. Produce only `schema_version=2` `security-contract.json` with `disposition_review`. Sign and upload `ghcr-security-contract-v2`. No silent v1 fallback.

The workflow has **no PR/push trigger**, no `packages: write`, no publication or NAS token. A and C are separate workflow dispatches. The actual #93 verifier is integrated via `python -m scripts.ghcr_digest_security finalize-v2`; C still fails closed without independently signed B evidence and a current owner-controlled trust/lifecycle channel. Both A and C verify the live GitHub `ghcr-security` protected environment/required reviewers and protected `main`, rather than relying on assertion variables. C additionally rejects B runs from A's actor and A runs lacking the `collect` stage.

## A artifact `ghcr-security-contract-v2-inputs`

Exact root paths when downloaded into `security/`:

| Path | Meaning |
| --- | --- |
| `context.json` | OIDC-signed producer context |
| `release-lock.json` | Raw approved complete R2 lock |
| `rendered-release-compose.json` | Only `services.{name}.image`, no secrets |
| `scanner.json` | Unmodified Trivy 0.76.2 metadata with positive VulnerabilityDB.Version and UpdatedAt |
| `vulnerability-exceptions.json` | Exact approved source exception ledger; must remain `{"schema_version":1,"exceptions":[]}` |
| `reports/<name>.vuln.json` | Original unsuppressed Trivy scan |
| `reports/<name>.sbom.spdx.json` | Original SPDX-2.3 |
| `reports/<name>.manifest.json` / `<name>.image-id` | Observed immutable OCI manifest and inspected config identity |

`context.json` contains **exactly**: `schema_version=1`, `repository="ItsFoxxin/Fox_Den_Media"`, `source_sha`, `producer_actor="github:<authenticated-A-run-actor>"`, `release_lock_sha256`, `r3_run_id`, `scan_run_id`, `scanner_metadata_sha256`, `images`. Every image maps exactly `image_repository`, `manifest_digest`, `platform_digest`, `trivy_report_sha256`, `spdx_sbom_sha256`. All digests are `sha256:<lowercase-hex>` of ORIGINAL raw bytes or locked OCI digest, as appropriate. The exact key sets and rules are in merged `scripts/verify_security_dispositions.py` (#93); the v2 producer independently checks them. Both enforce strict integer schema versions and reject duplicate underlying CVE/package/target/ecosystem/version identities even when severity, fixed-version metadata or descriptions differ.

Music web and worker use the **same** `music` image. First-party images: `portal`, `music`, `media`. Mandatory upstream: `nginx`. Additional exact enabled lock subjects: `browser` (Firefox), `jellyfin`, `gluetun`, `qbittorrent`. Missing profile image, locked service, scan, signer, manifest or platform digest **blocks A**, even if vulnerabilities are absent.

## C artifact `ghcr-security-contract-v2`

Contains every unmodified A file and `security-contract.json`, plus `review/disposition-verification.json`, `review/dispositions.json`, `review/signatures.json` and `review/proofs/<slug>.json` from the independently verified B artifact. Trust/private keys and current owner lifecycle are **not** taken from B as trusted policy and are not uploaded in the final release artifact.

`security-contract.json` retains all v1 data fields and original raw report/SPDX hashes, but **schema_version is 2, never 1**, and adds `disposition_review` with exactly:

| Field | Required value |
| --- | --- |
| `schema_version` | integer `1` |
| `artifact_name` | `security-disposition-review-v1` |
| `verification_file` | `disposition-verification.json` (B artifact root) |
| `verification_sha256` | SHA-256 of original signed B result bytes |
| `dispositions_sha256` | SHA-256 of canonical independently signed dispositions JSON |
| `review_workflow` | `.github/workflows/security-disposition-review.yml` |
| `review_run_id` | exact positive authenticated GitHub B run ID |
| `verified_at` | UTC second-precision timestamp |

**PR #81 still requires its own v2 consumer changes**: validate A/B/C workflows and run identities, reject v1, reconstruct full findings, validate present lifecycle, preserve `foxden.r4.release-ready.v1` outer manifest and bind the reviewed evidence through the R4/R5 signed file map. A green C cannot be treated as proof that #81 or #80 integration is ready.

## Operator prerequisites — external blockers

- Owner separately authorizes protected reviewed source promotion, immutable digest-pinned base, legitimate R3 images, A, independently reviewed B and C. `dev` code and this PR do not authorize `main` promotion.
- Confirm the actual GitHub `ghcr-security` Environment has required human reviewers and protected `main` restrictions, and that these controls are enforceable on the repository plan. Variables do not prove GitHub protection. The separate B environment `security-disposition-review` requires the same independent verification.
- Set one-time `GHCR_SECURITY_ENABLED=true`, `GHCR_SECURITY_ENV_PROTECTED=true`, `GHCR_SECURITY_APPROVED_SOURCE_SHA`, `GHCR_SECURITY_LOCK_B64`, `GHCR_SECURITY_RENDERED_B64`, and SHA-256 hex values `GHCR_SECURITY_LOCK_SHA256`, `GHCR_SECURITY_RENDERED_SHA256`. Lock and rendered content must be complete and nonsecret. The workflow checks hashes and authoritative R2 validator; disarm after authorized use.
- B and C require **owner-controlled**, source-independent trust/lifecycle: `SECURITY_DISPOSITION_TRUST_B64`, `SECURITY_DISPOSITION_LIFECYCLE_B64`, `SECURITY_DISPOSITION_LIFECYCLE_SIG_B64`, `SECURITY_DISPOSITION_LIFECYCLE_SHA256`. Keys, approved reviewer membership and independent review-submission uploader remain unimplemented/unverified. The owner must establish a trusted *latest* signed-lifecycle channel with anti-rollback; a fresh-looking older genuine ledger is not sufficient. **Do not operate on live release evidence until this trust prerequisite exists**.
- Patched `gh >= 2.102.0` is mandatory to prevent signer-workflow prefix confusion. GitHub Actions OIDC file attestations are checked by exact workflow/repo/ref/commit and SHA; the GitHub API verifies completed workflows and selected artifact run IDs.
- **Upstream allowlist remains deliberately empty** in `security/upstream-provenance.json`. For every enabled upstream (including mandatory nginx) independently verify real GitHub signed OCI provenance for the exact locked Docker Hub/LSCR digest before adding approved signer metadata; no fabricated source SHA/workflow, mutable alias, Docker pull alone, alternate registry assertion or `provenance_status=verified` substitute. If an image lacks equivalent trust, a separately reviewed versioned producer+consumer scheme is required.
- #76 security finding disposition, #92/#93 independent review, #81 R4 acceptance, #80 R5 publication and #18 NAS acceptance are separate gates. No empty policy exception may be introduced.

## Finite-decimal Trivy compatibility — F-01 (Issue #83 / PR #84)

Stage A and Stage C parse the **original unmodified Trivy vulnerability report JSON** using `strict_load(path, scanner_evidence=True)`. Only these raw scanner vulnerability reports may contain **finite Python binary64 decimal** values, including nested `CVSS.redhat.V2Score`, `CVSS.redhat.V3Score` and `CVSS.nvd.V3Score`. This exactly matches the separately owned Issue #94 draft verifier's intended contract: `float(token)`, `math.isfinite`, then canonical vulnerability bytes `json.dumps(vuln, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")`.

- Reject `NaN`, `Infinity`, `-Infinity`, exponent overflow (e.g. `1e309`), duplicate JSON keys, malformed JSON, malformed UTF-8 and oversized raw reports. Signed context/review/signatures/trust/lifecycle and release lock, policy, scanner metadata and SPDX remain **strict** and reject floating-point JSON.
- Preserve the exact original vulnerability-report bytes and SHA-256 regardless of decimal spelling. For instance, `3.700` and `3.7` canonically hash identically as parsed float `3.7` in the complete finding, but their original report-byte hashes differ. No CVSS fields are dropped or rewritten.
- Collection success with HIGH/CRITICAL, including CVSS decimals, **does not constitute security clearance**. Stage C still requires independently authenticated B, signed reviewer/owner dispositions, current trusted lifecycle, complete severe occurrence coverage and strict v2 finalization.
- The corresponding verifier correction is independently owned by Issue #94 / draft PR #95. **Do not dispatch real C or assert full-chain compatibility until #94 has been independently reviewed and merged into protected `dev`, followed by a deliberate one-time PR #84 reconciliation and fresh exact-head CI.** No verifier-source edits are made in PR #84.

## Synthetic validation and review boundaries

On the existing assigned branch, `python -m pytest tests/platform/test_ghcr_digest_security.py -q`; repository validation additionally runs all platform tests, actionlint, CodeQL, advisory Dependency Review and Trivy. Fixtures exercise A HIGH/CRITICAL evidence retention, v2 success under **mock verified** B inputs, UNKNOWN final rejection, missing/unmatched findings, exact review hash, wrong lock/scan/source/digest, stale review and incomplete upstream scope. They **do not** establish actual B reviewer/owner signatures or the protected environment. PR #93's separate tests verify Ed25519 semantics and lifecycle. The C workflow imports the integrated verifier's `require_r4_contract_v2` helper and independently re-runs its CLI against authenticated B and fresh owner-managed trust. Synthetic success does not replace actual attestations, keys, or lifecycle anti-rollback.

**Rollback:** this PR changes only a draft manual producer workflow and scripts, never images or user data. Disable the unapproved dispatch/arming variables and do not promote the code to `main` until separately reviewed. No root VERSION bump for preparatory security infrastructure.

**Merge/test note (2026-11-10):** PR #84's source branch was merged once with protected `dev` after #93 completed, preserving five producer-only changed files. New negative fixtures cover boolean schema versions, duplicate conflicting finding identities, exact B review hash/schema, protected environment and independent actor validation. Version remains 0.9.6; this is not a protected `dev` merge.
