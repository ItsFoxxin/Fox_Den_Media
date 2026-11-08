# RB-04: optional server-browser availability (0.9.5)

## Root cause and change

The optional Firefox `browser` Compose profile was disabled by default, but Music always received `REMOTE_BROWSER_URL=/server-browser/`. Its Add/Request templates offered a browser link from that setting without checking service or authorization. The watched-download POST could start the `ACQUIRING` transition despite an unavailable browser.

Compose now leaves `REMOTE_BROWSER_URL` empty by default. The supported `scripts/foxden.py` deployment controller sets this route only when `--browser` is selected and clears it otherwise. For **direct Docker Compose**, explicitly set `REMOTE_BROWSER_URL=/server-browser/` and select `--profile browser` together. The full-managed and Ugreen rehearsal environment examples include that value for direct Compose profile use; the controller still enforces the explicit flag.

Portal-integrated Music checks both the signed `admin` role and a bounded HTTP HEAD request to the **fixed internal** `download-browser:5800` frontend. There is no proxy, redirect following, user URL, public probe endpoint or Docker socket. HTTP errors, DNS failure, timeouts and disabled configuration fail closed. The Add/Request pages hide browser actions, direct browser GET returns 409 (403 if unauthorized), and watched-download POST fails before changing acquisition state. Existing external downloader, manual file upload/inbox import, name search, metadata-provider behavior and the prior Downloader Home destination are left unchanged. Standalone Music keeps its existing configured-browser behavior.

**Limit:** An HTTP response proves only HTTP frontend reachability, not an active Firefox desktop, usable RFB/noVNC or WebSocket. Browser status can change between rendering a page and clicking; guarded requests then fail safely.

## Automated checks

- Platform Compose regression: browser is opt-in, not host-published, examples explicitly configure the route.
- Deployment-controller regression: `--browser` selects the route, absent flag clears it even if set in an env file.
- Music internal readiness probe: 2xx/3xx success, 4xx/5xx failure, connection error/cleanup and no redirected or user-supplied probe.
- Signed integration identity: admin versus non-admin and unauthenticated, disabled/live/down browser, direct browser page and watched-download POST no state mutation, and name-search accessibility.
- Existing browser Home, Music search, request workflow, ingress/Compose and CodeQL checks must remain green.

## Real NAS acceptance, not yet performed

Use an approved **new isolated copied-state** NAS environment pinned to the reviewed commit and supported immutable Firefox digest; do **not** touch Test57, Test51, production, or `main`.

1. Without browser profile, confirm no Music browser action, while name-based Music searches, external/manual downloader and uploads remain accessible.
2. Enable the `browser` profile and Music URL. Verify an admin can open the actual browser route, noVNC desktop, correct Home button, clipboard handoff and desktop/mobile layouts. Confirm non-admin/unauthenticated users cannot open the browser.
3. Stop Firefox in the disposable stack; verify Music hides the button, a direct browser link returns 409, and a watched-download POST fails without advancing request status. Restart Firefox and confirm the link returns without restarting Music.
4. Complete a synthetic name request through download to the shared inbox, worker staging and import; verify that existing downloads and browser sessions are not lost. Repeat restart, transient failure and rollback checks; redact credentials, real media filenames and private paths in evidence.

## Rollback

Do not merge if CI or acceptance fails. Within a disposable test only: omit `--browser` (or clear `REMOTE_BROWSER_URL` for direct Compose) and recreate **only the copied-state Music container** if its environment changed. For a code rollback, switch the disposable test to the preceding reviewed commit/images and repeat auth and manual downloader checks. Never overwrite production databases, existing NAS media, secrets or worker state. This release block is tracked in the register #18 (RB-04) and single-bug issue #37.
