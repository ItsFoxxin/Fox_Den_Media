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

**Build reproducibility prerequisite:** all three current Dockerfiles use the
mutable parent `python:3.12.13-slim-bookworm`. R3 now runs
`scripts/check_release_base_images.py` and will **reject** publication until
all three have been independently verified and updated to the same approved
`python:3.12.13-slim-bookworm@sha256:<64-hex-digest>` parent.
Pinning the commit alone does not freeze mutable base-image contents.

The publisher records image, source SHA, linux/amd64 manifest digest, GitHub
run ID and BuildKit provenance/SBOM. It also creates a GitHub-signed image
attestation for the *published digest*, preserving package linkage through
the repo's GITHUB_TOKEN and OCI source metadata.

The only candidate tag is `sha-<full-source-sha>`. **Never** use `latest`,
`1.0.0` or `v1.0.0` here. The digest, not the tag, is the release identity.
OCI image metadata includes repository/source, revision, description and
version. No license label is added until the licensing decision.

## R4 — shared, independently signed security evidence

The read-only `ghcr-verify.yml` requires a successful R3 run on the same
exact source and a successful **trusted**
`.github/workflows/trivy-digest-security.yml` producer run. It downloads
all three immutable candidate artifacts and the *signed* shared security
contract plus release lock and nonsecret rendered release Compose file.

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
run against real R3 candidate images. This remains a hard release dependency. R4 remains blocked until the separate security workstream creates
and tests it. Do not weaken that gate, forge "pass" records or treat an
R4 structural test as security acceptance.

Shared contract v1 fields: exact producer, source SHA, publisher run,
platform, pinned Trivy version/DB timestamp, policy version, and one entry
per first-party digest with platform digest, verified provenance, SPDX SBOM
subject/hash, vulnerability scan subject/hash, decision and exceptions.
This contract is consumed, **not generated**, by this PR's verifier. It
currently rejects nonempty exception lists until a separately approved,
expiring, issue-linked exception policy is wired in.

The R4 consumer now requires pass decisions, provenance verification and
checksummed SPDX/Trivy evidence for **every enabled upstream image**, in
addition to the three first-party subjects. No upstream exceptions are
implicitly accepted. Because the separate digest-security producer does
not yet exist, these are required input conditions, **not completed scans**.
Final release-lock approval needs the owner-approved vulnerability exception
process, any required full-profile acceptance and independently retained
evidence for each digest.

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
by this PR) must be a successful, owner-approved, completed manual run on
the **same current main SHA and authenticated R3 run**. R4 downloads its
`ghcr-security-contract-v1` artifact. Expected relative paths:

| File | Required consumer binding |
| --- | --- |
| `security-contract.json` | Strict v1 fields, exact producer/source SHA/R3 run, scanner/policy, all first-party and enabled upstream decisions |
| `release-lock.json` | R2 v1 lock with full profile/service set and immutable SHA256 images |
| `rendered-release-compose.json` | **Sanitized** image-only Compose, no builds or sensitive environment values; maps exactly to lock |
| `scanner.json` | Trivy `Version=0.76.2`, positive integer `VulnerabilityDB.Version`, parseable UTC `UpdatedAt`, not future or older than 14 days |
| `reports/<name>.sbom.spdx.json` | SPDX package evidence; SHA-256 checksum matches signed v1 image entry |
| `reports/<name>.vuln.json` | Unsuppressed vulnerabilities; SHA-256 checksum matches signed v1 image entry |

`<name>` is exactly `portal`, `music`, `media` plus all enabled
upstreams from `nginx`, `browser`, `jellyfin`, `gluetun`,
`qbittorrent`. Music and Music Worker must map to the **same immutable**
Music package and digest. Every scan record must use the exact image digest
as both `scan_subject` and `sbom_subject` and report `decision=pass`,
`exceptions=[]` and separately verified provenance. An upstream image
without independently authenticated signer provenance is not accepted.

The producer's attestation step signs four separate top-level JSON files:
contract, lock, sanitized Compose and raw scanner metadata. R4 now verifies
the exact downloaded bytes of **all four** using
`gh attestation verify` (GitHub CLI >= 2.102.0, exact signed workflow,
source ref and SHA). The security contract's
`policy_version` must be `v1:` plus the SHA256 of sorted-key,
compact-serialized `security/vulnerability-exceptions.json` checked out
at the approved source commit. No security exceptions, including otherwise
approved time-limited exceptions, are compatible with v1. R4 checks raw DB
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
- R5 draft PR #80 expects an additional,
  separately authenticated `foxden-r4-release-ready-v1.0.0` bundle.
  R4 currently verifies but **does not produce that R5 artifact**.
  Agree a canonical schema/bundle with the R5 worker before either
  workstream can be marked release-ready.
- `main` currently uses `0.9.1`; a real `1.0.0` source, three
  candidate digests, passing security evidence and NAS/copy-state
  acceptance do not exist yet. Separate source promotion, release
  publication and NAS production approvals remain mandatory.
