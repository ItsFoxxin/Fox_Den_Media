# GitHub Wiki source and maintenance

This folder and `docs/wiki-pages/` are **reviewable Wiki publication sources**. They are **not** automatically published by GitHub. The public Wiki is a *separate Git repository*. Do not confuse its revision history with `main` or `dev`.

## Ownership and source of truth

- Keep technical detail and changed behavior in `docs/` and code first. Update only the matching Wiki summary/navigation page after that source is reviewed.
- The `docs/wiki-pages/*.md` files are intended to be copied verbatim to the Wiki Git repository root, including `Home.md`, `_Sidebar.md` and `_Footer.md`.
- Do not copy `docs/wiki-maintenance.md` into the Wiki. Do not upload live logs, network maps, credentials, environment files or migration inventory.
- Development documentation URLs deliberately point to `blob/dev`. When a public stable release exists, update relevant stable installation guidance to reviewed *immutable tag* links; retain explicitly identified development instructions for contributors.
- Audit dated release claims every time the Wiki is published. The initial source baseline is `dev` 0.9.6, `main` 0.9.1, with no published GitHub Release observed on 2026-11-07. These are **not** evergreen claims.
- Some canonical documents retain historical `0.9.1` / `0.9.2` headings. Their operational procedures must be checked against the current CLI/Compose implementation before use; do not duplicate historical commands as new stable instructions.

## Publication procedure — **manual review gate**

1. Merge a reviewed source PR to `dev`; verify links, statuses, current versions, privacy and all Markdown rendering. No Wiki publication occurs during this PR.
2. Confirm Wiki is enabled in repository settings. If the Wiki has **no initial page**, GitHub may not yet expose a cloneable `.wiki.git` repository. After completing review, create `Home` from the reviewed `Home.md` *using GitHub's Wiki UI* to initialize it; only then clone.
3. With Git authentication configured for a collaborator with Wiki write permission, run from the source repo root:

~~~bash
git switch dev
git pull --ff-only
git clone https://github.com/ItsFoxxin/Fox_Den_Media.wiki.git ../Fox_Den_Media.wiki
git -C ../Fox_Den_Media.wiki branch --show-current
git -C ../Fox_Den_Media.wiki status --short
~~~

4. **Inspect any existing Wiki pages before overwriting them.** Do not erase untracked/legacy pages; preserve/merge their valuable material and take a backup of the Wiki repository if it already exists. Once that comparison is complete:

~~~bash
cp -a docs/wiki-pages/. ../Fox_Den_Media.wiki/
git -C ../Fox_Den_Media.wiki add -- '*.md'
git -C ../Fox_Den_Media.wiki diff --cached --check
git -C ../Fox_Den_Media.wiki diff --cached --stat
git -C ../Fox_Den_Media.wiki diff --cached
~~~

5. Review the **entire staged diff** for secrets/private paths, broken Wiki links, obsolete release claims and unsupported security promises. In particular, verify the Home page, sidebar, installation cautions and all source links. Do not run the following until the review is explicitly approved:

~~~bash
git -C ../Fox_Den_Media.wiki commit -m "Publish reviewed Fox Den Media Wiki"
git -C ../Fox_Den_Media.wiki push origin HEAD
~~~

6. Open the Wiki tab and manually click each sidebar entry, documentation link and Quick Start reference; review mobile/desktop rendering. Record the published Wiki commit SHA and corresponding source PR/commit in the change record.

## Synchronization policy

For each PR changing installation, configuration, components, permissions, security, operations, test gates or release status: determine which Wiki summary pages must also change. Update `docs/wiki-pages/` **in the same source PR**; if no Wiki change is needed, explain why in the PR. A maintainer separately publishes the reviewed Wiki source and records both commit SHAs. Use a periodic review of broken links and dated version statements. Do **not** auto-push `dev` to the public Wiki without an independent approval and privacy scan.

## Links and Wiki files

Use `[[Label|Page-Slug]]` / `[[Home]]` for internal Wiki navigation. External technical links should use absolute GitHub URLs to version-identified source files. New pages must be added to `_Sidebar.md`. Do not duplicate long secrets/configuration/migration runbooks in the Wiki.

## Restrictions

No application version bumps, GitHub Releases, CI deployment, NAS changes, GitHub Actions secrets, branch protection or production state mutations are part of Wiki publication.