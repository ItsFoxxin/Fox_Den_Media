# GitHub repository migration checklist

> **Historical record — superseded for current operations.** This checklist
> records the approved *pre-consolidation* PR stack and repository rename plan.
> The active repository is now `ItsFoxxin/Fox_Den_Media`, with `main` as
> default/stable and `dev` as integration. Do not repeat the rename, PR merge
> sequence, or legacy-repository archiving/deletion from this record. For current
> release steps see [CI](ci.md) and [1.0.0 checklist](release-1.0-checklist.md).
> Original decisions and source history below are intentionally preserved.

No item in this checklist is authorized by the consolidation branch itself.

## Required stacked integration order

1. PR #3 — 0.5.0 monorepo consolidation into `dev`.
2. PR #4 — DenKit Midnight, after #3.
3. PR #5 — optional Jellyfin/Midnight integration, after #4.
4. PR #6 — Watch & Listen 0.7.0, after #5.
5. The 0.8.0 production-rehearsal PR, after #6.

Each head must be reviewed against its recorded base and pass the strict gate
after any rebase/retarget. Do not flatten, squash away imported lineage, or merge
a child before its parent. No item here grants merge permission.

- Record the final Music, Music integration, Media integration, and monorepo SHAs.
- Export repository bundles and verify they contain branches and tags.
- Record open PRs, issues, milestones, releases, discussions, and default branch.
- Record Actions variables, secret names, environments, required checks, and rulesets without exporting secret values.
- Record GHCR package names, tags, digests, retention rules, and consumers.
- Record deploy keys, webhooks, GitHub Apps, Dependabot configuration, badges, clone URLs, and documentation links.
- Pass the monorepo strict gate and retain its test/audit artifacts.
- Record the 0.8.0 inventory/backup/restore/rollback artifact schemas and their
  consumers before changing repository paths.
- Obtain explicit approval before renaming `Music_Downloader` to `FoxDen_Media`.
- Update remotes, package paths, badges, documentation, Caddy links, and automation after the rename.
- Keep `Media_Downloader` available during rollback validation.
- Archive it only after production acceptance; delete it only under a separate deletion approval.
