# Android and Wear OS media roadmap

No Android or Wear OS binaries are part of 0.7. This document defines the
backend boundary so native clients do not require a second media backend.

## Shared client contract

`/api/watch/v1` is the first read-only contract. Later compatible additions
will cover:

- an OAuth-style authorization-code/device flow for Fox Den client sessions;
- device registration, names, last-used timestamps, revocation, and rate limits;
- library browsing, search, metadata, and artwork;
- user-scoped playback authorization without tokens in URLs;
- playback start/progress/stop synchronization with Jellyfin;
- queues, playlists, favorites, and per-device handoff;
- short-lived stream authorization and capability negotiation.

Browser cookies are the implemented web transport, not the permanent mobile
identity design. Future native tokens must be revocable, audience-bound,
scoped, stored in Android Keystore, and independent of internal Ed25519 module
assertions. Private signing keys and Jellyfin administrator credentials never
belong on a client.

## Android milestone

Use Kotlin and Jetpack Compose with the versioned Fox Den API. Use Android
Media3 for playback, MediaSession, audio focus, notifications, transport
controls, queue state, and lock-screen/Bluetooth integration. Prove direct play,
transcoding, subtitles, seeking, background restrictions, and progress sync
against disposable users before production.

## Wear OS milestone

Start with standard MediaSession controls for playback active on the paired
phone. This automatically supplies the safest useful watch experience before a
custom application exists. A later companion may use Wear OS Data Layer for
queue browsing, artwork, favorites, device selection, and remote commands.

The watch must reuse the paired Android identity/session and must not introduce
an independent media authentication system. Fox Den SOC identities and
permissions remain completely separate.
