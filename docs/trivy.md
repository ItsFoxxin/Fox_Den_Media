# Trivy image scanning and SBOMs

**Status:** Advisory CI security evidence for release 1.0.0 readiness, not production approval.
Tracking: [issue #71](https://github.com/ItsFoxxin/Fox_Den_Media/issues/71).
This guide extends [CI](ci.md) and [security](security.md); it does not replace CodeQL, Bandit, pip-audit, Dependency Review, secret-history scanning or Dependabot.

## Scope and execution

The independent `.github/workflows/trivy.yml` runs on PRs targeting `dev` or `main`, pushes to those branches, and manual dispatch. It uses read-only repository permissions and cancels superseded runs. There is no automated schedule at initial rollout; add a daily/weekly scan only after DB availability, runner cost, and baseline triage have been assessed.

One build and scan per PR/push for each current **first-party application Dockerfile**:

| Component | Docker build context | Image under scan |
| --- | --- | --- |
| Portal | `apps/portal` | `foxden-ci-portal:<source SHA>` |
| Music web and worker | `apps/music/backend` | `foxden-ci-music:<source SHA>` |
| Movies/TV | repository root | `foxden-ci-media:<source SHA>` |

The Music web and worker use one image; scanning it twice would be redundant. Trivy inspects the **built images**, their OS packages and language-specific dependency inventory, including inherited base layers. Builds use `--pull`, so an upstream mutable base tag can change between runs; the local image ID and build source SHA are recorded. This does not constitute a production release-image digest or guarantee that multi-architecture upstream images have identical findings. The existing integration smoke setup references a historical Music source and cannot substitute for scanning the current Music Dockerfile.

**Not scanned:** the host/NAS or its mutable volumes; running services; the deployment's environment files; live VPN behavior; image provenance/attestation; other architectures; images not built by these Dockerfiles; secret detection or SAST (covered separately). This scan is not proof that a service is safe to deploy.

### Upstream deployment images

The Compose deployment additionally uses `nginx` ingress, `jellyfin/jellyfin`, `jlesage/firefox`, `lscr.io/linuxserver/qbittorrent` and `qmcgaw/gluetun`. Firefox and qBittorrent currently have digest references in the Compose defaults, while other upstream defaults are mutable tags. These are **not** included in every PR scan. Before source/publishing approval, inventory each actually selected upstream reference, architecture and immutable digest; scan those exact digests in a separate, deliberately invoked upstream review and retain one report and SBOM per image. Do not infer supply-chain trust from a clean vulnerability report. No optional images are pulled in this workflow.

## Evidence and advisory behavior

Each component job uploads a 21-day GitHub Actions artifact named `trivy-<component>-<run ID>` with:

- `vulnerabilities.json`: complete machine-readable Trivy OS/application findings, including CVE, severity, affected/installed package, and fixed version when known;
- `sbom.cdx.json`: CycloneDX SBOM with vulnerability scanning enabled;
- `summary.json` and `summary.md`: counts by severity, known fix, no known fix, image ID and scanned source SHA;
- `baseline.json`: normalized, per-component vulnerability identities suitable for manual baseline comparisons.

View the job summary under **Actions → Trivy first-party images (advisory)** and retrieve the artifacts from that same run. A **zero-finding report is not evidence of successful scanning** unless the Trivy invocation and artifacts succeeded. The scan explicitly uses `--exit-code 0` for findings, while a build, scanner, JSON parser, or upload failure remains an actual failing **advisory** check. Neither Trivy job nor its status is a required ruleset check, and it does not affect `Monorepo strict gate` or CodeQL. Do not ignore a scanner infrastructure failure merely because the check is advisory.

Artifact contents may disclose package inventories, base-image and software versions. Never scan secret-bearing production build contexts, embed credentials in Dockerfiles, or upload exported NAS state. CI uses only source checkout and intentionally does not provide deployment secrets.

## Vulnerability triage and exception policy

1. Review every **CRITICAL** finding immediately and identify exploitability, exposure and supported remediation. Track any material 1.0 release blocker in issue #18 and a focused issue. Review **HIGH** findings before the next candidate merge/release and remediate fixable findings promptly. `MEDIUM` and `LOW` go in a scheduled backlog, prioritized by exposure, reachability and fix availability. Do not treat the scanner's severity as proof of exploitability.
2. For each finding, record component, CVE/advisory, OS or application package, installed version, fixed version if available, exact source/image ID, severity, reachable attack surface, and authoritative advisory/upstream context. Prefer upstream base-image/package fixes; avoid direct ad-hoc system package upgrades inside production images without compatibility tests.
3. **No fix available** means track, assess mitigations and recheck on later scans; it is **not** an automatic exemption. Reassess accepted risks when a fix appears, exposure changes, or new exploit information arrives.
4. False positives or accepted risks require a tracked, time-limited issue or security register entry with rationale, compensating controls, asset/version scope, reviewer/owner, date, **expiry date** and next-review trigger. Revalidate before release; default no standing `.trivyignore` or global severity suppression. If a targeted exception is approved later, pin it to the finding/CVE and affected component and remove it on expiry. Keep original unsuppressed JSON evidence.
5. A report is advisory, not permission to publish or deploy. For 1.0 source/publishing decisions, explicitly disposition outstanding critical/high and inherited/upstream CVEs in the release blocker register.

## Baseline and newly introduced findings

Use the **first successful protected-`dev` scan** as the approved baseline, recording its URL, SHA, Trivy version and vulnerability DB date. Do not claim a baseline merely because this workflow or PR exists. A PR's merge commit may have different source/image IDs from a protected-`dev` build; normalized vulnerability keys are CVE + package ecosystem + package + installed version. This reveals newly detected and no-longer-detected findings but is not proof of the change that caused them: OS base refresh and vulnerability database updates can change results. Confirm deltas against both evidence sets and record both DB dates.

Download `baseline.json` from the same-component trusted `dev` artifact, then reproduce a PR report locally or download its `vulnerabilities.json` and run:

```bash
python scripts/trivy_report.py --input ./vulnerabilities.json \
  --output-dir ./trivy-review --component portal \
  --image foxden-ci-portal:review --image-id sha256:review --source-sha REVIEW_SHA \
  --baseline ./trusted-dev-baseline.json
cat ./trivy-review/summary.md
```

This writes `delta.json` with new, resolved and unchanged keys. Review database drift, severity and fix-version changes even for unchanged identities. No automatic baseline subtraction/ignore policy is enabled in the first phase; doing so without trusted provenance could hide new issues.

## Local reproduction and tool update

From the repository root on a trusted Linux amd64 workstation with Docker and `curl`:

```bash
bash scripts/install_trivy.sh /tmp/foxden-trivy-bin
docker build --pull -f apps/portal/Dockerfile -t foxden-ci-portal:local apps/portal
/tmp/foxden-trivy-bin/trivy image --scanners vuln --format json \
  --exit-code 0 --output /tmp/portal-vulnerabilities.json foxden-ci-portal:local
/tmp/foxden-trivy-bin/trivy image --scanners vuln --format cyclonedx \
  --exit-code 0 --output /tmp/portal-sbom.cdx.json foxden-ci-portal:local
python scripts/trivy_report.py --input /tmp/portal-vulnerabilities.json \
  --output-dir /tmp/portal-trivy-report --component portal \
  --image foxden-ci-portal:local \
  --image-id "$(docker image inspect -f '{{.Id}}' foxden-ci-portal:local)" \
  --source-sha "$(git rev-parse HEAD)"
```

For Music use `docker build --pull -f apps/music/backend/Dockerfile -t foxden-ci-music:local apps/music/backend`; for Movies/TV use `docker build --pull -f apps/media/Dockerfile -t foxden-ci-media:local .`. Do not use production bind mounts or secret-laden build args.

The installer downloads **official Trivy v0.76.2** from the `aquasecurity/trivy` GitHub release. It SHA-256 verifies the release checksum manifest against the fixed value in `scripts/install_trivy.sh`, then verifies the archive against that manifest; it does not run an unversioned remote install script. Review official release notes/security notices, update both version and checksum-manifest hash, verify provenance, run actionlint and safe parser fixtures, re-run actual image scans and assess changed results. Scanner vulnerability DB updates are separate from the pinned executable; record the DB age/details in assessment evidence.

## Before considering mandatory enforcement

Keep advisory until real GitHub runs prove all three Dockerfile builds, scans, CycloneDX validity, artifact retrieval, parser clean/finding fixtures, baseline comparison and stable performance. Investigate DB/network failures and available fixes, explicitly review approved exceptions and expiry controls, ensure third-party release digests are assessed, and define an enforceable **new critical/high** (or documented severity) policy with trusted baseline acquisition and regression tests. Require the owner's approval **before** adding new required checks or changing branch rulesets. Do not introduce CI-to-NAS or GHCR publishing permissions as part of this workflow.
