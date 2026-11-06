# Consolidation record

This branch preserves Music Downloader as the canonical first-parent lineage.
Authoritative Music was relocated to `apps/music` from integration commit
`85904c45a79421cd4a1e00378c231bb08c1a03fc`, which includes release security
fix `c0443de55d3d5f83ef051d79e923539c95860f39`.

Media Downloader head `9656a0cc653659a92e48c9c2cc81e2c53344ed60`
was initially rewritten in a disposable clone. The `music/` subtree was removed
from every commit before the histories were joined. Twenty-one original commits
mapped one-to-one to twenty-one rewritten commits, ending at
`5e5c6c5a4dcb2d86eff3e3a0057214c7020ac808`.

The legacy integration branch later gained four commits through
`af1a186be2363291e491ba13de6f14070010fb8e`. The same filter was reproduced
against the existing rewritten head and the four commits were continued as
`f4e807a7691b40ea42eec9aeea290bd4cb9e1e0c` through
`81cf15c267c6b3a860e7c8b0d9c9b106625a0b54`. Author and committer names,
emails, dates, subjects, parent order, and filtered trees were verified. The
continuation is joined with an `ours` merge so its provenance is reachable
without restoring obsolete pre-monorepo paths. Relevant readiness, volume
initialization, and restart-recovery behavior is reconciled separately in the
current monorepo paths.

The four legacy changes are accounted for as follows:

- `146571c` pinned an external Music checkout in the legacy CI workflow. It is
  superseded because monorepo CI tests `apps/music` from the same commit.
- `c4a9153` is retained by waiting for both routed modules before integration
  requests begin.
- `fda2e30` is retained by creating both `/music-config/cache` and
  `/music-staging/.upload-tmp` in the single privileged volume initializer
  before either non-root Music process starts. The Music config mount uses
  `nocopy: true` so concurrent container creation cannot race Docker's automatic
  image-to-volume copy-up before the initializer runs.
- `af1a186` is retained by polling Music and Movies/TV after the restart rather
  than issuing a one-shot request during recovery.

See `media-commit-map.csv` for the complete twenty-five-commit mapping.

The original repositories, branches, releases, PRs, and production deployment
were not renamed, merged, deleted, or deployed as part of this operation.
