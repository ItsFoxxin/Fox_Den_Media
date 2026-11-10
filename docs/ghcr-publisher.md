# GHCR candidate publisher and verifier — R3/R4

**Status:** implementation PR, not approval to publish. This design follows the
[merged artifact-first policy](release-1.0-checklist.md). R1/R2 validators merged into protected `dev` in PR #79. They must still
be included in a separately approved and fully checked `main` source SHA. All three first-party images must be built
from **one owner-approved immutable main commit**.

## Package names and roles

- Portal: ghcr.io/itsfoxxin/fox-den-media-portal
- Music web **and** worker: ghcr.io/itsfoxxin/fox-den-media-music
- Movies/TV: ghcr.io/itsfoxxin/fox-den-media-media

No fourth first-party package. NGINX, Firefox, Jellyfin, Gluetun and
qBittorrent stay on reviewed upstream registries. The publisher builds only
linux/amd64 for now. The root VERSION is not bumped by this PR.

## R3 — separate source approval, no release publication

The only trigger is **manual workflow_dispatch on main**, with the exact
40-digit approved commit SHA and a source-approval issue number. The workflow
checks the current remote main HEAD, root/Media version and changelog via R1,
the matching admin-managed authorization values, **an explicit current owner GO**
in the referenced issue, and GitHub's required main check-runs. An open issue
or repository variables alone are not source authorization. The writer job also requests the `ghcr-candidates` GitHub
Environment and rechecks the SHA/authorization before receiving its
job-specific `packages: write` token. It has no deployment credentials.

**Required GitHub settings, not configured by this PR:**

1. Create an environment named `ghcr-candidates`. Configure a required
   human reviewer and restrict permitted branches to protected `main`.
   Check whether your plan supports required reviewers; if not, leave the
   publisher disabled and choose an independently auditable approval process
   before enabling it. Never infer that naming an environment protects it.
2. Only after source promotion approval, set repository variables:
   `GHCR_CANDIDATES_ENABLED=true`,
   `GHCR_CANDIDATE_ENV_PROTECTED=true`,
   `GHCR_APPROVED_SOURCE_SHA=<approved exact main SHA>`,
   `GHCR_SOURCE_APPROVAL_ISSUE=<source-GO issue number>`.
   The `ENV_PROTECTED` variable is an operator assertion and **not**
   independent machine verification of environment review settings.
3. Verify protected main's exact post-merge required checks all passed.
   Check the source approval's scope and that it explicitly authorizes GHCR
   **candidate** creation. The repository owner must place exactly one
   standalone `GHCR-CANDIDATE-GO <40-hex-main-sha>` command in the referenced
   issue. A later `GHCR-CANDIDATE-REVOKE <same-sha>` rescinds that GO.
   The newest authenticated owner directive for the exact SHA must be GO
   both at preflight and immediately before the publisher obtains registry
   access. Missing, forged or revoked directives fail closed. Record owner,
   approval time and the source authorization URL.
4. Dispatch R3 **once** using the matching SHA/issue. It refuses to overwrite
   existing commit tags or proceed when registry responses are ambiguous.
   On partial publication, stop and inspect the existing digests — do not
   re-run with force, retag or silently rebuild.
5. Immediately disable the authorization variables after the authorized run.

**Build reproducibility prerequisite:** all three Dockerfiles still reference
mutable `python:3.12.13-slim-bookworm`. The updated R3 preflight now demands
one identical independently reviewed immutable
`python:3.12.15-slim-bookworm@sha256:<64-hex-digest>` in all three files.
No base digest was fabricated and the Dockerfiles were not modified. R3
publication remains blocked until the owner reviews and pins the real digest.

The publisher records image, source SHA, linux/amd64 manifest digest, GitHub
run ID and BuildKit provenance/SBOM. It also creates a GitHub-signed image
attestation for the *published digest*, preserving package linkage through
the repo's GITHUB_TOKEN and OCI source metadata.

