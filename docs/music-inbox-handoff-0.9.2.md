# Fox Den Media 0.9.2 candidate — Music browser inbox handoff

**Baseline:** `dev` `6c7f4b11a7a6978162057922d788fd9a85fb2d78`, currently rehearsed as isolated NAS Test57. This branch is review-only. No NAS or protected-branch change is approved.

## Confirmed defect

In `apps/music/backend/src/foxden_music/inbox_automation.py`, the selected `InboxFile` was stored in `candidate`. A resolved manifest with a `release_id` and `musicbrainz_payload` replaced `candidate` with a SQLAlchemy `ReleaseCandidate`. The later `add_event` payload tried to access `candidate.relative_path`, raising `AttributeError` before the DB transaction could commit.

The patch keeps `inbox_file` immutable throughout filename/reference tracking and uses `release_candidate` for the ORM object. Import jobs still retain their chosen MusicBrainz edition and confidence. No request workflow, search UI, downloader integration, schema or new migration is changed.

## Rollback and retry contract

- `database.session()` rolls back the transaction on exceptions. On a failed handoff, there must be **no committed** Job, ReleaseCandidate, AcquisitionArtifact, import association or transition to VALIDATING.
- With `download_inbox_move_files=true`, recovery returns the staged file to the scoped inbox using a unique `recovered-...` basename, then cleans the temporary job tree. A later worker polling pass can claim it once. The regression verifies original payload bytes and no double import.
- If recovery itself raises `OSError`, the worker must keep the **original exception** as the primary reported failure and log the secondary recovery exception with the import/acquisition IDs. Any remaining staged source must be treated as operator-recoverable; do **not** recursively clear `/staging/jobs` or rerun import on an unknown file.
- A staging `OSError` before database mutation is independent of the `AttributeError`. If the request's inbound file remains, it can be retried after fixing access. Auto-retry must not silently duplicate a committed handoff.
- Other recovery failure types, interrupted worker process/host crash and cross-device moves still require separate stress/rehearsal evidence. Passing synthetic tests is **not** proof of a transactional filesystem.

## 2026-11-07: new read-only Test57 log evidence

Test57 logged ten `AttributeError` handoff failures between 00:02:45 and 00:03:04 UTC, followed by one `OSError` at 00:03:06 UTC. The JSON log formatter emitted only `exception_type`; it did not include a numeric errno or traceback. The exact errno therefore **cannot be established** from these historical lines.

The recovery path prefixes the filename with `recovered-<8 hex digits>-` after every failed transaction; successive retries may repeatedly prepend prefixes, eventually reaching a filesystem component-size limit and raising `ENAMETOOLONG` (`errno=36` on typical Linux hosts). This is a strong mechanistic candidate for the observed transition from `AttributeError` to `OSError`, **not yet confirmed without errno**.

The 0.9.2 candidate now strips existing generated recovery prefixes, caps UTF-8 basename length to 255 bytes while retaining the extension and adds a synthetic 18-retry test proving file contents, database rollback and subsequent successful handoff. The structured JSON logger now emits a numeric `exception_errno` for future `OSError` events without disclosing paths or exception messages.

## Subsequent `OSError` investigation

Do **not** assume that the observed NAS `OSError` is a direct consequence of the variable collision. Distinguish these paths from timestamped, *redacted* traceback frames and errno:

| Location | Likely category | Safe diagnostic evidence |
| --- | --- | --- |
| `source.rename(destination)` | Cross-device rename (`EXDEV`), denied write (`EACCES`/`EPERM`), destination conflicts | Relative mount relationship and UID/GID/ACL metadata |
| `stage_inbox_file` (`mkdir`, `shutil.move`, `chmod`) | Staging owner/ACL, path availability, quota, read-only volume | Container UID and modes of *copied-state* directories |
| `staged_path.stat()` | File disappeared / permissions changed / storage error | Sanitized path, errno and safe stat metadata |
| `_restore_staged_file` (`shutil.move`, cleanup) | Recovery destination unavailable, permission failure, missing staging path | Whether staged source or recovered inbox file remains |
| SQLite transaction commit | Database/storage I/O failure | Sanitized exception class and error code, filesystem free space, container access |

Never include personal library names, provider cookies, secret material or raw container env in public PR logs. A read-only, redacted Test57 traceback may be collected separately without changing that environment. Do not attempt a NAS repair until root cause is established.

## Release metadata and checks

Root and Movies/TV `VERSION`, Compose Portal/Movies default tags, README and dated CHANGELOG advance together to candidate `0.9.2`, as required by `scripts/check_release.py`. The Music component remains `2.5.1`: this is an integration hotfix, not a separately approved Music component version promotion.

Required:
- `python scripts/check_release.py`
- `python -m pytest -c apps/music/backend/pyproject.toml apps/music/backend/tests/test_inbox_automation.py -q`
- Full Music suite under Python 3.12/3.13, coverage threshold, strict Monorepo workflow, CodeQL and dependency/secret audits
- `docker compose --env-file deploy/examples/full-managed.env.example -f deploy/compose.yaml --profile music --profile media --profile managed --profile browser config --quiet`
- On a separately **approved disposable** copied-state environment: browser request with populated MusicBrainz manifest, selected edition persisted, attachment → validation queue → import, no duplicate on second poll, interruption/retry, filesystem error injection, successful restore and private-path permissions.

**Rollback:** revert the focused PR/code changes to `dev` (after approval) or return the copied test to its exact pre-change snapshot. No schema migration, existing secrets rotation, service restart or NAS deployment is requested. Do not deploy `0.9.2` on Test57 or production without explicit approval.
