# Firefox Server Browser

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Fox Den Media offers an optional **admin-only contained Firefox browser** using the `browser` Compose profile and a noVNC/WebSocket experience through ingress.

## Enablement

The browser requires Music. With `scripts/foxden.py`, add `--browser` to the chosen Music-capable mode. For direct Docker Compose, enable the browser profile **and** set `REMOTE_BROWSER_URL=/server-browser/`; either alone is insufficient.

## Security and availability

- Only authorized Portal administrators should reach the browser.
- If Firefox's internal HTTP frontend is unavailable, the Music browser action is hidden or fails closed. A successful HTTP request is **not** proof of working Firefox/RFB/noVNC.
- WebSocket connections have a separate authorization/revalidation boundary; historical security documents must be read in the context of the current source.
- Exact digest-pinned image startup, real WebSocket operation and mobile behavior still need an independently approved disposable-runtime test.

Read [availability behavior](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/browser-availability-0.9.5.md), [browser security review](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/browser-session-security-1.0.md), [image review](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/browser-image-1.0-review.md) and [acceptance checklist](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/nas-current-dev-acceptance.md).