The only candidate tag is `sha-<full-source-sha>`. **Never** use `latest`,
`1.0.0` or `v1.0.0` here. The digest, not the tag, is the release identity.
OCI image metadata includes repository/source, revision, description and
version. No license label is added until the licensing decision.

## R4 — shared, independently signed security evidence

The read-only `ghcr-verify.yml` now requires approved R3, original signed
scan collection A, independent review B, and finalized signed v2 producer C,
all on the same exact immutable approved `main` source. R4 independently
authenticates A/B/C workflow, run, signer and source identities and verifies
unchanged original Trivy/SPDX inputs against the complete R2 lock and the
reviewed owner-controlled disposition lifecycle.

R4 verifies the expected GitHub workflow/run/SHA, the security contract's
attestation identity, every first-party image's GitHub attestation, OCI
platform manifest, digest in the lock, policy decision and scan/SBOM subject.
It then runs isolated integration by pulling the locked images and removing
all local build directives before Compose up. Synthetic temporary secrets and
volumes are destroyed; no NAS or production credentials are used.

**Critical dependency:** merged Trivy PRs #72/#74/#77 still provide
*advisory, locally built image* scans, not release-digest acceptance.
Separate draft security producer PR #84 / issue #83 implements the
`trivy-digest-security.yml` interface; it has **not** been merged or
run against real R3 candidate images. Its draft A/C implementation
must pass independent review and be integrated into the separately approved
main source before R4 can consume real signed release evidence. Do not weaken that gate, forge "pass" records or treat an
R4 structural test as security acceptance.

The mandatory `schema_version: 2` scan-security contract retains every
original source, publisher, OCI, provenance, Trivy, SPDX, DB-age and
`exceptions=[]` policy binding, plus the exact `disposition_review`
extension from PR #93. Legacy scan-security v1 has **no fallback**.
Only independently authenticated, technically verified FIXED or NOT_AFFECTED
records may clear a HIGH/CRITICAL finding, and UNKNOWN always blocks.
The source exception-policy hash semantics remain `v1:` without waivers.

The R4 consumer now requires pass decisions, provenance verification and
checksummed SPDX/Trivy evidence for **every enabled upstream image**, in
addition to the three first-party subjects. No upstream exceptions are
implicitly accepted. These are required input conditions, **not completed
scans or dispositions**. A full signed A/B/C chain, original findings,
reviewed proofs, newest owner lifecycle and separate full-profile
acceptance remain mandatory.

## PR #93 — Independent v2 disposition integration

