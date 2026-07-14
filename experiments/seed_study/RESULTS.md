# Seed-study result — 2026-07-12

This is a reproducible **synthetic integration result**, not validation of the
learned routing thesis. It proves that the acquisition, replication, isolation,
artifact, and metric path can collect real observations and that the fixture
contains the intended weak-oracle failure.

## Run identity

- Fixture SHA-256: `69dee7dbd276f073f3b84870750f594035c245737ebdf3699e74299384fa24ce`
- Candidates: 8 total; 2 specification-correct and 6 incorrect
- Acquisitions per runtime: 40
- Local runtime: Node `v24.2.0`
- Container runtime: Node 18 image
  `sha256:c6ae79e38498325db67193d391e6ec1d224d96c693a8a4d943498556716d3783`
- Container controls: no network, read-only root and candidate mount, bounded
  tmpfs/processes/memory/CPU, all capabilities dropped, no-new-privileges

Both runtimes produced the same decision counts:

| Evidence modality | Acquisitions | True accepts | False accepts | True rejects | False rejects | Inconclusive | False-accept risk among accepted |
|---|---:|---:|---:|---:|---:|---:|---:|
| Syntax/static check | 8 | 2 | 5 | 1 | 0 | 0 | 5/7 (71.4%) |
| Narrow targeted test | 8 | 2 | 3 | 3 | 0 | 0 | 3/5 (60.0%) |
| Inherited suite, repeated twice | 16 | 2 | 2 | 4 | 0 | 0 | 2/4 (50.0%) |
| Hardened oracle | 8 | 2 | 0 | 6 | 0 | 0 | 0/2 (0.0%) |

Observed total wall time was 2.73 seconds locally and 8.40 seconds in the
containerized run. These are single-machine integration timings, include
startup/cache effects, and are not general cost estimates.

The result is deliberately small but important: **repeated full execution was
stable and still wrong for two candidates** because the inherited tests did not
cover the complete specification. Stronger execution, not repetition alone,
removed those false accepts. This validates the need to model oracle validity in
the collection pipeline; it does not establish that a learned router can predict
when hardening is necessary.

## Raw-run integrity

The uncommitted machine-local reports used for this summary were:

- local report SHA-256:
  `d6134fa3a3840226119c771c1f4f3e192430730872ef2bef4641702cc95f57dd`
- container report SHA-256:
  `123fc9a31678a8215bb623eeb2c880c7e109abf6b0fe26eac0e97cbbe8efdabd`

Each report refers to 40 separate, digest-bound acquisition artifacts. The raw
artifacts contain machine-local paths and are intentionally not presented as a
publication dataset.

## Hard limitations

- One hand-authored JavaScript task is not a representative SWE distribution.
- Candidate truth is specification-derived, not blinded multi-annotator truth.
- Candidates are not sampled from contemporary agents.
- There is no randomized acquisition policy, calibrated router, prospective
  held-out stream, confidence interval, or downstream SFT/RL experiment.
- Therefore none of the percentages above may be generalized or used in a
  paper abstract; they are fixture-level counts only.
