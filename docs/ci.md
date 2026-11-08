# Development workflow, CI and release metadata

**Current branches:** `main` is the default/stable branch and `dev` is integration. Both are protected. Work in short-lived branches; open PRs into `dev` for review, then use a separately reviewed promotion PR from `dev` to `main`. This documentation task does not change protections, workflows or branch history.

**Code source of truth:** [monorepo workflow](../.github/workflows/monorepo.yml), [CodeQL workflow](../.github/workflows/codeql.yml), [release check](../scripts/check_release.py) and [secret-history scan](../scripts/scan_history_secrets.py). Previous descriptions of `master` and an old `CI gate` workflow are historical; the active aggregate job is named **Monorepo strict gate**.

## Active jobs

| Job | What it verifies |
| --- | --- |
| Validation and deployment modes | Python compile, JS syntax, release metadata, history secret scan, platform tests and seven Compose rendering/profile combinations |
| Music regressions and real audio | Python **3.12 and 3.13**, pinned FFmpeg/FFprobe fixture installer, Music tests and coverage threshold |
| Portal and Movies TV | App/Portal/platform tests, published JUnit reports |
| Dependency vulnerability audits | Strict `pip-audit` of Music, Movies/TV and Portal |
| Static analysis and secret scan | Bandit medium/high with medium/high confidence, full-history secret scan |
| Migration backup restore and rollback | Synthetic archive/restore/rollback tests and checksums |
| Optional Jellyfin container | Disposable official-image smoke test |
| Consolidated container integration | Disposable integrated stack and synthetic VPN fail-closed fixture |
| **Monorepo strict gate** | Requires all prerequisite jobs to succeed |
| CodeQL security analysis | Separate Python and JavaScript/TypeScript `security-extended` analysis |

The workflows trigger on PRs/pushes to `dev`, `main`, `feature/**` and `security/**`; the monorepo workflow also listens to `merge_group`. A docs-only branch itself is not a push trigger, but its PR targeting `dev` is. CodeQL has its **own** workflow/check, not an internal step of the monorepo gate. Always inspect all required GitHub checks before merging.

CI runs on disposable GitHub runners with synthetic data; it does **not** deploy, replace NAS application state, exercise real VPN credentials or authorize a cutover. Review the [0.9.1 security assessment](security-0.9.1.md) and [production readiness](production-readiness.md) for limits.

## Local contributor verification

From repository root in an isolated Python environment:

```bash
python -m compileall -q apps scripts tests
python scripts/check_release.py
python -m pytest tests/platform tests/test_integration_compose.py tests/test_ingress_config.py -q
node --check apps/media/app/static/app.js
node --check apps/music/backend/src/foxden_music/static/app.js
```

Install tests/dependencies as the workflow specifies before running broader suites. Tests involving Docker, network egress, real FFmpeg, secrets history or multiple Python interpreters require the matching installed tools. For profile rendering without starting containers:

```bash
docker compose --env-file deploy/examples/music.env.example -f deploy/compose.yaml --profile music config --quiet
docker compose --env-file deploy/examples/full-managed.env.example -f deploy/compose.yaml --profile music --profile media --profile managed config --quiet
```

Do not commit generated reports, temporary secrets, real environment files or production paths.

## Version and release process

The root `VERSION` is currently `0.9.2`. [`scripts/check_release.py`](../scripts/check_release.py) verifies semantic version format, the Media image tag in Compose, bold README version, dated [changelog](../CHANGELOG.md), and Dockerfile version copy. For a stable promotion it can additionally compare `--base` against an earlier commit and enforce an increase; it can check JUnit report skip/failure policy with `--reports`. `apps/media/VERSION` remains part of the image build.

The prospective [versioning and bug-tracking policy](versioning-and-bug-tracking.md) requires exact one-step major/minor/patch increments. Every future bug fix must have its own GitHub issue, dedicated patch version, single-root-cause changelog entry, and linked PR. CI validates PR version changes and checks that the patch's issue exists. Historical versions through `0.9.2` are grandfathered.

1. Develop, test and review changes against `dev`.
2. For an actual release proposal, update all required version metadata together, collect passing hosted checks and record approved image digests.
3. Complete copied-state NAS, authentication, VPN, file-permission, client and rollback rehearsals.
4. Request independent owner approval of the production cutover and a `dev` → `main` promotion.
5. Only after successful production acceptance consider a 1.0.0 tag/release.

There is no automatic production deployment in these GitHub workflows, and a repository version label is not proof of a published release. See [1.0.0 checklist](release-1.0-checklist.md).

## Advisory container image scanning

The independent [Trivy image scanning and SBOM guide](trivy.md) documents built-image coverage, 21-day report artifacts, vulnerability triage and manual baseline comparisons. It is not part of the required Monorepo strict gate and does not deploy or publish images.
