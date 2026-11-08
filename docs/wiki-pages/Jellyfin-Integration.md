# Jellyfin Integration

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Fox Den Media can run the **official Jellyfin server** as a selected module or connect to an external Jellyfin service. Jellyfin retains its own accounts and media permissions.

## What Fox Den provides

- Optional `jellyfin` Compose profile with persistent configuration/cache and read-only library mounts.
- Watch & Listen at `/watch/`, scoped to each Portal user's **own linked Jellyfin identity**.
- Browsing, search, art, continue-watching and playback **handoff** to Jellyfin Web; no embedded player is promised.
- An optional, *separate* Music-worker API-key integration for requesting library refreshes.

## Boundaries

Use a dedicated Jellyfin hostname so TV/desktop/mobile native clients can authenticate without browser-only forward auth. Linking Jellyfin does not make a user a Portal admin, nor vice versa. Real schema/plugin compatibility, playback, client behavior and optional GPU transcoding require isolated runtime acceptance.

Read [Jellyfin deployment and routing](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/jellyfin.md), [Watch & Listen security model](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/watch-listen.md), [copied-state migration](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/jellyfin-migration.md), and [identity boundaries](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/authentik-jellyfin-auth.md).