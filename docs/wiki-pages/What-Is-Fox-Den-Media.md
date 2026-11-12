# What Is Fox Den Media?

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

Fox Den Media combines several independently deployed media workflows behind a shared Portal. It is intended for people who want to manage their own media services while keeping authentication, storage boundaries and changes reviewable.

## Core idea

- **One entry point:** Nginx ingress and Fox Den Portal.
- **Modular services:** Turn on Music, Movies/TV, Jellyfin, a contained server browser and managed download services as needed.
- **Separate state:** Components retain individual databases, application state and container lifecycles.
- **Reviewed acquisition:** Media requests and imports are distinct from playback and use validation/review boundaries.
- **Safe migration:** A copied-state rehearsal and explicit restore/rollback evidence precede any approved production cutover.

This is **not** a replacement for Jellyfin's native accounts or clients. Fox Den's Watch & Listen interface hands playback to Jellyfin Web.

Read [[Features and Components|Features-and-Components]] and [the architecture reference](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/architecture.md). The [roadmap](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/ROADMAP_TO_3.0.0.md) describes proposals rather than implemented guarantees.