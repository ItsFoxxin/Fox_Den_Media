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

At the verified 2026-11-12 protected `dev` baseline `4df56bf467055e10d1406fec160693316dfcbeb8`, root `VERSION` is **`0.9.9`** (the earlier `0.9.6` at `9d770faa…` is historical only). [`scripts/check_release.py`](../scripts/check_release.py) verifies semantic version format, the Media image tag in Compose, bold README version, dated [changelog](../CHANGELOG.md), and Dockerfile version copy. For a stable promotion it can additionally compare `--base` against an earlier commit and enforce an increase; it can check JUnit report skip/failure policy with `--reports`. `apps/media/VERSION` remains part of the image build.

The prospective [versioning and bug-tracking policy](versioning-and-bug-tracking.md) requires exact one-step major/minor/patch increments. Every future bug fix must have its own GitHub issue, dedicated patch version, single-root-cause changelog entry, and linked PR. CI validates PR version changes and checks that the patch's issue exists. Historical versions through `0.9.2` are grandfathered.

1. Develop, test and review changes against `dev`, with synchronized version metadata when a release is actually proposed.
2. **Before source promotion**, follow the merged [A0–A4 evidence map](release-1.0-acceptance-evidence-map.md) and [1.0.0 checklist](release-1.0-checklist.md): separately authorize read-only inventory (A0), copied-state backup/empty-target restore (A1), isolated startup (A2), controlled fail-closed/rollback testing (A3) and owner review (A4). Disposition open release/security blockers and obtain the source-bound pre-promotion decision; A0 is not permission for A1–A3.
3. Obtain **independent owner approval** for application source promotion into protected `main`; only afterward, under separate authorization, publish commit-identified R3 GHCR **candidate** images and verify exact digests, authentic signed A/B/C evidence and R4 release-ready security/integration artifacts. Do not require final candidate digests before source promotion.
4. Only after real R4 approval and the separate release-publication authorization and protections, allow the manually gated R5 tag/GitHub Release process. A green workflow or merged release source does not authorize it.
5. Independently authorize final NAS production preparation and cutover under the approved maintenance/rollback plan. Publication and earlier copied-state acceptance do not grant NAS production GO.

**Merged release implementation, not an executed release:** R1/R2 [#79](https://github.com/ItsFoxxin/Fox_Den_Media/pull/79), R3/R4 [#81](https://github.com/ItsFoxxin/Fox_Den_Media/pull/81), independent A/C security producer [#84](https://github.com/ItsFoxxin/Fox_Den_Media/pull/84), B disposition verifier [#93](https://github.com/ItsFoxxin/Fox_Den_Media/pull/93) and finite-decimal verifier fix [#95](https://github.com/ItsFoxxin/Fox_Den_Media/pull/95), and manually gated R5 [#80](https://github.com/ItsFoxxin/Fox_Den_Media/pull/80) have merged into `dev`. The source is still `0.9.9` (not a released or accepted 1.0.0); `main` remains `0.9.1` at this verification. No real candidate publication, signed R4 acceptance artifact or R5 GitHub Release was verified.

Actual HIGH/CRITICAL dispositions [#76](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76), authenticated release-digest evidence [#83](https://github.com/ItsFoxxin/Fox_Den_Media/issues/83), [F-03 reusable GO/partial-publication recovery](ghcr-publisher.md), [F-04 independently anchored lifecycle continuity](release-publication-r5.md) and copied-state acceptance [#18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18) remain separate **NO-GO** obligations. The merged [operational evidence map](release-1.0-acceptance-evidence-map.md) is **preflight documentation**: a source-bound **PASS IN CI** is not a **PASS IN ISOLATED NAS** or **OWNER ACCEPTED**; new A0 inventory and later A1–A4 tests/approvals are not recorded as completed.

There is no automatic production deployment in these GitHub workflows, and a repository version label or green synthetic run is not proof of a published release. See the [1.0.0 checklist](release-1.0-checklist.md).

## Advisory container image scanning

The independent [Trivy image scanning and SBOM guide](trivy.md) documents real **first-party images built and scanned on disposable CI runners**, 21-day report artifacts, vulnerability triage and manual baseline comparisons. [Protected-`dev` advisory Trivy run 43326608873](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/43326608873) succeeded on `4df56bf…`, **but that job is not the required Monorepo strict gate, does not publish images, and is not authenticated R3/R4 security evidence for immutable release OCI manifest digests**.

The advisory Trivy image artifacts also carry a [versioned security contract](security-contract.md) with unsuppressed findings, exception expiry evaluation, report/SBOM hashes and an explicit distinction between advisory assessments and future release enforcement. It is **not** part of Monorepo strict gate.
