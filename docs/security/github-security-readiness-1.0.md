# GitHub Security and Quality readiness — 1.0.0

**Historical snapshot:** 2026-11-07, checked against protected `dev` at `91f7fb0e0088b3b4ae00cec116b881f82ae4d86e`, repository metadata and branch rulesets. Historical alert evidence remains attributed to that inspection.

**Current reconciliation:** 2026-11-08, originally assigned `dev` baseline `9d770faa5427551f76dac504c9e069887d52aba9` (`VERSION=0.9.6`); the current integration branch may advance while this documentation PR is reviewed. **This is not a live alert API export, security sign-off, merge approval, source-promotion approval or release/production authorization.** Reverify on the eventual candidate SHA.

Status meanings at the stated inspection date: **Verified enabled** = directly observed configuration or execution; **Verified missing** = confirmed absent in the checked branch/settings; **Unverifiable** = connected GitHub evidence does not establish the private setting/alert state; **Planned** = proposed but unmerged. Rows explicitly reconciled to 2026-11-08 supersede the original historical status.

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
| Recognized security policy | Verified present on `dev`; absent from `main` (2026-11-08) | Root [`SECURITY.md`](../../SECURITY.md) is merged via [#75](https://github.com/ItsFoxxin/Fox_Den_Media/pull/75). The default `main` branch still lacks the file; do not assume public default-branch recognition |
| Contribution policy | Verified present on `dev`; absent from `main` (2026-11-08) | Root [`CONTRIBUTING.md`](../../CONTRIBUTING.md) is merged via [#75](https://github.com/ItsFoxxin/Fox_Den_Media/pull/75); it is not yet present on the default branch |
| Issue / PR templates | Verified present | `.github/ISSUE_TEMPLATE/bug_report.yml` and `.github/PULL_REQUEST_TEMPLATE.md`; improve private-reporting guidance |
| Repository license | Verified missing | GitHub metadata `license: null` and root directory inventory. **Owner must select/approve any license; this PR does not add one** |
| Trivy images/SBOMs | Verified merged into `dev`; **advisory** | [#72](https://github.com/ItsFoxxin/Fox_Den_Media/pull/72), [#74](https://github.com/ItsFoxxin/Fox_Den_Media/pull/74) and [#77](https://github.com/ItsFoxxin/Fox_Den_Media/pull/77) merged. [Protected-`dev` run 42479159484](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/42479159484) succeeded at `9d770faa…`; it is not a required ruleset check, critical/high policy acceptance or signed release-digest verification |

Do not change GitHub permissions, alert dismissals, scanner gates, release workflows or branch/tag protection as part of this documentation PR.

## Reconciled source, security and publication stages (2026-11-08)

- [#79](https://github.com/ItsFoxxin/Fox_Den_Media/pull/79) R1 metadata/R2 immutable lock **merged** into `dev`; this is a release-code foundation, not a published 1.0.0 release image.
- [#84](https://github.com/ItsFoxxin/Fox_Den_Media/pull/84) trusted digest-security producer, [#81](https://github.com/ItsFoxxin/Fox_Den_Media/pull/81) R3/R4 candidate publisher/verifier and [#80](https://github.com/ItsFoxxin/Fox_Den_Media/pull/80) R5 publication remain **open draft PRs**. No signed R4 release-digest verification or approved R5 publication is established by draft status.
- [#70](https://github.com/ItsFoxxin/Fox_Den_Media/issues/70) remains **open**; the real Dependency Review workflow has `warn-only: true` and is not enforced as a required check. Later enforcement is separately tracked, not silently a new 1.0.0 blocker.
- [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) is the **open critical/high CVE disposition gate**; [#18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18) is the **open copied-state/release acceptance register**. Merged source and passing advisory CI do not replace accepted security dispositions, copied-state runtime proof, independently approved source promotion to `main`, immutable signed image evidence, separately authorized publication, or NAS production GO.

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

**Historical PR-only evidence (2026-11-07):** The original Trivy results were obtained on then-unmerged PR #72. [Its recorded artifact review](https://github.com/ItsFoxxin/Fox_Den_Media/issues/71#issuecomment-6716973143) counted Portal **5 critical / 52 high**, Music **11 critical / 256 high**, and Movies/TV **11 critical / 256 high**. Findings overlap among images; **11 critical CVE IDs were distinct** in that snapshot. These counts are historical, not a fresh count from a later release digest.

**Protected-`dev` advisory evidence (2026-11-08):** [Run 42479159484](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/42479159484) completed successfully for Portal, Music and Movies/TV at `9d770faa5427551f76dac504c9e069887d52aba9`. A post-merge protected-`dev` scan is no longer pending; the [current #76 register](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) records unresolved dispositions. Advisory workflow success is **not** high/critical release-policy acceptance. Scanner detection establishes neither exploitability nor a false positive; no finding is waived by a green job. A local image ID or hashed report is **not** an authenticated signed OCI release manifest digest.

**Dedicated image-vulnerability remediation:** Open [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) tracks critical/high CVE disposition, applicable fixes, exact eventual release digests and pre-1.0 security sign-off separately from the already-merged Trivy automation.

**Related security tracking:** [#57](https://github.com/ItsFoxxin/Fox_Den_Media/issues/57) OIDC administrator-role lifecycle, [#62](https://github.com/ItsFoxxin/Fox_Den_Media/issues/62) noVNC session revocation, [#70](https://github.com/ItsFoxxin/Fox_Den_Media/issues/70) Dependency Review enforcement, [#71](https://github.com/ItsFoxxin/Fox_Den_Media/issues/71) Trivy tracking (automation #72/#74/#77 already merged), and [#18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18) full release acceptance. Source fixes and automated tests do not themselves close outstanding NAS/runtime acceptance.

## Owner-only UI verification checklist

1. **Settings → Security and quality → Advanced Security** (GitHub may vary labels): inspect and record Dependency graph, Dependabot alerts, Dependabot security updates, native Secret scanning, Push protection and applicable plan/visibility restrictions. If an option is absent, record **unavailable/plan-dependent** instead of disabled.
2. **Security → Code scanning → Alerts:** filter open alerts and record rule, number, component, severity, state, dismissal reason (if any), and matching fixing SHA/PR. Pay special attention to historical regex #1 and intentional media-permissions #13.
3. **Security → Dependabot → Alerts:** triage by package, manifest, severity, introduced/fixed versions and applicability; link existing remediation PRs or create a specific tracking issue only after review. Verify the security-updates setting separately from version PRs.
4. **Security → Secret scanning → Alerts:** if available, review exposure and revoke/rotate *real* secrets before updating code; never publish the secret or rely on dismissal as remediation.
5. **Settings → Security and quality → Advanced Security → Private vulnerability reporting** or **Security and quality → Advisories:** enable private reporting if the owner approves and GitHub exposes the option; then verify the public Security tab shows **Report a vulnerability**. Create advisories privately as appropriate.
6. **Settings → Rules → Rulesets:** verify the two active branch rulesets match required statuses. Evaluate (do not silently create) a restrictive `refs/tags/v*` release-tag rule and approved release automation bypass/permissions before version 1.0.0 tagging. Keep existing protections.
7. **Default-branch recognition:** Root `SECURITY.md` and `CONTRIBUTING.md` are already merged into `dev` but were still absent on the default `main` branch when checked. Obtain separate approval for a reviewed documentation-only promotion and verify public Security/contributor entry points; do not promote application source wholesale or add a license without owner approval.
8. **CI/CD handoff:** #72/#74/#77 are merged and protected-`dev` advisory Trivy execution is observed. Disposition critical/high findings in [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) and prove [#18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18) acceptance before 1.0.0 approval. [#70](https://github.com/ItsFoxxin/Fox_Den_Media/issues/70) is still a separate advisory-to-enforced rollout, not already a mandatory branch check. No automated issue flooding or blanket exceptions.

Record UI evidence in restricted maintainer notes where it could disclose private security reports or sensitive affected package inventory. Public issues and PRs should contain only sanitized summaries.

## Decision before 1.0.0

**NOT READY for 1.0.0 security sign-off:** Owner-accessible native alert queues and private reporting settings still need verification; critical/high image findings in #76 and unresolved CodeQL alerts require individual disposition; copied-state security and runtime/NAS acceptance in #18 remains outstanding; exact signed release-digest verification is not established by draft R3/R4 workflows. Root security/contribution policies are merged on `dev` but not yet present on `main`. #70 enforcement remains a separate post-1.0 improvement, not an automatically imposed release GO gate. This document grants no merge, source-promotion, publication or production-cutover approval.
