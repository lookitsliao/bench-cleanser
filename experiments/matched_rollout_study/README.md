# Matched three-rollout development study

This experiment matches three checked, single-attempt submissions from the
OpenHands submission family over the same SWE-bench Verified tasks:

- GPT-5: `20250807_openhands_gpt5` (499 task prefixes);
- Kimi K2: `20250716_openhands_kimi_k2` (500 task prefixes); and
- Claude 4 Sonnet: `20250524_openhands_claude_4_sonnet` (500 task prefixes).

That is the strongest identity claim supported by the public metadata. Exact
scaffold/code version, system prompt, agent configuration, environment,
resource budget, and runtime are not pinned and therefore are **not claimed as
matched**. Model and generation date also remain confounded.

The common frame contains 499 tasks. The default development cohort freezes 24
tasks: six outcome-blind hash-selected tasks from each of the four largest
eligible repositories. It is a deterministic development slice, not a
population sample or held-out benchmark.

## Question and evidence timing

Given three already-generated candidates for one task, the study freezes a
complete ordering and retrospectively asks which candidate would be selected
under equal maximum hosted-label reveal budgets from zero to three. It compares
seeded random, patch-static risk and size, post-rollout history size, a fixed
rank-sum hybrid, and submission-priority baselines.

Two evidence classes must not be conflated:

- patch-static features can be computed from the candidate diff without
  executing its tests; and
- trajectory structure is **post-rollout tool/history evidence**. Public
  trajectories may contain shell and test execution, and their already-incurred
  execution, latency, and infrastructure cost is not reconstructed here.

Accordingly, this is not an execution-free selector experiment. It is a
reference-free retrospective ordering study with both pre-execution patch
features and post-rollout history features.

## Provenance and leakage contract

Production acquisition pins and preserves:

1. the exact SWE-bench experiments Git revision, metadata, official results,
   raw S3 frame listings, and selected patch/report/trajectory objects by byte
   count and SHA-256;
2. the canonical `princeton-nlp/SWE-bench_Verified` parquet at revision
   `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, 2,096,679 bytes, SHA-256
   `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`;
3. the exact canonical task-ID/repository projection plus each task's full
   `base_commit` and `environment_setup_commit`; and
4. the acquisition script bytes under a stable logical path and digest.

The canonical parquet reader projects only task identity columns. Gold patches,
test patches, problem statements, hints, and oracle test columns never enter
feature construction.

Analysis projects the validated acquisition manifest into a typed,
outcome-sanitized interface containing only selected task/submission identity,
canonical commit identity, and patch/trajectory artifact identity. It cannot
carry `results.json`, `report.json`, their URLs, sizes, digests, or availability.
The analyzer then:

1. builds and durably writes the feature/order freeze;
2. reloads its canonical bytes and exactly rederives it from the sanitized
   inputs; and only then
3. decodes official outcome categories and optional hosted reports.

Reports contain content identities, never output paths, so identical analysis
bytes produce identical report bytes across directories. Tests also prove that
outcome flips cannot change features/orders and that a tampered durable freeze
fails before label decoding.

## Outcome contract

Official outcomes are typed as `resolved`, `failed`, `no_generation`, or
`no_logs`. The latter two carry `hosted_resolved = null`; they are never cast to
failure. If any candidate for a task is unknown, the entire task is quarantined
from matched policy rates. A reveal of an unknown candidate still consumes a
reveal in the low-level budget semantics, but cannot count as success or
failure.

The report also records exact candidate-patch SHA-256 diversity and compares
the group-wise hosted-report test-ID signatures across submissions. Missing
reports are reported as incomplete comparability, not silently treated as a
match.

## Reproduce

Acquire to a new directory; the command refuses an existing target:

```bash
python experiments/matched_rollout_study/run_study.py acquire \
  --artifact-dir /tmp/bench-cleanser-matched-rollouts \
  --repositories 4 --tasks-per-repository 6 \
  --workers 8 --retries 3
```

Then freeze predictors and analyze. Both outputs must be new paths outside the
immutable acquisition tree:

```bash
python experiments/matched_rollout_study/run_study.py analyze \
  --artifact-dir /tmp/bench-cleanser-matched-rollouts \
  --freeze-output /tmp/bench-cleanser-matched-rollouts-freeze.json \
  --output /tmp/bench-cleanser-matched-rollouts-report.json
```

No LLM or API key is used. Offline contract tests do not access the network:

```bash
pytest tests/test_matched_rollout_study.py -q
```

[`RESULTS.md`](RESULTS.md) separates the source-locked, post-outcome full-frame
diversity ceiling from a fresh source-identical 24-task v2 development result.
On that small slice Claude-first already reaches the 18-task hosted oracle
ceiling, so the fixed hybrid supplies zero selection lift. The result remains
retrospective hosted-label evidence, not independent execution or H1–H6
validation.

## What this can and cannot support

The study can measure candidate byte diversity, hosted-report test-signature
comparability, preserved-label diversity headroom, and retrospective ordering
behavior on fully observed tasks. A hosted `resolved` label is still an
execution measurement—not semantic correctness, valid-task truth,
oracle-validity truth, or independent reproduction.

A headline result still requires a prospectively frozen policy, held-out
repositories/tasks, exact scaffold and budget provenance, pinned independent
executions with disagreement handling, measured targeted/full/repeated/hardened
evidence costs, uncertainty estimates, and blinded task/candidate/verifier
adjudication. Results here must not be presented as a new SWE-bench score.

The intended center remains: **route evidence, not models; execution is a
measurement, not ground truth.**
