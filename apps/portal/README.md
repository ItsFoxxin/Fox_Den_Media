# Fox Den Portal foundation

The Portal provides local authentication, optional OIDC,
Portal-owned SQLite state, mocked module contracts, and failure-isolated module
status aggregation, administrator-only module navigation, and a user-scoped
Watch & Listen adapter for external or managed Jellyfin.

See `docs/phase-1a` for architecture, threat model, demo, and Authentik setup.
The language-neutral v1 module and identity contracts live in `contracts/v1`.
Watch & Listen is documented in `docs/watch-listen.md` and uses `/api/watch/v1`.
