# Fox Den Media 0.9.0 release-candidate checklist

## Repository evidence

- [ ] Exact 0.9.0 commit recorded and all hosted jobs pass without waivers.
- [ ] PR remains stacked after 0.8.0 and no parent history is flattened.
- [ ] Dependency, history-secret, Compose, container and VPN fixture gates pass.

## Copied-state rehearsal

- [ ] Complete storage inventory has no missing required roles.
- [ ] Music 2.3.4 SQLite and job/download state are structurally readable.
- [ ] Consolidated Music starts against a copy and preserves history, pending work, imports and Jellyfin refresh.
- [ ] Jellyfin 10.11 starts against copied config/cache with `/media` unchanged.
- [ ] Jellyfin users, history, progress, plugins, providers, web and native clients pass.
- [ ] qBittorrent metadata/resume pair and payload location are confirmed offline.
- [ ] Gluetun HTTPS egress and tunnel-loss fail-closed behavior both pass.
- [ ] Authentik and restricted local emergency administrator recovery pass.
- [ ] Radio continues reading the unchanged Music library path.
- [ ] Software transcoding works; hardware transcoding is optional and must be proven by a real synthetic transcode.

## Backup and rollback

- [ ] Old writers are stopped before each final SQLite-bearing backup.
- [ ] Archive, external manifest, embedded manifest and every file checksum pass.
- [ ] Restore targets are empty, isolated and preserve reviewed ownership/modes.
- [ ] Rollback uses an immutable pre-migration copy, never a database modified by a newer application.
- [ ] Operator reviews the human and machine readiness reports.

Any unchecked critical item keeps the decision `BLOCKED`. Passing 0.9.0 means
ready to perform a controlled rehearsal; it does not authorize production cutover.
