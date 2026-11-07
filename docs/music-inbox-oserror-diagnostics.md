# Music inbox handoff: read-only `OSError` diagnostics (issue #23)

**Status: investigation only — cause not established.** This instrumentation
does not claim a new bug fix, increment the release version, or authorize a
NAS deployment.

## Why this investigation remains open

Test57's historical `0.9.1` worker logs show repeated `AttributeError`
events followed by an `OSError`, but do not record the failing syscall,
numeric errno or traceback. Release candidate `0.9.2` addressed the
`InboxFile`/ORM variable collision and bounded repeated recovery filenames.
That makes `ENAMETOOLONG` a plausible hypothesis, **not** a confirmed
diagnosis of the observed NAS error.

Other candidate failures include `EXDEV` during routing/copying,
`EACCES`/`EPERM` for container UID/GID/ACLs, unavailable staging
storage, or a failed cleanup/recovery. The actual fault cannot be established
from the existing log alone.

## New diagnostics

The Music worker's existing JSON error record may now include both a numeric
`exception_errno` and a fixed `handoff_operation` string when an `OSError`
occurs inside an instrumented operation. Illustrative **synthetic** example:

```json
{"message":"Automatic server-download handoff failed","exception_type":"OSError","exception_errno":18,"handoff_operation":"stage_file_move"}
```

The operation values come from a static code allowlist, never from a filename,
absolute path, provider URL or exception message. If a filesystem failure
occurs outside an instrumented checkpoint, the record may include errno but
**no** operation label; the absence of a label must not be guessed or
misinterpreted.

Relevant stages include request-directory creation, top-level browser
download routing, original source inspection, staging directory creation,
copy/move/chmod, staged artifact and event size stat, and restoring a file
after a rolled-back handoff. The original error type, errno and traceback
remain available for internal exception handling; sensitive exception
messages and filesystem paths are not rendered by the JSON formatter.

Synthetic regressions demonstrate:
- `EXDEV` while staging a file preserves the source bytes and identifies
  `stage_file_move`;
- `EACCES` on restore preserves the already staged bytes and identifies
  `restore_staged_file_move`;
- a vanished staged artifact identifies `staged_artifact_stat`;
- nested labels preserve the innermost operation; unapproved labels and
  private paths are never emitted in the structured JSON.

## Evidence needed to close #23

Collect **read-only**, redacted evidence from the intended environment
*only with explicit authorization*. Do not restart or modify Test57, Test51,
NAS, or production solely to obtain a new log.

1. Capture the relevant UTC timestamp, error class, numeric errno and — if
   present in a separately approved disposable reproduction — the fixed
   `handoff_operation` label. Do not publish real filenames or paths.
2. Correlate that timestamp with the worker's active acquisition state,
   request-scoped inbox vs staging location, and whether bytes remained in
   either location; use read-only inspection.
3. Record whether download/inbox and staging are the same filesystem,
   and only the required configured worker numeric identity and directory
   access metadata; do not publish raw environment/secrets.
4. Reproduce the *specific confirmed operation* on a separately approved,
   disposable copy. Verify no loss, exactly one eventual import, safe
   retries, and a documented rollback.
5. Once the root cause is demonstrated, implement a **separate**, one-defect
   `0.9.3` patch PR linked to issue #23 as `Fixes #23`. Do not claim that
   this diagnostics PR fixed an unconfirmed error.

No new downloader, migration, auto-import bypass, broad file cleanup or
production deployment is introduced. Existing manual validation and review
boundaries remain intact.
