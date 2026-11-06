# Next steps after 0.9.1

The repository is **Fox_Den_Media**, with protected default/stable **`main`** and protected integration **`dev`**. The historical repository rename and stacked integration PRs are already reflected in this codebase; do not repeat them. Documentation and application PRs target `dev` before any separately reviewed `main` promotion. See [CI](docs/ci.md) and [historical migration checklist](docs/github-migration-checklist.md).

## Before a NAS rehearsal, stable promotion or release

- [ ] Review [production-readiness blockers](docs/production-readiness.md) and prepare isolated [Ugreen deployment](docs/ugreen-nas.md) and [side-by-side rehearsal](docs/side-by-side-migration.md).
- [ ] Record exact current NAS images/digests, Compose projects, mounted paths, users/groups/ACLs, plugins, proxy hosts, backup capacity and prior-service health.
- [ ] Take a consistent verified backup, protect media/torrent payloads separately and rehearse restore/rollback on **copied** state.
- [ ] Build/start all selected images on the actual Linux Docker host using isolated state; verify numeric identities and host bind permissions.
- [ ] Confirm Portal login, administrator-only acquisition routes, Music intake/browser, Media import/checksum, Jellyfin user/native clients and configured OIDC + emergency local recovery.
- [ ] Resolve the existing qBittorrent resume/payload gap and verify the **managed-mode** Gluetun tunnel, killswitch, health and port forwarding with separately approved staging credentials. The prior existing NAS Gluetun DNS-health correction does not satisfy this gate.
- [ ] Freeze image digests and configuration versions and collect time-stamped rollback evidence.
- [ ] Revisit [1.0.0 release checklist](docs/release-1.0-checklist.md) for explicit go/no-go and separate production change approval. Do not mark release-ready merely because CI passes.

## Follow-on product work (not part of the release gate)

- Reviewable indexer/resolver for names and metadata links without CAPTCHA bypass.
- Movie/TV metadata matching and incremental series imports with no-overwrite semantics.
- Pre-existing media inventory/baseline approval and optional independently retryable Jellyfin refresh for video imports.
- Optional hardlink imports only where sharing inodes is explicitly safe and accepted.
- File-level progress/cancel, paginated audit history, cross-library duplicate checks.
- Browser-session maximum lifetime/revocation strengthening and additional security hardening.
- Follow the [roadmap](docs/ROADMAP_TO_3.0.0.md) for UI refinements and future mobile/Wear OS.

Never enable automatic source/torrent deletion, replacement of library media or weakened VPN isolation without a separate reviewed policy.
