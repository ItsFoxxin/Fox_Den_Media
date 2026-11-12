# Contributing

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Fox Den Media welcomes narrowly scoped documentation, tests, bug reports, security improvements and component changes.

## Suggested process

1. Read the [README](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/README.md), [documentation index](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/README.md) and relevant component/runbook.
2. Open a GitHub issue for a reproducible bug or proposed enhancement, avoiding sensitive logs and production details.
3. Branch from current `dev`, keep the change focused, add a regression test for bug fixes and update canonical `docs/` when behavior changes.
4. Open a PR targeting `dev`; describe scope, risk, testing and remaining manual checks.
5. Wait for the required CI/security checks and review before merge.

The repository's version policy tracks bugs individually; a development version bump is not a published release. Do not change branch protection or release workflows as part of an unrelated documentation contribution.

For Wiki changes, **edit the reviewed source under `docs/wiki-pages/` alongside the authoritative `docs/` change** and follow `docs/wiki-maintenance.md`. The public Wiki is published independently after review; do not modify it as the only copy.

Read [CI contribution workflow](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/ci.md), [bug and version tracking](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/versioning-and-bug-tracking.md) and [security reporting precautions](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/security.md).