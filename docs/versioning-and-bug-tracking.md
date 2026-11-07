# Fox Den Media release and bug-tracking policy

Status: **prospective** (effective after this policy PR is merged). Existing `0.9.x`
entries are historical and are not retroactively split, renumbered or deployed.
The root `VERSION` is the platform release version. Component/API/schema
versions may be tracked separately for compatibility, but cannot replace it.

## Semantic versioning

Use `MAJOR.MINOR.PATCH` with **one component increment per release**.
These examples describe increments, not fixed version numbers:

| Change | Increment | Example starting at `1.2.3` |
| --- | --- | --- |
| Major / breaking change or approved major milestone | `+1.0.0` | `2.0.0` |
| Minor / backward-compatible feature | `+0.1.0` | `1.3.0` |
| Patch / fix for **one** particular bug | `+0.0.1` | `1.2.4` |

Major and minor bumps reset lower components to zero. Never skip versions,
bundle multiple patch increments, or combine a feature or another unrelated
bug fix into a patch. A `0.x` release remains pre-1.0.0, so breaking
changes must be clearly labeled and reviewed; reaching `1.0.0` remains
subject to the independent production-readiness and approval checklist.

A bug patch may contain **one defect**, the minimum directly related code
change, safety corrections needed for that defect, its regression tests,
necessary documentation, and its rollback notes. If testing reveals another
independent bug, open a separate issue and branch; it receives a separate
patch version and PR. Multiple symptoms from a single root cause may be
one bug when the issue explicitly explains that relationship.

## Bug lifecycle: issue first

1. Create one GitHub **Bug report** issue in this repository before code work.
   Record reproduction steps, expected/actual behavior, scope and impact,
   evidence with secrets redacted, acceptance criteria and proposed regression
   tests. Use the `bug` label when it is available. One issue tracks **one
   root-cause defect**. Do not mix enhancement requests into bug reports.
2. Start a focused `fix/<issue-number>-short-description` branch from the
   current integration branch. Add regression tests demonstrating the failure.
3. Open a `fix(scope): description` PR targeting `dev`; include `Fixes #123`
   (or `Closes #123`) in the PR description. Do not link a second independent
   bug as another closure in that PR.
4. Increment root `VERSION` by exactly one patch step. Synchronize
   `CHANGELOG.md`, Compose image version references, README version,
   and any other version metadata required by `scripts/check_release.py`.
5. Add one canonical changelog bullet in the new version's `### Fixed`
   section: `- Fixes #123: <specific bug and impact>`. Additional bullets
   may document tests, security verification, or related implementation,
   but must not introduce another issue or independently fixed bug.
6. Run the focused regression, complete monorepo CI and CodeQL, verify
   expected behavior and rollback on disposable/copied state, and collect
   the evidence in the linked issue/PR.
7. Request review. An accepted PR is **not** automatically a published release,
   and `Fixes #123` should not close the issue until a merged PR (according
   to GitHub's default-branch closure behavior) or an explicit owner action.
   Record final commit SHA, actual release tag and deployment verification
   separately. Do not imply the issue is deployed merely because it is closed.

If another patch release lands first, rebase/update the pending patch's
version and changelog before merge. Patch versions cannot both claim the same
`X.Y.Z`, and concurrent patch fixes should be promoted sequentially.
Do not silently bundle several bug issues to avoid rebase work.

## CI enforcement and boundaries

`scripts/check_version_policy.py` checks PRs against the target branch
VERSION and validates the one-step increment. It requires bug-fix PRs (by
conventional `fix:` title or bug label) to bump the patch component, and
patch releases to have exactly one issue in their new dated changelog entry
and exactly the same issue in their PR description. The CI workflow also
verifies the referenced issue is a real issue in the same repository, not
another pull request. It does **not** infer runtime correctness or authorize
release or NAS changes.

A PR with no release bump is permitted for documentation, release-process
changes, tests unrelated to a bug, and non-release preparatory work, but
**not** for a bug-fix PR. Feature PRs intended for release use a minor bump;
major promotions must pass their existing readiness gates.

`main` remains stable and `dev` remains integration. A merged PR to
`dev`, green CI, closed issue, or new VERSION number does **not** trigger
an automatic image release, production/NAS deployment, or change to Test57.
All production promotion, migration, and cutover gates remain independent.
Historical versions through `0.9.2` predate this policy; they are
grandfathered rather than rewritten.
