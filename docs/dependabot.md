# Dependabot maintenance — Fox Den Media

This repository uses a single active Dependabot configuration at
[`.github/dependabot.yml`](../.github/dependabot.yml). The old
`apps/music/.github/dependabot.yml` was removed: GitHub does not read
that nested file as the configuration of this monorepo.

## Coverage and cadence

| Ecosystem | Dependency definitions | Frequency | Routine PR cap |
| --- | --- | --- | --- |
| GitHub Actions | Root `.github/workflows/` | Monday, 00:15 America/New_York | 2 |
| pip | `apps/music/backend`, `apps/music/ci`, `apps/media`, `apps/portal` | Wednesday, 00:15 America/New_York | 3 |
| Docker | Dockerfiles in `apps/music/backend`, `apps/media`, `apps/portal` | Friday, 00:15 America/New_York (weekly) | 2 |

The cap limits open **routine version-update PRs** per update entry, not
the number of dependencies examined. Unrelated updates are not deliberately
grouped, allowing changes and failed tests to be attributed to a dependency.
The schedule does not guarantee that an update exists or that GitHub will
create a PR at precisely the specified minute. The morning 02:00 briefing
may contain checks still running or GitHub scheduling delays.

### Known boundaries

- The root `.github/workflows/` directory is active. Inherited
  `apps/music/.github/workflows/` files are not repository-level
  workflows and are not monitored by the GitHub Actions entry.
- Music's separate browser test pin in `apps/music/ci/requirements.txt`
  is included. Python packages installed directly in workflow `run:`
  commands without a dependency manifest (such as CI-only pinned tools)
  are **not** automatically updated by the pip entries; review them manually
  or migrate them to a maintained manifest in a future CI-specific PR.
- Music lists some dependencies in both `pyproject.toml` and
  `requirements*.txt`. Review Dependabot diffs for consistent pins
  across manifests; the CI installation path and package metadata must
  continue to agree.
- The Docker entry covers `FROM` image references in the three listed
  Dockerfiles. Variable-driven images and image digests in
  `deploy/compose.yaml`, including external services such as Gluetun,
  qBittorrent, Jellyfin and Firefox, are **not** included in this foundation.
  Define their update/testing and rollback policy separately before
  enabling updates for those services.
- Some other tools, OS packages, and runtime images are outside the above
  supported manifests. Dependabot is not an all-dependencies audit.

## Overnight reporting target

- Routine version-update checks are requested Monday (Actions), Wednesday
  (Python), and Friday (Docker) at 00:15 America/New_York. The intended
  reporting cutoff is 02:00 local time on those days.
- This is a **best-effort reporting target, not a completion guarantee**.
  Dependabot checks, dependency resolution, PR creation, and subsequent CI
  jobs can be delayed or fail to start. Security updates are event-driven
  and do not follow this routine schedule.
- A future read-only reporting integration must query current GitHub state
  at report time rather than assume the scheduled job completed. Clearly
  distinguish PASS, FAIL, RUNNING, QUEUED, NOT STARTED and NO UPDATE FOUND
  (only when confirmed), and include relevant PR/run URLs and last checked
  timestamps. Do not infer "nothing changed" from missing activity.
- For missed cutoffs, queue delays or failures, preserve the item as
  pending in the report and surface the completed result in the next
  check/report; do not create duplicate issues for the same failing
  workflow/PR. That report plumbing belongs to the later CI/event-hub
  work, not the Dependabot foundation.

## Activation and routing

1. Review and merge the Dependabot foundation PR into `dev` only with
   maintainer approval.
2. Promote the approved configuration to the repository default branch
   `main` through the usual tested PR process. Dependabot reads its
   configuration from **main**; a file on `dev` alone does not activate
   scheduled updates.
3. Once active, **routine version-update PRs** are opened against `dev`
   and run the existing monorepo/CodeQL checks. Merge only after reviewing
   the dependency diff, release notes, build/test impact, and CI outcomes.
4. **Dependabot security-update PRs** target default branch `main`.
   `target-branch: dev` and its associated entry options do not control
   those security PRs. Ensure Dependabot alerts and security updates are
   separately enabled in repository security settings. Review and test
   security PRs before an approved merge to `main`; then sync the
   accepted changes back to `dev` and verify CI there.

The repository has **no Dependabot auto-merge workflow** in this foundation.
A bot PR is a proposal, never an approval to merge or deploy. Solo-maintainer
review is sufficient under the project's existing policy; no additional
reviewer is requested.

## Routine PR review checklist

1. Confirm the PR targets `dev` (or `main` for a security update) and
   changes only the expected dependency manifests and any required lock data.
2. Read the upstream changelog/security advisory; assess major-version
   compatibility, migration changes, and Docker image tag/digest behavior.
3. Review duplicate Music package pins and any indirect dependency changes.
4. Require passing CI, CodeQL and relevant integration tests; investigate
   failures rather than blindly retrying or merging. A green bot config
   check validates syntax, not end-to-end update compatibility.
5. Manually merge only after approval. Do not deploy to or modify the NAS
   based on a dependency update PR alone.

## Versioning and issue tracking

- An ordinary Dependabot dependency-update PR is already the tracking work item;\n  avoid creating a duplicate GitHub issue for every routine update.\n- Future CI automation may create or update a deduplicated issue for actionable\n  persistent CI failures, regression detections, and confirmed security work.\n  That ticket-writing workflow belongs in the CI redesign rather than this\n  Dependabot foundation. Sensitive vulnerability details must not be\n  published in public issues. FoxForge execution should require separately\n  scoped authorization, and neither issue creation nor issue labeling is\n  permission to merge, release, or deploy.\n\n
- Routine dependency maintenance is **non-release** work unless it changes
  released application behavior. Do not automatically bump the product's
  root `VERSION` just because Dependabot opened a PR.
- An actual application bug fix must follow the existing **one bug / one
  GitHub issue / one +0.0.1 patch release** rule, with the required changelog
  and PR issue reference. Feature and breaking releases follow existing
  minor/major policy.
- A security dependency remediation may require a patch release if it
  corrects a released defect. Classify it deliberately and track the
  relevant issue without publishing sensitive exploit details. Coordinate
  an urgent `main` security merge and subsequent `dev` sync so that
  versions and branches do not diverge.
- Do not label a plain dependency refresh as an application `bug` or
  `fix(...)` PR: those labels/titles invoke the repository's patch-release
  enforcement.

GitHub references:
[Dependabot configuration](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference),
[default-branch/security routing](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/customizing-dependabot-prs),
[security update settings](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-security-updates).
