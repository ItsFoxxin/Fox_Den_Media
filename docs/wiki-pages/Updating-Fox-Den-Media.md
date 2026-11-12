# Updating Fox Den Media

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

An upgrade is an **operator-controlled change**, not a blind `git pull` followed by restart.

## Review and rehearsal

1. Identify the exact running commit and image digests. Read [CHANGELOG](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/CHANGELOG.md) and applicable security/migration notes.
2. Choose a **reviewed immutable ref**; do not treat `VERSION` or a passing CI check as proof of a published release.
3. Quiesce writers and make consistent state backups **plus separate large-media/torrent backups**. Verify hashes and an empty-target restore.
4. Test the upgrade on a **copied-state, separately named** Compose project with isolated paths and ports. Record database/permissions/client compatibility.
5. Obtain separate required approvals before affecting any production NAS state or routing.

## Deployment and rollback boundaries

For the approved *test* copy, run `validate`, inspect the `deploy` dry run and run `deploy … --execute` only with explicit authorization. Confirm login, module access, imports, Jellyfin clients and VPN fail-closed behavior as relevant.

If a migration fails, stop **all writers** and restore the compatible pre-upgrade snapshot to an empty target. Never point an older image at an upgraded database without a documented compatible rollback.

Read [updates and rollback](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/deployment.md), [recovery runbook](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/recovery.md), [migration rehearsal](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/side-by-side-migration.md) and [release gates](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/release-1.0-checklist.md).