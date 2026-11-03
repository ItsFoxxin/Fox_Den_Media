# Fox Den Media 1.0.0 release checklist

This checklist prepares a future stable release; it does not publish or deploy it.

## Repository and history

- [ ] Review and integrate stacked PRs #3, #4, #5, #6, and the 0.8.0 PR in order.
- [ ] Record every approved head SHA and successful strict-gate run.
- [ ] Verify Music lineage, filtered Media history, commit map, branches and tags.
- [ ] Create and verify repository bundles before any rename.
- [ ] Inventory releases, issues, PRs, Actions environments, secret *names*,
      variables, rulesets, packages, deploy keys, webhooks, apps and consumers.
- [ ] Obtain separate approval before renaming `Music_Downloader` to
      `FoxDen_Media`; retain `Media_Downloader` through rollback acceptance.

## 0.9.0 release-candidate freeze

- [ ] Freeze Compose structure, image tags/digests, environment schema and paths.
- [ ] Complete dependency and container security review.
- [ ] Pass every hosted workflow without waivers or unexpected skips.
- [ ] Complete copied-state rehearsal and all application compatibility checks.
- [ ] Review final Caddy/DNS/TLS, Authentik, Jellyfin, qBittorrent and VPN config.
- [ ] Validate backup, restore and rollback artifacts with checksums.
- [ ] Produce a `BLOCKED`/`CUTOVER_READY` report for the exact RC commit.

## Stable cutover and acceptance

- [ ] Approve a maintenance window and exact operator runbook.
- [ ] Stop old writers and verify exclusivity before final backup.
- [ ] Validate Portal, modules, VPN/torrent behavior, Jellyfin and native clients.
- [ ] Switch routing only after direct service validation.
- [ ] Observe the agreed stabilization window with previous deployment intact.
- [ ] Tag `1.0.0` only after production acceptance; no Android or Wear OS app is required.
