# Contributing to Fox Den Media

Fox Den Media welcomes focused improvements and reproducible bug reports. This repository is in a pre-1.0 integration phase; there is no production-deployment approval implied by a merged pull request.

## Before reporting an issue

- Search existing issues and review the [release blocker register](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18).
- For a normal bug, use the Bug report template. Report **one independently identifiable defect/root cause per issue**, with an affected version/SHA, component, expected and observed behavior, safe reproduction, redacted logs, and acceptance/regression criteria.
- **Do not publish security vulnerabilities in GitHub Issues.** Read [SECURITY.md](SECURITY.md) and submit privately when GitHub offers that facility.
- Avoid posting private media, host paths, service topology, account data, login cookies, secrets, full `.env` files, or real VPN credentials. Use synthetic examples and scrub logs.

## Branching and change scope

- Target the current `dev` branch. `main` is a protected release branch; source promotion is separately approved.
- Use a focused branch and PR for each logical change. One bug fix corresponds to one tracking issue and one patch increment; do not bundle unrelated bugs into one patch.
- Follow [versioning and bug tracking](docs/versioning-and-bug-tracking.md) for `MAJOR.MINOR.PATCH` rules and required `VERSION`, changelog, README, and deployment metadata updates.
- Documentation and security-configuration changes that do not fix a runtime bug may remain non-release PRs; do not bump `VERSION` solely for those changes.
- Do not change branch rulesets, required checks, publishing credentials, NAS deployment, or actual secrets without explicit maintainer review and authorization.

## Pull request expectations

Provide in the existing PR template:

1. A concise purpose, scope and linked issue (use `Fixes #N` only when that closure is intended).
2. The changed components, threat/safety considerations and whether data migration or configuration is needed.
3. Exact test commands and outcomes, GitHub Actions links/SHAs, and relevant reproducible failure/negative tests.
4. Evidence for sensitive behavior (authorization, file permissions, secret redaction, networking, image provenance, or rollback) using isolated fixtures.
5. Known limits and still-pending integration/NAS tests; do not claim CI tests prove production readiness.

Reviewers should check backward compatibility, input validation, least privilege, unsafe defaults, tests, release metadata, confidentiality of logs, and alignment with the tracked issue. Changes affecting authentication, filesystem boundaries, download isolation or publishing warrant focused security review. An open PR or passing CI never replaces a review/approval decision.

## Validation

Run relevant local tests before requesting review; the repository's required GitHub checks include **Monorepo strict gate**, **CodeQL (python)**, and **CodeQL (javascript-typescript)**. On `main`, an additional `CodeQL` context is currently required. Read [CI documentation](docs/ci.md) and [security architecture](docs/security.md).

Dependency Review remains **advisory** (`warn-only: true`), not an enforced high/critical threshold or protected required check; enforcement remains tracked by [issue #70](https://github.com/ItsFoxxin/Fox_Den_Media/issues/70). Trivy built-image scans and SBOMs [#72](https://github.com/ItsFoxxin/Fox_Den_Media/pull/72), trusted PR reporting [#74](https://github.com/ItsFoxxin/Fox_Den_Media/pull/74), and the advisory security contract [#77](https://github.com/ItsFoxxin/Fox_Den_Media/pull/77) have **merged into `dev`** (tracking [#71](https://github.com/ItsFoxxin/Fox_Den_Media/issues/71)). Do not add overlapping scanners in application PRs.

Successful [advisory Trivy image scans](docs/trivy.md) **build and scan actual first-party images on disposable CI runners**, but passing their jobs does **not** accept remaining critical/high findings or authenticate signed **R3-published OCI manifest digests**. [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76) remains the vulnerability-disposition gate; [#83](https://github.com/ItsFoxxin/Fox_Den_Media/issues/83) remains open for real authenticated A/B/C digest-security evidence. The R1–R5 code and workflow infrastructure has merged into `dev` through [#79](https://github.com/ItsFoxxin/Fox_Den_Media/pull/79), [#81](https://github.com/ItsFoxxin/Fox_Den_Media/pull/81), [#84](https://github.com/ItsFoxxin/Fox_Den_Media/pull/84), [#93](https://github.com/ItsFoxxin/Fox_Den_Media/pull/93), [#95](https://github.com/ItsFoxxin/Fox_Den_Media/pull/95) and [#80](https://github.com/ItsFoxxin/Fox_Den_Media/pull/80); **no live release dispatch, signed R4 approval, publication or promotion is thereby established**. The release publisher's [F-03 reusable owner-GO/partial-retry](docs/ghcr-publisher.md) and [F-04 monotonic lifecycle continuity](docs/release-publication-r5.md) limitations remain separate blockers.

Use the [source-bound operational acceptance evidence map](docs/release-1.0-acceptance-evidence-map.md) merged by [#90](https://github.com/ItsFoxxin/Fox_Den_Media/pull/90) for the **separately authorized** A0 read-only inventory, A1 copied-state backup/restore, A2 isolated runtime start, A3 failure/recovery and A4 owner review. **PASS IN CI** is not **PASS IN ISOLATED NAS** or **OWNER ACCEPTED**; new rehearsal cases remain **NOT TESTED**. Security disposition, operational acceptance [#18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18), source promotion, actual R3/R4 signed digest verification, R5 publication and NAS production GO are distinct owner-controlled gates under the [1.0.0 checklist](docs/release-1.0-checklist.md).

Do not modify running NAS tests, Test51, Test57, or production to validate a contribution. Manual runtime acceptance requires an independently approved disposable copied-state environment.

## License

No repository license is currently published. **Do not assume a license or add one on the project's behalf.** Reuse, distribution and licensing permissions must be resolved with the repository owner; contributions should not introduce material with incompatible or unclear rights.
