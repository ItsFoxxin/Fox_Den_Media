# Issue #76 — isolated replacement-image runtime evidence

**Purpose:** One reusable, source/image-bound evidence bundle for the existing #76-A/#76-B/#76-C reviewers, not a vulnerability disposition or a 1.0.0 approval.

## Historical-image boundary

The protected-`dev` Trivy run [42479159484](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/42479159484) produced per-image vulnerability JSON, CycloneDX SBOM, scanner metadata and security contracts, including *local Docker configuration IDs*. Its three retained artifacts do **not** contain image tarballs, executable filesystem snapshots or OCI manifest digests. The ephemeral runner's actual local Docker images were not recovered by this task. No claim of exhaustive historic-image availability is made for inaccessible external caches.

Generation 1 ([run 42525566004](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/42525566004)) remains historical evidence tied to **source `abccc61f6e766a8c01c8ad7ba241747974b1a33f`**, preceding the #68 Music Python base-image merge. Generation 2 pins the approved source checkout to **post-#68 `dev` commit `46ed8189e2c46f7e0bebbd51c03b60fa0775ba4f`**, with a separate current PR-head **harness SHA**. Do not reuse or relabel generation 1's package, image or runtime evidence as proof for the later source. It rebuilds Portal, Music and Media using `.github/workflows/trivy.yml`'s exact per-component Dockerfile/context identities and `docker build --pull`. The outputs are **reproducible replacement images**, not the historical scan images. The source SHA, harness SHA, image local configuration ID, platform architecture, selected package versions and inspected ELF hashes are included in every JSON report. Because base tags, APT and pip are unpinned to immutable full artifacts, byte-for-byte equivalence to historical images **cannot** be proven. Local Docker IDs are not registry OCI manifest digests.

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


## Generation 2 — specifically requested follow-up coverage

All findings below are **observations only**. They cannot establish a formal CVE
disposition. New `report.json` fields are required by the bundle validator;
old generation reports intentionally fail the updated completeness contract.

| Review | New bounded measurements | What they do **not** prove |
| --- | --- | --- |
| #76-A — MiniZip/Mbed | Selected named MiniZip shared/static archives and /app native extensions, exported and imported symbols including `psa_export_public_key`, native dpkg package ownership, librist.so.4 dependencies and Mbed imports | Global absence of stripped/bundled code, real MiniZip or mbedTLS PSA/FFDH/X.509/TLS invocation or exploitation |
| #76-B — FFmpeg | Synthetic one-frame black AVI encoded/decoded with CineForm HD (`cfhd`) and MagicYUV (`magicyuv`) when supported; FFprobe-selected format/codec and input hash; RASC explicitly fixture-unavailable without verified safe input | Specific application input routes, exploitation or a tested RASC decoder |
| #76-B — Music FFprobe | Synthetic AVI bytes copied to .sub and .mpd filenames, isolated FFprobe selection or rejection and input hash | Real VobSub/DASH format parsing or Music app invocation; these are **extension mislabels only** |
| #76-C — SQLite/XML/GLib | In-memory SQLite copied to disposable tmpfs, read-only URI reopen, `trusted_schema=OFF`, integrity and rejected write; pyexpat/runtime Expat versions, Python libxml2/lxml importability; native libgio GDBus and libavformat/libxml2 imports/dependencies | Untrusted user DB, real application schema/call path, vulnerable GDBus or SAX parser invocation |

`targeted_ffmpeg` records each AVI decoder and mislabeled FFprobe fixture
separately as `pass`, `failed`, `accepted`, `rejected`, or
`fixture_unavailable`. RASC intentionally remains `fixture_unavailable` when
no verified benign decoder fixture exists. Never fabricate an RASC bitstream or
use an exploit payload. The .sub/.mpd fixtures are valid synthetic AVI content
with misleading extensions, not genuine VobSub/DASH bitstreams.

The bounded collector reads selected ELF/static-archive candidates with host
nm/readelf, never uploading binary contents. `not_identified_in_bounded_inventory`
does not mean absent or not affected. Native discovery is limited to system
library roots and a shallow /app scan. The SQLite copy uses disposable
network-disabled tmpfs. Real user DBs, media, secrets, mounts, runtime state
and full container archives are excluded.

Run `python -m unittest discover -s tests/platform -p 'test_image_runtime_evidence.py' -v`
for additional negative tests. Every new source/harness/image-bound generation
needs its own run and artifact links. If dev advances further, revise the
source pin explicitly rather than treating old results as current.

## Local negative tests and operational limit

Run `python -m unittest discover -s tests/platform -p 'test_image_runtime_evidence.py' -v`. Existing monorepo CI supplies Python compilation, actionlint and required CodeQL. This diagnostic job is *additive/advisory* and does not alter Trivy, CodeQL, GHCR publishing or branch protection. Changing the approved source SHA requires a **reviewed workflow change and new evidence**. No `VERSION` bump is appropriate for a non-release diagnostic tool. Rollback is removal of this additive workflow/script; no migration, NAS or production change occurs.
