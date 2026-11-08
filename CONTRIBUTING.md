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

Dependency Review is currently **advisory**, not a protected required check; enforcement rollout is tracked in [issue #70](https://github.com/ItsFoxxin/Fox_Den_Media/issues/70). Trivy is being developed separately in [issue #71](https://github.com/ItsFoxxin/Fox_Den_Media/issues/71). Do not add overlapping scanners in application PRs.

Do not modify running NAS tests, Test51, Test57, or production to validate a contribution. Manual runtime acceptance requires an independently approved disposable copied-state environment.

## License

No repository license is currently published. **Do not assume a license or add one on the project's behalf.** Reuse, distribution and licensing permissions must be resolved with the repository owner; contributions should not introduce material with incompatible or unclear rights.