[Authoritative interface guide](https://github.com/ItsFoxxin/Fox_Den_Media/blob/5da5328c923f548794f7ee9568fd6c8c175dea13/docs/security-disposition-review.md).

The reviewer interface is separate from release security acceptance.
**A** collects complete unsuppressed original Trivy/SPDX bytes, signed
`context.json`, scanner, policy and complete R2 lock as artifact
`ghcr-security-contract-v2-inputs`. **B** independently verifies all findings
and human Ed25519 review/owner concurrence in a protected main-only workflow
and signs `disposition-verification.json` in artifact
`security-disposition-review-v1`. **C** consumes A and B, preserving original
reports, and signs the finalized `ghcr-security-contract-v2` with exact
`disposition_review`. A successful scan collection is never a pass decision.

At R4 acceptance, the workflow requires exact successful and distinct
authenticated A/B/C run IDs and expected signer workflow, current approved
source SHA, attested file-subject raw hash, independently authenticated scan
producer actor, current R2/OCI identities and source exception policy. The
trusted owner-managed review Environment must enforce required reviewers and
protected main. Review signer public keys, fresh signed lifecycle,
revocation/supersession, expiry, scanner age and every HIGH/CRITICAL
finding/proof are independently re-evaluated through the PR #93 verifier.
Producer-provided trust and stale lifecycle snapshots are not accepted.

The final C security contract names the review artifact ROOT file
`disposition-verification.json`. After validation, the R4 signed
`verification.json` adds the exact `disposition_review` extension with
`schema_version:1`, `artifact_name:security-disposition-review-v1`,
`verification_file:integration/disposition-verification.json`,
`verification_sha256`, `dispositions_sha256`, `review_workflow`,
`review_run_id` and `verified_at`.

The existing `foxden.r4.release-ready.v1` root envelope remains **unchanged**
with precisely `schema_version`, `version`, `repository`, `workflow`,
`source_sha`, `r3_run_id`, `r4_run_id` and `files`. The two existing
file maps (in `verification.json` and the signed root) include SHA-256 of
all the original copied disposition evidence:

| Required flattened signed path | Exact origin |
| --- | --- |
| `integration/disposition-verification.json` | Independently B-signed verification result |
| `integration/security-dispositions.json` | Original signed dispositions document |
| `integration/security-disposition-signatures.json` | Detached reviewer/owner signatures |
| `integration/disposition-proof-<slug>.json` | Every original `review/proofs/<slug>.json` |

The original disposition document uses a **canonical** SHA-256; bundle
file hashes cover the **raw original bytes**. Missing, duplicate, extra or
altered proofs, or missing signed-map entries, fail closed. No unsigned
sidecar and no competing R5 schema are introduced.

**Latest owner-state anti-rollback:** R4 requires an independently
provisioned protected read-only environment secret
`SECURITY_DISPOSITION_STATE_READ_TOKEN` to re-fetch GitHub Actions
repository variables and compare the latest owner-managed trust/lifecycle
snapshots immediately before acceptance. A missing credential, changed
newest state or inaccessible API fails closed. This PR provisions none of
these settings or credentials.

**External blockers:** PR #93's `scripts.verify_security_dispositions`
is not merged onto this branch, so R4 deliberately refuses real acceptance
until its independently reviewed verifier is available. PR #84 owns the
future A/C producers; PR #80 owns mandatory R5 independent review
revalidation. Protected Environment policy, owner Ed25519 trust/key
custody, independent submission transport, latest owner-signed lifecycle
publication and anti-rollback, actual severe-finding resolution, upstream
provenance and owner approvals remain unverified or absent.
No real CVE has been cleared by these synthetic integration changes.


## Package presentation, permissions and release boundaries

After the **first authorized** candidate push, open each GHCR package page:
verify that it is linked to `ItsFoxxin/Fox_Den_Media`, GitHub Actions has
only the access needed, and visibility is set deliberately. Public code
does not make packages automatically public. The connected GitHub tool
cannot inspect/manage every GHCR package setting or environment reviewer.

Source promotion GO, release publication GO and production NAS cutover GO
remain three separate approvals. R3 does not make version tags, R4 does
not publish or deploy, and this PR does not introduce R5 or R6.

## Exact independent security-producer handoff (PR #84 / issue #83)

The separate `.github/workflows/trivy-digest-security.yml` (not modified
by this PR) requires separately authorized original scan collection A
(`ghcr-security-contract-v2-inputs`) and finalized C
(`ghcr-security-contract-v2`), on the **same main SHA and authenticated R3**,
with independently signed review B (`security-disposition-review-v1`).
Expected C-relative paths:

| File | Required consumer binding |
| --- | --- |
| `security-contract.json` | Strict v2 fields, exact producer/source SHA/R3 run, scanner/policy, all first-party and enabled upstream decisions |
| `release-lock.json` | R2 v1 lock with full profile/service set and immutable SHA256 images |
| `rendered-release-compose.json` | **Sanitized** image-only Compose, no builds or sensitive environment values; maps exactly to lock |
| `scanner.json` | Trivy `Version=0.76.2`, positive integer `VulnerabilityDB.Version`, parseable UTC `UpdatedAt`, not future or older than 14 days |
| `reports/<name>.sbom.spdx.json` | SPDX package evidence; SHA-256 checksum matches signed v2 image entry |
| `reports/<name>.vuln.json` | Unsuppressed vulnerabilities; SHA-256 checksum matches signed v2 image entry |

`<name>` is exactly `portal`, `music`, `media` plus all enabled
upstreams from `nginx`, `browser`, `jellyfin`, `gluetun`,
`qbittorrent`. Music and Music Worker must map to the **same immutable**
Music package and digest. Every scan record must use the exact image digest
as both `scan_subject` and `sbom_subject` and report `decision=pass`,
`exceptions=[]` and separately verified provenance. An upstream image
without independently authenticated signer provenance is not accepted.

Final C attests seven JSON subjects: contract, context, lock, sanitized
Compose, scanner, exception ledger and the copied B verification result.
A separately signs its collection context, lock, rendered Compose, scanner
and policy; B signs its reviewed result. R4 authenticates exact signed
subjects via `gh attestation verify` (GitHub CLI >= 2.102.0), approved
source/workflow/run invocation, then reconstructs the complete review
against unchanged raw A/C Trivy/SPDX and owner-managed lifecycle. The security contract's
`policy_version` must be `v1:` plus the SHA256 of sorted-key,
compact-serialized `security/vulnerability-exceptions.json` checked out
at the approved source commit. No security exceptions, including otherwise
approved time-limited exceptions, are compatible with v2. R4 checks raw DB
schema version and matches the signed updated timestamp/version to the
contract; malformed or old DBs fail closed. This avoids inventing an
unreviewed contract v2 DB-version field while still verifying DB version.

All proof above is a **required runtime contract**, not evidence the
real release has passed it. Existing synthetic unit tests prove only
rejection/acceptance of artificial inputs.

## Remaining integration and owner settings

- **Draft PR #84** must pass independent review and merge with the same
  contract; the producer currently has an intentionally empty
  `security/upstream-provenance.json` allowlist. The owner must authenticate
  and approve real upstream provenance or keep the release blocked.
- R3 `ghcr-candidates` and producer `ghcr-security` must each be an actual
  protected GitHub Environment with enforced independent required reviewers
  and branch restriction to protected `main`. Repository flags claiming
  protection **do not** prove configuration. Admin must review those settings.
- R3 uses repo variables `GHCR_CANDIDATES_ENABLED`,
  `GHCR_CANDIDATE_ENV_PROTECTED`, `GHCR_APPROVED_SOURCE_SHA` and
  `GHCR_SOURCE_APPROVAL_ISSUE` only for a specifically authorized run;
  clear/disable afterward. R3 has `packages: write` **only** on
  the environment-gated candidate jobs. R4 has no package write capability.
- Before any main publication, pin and independently review identical
  Python base-image SHA256 digest in all three first-party Dockerfiles,
  verify all required checks on the exact source, and obtain source GO.
- **R4-to-R5 handoff is now implemented but not executed.** After every
  real R4 gate succeeds, `scripts/r4_release_ready.py` stages a canonical
  `foxden-r4-release-ready-v1.0.0` artifact with `release-ready.json`
  (`foxden.r4.release-ready.v1`) and SHA-256 bindings for all included
  evidence files. The R4 workflow authenticates and signs the exact root
  manifest bytes through GitHub OIDC before uploading that bundle. Draft
  R5 PR #80 verifies the independent R4 signer, source/workflow/run identity,
  schema and file hashes under its canonical
  `docs/r4-r5-release-ready-v1.schema.json` contract. No live R4 bundle or
  R5 acceptance exists until an authorized run satisfies all prerequisites.
- `main` currently uses `0.9.1`; a real `1.0.0` source, three
  candidate digests, passing security evidence and NAS/copy-state
  acceptance do not exist yet. Separate source promotion, release
  publication and NAS production approvals remain mandatory.
