# Architecture

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Fox Den Media is a modular monorepo with one HTTP ingress, one Portal, and independently deployed application processes and persistent state.

~~~text
Browser -> HTTPS reverse proxy (operator-owned, when remote)
        -> Nginx ingress -> Portal
                         -> Music web -> Music worker
                         -> Movies & TV
                         -> Firefox/noVNC (optional)
Jellyfin native clients -> dedicated Jellyfin hostname (optional)
Movies & TV -> qBittorrent (external or via managed Gluetun)
~~~

## Trust boundaries

Portal authenticates users and protects module routes; internal service claims are signed. Jellyfin retains native identities. The managed downloader's network namespace and host mounts determine security and data boundaries. Host ports remain restricted and app backends should not be directly exposed.

Refer to the versioned [architecture description](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/architecture.md), [Compose topology](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/deploy/compose.yaml), [ingress configuration](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/infra/gateway/portal-ingress.conf) and [architecture decision record](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/adr/0002-modular-monorepo-and-portal.md). Historical ADRs/phase plans may be superseded; prefer the current code and deployment guide.