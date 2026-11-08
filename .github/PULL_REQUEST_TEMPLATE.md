## Summary and change type

<!-- Use fix(scope): ... for exactly one bug. Feature releases use feat(scope): ... -->

- [ ] Major (breaking or approved milestone; MAJOR +1, reset lower components)
- [ ] Minor (backward-compatible feature; MINOR +1, PATCH reset)
- [ ] Patch (one specific bug; PATCH +1)
- [ ] Non-release (documentation, versioning/process or preparatory work without a bug fix)

## GitHub tracking

<!-- For a PATCH release, include exactly one existing GitHub bug issue:
Fixes #123
Do not use additional closing keywords for other issues in the same patch. -->

Issue: 

## Security and review impact

- [ ] Public diff, evidence, test data and CI logs contain no secrets or private security-report details
- [ ] Authorization, file permissions, user data, dependency/image provenance and network boundaries have been assessed where relevant
- [ ] Privileged or release-control changes are identified explicitly for maintainer approval
- [ ] Security vulnerabilities are handled privately under [SECURITY.md](../SECURITY.md); do not disclose an embargoed finding in this PR

## Verification

- [ ] Root VERSION, README, Compose image tag and dated CHANGELOG entry agree if releasing
- [ ] PATCH release has one `### Fixed` bullet linking the exact issue
- [ ] Focused regression tests and failure reproduction documented
- [ ] Full CI and CodeQL reviewed
- [ ] Safe rollback and security implications considered
- [ ] No secret, protected-branch or real NAS change without explicit approval

## Deployment boundary

No production/NAS deployment, 1.0.0 release or `dev` → `main` promotion is authorized by this PR alone.
