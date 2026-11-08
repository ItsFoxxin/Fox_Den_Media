# Issue #76 — isolated replacement-image runtime evidence

**Purpose:** One reusable, source/image-bound evidence bundle for the existing #76-A/#76-B/#76-C reviewers, not a vulnerability disposition or a 1.0.0 approval.

## Historical-image boundary

The protected-`dev` Trivy run [42479159484](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/42479159484) produced per-image vulnerability JSON, CycloneDX SBOM, scanner metadata and security contracts, including *local Docker configuration IDs*. Its three retained artifacts do **not** contain image tarballs, executable filesystem snapshots or OCI manifest digests. The ephemeral runner's actual local Docker images were not recovered by this task. No claim of exhaustive historic-image availability is made for inaccessible external caches.

The new diagnostic workflow uses the **approved source checkout pinned to `abccc61f6e766a8c01c8ad7ba241747974b1a33f`** (`dev` after #67), with the separate current PR-head **harness SHA**. It rebuilds Portal, Music and Media using `.github/workflows/trivy.yml`'s exact per-component Dockerfile/context identities and `docker build --pull`. The outputs are **reproducible replacement images**, not the historical scan images. The source SHA, harness SHA, image local configuration ID, platform architecture, selected package versions and inspected ELF hashes are included in every JSON report. Because base tags, APT and pip are unpinned to immutable full artifacts, byte-for-byte equivalence to historical images **cannot** be proven. Local Docker IDs are not registry OCI manifest digests.

## How to use

1. Review the *draft* evidence PR to `dev`; its standalone `Issue 76 isolated image runtime evidence (diagnostic)` workflow builds all three images on a GitHub-hosted ephemeral runner. It has only `contents: read` permission, no secrets, no registry push, and no production connection.
2. Require exact-head success of its `negative-tests`, all three `evidence` matrix jobs and `bundle`. Download `image-runtime-bundle-<run-id>` with three `report.json` / `summary.md` pairs plus `manifest.json`; per-component artifacts are also provided. The report hash in the manifest binds each JSON file to the bundle.
3. Recheck the manifest's `source_sha`, `harness_sha`, each `image_id` and report hashes. A copied bundle can be checked using `python scripts/image_runtime_evidence.py verify --source-sha <source> --harness-sha <harness> --reports-dir bundle --output bundle/manifest.json`.
4. Forward **only non-sensitive** reports to the existing reviewers, preserving the full identities and limitations. Never post a formal not-affected/fixed/excepted determination from this collector.

## Evidence interpretation by existing review stream

| Review | Evidence provided | Remains unproven |
| --- | --- | --- |
| #76-A — zlib / MiniZip, Mbed TLS | Package versions; identified ELF SHA-256, `DT_NEEDED`, selected `inflate`/MiniZip and Mbed TLS `dhm`/crypto/X.509/TLS exported symbols; synthetic zlib roundtrip | Actual vulnerable API invocation, MiniZip application call paths, real Mbed TLS FFDH/TLS negotiation and reachability |
| #76-B — FFmpeg and other media libraries | Exact FFmpeg encoder/decoder/demuxer/muxer/filter/protocol *registrations*, libaom/FFmpeg library linkage, synthetic MPEG-4 encode/mux/demux/decode | Any specific untested codec/demuxer/filter/protocol path; attacker-controlled inputs or application routes |
| #76-C — SQLite, GLib, libxml2, Expat | Live `sqlite3` compile options/version, in-memory FTS5 and JSON1 probes, `_sqlite3`/libsqlite linkage, session-related symbols, GLib/libxml2/Expat parser exports and fresh synthetic Expat parse | Session API invocation, real application SQLite schemas or affected SQL shapes, GLib/libxml2 runtime parser invocation, unsafe XML or live data exposure |

`readelf` and `nm` run **on the GitHub host against temporary, selected system-library ELF copies**; copies are not uploaded. Synthetic runs use non-root image defaults in disposable containers with `--network none`, `--cap-drop ALL`, `--read-only`, `no-new-privileges`, resource limits and at most an isolated `/tmp` tmpfs for the FFmpeg fixture. No real user data, `.env`, container filesystem tarball or private application state is collected. The collected package/binary inventory is intentionally bounded to named system locations and symbols; missing evidence must **not** be translated into proven absence. FFmpeg registration != application invocation; symbol presence != exploitability.

## Local negative tests and operational limit

Run `python -m unittest discover -s tests/platform -p 'test_image_runtime_evidence.py' -v`. Existing monorepo CI supplies Python compilation, actionlint and required CodeQL. This diagnostic job is *additive/advisory* and does not alter Trivy, CodeQL, GHCR publishing or branch protection. Changing the approved source SHA requires a **reviewed workflow change and new evidence**. No `VERSION` bump is appropriate for a non-release diagnostic tool. Rollback is removal of this additive workflow/script; no migration, NAS or production change occurs.
