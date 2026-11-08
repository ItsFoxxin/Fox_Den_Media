# Fox Den Media GHCR and release lock (R1/R2)

This is **pre-release implementation groundwork**, not approval to promote
source, publish packages, tag 1.0.0, or deploy to the NAS. The governing
documents are [the merged release policy](release-1.0-checklist.md) and
[the R1–R6 design](release-publishing-1.0-design.md).

## Package inventory

| Runtime | Repository |
| --- | --- |
| Portal | ghcr.io/itsfoxxin/fox-den-media-portal |
| Music web and worker — identical digest | ghcr.io/itsfoxxin/fox-den-media-music |
| Movies/TV | ghcr.io/itsfoxxin/fox-den-media-media |

NGINX, Firefox, Jellyfin, Gluetun and qBittorrent remain upstream. The
release lock requires a digest-only reference for **every enabled image**;
linux/amd64 is the initial supported architecture. Build references and tags
are not release identities. The original Compose continues to support local
builds; a release-rendered Compose must **remove all build directives** and use
only digest-qualified image names.

## R1: metadata and exact source

The normal read-only metadata check is `python scripts/check_release.py`.
After independently verifying the current protected main commit and obtaining
a separately signed-off source SHA, run:

```bash
python scripts/release_metadata.py --version 1.0.0 \
  --source-sha "$APPROVED_MAIN_SHA" --main-head "$ACTUAL_MAIN_HEAD"
```

Checks: strict version, matching root/Media VERSION, the current source
milestone in README, one calendar-valid dated changelog section, the Compose
MEDIA_IMAGE default, and the Media Dockerfile version copy.
The caller **must obtain** main HEAD from GitHub, not accept two untrusted
equal inputs. Release CI/check results and explicit approvals are separate.

## R2: offline versioned lock

`docs/release-lock-v1.schema.json` defines the structural JSON format.
`scripts/release_lock.py` enforces additional cross-field invariants.

The lock contains `schema_version=1`, version, exact source SHA,
`compose_sha256`, platform, enabled profiles, images, services, publisher
identity and previous rollback lock SHA. For every enabled image it records
the exact registry digest and linux/amd64 platform digest; first-party images
must carry the same source SHA. Music and Music Worker map to one image.
Extra fields are rejected to avoid accidentally storing secrets. The rollback
version must predate the candidate release. The CLI requires a verified source
SHA, the authoritative Compose file, and a build-free rendered Compose JSON;
synthetic unit fixtures exercise the internal validator without these inputs.

Check a future completed lock against the exact source Compose and a private,
**build-free**, already-rendered Compose JSON:

```bash
python scripts/release_lock.py release-lock.json --compose deploy/compose.yaml \
  --rendered "$PRIVATE_RENDERED_COMPOSE" --source-sha "$APPROVED_MAIN_SHA"
```

Never upload expanded real Compose files to public CI artifacts; they can
contain environment secrets. A valid R2 lock does **not** prove the registry
has images or that security checks have passed. The actual lock will only be
populated once R3 has produced immutable candidate digests. To run fixtures:

```bash
python -m pytest tests/platform/test_release_lock.py -q
```

## R3/R4 future execution gates

R3 must only run on a manually authorized **exact main SHA** after owner
source-promotion approval, required CI and a protected candidate-publisher
environment. The publisher is never triggered by PRs, Dependabot, or a
development merge. R4 must verify the same published digests against
provenance, the shared Trivy/SBOM contract, image architecture, policy, and
a real image pull + integration without rebuilding. The Trivy/SBOM security
workstream (#72, #74 and #77) is now merged into dev, but its existing
built-image scans are still advisory; published-digest verification and
release-blocking security evidence remain separate R4 dependencies.

OCI package metadata should include source URL, revision, release version and
a concise description; omit a license label pending a licensing decision.
Prefer publishing with the repository's GITHUB_TOKEN and the OCI
`org.opencontainers.image.source` label so GitHub can link packages back to
this repository. After a first authorized push, a maintainer must check
**each package's** repository linkage, visibility and access settings.
Public repository visibility does not imply public package visibility.

Separate approvals are required for source promotion, release publication
and production NAS cutover. These schema/fixture changes grant none of them.

## Compatibility and ownership

This PR intentionally leaves `VERSION=0.9.6`, root/Media Dockerfiles,
`deploy/compose.yaml`, version-policy rules, deployment profiles, and all
security workflows unchanged. Offline tests compare lock service/profile
inventory and shared Music image/build inputs with the live Compose structure.
The R1 `1.0.0` check is exercised using synthetic fixtures until a separately
approved source promotion sets exact release metadata on protected main.

The future R5 publication workstream (#80) currently expects a different
release-lock data layout from this v1 schema. Align the versioned producer and
consumers in separate coordinated PRs before executing R3/R4/R5. Do not silently
rewrite the R2 schema or treat an advisory Trivy pass as release authorization.
