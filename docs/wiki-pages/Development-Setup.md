# Development Setup

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Development uses a monorepo and reviewed pull requests. The default `main` branch is the protected promotion target; work normally starts from `dev`.

## Contributor environment

~~~bash
git clone https://github.com/ItsFoxxin/Fox_Den_Media.git
cd Fox_Den_Media
git switch dev
git switch -c docs/example-change
python -m venv .venv
. .venv/bin/activate
python -m pip install -e apps/portal
~~~

Install additional Music/Movies/TV/test dependencies following the current CI workflow and the specific component's README. Container integration requires Docker; real-media tests may require FFmpeg/FFprobe. Use *synthetic* fixtures and isolated volumes, never live NAS state.

## Workflow

Make small feature, fix, security or documentation changes; add/update tests as relevant; open a PR **to `dev`**. Use a separate reviewed promotion PR for `dev` → `main`. Source version metadata does not imply a release.

Read [development and CI](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/ci.md), [monorepo workflow](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/.github/workflows/monorepo.yml), [Portal guide](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/apps/portal/README.md) and [version policy](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/versioning-and-bug-tracking.md).