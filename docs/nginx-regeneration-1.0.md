# Ingress configuration regeneration — 1.0.0 candidate

Baseline: `dev` `6c7f4b1`. Scope: `scripts/foxden.py` and tests only. No NAS changes.

## Failure mode

The deployment CLI previously regenerated `FOXDEN_RUNTIME_DIR/nginx.conf` during *every* `validate`, `config`, `deploy`, and `stop` invocation. Each render creates a new mode-`0600` inode owned by the CLI user, then replaces the existing file. Ingress runs as the distinct `FOXDEN_PUID:FOXDEN_PGID` and may become unable to read it. A Docker **file bind mount references a file inode**: atomic replacement on the host does not make a running container automatically see the new inode.

## Change

- `validate`, `stop`, and `deploy` **without** `--execute` no longer write or regenerate the configuration. Only explicit `config` or `deploy --execute` renders.
- The renderer atomically creates a secret-bearing file at mode `0600` and sets owner/group to `FOXDEN_PUID:FOXDEN_PGID` **before** replacement.
- A failure to assign owner or unsafe existing target aborts without replacing the prior configuration; symlink and hardlink targets are refused.
- When content and owner/mode are already correct, renderer returns without changing the inode.
- Do not log `ingress-auth` contents or the generated NGINX file.

## Operational restrictions

- A *separate*, administrator-authorized configuration render may require host root to read `ingress-auth` once RB-01 provisions owner-only secrets and to assign the non-root ingress UID. Do not weaken the mode or make secrets world-readable to avoid this.
- An explicitly authorized `deploy --execute` runs scoped Compose `up -d`, then **recreates only ingress** with `up -d --no-deps --force-recreate ingress` if the first operation succeeded. This refreshes the file bind mount without forcing recreation of stateful application writers. `config` alone does not restart ingress; when used against an existing stack, a separate approved ingress recreation is still required. Do not run these commands against Test57, Test51, or production.
- Rendering safely writes the host file; it does not automatically test a running container's NGINX syntax. Acceptance requires `nginx -t` in a disposable container using the rendered file with the full expected paths/user, and `docker compose config --quiet` for the chosen mode.
- The `ingress-auth` value is embedded in the generated config by design. Restrict backups/diagnostics as secrets; never publish the file or expanded configuration.
- Verify that `FOXDEN_RUNTIME_DIR` is dedicated to the isolated installation and that the selected UID maps to the correct host identity (including Docker user namespaces/NAS ACL behavior).

## Verification / rollback

CI: `python -m pytest tests/platform/test_nginx_regeneration.py tests/platform/test_deployment.py tests/test_ingress_config.py -q`, strict monorepo validation and CodeQL. Review pending host/runtime evidence before release.

Rollback: revert this PR code, preserve prior protected configuration and read-only backup. Do not revert by changing permissions to 0644 or replacing the running ingress bind mount without an approved test. No automatic restart/deployment is performed by these changes.
