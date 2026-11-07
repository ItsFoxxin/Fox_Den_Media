# 1.0.0 — host secret and state ownership

The `init` command creates private files as the invoking host user, while Compose uses separate numerical service UIDs. A mode-0600 file created by a NAS administrator cannot be read by a different Portal, Music, or Media UID. **Do not use chmod 644/777 as a workaround.**

## Explicit isolated-install provisioning

1. Audit the isolated env file, `FOXDEN_SECRETS_DIR`, `FOXDEN_RUNTIME_DIR`, all `*_PUID`/`*_PGID`, symlinks and copied paths. Do not run provisioning against Test57, Test51, or live NAS state.
2. In a disposable, separately approved deployment only: `sudo python scripts/foxden.py init --env /path/to/isolated.env --create-paths --apply-permissions`. Install Portal signing-key Python dependencies beforehand. Host root is required only for this explicit provisioning action, not for steady-state containers.
3. Use the approved privileged Python environment to run `sudo python scripts/foxden.py validate full-managed --env /path/to/isolated.env --check-service-owners` to audit per-file ownership; the operator account may no longer be able to read owner-only secret contents after the chown. Adjust mode and optional profile flags as appropriate. The legacy validate operation also renders NGINX configuration; it is not read-only in the current baseline (tracked separately under RB-02).
4. Inspect actual service access under mapped numeric UIDs and record redacted evidence. Group ownership, NAS ACL inheritance, Docker user namespaces, and filesystem semantics can alter access results.

## Scope and security boundaries

- Dedicated secret files are individually chowned to the consumer: `portal-secret`, `portal-bootstrap`, `ingress-auth`, `identity-private.pem`, `oidc-client-secret` to `FOXDEN_PUID`; `music-csrf` and `jellyfin-api-key` to `MUSIC_PUID`; `media-app-token` and `qbit-password` to `MEDIA_PUID`; `wireguard-private-key` to root, for the root-run Gluetun process.
- Private secrets stay `0600`; `identity-public.json` is a public verification key and may stay `0644`.
- Secret and runtime host directories retain their existing operator ownership and use mode `0700`; the Docker daemon mounts explicit individual files, not whole secret directories. The renderer/NGINX access behavior is addressed in the separate RB-02 PR.
- Only empty or newly created application config directories receive non-recursive ownership provisioning. Populated copied-state directories are **intentionally not modified**. Inspect their owners and ACLs manually before acceptance.
- Shared paths (`MUSIC_DOWNLOAD_PATH` used by browser/Music, `MUSIC_LIBRARY_PATH` and `MEDIA_LIBRARY_PATH` read by Jellyfin, `TORRENT_DATA_PATH`, `JELLYFIN_MEDIA_PATH`) are never auto-chowned because their reader/writer identities differ. Review controlled shared groups or ACLs separately.
- No automatic recursive chown, no secret printing, no secret rotation, and no NAS commands are executed by CI.
- The env file and its absolute paths are privileged input. Review them before running the optional root action.

## Test / rollback

CI: `python -m pytest tests/platform/test_host_permissions.py tests/platform/test_deployment.py -q` plus the full monorepo strict gate and CodeQL. Host-level validation of actual bind mounts, the source root and mapped identities remains mandatory.

Rollback: revert the isolated code PR. Before any operator-approved test, save ACL/ownership metadata and source SHA. Restoring filesystem metadata requires an explicit reviewed host procedure, not bulk recursive chmod/chown. Existing secret bytes and persistent data must remain unchanged.
