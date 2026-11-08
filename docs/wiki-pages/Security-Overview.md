# Security Overview

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Fox Den Media is designed around independent trust boundaries, **not** the claim that every optional container or deployment is identically hardened.

## Controls described in source

- Portal local/OIDC authentication and administrator-only acquisition/browser routes.
- Short-lived Ed25519-signed internal module identity, and Nginx ingress authorization.
- Private secret-file mounts and non-root hardening for first-party services.
- Safe reviewed Media imports, path containment and checksum/no-overwrite protections.
- qBittorrent sharing Gluetun's network namespace in managed mode.
- CI security checks (CodeQL, Bandit, dependency auditing and secret-history scanning).

## Limits and deployment obligations

Third-party Firefox/qBittorrent images have their own process requirements. Gluetun needs network privileges. An external TLS proxy, host firewall, host ACLs, IdP operation, real VPN fail-closed testing and actual NAS acceptance are **operator duties**. The Wiki is not a penetration-test certificate or security approval.

**Public contribution rule:** never publish credentials, cookies, session tokens, real private NAS paths, private network addresses, sensitive infrastructure maps or real VPN keys. Redact logs and reproduction steps.

See [security model](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/security.md), [permissions](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/permissions.md), [unclosed release checks](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/release-1.0-checklist.md) and [browser boundary review](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/browser-session-security-1.0.md).