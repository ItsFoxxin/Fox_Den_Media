# GitHub Security and Quality readiness — 1.0.0

**Snapshot:** 2026-11-07; checked against protected `dev` at `91f7fb0e0088b3b4ae00cec116b881f82ae4d86e`, repository metadata and branch rulesets. **This is not a live alert API export, approval to merge, or release authorization.** Reverify before 1.0 promotion.

Status meanings: **Verified enabled** = directly observed configuration or recent execution; **Verified missing** = confirmed absent in the checked branch/settings; **Unverifiable** = current GitHub connection lacks the private setting/alert endpoint; **Planned** = proposed but unmerged.

## Native feature and configuration matrix

| Feature | Observed state | Evidence and next step |
| --- | --- | --- |
| Repository visibility | Verified public | GitHub repository metadata |
| CodeQL / code scanning execution | Verified enabled | `.github/workflows/codeql.yml` analyzes Python and JavaScript/TypeScript using `security-extended`; passing PR #72 and #74 workflow runs. **Open dashboard alerts are not retrievable via this connection** |
| Dependabot version updates | Verified active | `.github/dependabot.yml` and multiple live Dependabot update PRs; coverage documented in `docs/dependabot.md` |
| Dependabot vulnerability alerts | Unverifiable | Check Security > Dependabot > Alerts; no active count or dismissal assertions |
| Dependabot automatic security updates | Unverifiable | Verify separate security-update switch; routine version-update PRs do not prove this setting is on |
| Dependency Review | Verified advisory | `.github/workflows/dependency-review.yml`, high/critical findings with `warn-only: true`; **not a required check**; rollout tracked by [#70](https://github.com/ItsFoxxin/Fox_Den_Media/issues/70) |
| GitHub secret scanning | Unverifiable | Verify native secret scanning and alert status in Security / Settings; it is **not** the same as the confirmed custom full-history scanner |
| Custom secret-history scan | Verified enabled | `scripts/scan_history_secrets.py` runs in the Monorepo validation job |
| Secret scanning push protection | Unverifiable | Check Settings > Advanced Security / Secret scanning; do not infer enabled from custom scan |
| Private vulnerability reporting | Unverifiable | Verify GitHub Security > Advisories > private vulnerability reporting setting and public `Report a vulnerability` control |
| Repository security advisories | Unverifiable | Advisory creation and repository advisory inventory are not exposed by the connection |
| Branch ruleset — `dev` | Verified active | [Ruleset 26664707](https://github.com/ItsFoxxin/Fox_Den_Media/rules/26664707): PR-only, prevent deletion/non-fast-forward, require resolved review threads, strict checks `Monorepo strict gate` and CodeQL Python/JS; **0 mandatory approvals** |
| Branch ruleset — `main` | Verified active | [Ruleset 26667058](https://github.com/ItsFoxxin/Fox_Den_Media/rules/26667058): same protections, plus an additional `CodeQL` check; **0 mandatory approvals** |
| Tag ruleset | Verified missing | Repository ruleset collection has no tag-target ruleset; recommend owner review before release tags (no change made) |
| Recognized security policy | Verified missing on `dev` and `main` | No root `SECURITY.md`; this PR proposes one |
| Contribution policy | Verified missing on `dev` | No root `CONTRIBUTING.md`; this PR proposes one |
| Issue / PR templates | Verified present | `.github/ISSUE_TEMPLATE/bug_report.yml` and `.github/PULL_REQUEST_TEMPLATE.md`; improve private-reporting guidance |
| Repository license | Verified missing | GitHub metadata `license: null` and root directory inventory. **Owner must select/approve any license; this PR does not add one** |
| Trivy images/SBOMs | Planned, separate CI workstream | [Draft #72](https://github.com/ItsFoxxin/Fox_Den_Media/pull/72) Phase 1 and stacked [draft #74](https://github.com/ItsFoxxin/Fox_Den_Media/pull/74) Phase 2 are **unmerged**; not required ruleset checks |

Do not change GitHub permissions, alert dismissals, scanner gates, release workflows or branch/tag protection as part of this documentation PR.

## Alert disposition and verification register

**Critical caution:** The connected API cannot enumerate current CodeQL, Dependabot or secret-scanning alerts. The following describes **documented historical findings** and **observed Trivy PR artifacts**, not a verified current-open-alert list. Match every ID to the current Security tab before triage.

| Tool / alert ID | Affected component | Severity | Finding/disposition | Fix/tracking | Remaining verification |
| --- | --- | --- | --- | --- | --- |
| CodeQL #1, `py/polynomial-redos` | Music regex | Historical security finding (severity must be checked in UI) | Earlier documentation shows as a pre-existing finding; **current state unknown**, not classified false positive | Prior work on PR #1; confirm current alert lineage | Verify query, vulnerable path, exact active state, latest-CodeQL fix and regression |
| CodeQL #11 | Music staged inbox file | Overly permissive file (CodeQL high family) | Documented permission hardening, not dashboard-verified as closed | `docs/security/media-file-permissions.md` | Confirm actual CodeQL state and staging 0600/0700 on NAS |
| CodeQL #12 | Music web upload | Overly permissive file (CodeQL high family) | Documented hardening, current alert state unknown | Same review | Verify mode after rename and safe group isolation |
| CodeQL #13 | Music published library | Overly permissive file (CodeQL high family) | **Intentional 0640 group read; exception NOT yet justified by runtime proof** | Same review, release register [#18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18) | Verify Music/Jellyfin group membership, ACL, mount chmod semantics, read-only Jellyfin access and unrelated-user denial before any disposition |
| CodeQL #14 | Music working cover art | Overly permissive file (CodeQL high family) | Documented hardening, current alert state unknown | Same review | Verify owner-only working files and latest CodeQL |
| CodeQL #15 | Music working audio | Overly permissive file (CodeQL high family) | Documented hardening, current alert state unknown | Same review | Verify owner-only files and latest CodeQL |
| CodeQL #2–10, #16–18 | Gateway, tests, Jellyfin, Movies/TV | Historical high/medium/critical mixed | Previously documented as fixed/test-only/false-positive with supporting reasoning; **not reaudited as active alerts** | `docs/security/pr10-codeql-remediation.md` | Reconcile current Security UI, confirm dispositions and regression evidence; do not dismiss in bulk |
| Trivy `CVE-2023-45853` | All three built images, `zlib1g` | Critical | Scanner-reported; package applicability unresolved | [#71](https://github.com/ItsFoxxin/Fox_Den_Media/issues/71), [PR #72](https://github.com/ItsFoxxin/Fox_Den_Media/pull/72) | Check vendor advisory, reachable usage, base-image package version and remediation |
| Trivy `CVE-2025-7458` | All three, `libsqlite3-0` | Critical | Scanner-reported; untriaged | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Verify installed version, upstream Debian status and runtime exposure |
| Trivy `CVE-2026-13221` | All three, `perl-base` | Critical | Scanner-reported with claimed fixed Debian package | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Test base-image refresh to vendor-fixed `5.36.0-7+deb12u4` or later applicable security release |
| Trivy `CVE-2026-42496` | All three, `perl-base` | Critical | Same | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Verify package provenance, fix status and rebuilt-image rescans |
| Trivy `CVE-2026-8376` | All three, `perl-base` | Critical | Same | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Verify package provenance, fix status and rebuilt-image rescans |
| Trivy `CVE-2023-6879` | Music and Movies/TV, `libaom3` | Critical | Scanner-reported; untriaged | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Confirm installed package and runtime FFmpeg reachability |
| Trivy `CVE-2025-47917` | Music and Movies/TV, `libmbedcrypto7` | Critical | Scanner-reported; untriaged | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Confirm package applicability and Debian advisory |
| Trivy `CVE-2026-34873` | Music and Movies/TV, `libmbedcrypto7` | Critical | Scanner-reported; untriaged | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Confirm package applicability and Debian advisory |
| Trivy `CVE-2026-34875` | Music and Movies/TV, `libmbedcrypto7` | Critical | Scanner-reported; untriaged | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Confirm package applicability and Debian advisory |
| Trivy `CVE-2026-58016` | Music and Movies/TV, `libglib2.0-0` | Critical | Scanner-reported; untriaged | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Confirm package applicability and Debian advisory |
| Trivy `CVE-2026-6653` | Music and Movies/TV, `libxml2` | Critical | Scanner-reported; untriaged | [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) / #71 / #72 | Confirm package applicability and Debian advisory |

The above Trivy scan ran on **unmerged PR #72**. [Its recorded artifact review](https://github.com/ItsFoxxin/Fox_Den_Media/issues/71#issuecomment-6716973143) counted Portal **5 critical / 52 high**, Music **11 critical / 256 high**, and Movies/TV **11 critical / 256 high**; findings overlap between images, and **11 critical CVE IDs are distinct**. Trivy exit code 0 was **advisory**. Scanner detection is neither proven exploitability nor a false positive; do not dismiss or waive without reproducible evidence. First authoritative protected-`dev` baseline is pending.

**Dedicated image-vulnerability remediation:** [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) tracks the 11 critical CVE IDs, high-severity baseline triage, applicable fixes, new image digests, and pre-1.0 sign-off separately from Trivy implementation.

**Security control gaps separately tracked:** [#57](https://github.com/ItsFoxxin/Fox_Den_Media/issues/57) OIDC administrator-role lifecycle, [#62](https://github.com/ItsFoxxin/Fox_Den_Media/issues/62) noVNC session revocation, [#70](https://github.com/ItsFoxxin/Fox_Den_Media/issues/70) Dependency Review enforcement, [#71](https://github.com/ItsFoxxin/Fox_Den_Media/issues/71) Trivy integration and triage, and [#18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18) full release acceptance. The OIDC/browser fixes have source and/or automated test progress, but their open issue status and NAS runtime gates must be reconciled before closing.

## Owner-only UI verification checklist

1. **Settings → Security and quality → Advanced Security** (GitHub may vary labels): inspect and record Dependency graph, Dependabot alerts, Dependabot security updates, native Secret scanning, Push protection and applicable plan/visibility restrictions. If an option is absent, record **unavailable/plan-dependent** instead of disabled.
2. **Security → Code scanning → Alerts:** filter open alerts and record rule, number, component, severity, state, dismissal reason (if any), and matching fixing SHA/PR. Pay special attention to historical regex #1 and intentional media-permissions #13.
3. **Security → Dependabot → Alerts:** triage by package, manifest, severity, introduced/fixed versions and applicability; link existing remediation PRs or create a specific tracking issue only after review. Verify the security-updates setting separately from version PRs.
4. **Security → Secret scanning → Alerts:** if available, review exposure and revoke/rotate *real* secrets before updating code; never publish the secret or rely on dismissal as remediation.
5. **Settings → Security and quality → Advanced Security → Private vulnerability reporting** or **Security and quality → Advisories:** enable private reporting if the owner approves and GitHub exposes the option; then verify the public Security tab shows **Report a vulnerability**. Create advisories privately as appropriate.
6. **Settings → Rules → Rulesets:** verify the two active branch rulesets match required statuses. Evaluate (do not silently create) a restrictive `refs/tags/v*` release-tag rule and approved release automation bypass/permissions before version 1.0.0 tagging. Keep existing protections.
7. **Default-branch publication:** merge this documentation PR into `dev` only after review; because the repository default is `main`, GitHub's public Security policy, new issue templates, and contributor entry points **will not be activated for visitors by a `dev` merge alone**. Request a **separate reviewed documentation-only promotion to `main`** under the existing release rules and verify the Security tab then. Do not promote the application source wholesale. Review repository licensing with owner approval only.
8. **CI/CD handoff:** complete [#70](https://github.com/ItsFoxxin/Fox_Den_Media/issues/70) after evidence and approval; review/merge #72 first, then re-evaluate stacked #74, observe a protected-`dev` Trivy baseline, and disposition critical/high findings in [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) before 1.0.0 approval. No automated issue flooding or blanket exceptions.

Record UI evidence in restricted maintainer notes where it could disclose private security reports or sensitive affected package inventory. Public issues and PRs should contain only sanitized summaries.

## Decision before 1.0.0

**NOT READY for security sign-off** until the current native alert queues and reporting settings are manually verified, critical/high image findings are triaged, unresolved CodeQL alerts are individually dispositioned, #70 rollout is evaluated, repository reporting policy is merged/recognized, and relevant runtime/NAS security gates in #18 have evidence. This document does not grant source-promotion, release-publication, or production-cutover approval.
