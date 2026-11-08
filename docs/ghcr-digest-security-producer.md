# Trusted immutable GHCR security evidence producer (issue #83)

**Status: implementation only, NOT real release evidence or approval to publish/deploy.**
This is a separate, manual R4 producer for draft PR #81's **strict**
`ghcr-security-contract-v1` consumer. The existing `trivy.yml` advisory
Dockerfile builds, Trivy PR reporter and `security_contract.py` assessment
are untouched. Source of truth for time-bounded exceptions remains
`security/vulnerability-exceptions.json`. Issue #76 owns remediation.

## Separation and prerequisites

1. Merge reviewed R1/R2 PR #79 and R3/R4 PR #81 into `dev` only after
   owner approval and separately promote the approved source to `main`.
   Neither release workflows nor this producer are runnable on this PR branch.
2. Obtain an **authorized, successful R3** `ghcr-candidates.yml`
   `workflow_dispatch` on the exact current approved `main` SHA. R3 must
   have created **all three digest-identified candidate artifacts**:
   `ghcr-candidate-portal`, `ghcr-candidate-music`,
   `ghcr-candidate-media`; Music web and worker share the Music digest.
   There are currently no approved 1.0.0 candidate images to assess.
3. After R3, an owner reviews a complete R2 JSON release lock, the
   `linux/amd64` platform manifests, selected profiles, rollback digest
   and a **sanitized image-only** rendered Compose JSON. All enabled upstream
   images must be digest-locked, not mutable tags or implicit aliases.
4. **Before approving/promoting the source SHA to main**, commit reviewed
   `security/upstream-provenance.json` entries for **each intended upstream
   image**. Upstream digests and signer identities can be selected before R3;
   changing this file after R3 would change the approved main SHA and
   invalidate the R3 run.
   Its default `upstream: {}` is deliberately **non-accepting**: if nginx
   has no exact signer metadata, this workflow stops before scanning.
   Each entry is keyed by `nginx`, `browser`, `jellyfin`, `gluetun` or
   `qbittorrent` and contains:
   `ref` (full exact registry digest),
   `source_repo` (GitHub owner/repository),
   `source_sha` (signed source commit),
   `source_ref` (signed branch/tag),
   `signer_workflow` (full GitHub Actions workflow path in that repo).
   **Never invent a signer.** If an upstream image lacks a verifiable
   GitHub OCI attestation, R4 is blocked pending owner-approved support for
   another independently authenticated provenance scheme; marking it
   `verified` without proof is prohibited.

## Manual environment and operator inputs

Set a **required-reviewer** GitHub environment named `ghcr-security`,
restricted to protected `main`. If reviewer enforcement is not supported
on the account plan, do not enable this release gate. Confirm the settings
in GitHub independently; the environment name/variable alone is not proof.

For a single separately approved source/run only, set the following
repository variables (not secrets or public deployment environment values):

| Variable | Required exact value |
| --- | --- |
| `GHCR_SECURITY_ENABLED` | `true`, manually armed for one approved run |
| `GHCR_SECURITY_ENV_PROTECTED` | `true`, verified by owner in GitHub UI |
| `GHCR_SECURITY_APPROVED_SOURCE_SHA` | 40-hex approved current main commit |
| `GHCR_SECURITY_LOCK_B64` | Base64-encoded complete nonsecret R2 lock JSON |
| `GHCR_SECURITY_RENDERED_B64` | Base64-encoded image-only rendered Compose JSON |
| `GHCR_SECURITY_LOCK_SHA256` | SHA-256 hex checksum of raw lock bytes |
| `GHCR_SECURITY_RENDERED_SHA256` | SHA-256 hex checksum of raw rendered JSON bytes |

Use `base64 -w0 release-lock.json` and `sha256sum release-lock.json` on
a trusted local workstation to prepare the lock values. The **rendered JSON
is a minimal `{"services": {"portal": {"image": "<digest-ref>"}, ...}}`**:
no environment, passwords, bind paths, volumes, labels, build or user state.
R2 validates against `deploy/compose.yaml`; the producer separately rejects
any extra rendered data. Do not upload a real `docker compose config`
containing secrets. GitHub variables have size limitations; fail rather
than truncate or switch to unreviewed external artifact URLs.

Dispatch `trivy-digest-security.yml` only on `main` with
`source_sha` and `publisher_run_id` matching the explicitly reviewed R3
run. The job authenticates R3 run identity, SHA, path, branch, event and
success via GitHub API and downloads the **exact** candidate artifacts.
The GitHub CLI must be >=2.102.0 for exact `--signer-workflow`
matching; an older CLI is a hard failure. The operator disables the arming
variables afterward. There is no triggered PR/build/push/publishing event.

## Security procedure (blocking)

- Calls the **authoritative** R2 validator from PR #79. Missing validator,
  changed source/Compose, unexpected profile/service or digest fails.
