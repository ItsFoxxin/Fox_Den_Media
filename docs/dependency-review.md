# Dependency Review — advisory rollout

This workflow is intentionally independent from `monorepo.yml` and the
Phase 1 workflow-hygiene work in PR #31. It is an additional review of
**newly introduced dependency vulnerabilities**, not a replacement for
`pip-audit`, Dependabot alerts, Bandit, CodeQL or secret scanning.

## How it works

- On every pull request against `dev` or `main`, a GitHub-hosted runner
  uses `actions/dependency-review-action` to compare the dependency graph
  for the PR's base and proposed head. The action is pinned to the full
  commit SHA of the upstream `v5.0.0` release, which requires a recent
  GitHub Actions runner supporting Node.js 24.
- `fail-on-severity: high` selects **high and critical** introduced
  vulnerabilities for the vulnerability policy; all dependency scopes
  (runtime, development, unknown) are considered.
- `warn-only: true` means vulnerability findings appear as warnings and
  the job succeeds. This is **advisory mode**, not a merge-blocking gate.
  Infrastructure errors such as API access failures may still fail the
  job; investigate them instead of interpreting them as vulnerable code.
- The action does **not** post PR comments, open issues, or fix packages.
  Findings are visible in the workflow run/job summary. The only token
  permission requested is `contents: read`. The runner does not
  upload code artifacts or use production secrets.
- It runs on `pull_request`, not `pull_request_target`, so it does not
  receive privileged repo write permissions while evaluating untrusted PRs.
  It is not currently included in the protected branch required-check list.

## Prerequisites and coverage caveats

- Verify **Dependency graph** is enabled in repository Settings →
  Security and quality → Advanced Security. This public repository can
  use the action, but the connected GitHub interface does not expose
  the switch state; the live workflow result will also reveal API errors.
- GitHub can analyze supported manifests such as `requirements.txt` and
  root `.github/workflows/*.yml`. GitHub's dependency graph support for
  project metadata, extras and transitive Python packages is not equivalent
  to a complete, locked installed environment. Some `pyproject.toml`
  dependency sets may require dependency submission or lock files to
  appear completely.
- Dockerfile base image and deployment Compose coverage should **not**
  be assumed from this action. Use a dedicated image scanner in a
  subsequent PR, particularly for variable-driven external service tags.
- Dependencies already present in the base without being introduced or
  newly made vulnerable by the PR are not the main target of this check.
  `pip-audit` and Dependabot alerts address baseline risk separately.
- GitHub Actions referenced by immutable SHAs are protected from tag drift
  but their vulnerability visibility in the dependency graph is limited.
  Periodic action version review and workflow security linting remain
  necessary.

## Promotion to enforcement (separate approval)

1. Confirm the workflow succeeds on representative PRs, including Python
   dependency and action-update PRs, and inspect its dependency-change
   summary for gaps. Test detection using an **isolated synthetic PR**
   with a known vulnerable test package, never a production dependency.
2. Compare findings with `pip-audit` to verify that the new check adds
   distinct PR-diff coverage and does not overwhelm review.
3. In a later approved security PR, remove `warn-only: true` and keep
   `fail-on-severity: high`. A high/critical newly introduced known
   vulnerability would then produce a failing check.
4. After observing enforcement and explicitly approving policy, add
   `Dependency Review (advisory)` (or rename to `Dependency Review`
   in a coordinated change) to the `dev`/`main` required-status rulesets
   if hard merge blocking is wanted. Do not add a mandatory second
   human reviewer. Preserve the existing required check names.

This rollout does not authorize merges, releases, automatic issue creation,
or NAS deployment.
