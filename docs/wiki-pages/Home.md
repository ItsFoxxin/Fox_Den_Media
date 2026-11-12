# Fox Den Media Wiki

Fox Den Media is a **modular, self-hosted media platform** with a unified Portal and Nginx ingress, a music request/processing workflow, Movies & TV requests and reviewed imports, and optional Jellyfin, Firefox, and VPN-managed download services.

> **Current status (reviewed 2026-11-07):** The `dev` branch advertises **0.9.6**, a security-hardened *copied-state rehearsal candidate*. `main` currently reports **0.9.1**. Neither is an approved public 1.0.0 release, and no GitHub Release is published. This Wiki is installation/development guidance, **not** NAS cutover approval.

## Start here

| I want to… | Read |
| --- | --- |
| Understand the platform | [[What Is Fox Den Media?|What-Is-Fox-Den-Media]] and [[Features and Components|Features-and-Components]] |
| Check hardware and prerequisites | [[System Requirements|System-Requirements]] |
| Try an isolated local deployment | [[Quick Start|Quick-Start]] |
| Select a deployment mode | [[Deployment Modes|Deployment-Modes]] |
| Configure a service | [[Configuration|Configuration]] |
| Diagnose startup problems | [[Troubleshooting|Troubleshooting]] |
| Review security boundaries | [[Security Overview|Security-Overview]] |
| Help develop or test | [[Development Setup|Development-Setup]] and [[Contributing|Contributing]] |

## What runs together?

The Portal and ingress are the common entry point. Music web and worker, Movies/TV, the Firefox server browser, the official Jellyfin server, and managed qBittorrent/Gluetun are separately selected modules. The browser needs Music; Jellyfin can run separately or as an add-on.

Fox Den **does not currently** provide embedded Jellyfin playback, released Android/Wear OS clients, automatic torrent cleanup or an approved production migration.

## Documentation policy

- **Source of truth:** [repository README](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/README.md), [documentation index](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/README.md) and maintained [deployment guide](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/deployment.md), [configuration](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md), [security guide](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/security.md).
- **Development vs. release:** Links to `dev` describe integration code and may change. Release operators must use a separately reviewed release tag/digest when one exists.
- **Privacy:** Never paste deployment secrets, private addresses, live storage layouts, real authentication cookies or VPN keys into public Wiki pages or issues.
- **Release gate:** [1.0.0 acceptance checklist](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/release-1.0-checklist.md) and [production readiness](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/production-readiness.md) remain authoritative for pending acceptance.

Use the sidebar for all topics. See [[Release History and Roadmap|Release-History-and-Roadmap]] for current progress.