# Authentik / OIDC

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Portal supports local accounts, optional **Authentik OpenID Connect**, and hybrid authentication. The IdP is externally administered; Fox Den does not create or change an Authentik provider automatically.

## Setup concepts

1. Create a confidential OIDC application/provider in your own IdP with verified HTTPS issuer and redirect URI.
2. Configure Portal's issuer, client ID, redirect, scopes and **private client-secret file**.
3. Define and test allowed and administrator group mappings. Never interpret missing group data as proof of administrator status.
4. Keep and validate a **local emergency administrator** recovery path before changing login modes.
5. Test ordinary users, removed groups, disabled local accounts, invalid tokens and upstream outages in staging.

## Session caveat

Authentication-time role synchronization and session revalidation are separate concerns. A change made only inside Authentik is **not necessarily detected immediately in an existing Portal session** without a supported logout event, refresh or polling mechanism. Check the current code, tests and acceptance status before claiming automatic immediate revocation.

Read [identity design](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/authentik-jellyfin-auth.md), [role synchronization review](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/oidc-role-synchronization-1.0.md), [OIDC setup reference](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/phase-1a/authentik-oidc-setup.md), [OIDC settings](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md), [permissions matrix](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/permissions.md).