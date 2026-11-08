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


## Phase 2 — Trusted PR summaries and automation

**Dependency:** PR #72 is required. Until it merges, Phase 2 is stacked on its head and the Phase 2 PR targeting dev shows Phase 1 and Phase 2 changes. No Phase 1 code is overwritten. The trusted reporting workflow is activated only after the workflow file exists on **the default main branch**; merging only into dev can test it but cannot demonstrate live workflow_run publication. Promotion to main requires the separate existing approval process.

### Trust boundary, output and GitHub permissions

The regular Trivy workflow stays read-only and uploads scan JSON, CycloneDX SBOM, component baseline files, and a new trivy-version.json recording scanner and vulnerability DB update time. The separate trivy-publish.yml consumes completed workflow_run data and checks out only trusted main code. It has job-level contents:read, actions:read and issues:write, with no deployment credentials, registry publishing or security-events permission. PR source code is never executed with write permissions.

The publisher verifies repository, workflow, PR identity, current head SHA, completed status, artifact provenance, exactly three component artifacts, expected source merge SHA, image ID, scanner version, recomputed counts, CycloneDX structure and ZIP limits. It skips fork PRs, closed PRs and superseded runs. It rejects scan workflow or scanner-installer modifications compared with protected dev. Failed or incomplete scans cannot appear clean.

After successful publication the PR receives one **bot-authored** updateable comment, recognized by hidden marker foxden-trivy-pr-v1. It lists PR and SHA, run link, scanner and vulnerability DB version/date, scan status, image identities, severity/fixability counts, new/resolved counts, baseline status, advisory policy, and artifact links. No hundreds-of-CVEs comment dump. It updates its own comment, never a human comment.

### Automation-owned labels

| Label | Color | Meaning |
| --- | --- | --- |
| security: review-required | D4A017 | Invalid/missing/stale baseline, failed scan or new high/critical vulnerability |
| security: new-critical | B60205 | Newly observed or escalated critical findings against trusted dev |
| security: new-high | D93F0B | Newly observed or escalated high findings against trusted dev |

The default-branch reporter **will create** these three labels with descriptions when they are first required if they are missing. They are not created by an unmerged branch. Only these three reserved names can be added or removed by automation; operators must not manually apply them. Existing type, area, priority, needs-testing, release-blocker and Dependabot labels remain untouched. On baseline failure, no severity label is assigned as new solely due to inherited OS CVEs; review-required remains.

### Trusted dev baseline

The first completed successful push scan on protected dev following Phase 1 approval is the candidate. The reporter verifies the baseline workflow and repository, protected dev ancestry, run conclusion, artifact ownership, three image identities and valid JSON. It rejects unavailable baselines (missing), outdated baselines (older than 14 days, stale) and malformed baselines (invalid). It never promotes an untrusted PR report as dev baseline. Relative changes use CVE plus ecosystem plus package plus installed version, per component, with severity escalations separately detected. A vulnerability DB update or upstream --pull refresh may produce newly observed CVEs unrelated to source code changes; the report records DB freshness and makes no causal attribution.

### Remediation issue proposal (not yet automatic)

Do not open an issue for every CVE. Triage confirmed critical findings, fixable high, externally reachable packages, shared vulnerable packages and 1.0 blockers. Propose one reviewed remediation issue per actionable package/advisory group, deduplicated using ecosystem + advisory ID + package/version, with all affected image/components recorded. Each issue should include CVE, installed/fixed version, evidence run/Image ID, severity/exposure, remediation, regression tests, owner and exception expiry when applicable. Reuse type: security, relevant area, assessed priority and needs-testing appropriately. Maintain #18 as the consolidated release blocker register. No unrestricted automatic issue creation has been enabled.

### SARIF and scheduled scanning decisions

**SARIF: deferred.** Trivy can generate SARIF for GitHub Code Scanning in public repositories, but an upload introduces security-events:write and may flood code scanning with OS packages lacking meaningful source-file locations, overlapping CodeQL and Dependency Review. Review code-scanning alert volumes, stable identities and deduplication first. See https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/integrate-with-existing-tools/upload-sarif-file . CodeQL is not modified.

**Weekly scans: deferred.** A scheduled --pull rebuild could conflate new CVEs with mutable upstream base images and consume extra Actions minutes. Before adding a weekly scan, approve an immutable image/digest inventory, define DB-age and artifact retention rules, and benchmark a protected-dev snapshot scan. No automatic build, dependency upgrade, issue flood or NAS deployment is scheduled by Phase 2.

### Validation boundaries

Phase 2 regression fixtures validate clean/finding scans, high/critical deltas, resolved and escalated CVEs, missing baselines, different image identities, corrupt or duplicated artifacts, comment upserts, label ownership/idempotency, stale and closed PRs, fork rejection, and simulated missing permissions. This is **mock/fixture coverage**, not evidence that the trusted workflow has actually posted a GitHub comment. Real publication requires both workflows on default main and a controlled reviewed PR test; it cannot be marked verified while PR #72 and Phase 2 remain unmerged.

## Shared security contract for future release checks

The per-image artifact also contains `security-contract.json`, generated from the **same** Trivy report, CycloneDX SBOM, scanner metadata and versioned exception ledger. See [security contract and exception policy](security-contract.md). The current decision is **advisory**, even when `policy.decision=fail`: no finding has been implicitly exempted and this is not a release approval. The existing Phase 2 PR reporting and protected-dev baseline checks remain separate and unchanged. Future exact GHCR digest and upstream-image release enforcement is not active.
