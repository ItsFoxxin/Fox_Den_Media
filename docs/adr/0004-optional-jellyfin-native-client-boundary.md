# ADR 0004: Optional Jellyfin and native-client boundary

- Status: Proposed for Fox Den Media 0.6.0 review
- Date: 2026-11-01

## Context

Fox Den Media needs an optional playback server without coupling Portal,
acquisition services, or the VPN namespace to playback availability. Jellyfin's
web client can operate behind a path base, but phones, televisions, discovery,
WebSockets, and third-party clients are most reliable when the server has its own
origin. Portal session cookies and browser redirects are not a substitute for
Jellyfin's native client authentication protocol.

An existing NAS Jellyfin installation contains production accounts, playback
history, metadata, plugins, and path-sensitive library records. Its live data
must not be opened by two servers or changed during this milestone.

## Decision

Add the official Jellyfin image as an opt-in Compose profile. The service has
independent configuration and cache persistence, read-only media by default,
its own restart lifecycle, and ordinary platform/outbound networking. It never
joins the Gluetun network namespace.

Expose Jellyfin at a dedicated configurable hostname. Nginx forwards WebSockets
and the standard reverse-proxy headers, but does not apply Portal `auth_request`
to Jellyfin. Jellyfin remains the authentication and library-authorization
authority for native and browser clients. Ingress strips Fox Den and Authentik
identity headers and does not manufacture a Jellyfin identity.

Local Jellyfin authentication remains available, including a separately managed
emergency administrator. A future directory integration may use the official
LDAP authentication plugin with Authentik's LDAP outpost after compatibility
testing. Directory groups may provision ordinary users, but must not grant
Jellyfin administrator access automatically. OIDC browser plugins are not the
default because support varies across native clients.

Fox Den Midnight browser styling is a documented Custom CSS asset served by
Portal. It changes presentation only; it does not patch or replace the official
Jellyfin image. Native applications retain their own supported appearance.

Intel `/dev/dri` acceleration is an explicit Compose override. Operators must
verify the render device and group IDs on the target host before enabling it.

## Migration and rollback boundary

The production instance remains untouched. Validation uses a consistent backup
restored into separate paths and preserves the old container's internal media
mount paths. Only one instance may write a given config/database directory.
Cutover requires an approved maintenance window, a fresh stopped-state backup,
functional validation, and a rollback path that restarts the unchanged previous
container against its original data.

## Consequences

- Jellyfin can be enabled, restarted, upgraded, or rolled back independently.
- Portal and the administrative modules work with Jellyfin absent or unhealthy.
- Native clients use normal Jellyfin login and do not inherit Portal sessions.
- General Jellyfin access does not grant Fox Den administrative access.
- A dedicated DNS/TLS name and production-specific account/group mapping remain
  operator configuration, not repository defaults.