- Requires all three first-party images, ingress and every upstream image
  enabled by the lock. Rejects missing signer metadata, wrong candidate
  source/publisher, altered amd64 manifest, registry mismatch, no image,
  malformed/duplicate platform or extra service/build directives.
- Uses the existing SHA-256-verified Trivy `0.76.2` installer. Pulls and
  scans exact `<registry>@sha256:<manifest-index>` with Docker, without
  building, pushing or using mutable tags. Includes OS/application
  vulnerabilities and produces Trivy JSON and SPDX 2.3 per image.
- Before assessment, `gh attestation verify oci://...` must independently
  authenticate **every** image's signer workflow, source ref and commit;
  first-party must match R3 publisher workflow. The manifest index,
  platform digest, Docker image config ID and Trivy report subject are
  checked separately. Image signatures, not source JSON, establish provenance.
- Enforces Trivy version, a nonmissing parseable vulnerability DB timestamp
  not future-dated or older than 14 days, complete unsuppressed report,
  package-containing SPDX SBOM, exact scan subject, and per-file SHA-256 hashes.
  The tool's raw scanner JSON is retained for DB version/details.
- HIGH, CRITICAL and UNKNOWN severity cause hard failure; missing evidence,
  malformed CVE/package identities and any nonempty exception ledger fail
  without producing a passing signed contract. This **intentionally blocks**
  even otherwise approved exceptions: PR #81 v1 requires `exceptions: []`.
  Owner-approved, issue-linked, expiring exceptions cannot pass R4 until the
  consumer is independently extended and tested. No suppression or
  `.trivyignore` is introduced.
- Only after *every* scan and check passes, signs `security-contract.json`
  using GitHub OIDC `actions/attest`, then uploads
  `ghcr-security-contract-v1`. The producer has `packages: read`, not write.
  R4 separately verifies run identity and GitHub attestation before reading
  the artifact. No GitHub release/tag, GHCR publication or NAS operations.

## Consumer interface: exact PR #81 artifact layout

| Inside `ghcr-security-contract-v1` | Role |
| --- | --- |
| `security-contract.json` | Strict R4 consumer schema v1 (source, publisher, scanner, signed policy, images/upstream) |
| `release-lock.json` | Complete R2 lock, all enabled profiles and digest subjects |
| `rendered-release-compose.json` | Sanitized, build-free, image-only Compose render |
| `reports/<name>.sbom.spdx.json` | Trivy SPDX SBOM, bytes hashed as `sbom_sha256` |
| `reports/<name>.vuln.json` | Unsuppressed Trivy findings, bytes hashed as `vulnerability_report_sha256` |
| `reports/<name>.manifest.json` | Observed OCI index for amd64 platform verification |
| `reports/<name>.image-id` | Inspected local image config ID; matches Trivy Metadata.ImageID |
| `scanner.json` | Raw Trivy version/database metadata including database version when present |

Names cover `portal`, `music`, `media`, plus exactly the enabled subset
of `nginx`, `browser`, `jellyfin`, `gluetun`, `qbittorrent`.
`security-contract.json` has no extra properties because R4's consumer
rejects them. `policy_version` is `v1:<SHA256 of canonicalized reviewed
exception ledger>`; scanner name/version/DB timestamp are exact consumer
fields. A successful synthetic contract is **not** a real signed release
artifact. The workflow never emits a signed contract on failure.

## Verification and unresolved integration decisions

Run `python -m pytest tests/platform/test_ghcr_digest_security.py -q`,
then the existing Monorepo CI, CodeQL, Dependency Review and actionlint.
Fixtures cover a complete good contract, wrong source/lock/publisher,
manifest drift, missing reports, altered scan subject, unsatisfied optional
upstream scope, unsupported signer, incomplete SPDX, stale database,
HIGH/CRITICAL/UNKNOWN and rejected exceptions. They do not claim live GHCR
scan, signed OCI provenance, protected environment, or R3 publication.

For the PR #81 worker: verify `scripts/verify_image_security.py` accepts
this exact v1 file layout and `ghcr-verify.yml` fetches the same artifact
and verifies exact `trivy-digest-security.yml` signature. The R4 consumer
currently records only DB update time; the producer also uploads raw
`scanner.json`, but its DB version cannot be added to the strict
contract without an approved matching consumer schema revision. Also assess
whether Docker Hub/LSCR upstream images offer signed provenance that
`gh attestation verify` can authenticate. Resolve these *as coordination
items*, not by changing PR #81's branch without its owner's review.

Real 1.0.0 release readiness remains blocked by source/R3 approval,
current R2 lock, complete approved upstream signer identities, current
database scans, issue #76 vulnerability disposition, successful trusted
producer attestation, R4 no-rebuild acceptance, issue #18 and separate
release/NAS approvals.
