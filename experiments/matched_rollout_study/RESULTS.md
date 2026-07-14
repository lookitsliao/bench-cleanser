# Matched-rollout v2 development result (2026-07-13)

## Fresh source-identical cohort result

A fresh immutable acquisition and analysis now exercise the repaired v2
contract end to end. The deterministic development cohort contains 24 tasks
(six hash-selected tasks from each of four repositories), 72 candidates, and
215 of 216 requested patch/report/trajectory artifacts. The only unavailable
artifact is GPT-5's hosted report for `sphinx-doc__sphinx-8475`; its patch and
trajectory are present.

All 24 tasks have known outcomes for all three candidates, so no task is
quarantined. Across the 72 hosted candidate outcomes, 48 are `resolved` and 24
are `failed`:

| pinned submission | hosted resolved | rate over 24 |
|---|---:|---:|
| GPT-5 | 15 | 62.5% |
| Kimi K2 | 15 | 62.5% |
| Claude 4 Sonnet | 18 | 75.0% |
| Best-of-3 hosted oracle ceiling | 18 | 75.0% |

Claude-first already resolves every task that any candidate resolves on this
slice. The observed Best-of-3 headroom above the best single submission is
therefore **zero**. This is a negative selector result, not evidence for the
router:

| maximum hosted-label reveals per task | Claude-first | best non-Claude-first order | fixed hybrid rank-sum | observation |
|---:|---:|---:|---:|---|
| 0 | 18/24; 0 labels | hash-random 16/24; 0 labels | 15/24; 0 labels | no execution/label reveal improves on Claude-first |
| 1 | 18/24; 24 labels | 17/24; 24 labels | 17/24; 24 labels | one reveal still leaves one oracle-resolvable task missed |
| 2 | 18/24; 30 labels | hash-random 18/24; 32 labels | 18/24; 33 labels | other orders recover the ceiling with more reveals |
| 3 | 18/24; 36 labels | hash-random 18/24; 39 labels | 18/24; 40 labels | no policy can exceed the slice's 18-task ceiling |

The label totals are retrospective reveal-accounting proxies, not newly
measured execution cost. All 24 task-level candidate sets contain three
byte-distinct patches. Twenty-three tasks have all three hosted reports, and all
23 have exact group-wise test-ID signatures across submissions; the missing
report makes the remaining task incomparable on that diagnostic rather than a
mismatch.

The acquisition and analysis source identities now match exactly. Repeating
analysis to different output paths produced byte-identical freeze and report
files:

| evidence object | SHA-256 |
|---|---|
| repaired study source (142,188 bytes) | `7afd78959705bdad301239a3fae85a9fb56d0253e9fca63c65ffbe01c3ce83c3` |
| acquisition manifest | `f79578fb9860ef0eb4bf02a62691e98c4002a5de96b8dda9ab2d3616f082b574` |
| durable feature freeze | `b01e8c9408acce759b75bd299f4323a37398e417e80a97ef52f09b8a14abc01c` |
| analysis report | `377198204b1423e9e17415547a1ea35479b0dc1a8678ee31b1f53ee1539cae76` |

These hashes identify the audited local evidence. A paper or empirical release
must still preserve the objects in durable release/DOI storage. The cohort is a
single development slice, not held out or prospectively routed; model and date
remain confounded; exact scaffold and budget equality are unavailable; and no
candidate was independently executed or adjudicated. Hosted labels are
retrospective execution measurements, not candidate truth.

## Source-locked full-frame diversity ceiling

The three pinned S3 frame listings have an exact 499-task intersection. After
decoding the pinned official result categories, `psf__requests-1142` has
`no_logs` outcomes for two submissions. Quarantining the whole matched task
leaves 498 tasks with known outcomes for all three candidates.

On that fully observed frame:

| submission/ceiling | hosted-resolved tasks | rate over 498 |
|---|---:|---:|
| GPT-5 | 358 | 71.89% |
| Claude 4 Sonnet | 352 | 70.68% |
| Kimi K2 | 327 | 65.66% |
| union / Best-of-3 oracle ceiling | 397 | 79.72% |

The union is 39 tasks, or 7.83 percentage points, above the best single pinned
submission. This is a useful candidate-diversity diagnostic: the public sources
contain genuine aggregate headroom for selection research.

It is strictly post-outcome and is **not** evidence that any deployable policy
can recover that headroom. It uses no cohort features, does not choose a policy,
and must not be reported as a new SWE-bench score or model comparison. The
submissions differ in model and date, while exact scaffold/configuration and
resource-budget equality are unavailable.

## Superseded pre-v2 diagnostic

The earlier local 24-task diagnostic happened to select the same deterministic
cohort and reached the same substantive zero-headroom observation, but its
acquisition snapshot predates the repaired decoder and its report predates the
path-independent v2 schema. The source-identical run above supersedes it.

## Superseded one-task smoke

The earlier `django__django-11555` smoke established that the old acquisition,
feature-freeze, and post-freeze label-reveal plumbing could execute end to end.
All three candidates were hosted-resolved, so it contained no discriminating
selection signal. Its old report included an output path and belongs to the
superseded v1 schema; its hash is intentionally not treated as a canonical v2
result identity.

## Next publishable experiment

A publishable next step is a preregistered, prospectively frozen hybrid policy
on held-out repositories/tasks. It should compare patch-static routing against
post-rollout history and measured execution tiers, preserve unknown outcomes,
record actual latency/tool/runtime costs, independently rerun candidates in
pinned environments, and publish the acquisition manifest, feature freeze,
report, code identity, and uncertainty analysis as durable release or DOI
assets.
