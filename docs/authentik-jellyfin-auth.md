# Authentik, Active Directory, and Jellyfin authentication

## Portal OIDC audit

The Portal implementation retains authorization-code flow, PKCE, state and
nonce validation, discovery and signing-key validation, issuer/audience/time
checks, group admission, administrator-group mapping, local-only/OIDC-only/
hybrid modes, local logout, provider logout, and a local emergency account.
The isolated protocol and identity tests cover success, invalid and expired
tokens, state/nonce misuse, provider outages, unauthorized groups, logout, and
spoofed internal identity headers.

Connecting production Authentik still requires a human-created confidential
OIDC provider/application, exact redirect URI, client secret file, allowed and
administrator group names, Caddy reachability, and a recovery test. Fox Den
does not modify Authentik automatically.

## Four distinct authentication concerns

1. **AD-backed Jellyfin login:** the Jellyfin LDAP plugin can authenticate a
   Jellyfin identity against Active Directory or an Authentik LDAP outpost.
   This preserves Jellyfin's per-user libraries, history, and restrictions.
2. **Portal OIDC:** Authentik authenticates the Portal identity. This does not
   create a Jellyfin session by itself.
3. **Browser SSO into Jellyfin:** this needs a Jellyfin-compatible SSO plugin or
   an explicit token-exchange design. Forward-auth headers alone are not a
   supported substitute for Jellyfin user authentication.
4. **Native clients:** Android, TV, WebOS, and other clients use Jellyfin's own
   login/Quick Connect behavior. Portal cookies and reverse-proxy forward-auth
   cannot be assumed to work in those clients.

## Recommended production architecture

- Use Authentik OIDC for Portal primary login and retain a restricted local
  Portal emergency administrator.
- Initially keep Jellyfin native login. Optionally validate the official LDAP
  plugin against a copied Jellyfin configuration and AD/Authentik LDAP in the
  isolated rehearsal.
- Map ordinary media users only; do not use LDAP group matching to grant
  Jellyfin administrator rights automatically. Maintain a tested local
  Jellyfin recovery administrator.
- Let each Jellyfin user explicitly connect once in Watch & Listen. This yields
  real user-scoped API access without sharing an administrator token.
- Treat seamless browser SSO as a later security milestone after plugin/server
  version compatibility, account linking, logout, recovery, and native-client
  behavior are proven.

Portal administrator status never implies Jellyfin administrator status.
Jellyfin library grants remain authoritative.
