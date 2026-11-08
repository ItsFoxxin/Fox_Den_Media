# Security policy

Fox Den Media is a self-hosted media-management platform. This policy explains how to disclose suspected vulnerabilities without exposing users, credentials, or infrastructure.

## Supported versions

Fox Den Media has **not released or validated version 1.0.0**. The published status of a branch or tag must not be taken as production-readiness approval.

| Source/version | Security response |
| --- | --- |
| Current `dev` integration branch | Receives security triage and proposed fixes; experimental and not production-validated |
| Current `main` branch | Reviewed fixes are promoted selectively according to release controls; not a blanket promise of a supported production release |
| Older `0.x` commits, test builds, and development tags | No routine backport commitment; use a reviewed newer revision when safe |
| Future `1.x` releases | Support scope will be defined when a release is approved and published |

We prioritize credible reports affecting current maintained code. We cannot guarantee a fixed response or remediation timeline.

## Report a vulnerability privately

1. Open the [repository Security page](https://github.com/ItsFoxxin/Fox_Den_Media/security).
2. If **Report a vulnerability** is available, use it to submit a private vulnerability report through GitHub's private vulnerability reporting workflow.
3. If that option is unavailable, **do not disclose details in a public issue, PR, Discussion, commit, or comment**. Ask the repository maintainer to enable a private reporting channel using a public message **without technical details, proof of concept, or sensitive information**. Wait for a confirmed private channel before sending the report.

There is no published security-report email address. Do not send sensitive details to guessed email addresses or unrelated accounts. The GitHub private-reporting option depends on repository settings and is not guaranteed to be enabled.

### Useful information for a private report

- Affected version, commit SHA, service or endpoint, deployment profile, and prerequisites.
- A concise impact and threat model, including required roles, exposure, and whether exploitation crosses an authentication or filesystem boundary.
- Minimal safe reproduction steps using disposable or synthetic data, with expected versus observed behavior.
- Sanitized error messages or logs, and any proposed mitigation.
- Whether any real-world exploitation is suspected. Do not test against third-party systems or live production data without authorization.

Never include secrets, API tokens, private keys, complete environment files, real user media, personal data, unredacted system paths, authentication cookies, VPN configuration, public exploit payloads, or production connection details in public reports.

## Coordinated disclosure

Please allow maintainers a reasonable opportunity to reproduce, assess severity, mitigate, test, and release a fix before making details public. We will triage reports according to available maintainer capacity, communicate significant status changes where the private reporting channel permits, and coordinate publication of advisories when appropriate. Response times are **best effort**, not a service-level agreement.

A submitted report does not authorize penetration testing of someone else's installation, destructive tests, credential access, or network scanning. Prefer isolated local proof. We do not guarantee a bounty or reward.

## For maintainers

- Keep reports private while impact and exposure are investigated; do not copy confidential reports into public tracking issues.
- Record an internal/private disposition, affected versions, remediation and regression evidence. Create a public issue only when its contents are safe to disclose.
- Use GitHub repository security advisories and coordinated disclosure where supported; do not dismiss scanner findings only to clear the dashboard.
- Preserve the existing protected-branch checks and require reviewed CI, CodeQL, and relevant isolated-runtime validation before merging fixes.
- Follow [security architecture](docs/security.md), [contribution and review standards](CONTRIBUTING.md), [1.0 acceptance](docs/release-1.0-checklist.md), and [security readiness inventory](docs/security/github-security-readiness-1.0.md).

**Release boundary:** A security fix merged to `dev` is not proof of a secure production deployment or authorization for the NAS cutover.
