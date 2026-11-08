# Fox Den Portal

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

Portal is the shared entry point for Fox Den Media. It offers local authentication, optional Authentik/OIDC integration, module navigation, activity/status, and user-facing Watch & Listen where configured.

## Roles

- **General Portal users:** access their own authorized media experience and individually linked Jellyfin libraries.
- **Portal administrators:** may use acquisition modules (Music, Movies/TV) and the contained server browser.
- **Jellyfin users/admins:** governed independently by Jellyfin; one role does not automatically grant another.

A first-run local administrator is set up through `/setup` with the restricted, expiring bootstrap secret. Preserve and verify an emergency local administrator before enabling IdP-only behavior.

## Operator notes

Check HTTPS origin/cookie settings and group mappings. The Portal's signed internal service identity is not a substitute for external TLS. OIDC changes are not guaranteed to revoke existing sessions immediately without a supported refresh/event mechanism.

See [Portal component guide](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/apps/portal/README.md), [role matrix](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/permissions.md), [identity architecture](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/authentik-jellyfin-auth.md) and [security model](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/security.md).