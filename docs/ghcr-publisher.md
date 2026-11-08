# GHCR candidate publisher and verifier — R3/R4

**Status:** implementation PR, not approval to publish. This design follows the
[merged artifact-first policy](release-1.0-checklist.md). The R1/R2 validators
are supplied separately by PR #79. All three first-party images must be built
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
the matching admin-managed authorization values and GitHub's required main
check-runs. The writer job also requests the `ghcr-candidates` GitHub
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
   **candidate** creation. Record owner, approval time and link.
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

**Critical dependency:** PR #72 is still an advisory *built-local-image*
scan. It does NOT currently produce an attested, blocking digest-security
contract, approved vulnerability/exception ledger, fully pinned upstream
image evidence, or an R2-complete signed lock. The R4 producer path above
is a **required integration contract**, not a claim that this producer
exists. R4 remains blocked until the separate security workstream creates
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
