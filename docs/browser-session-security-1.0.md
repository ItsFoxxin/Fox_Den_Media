# 1.0 browser-session security — RA-06 / issue #18

**Reviewed baseline:** dev commit 60cce4e7e4cd73ca20f467af3f9f9e4b84f524f6 (2026-11-07).
**Scope:** Portal, NGINX, jlesage Firefox/noVNC WebSockets.
**Deployment:** source and draft PR only; no NAS, Test51, Test57 or production operations.

## Threat and impact

The optional Firefox profile exposes a shared interactive desktop under /server-browser/.
Administrators can use the desktop for downloads and to access its mounted /downloads
directory. Continued access after Portal session revocation is an authorization bypass
with confidentiality and integrity impact. **Severity: Medium** under the existing
0.9.1 classification; higher if sensitive credentials or privileged networks are exposed.

## Verified pre-fix behavior

1. Browser HTTP and WebSocket upgrades enter NGINX /server-browser/, which uses
   an internal Portal auth_request. Unauthorized and failed Portal requests fail closed.
2. Portal's internal session API checks the live SQLite session expiry, account
   active flag and stored administrator role.
3. After HTTP 101, NGINX tunnels WebSocket data straight to download-browser:5800
   without additional authorization. Its read/send timeouts are *inactivity* timers,
   not an absolute lifespan.
4. Logout deletes the session, expiry invalidates it, and Portal account disablement
   or stored-role changes affect *new* connections. Existing active sockets survive.

## Focused mitigation in this draft

- Preserve the existing Portal auth_request, Firefox digest, optional Compose
  browser profile, static resources, ordinary HTTP, and RB-04 UI/capability logic.
- Route **every browser Upgrade** to a Portal-owned WebSocket relay. Keep ordinary
  browser HTTP going directly to Firefox. Unknown Upgrade paths fail closed.
- Restrict upstream to bounded websockify-compatible endpoint names and fixed
  private Firefox host; require same public Origin, current Portal session and
  stored admin role before connecting.
- Reauthorize the established socket against the session DB every **15 seconds**,
  regardless of network activity; revoke on logout, expiry, disablement, local
  role downgrade, or DB errors. Enforce a **one-hour absolute connection lifetime**
  and require a new handshake.
- Preserve binary and text frames, the noVNC binary subprotocol and audio
  websockify-style paths. Bound payload sizes. Fail closed if Firefox is absent.
- No new external port, container, secret, bind mount, or RB-04 state variable.
  The Portal uses the same private platform network as Firefox.

## Remaining threats

**OIDC role revocation is not immediate.** An Authentik account/group change
does not automatically mutate the Portal session database. Source inspection
also shows that PortalStore.map_external_identity() refreshes claims on later
OIDC login without updating the existing user's stored role. An OIDC admin
group removal may therefore leave a stale stored administrator privilege even
at subsequent login. This is a distinct identity-sync security finding needing
a dedicated remedy and explicit 1.0 acceptance. This WebSocket relay uses the
Portal DB as authority and must not be presented as fixing IdP propagation.

The Firefox desktop/profile is shared between admins. Disconnecting a
revoked socket does not erase browser tabs, cookies or files. Compromised
credentials may require separate profile reset and credential rotation.

Verify no root-relative WebSocket paths bypass the protected /server-browser/
route, and audit direct 5800/5900 exposure and east-west Docker connectivity.
Firefox's internal VNC transport must remain available to noVNC.

## Automated coverage and release gates

Regression tests cover successful authorized binary/text relay; logout,
session expiry, disabled Portal account, local role revocation, wrong Origin,
non-admin, unknown paths, offline Firefox and an absolute lifetime.
NGINX static assertions verify Upgrade routing, preserved HTTP Firefox proxy,
auth_request and header stripping.

Run Portal pytest, platform/ingress tests, dependency audit, CodeQL, Compose
validation and syntax validation. These do not substitute for live-image QA.

## Mandatory manual acceptance — approved disposable copy only

1. Record approved PR SHA, actual pinned Firefox image digest and new
   disposable mount paths; never reuse Test51/Test57 or production state.
2. Validate generated ingress using nginx -t, then verify admin login,
   general-user denial, logged-out denial, desktop/mobile noVNC,
   clipboard, audio, file manager, downloads and ordinary Firefox HTTP.
3. While continuously interacting with noVNC, test logout, Portal session
   expiry, account disablement and stored-role downgrade in copied state.
   Expect connection termination within 15s plus scheduler/network margin.
4. Prove hard one-hour closure/reconnection, Firefox restart and Portal
   outage failure, and deny fallback through any other WebSocket path.
5. Separately test Authentik account/group disablement and remediate the
   stale OIDC-role mapping; local Portal role changes do not prove IdP revocation.
6. Confirm no direct browser port bypass, no RB-04 availability regression,
   no Downloader Home/search regression and no unexpected portal load.
7. Review shared Firefox desktop privacy and multi-admin behavior.

## Rollback

The draft is unmerged; leave dev, main and deployed environments untouched.
If merged later, revert this focused set of Portal relay, ingress routing,
dependency, test and documentation changes on the approved source branch.
Only rebuild/restart in an explicitly approved **new disposable** environment.
Reversion reinstates the unbounded active WebSocket risk: disable optional
browser access or explicitly accept that risk until a replacement is proven.
Do not rotate secrets, clear profiles or touch production data as rollback.
