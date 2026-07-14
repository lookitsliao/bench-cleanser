# Taxonomy

Two independent axes, fused at Stage 7 ([FUSION.md](FUSION.md)).

| Axis | Question | Cardinality | Module |
| --- | --- | --- | --- |
| **Axis 1 — Task contamination** | Is the benchmark item fair? | Multi-label (0–7) | `bench_cleanser.classification.dual_taxonomy` |
| **Axis 2 — Agent trajectory** | How did this agent reach its answer? | Single label per `(task, agent)` | `bench_cleanser.trajectory.classifier` |

The axes serve different questions and must not be conflated. A task
with `APPROACH_LOCK` is broken regardless of the agent. Package installation,
high patch similarity, a fast fix, or cross-agent convergence is not proof of
leakage; an agent-side leakage label requires direct access-and-use evidence.
Only Stage 7 combines the axes.

### OpenAI Verified-audit crosswalk (February 2026)

| OpenAI term | bench-cleanser label |
| --- | --- |
| "Narrow test cases" | `APPROACH_LOCK` |
| "Wide test cases" | `OVER_TEST` |

Gold patches and F2P tests commonly share PR provenance, which motivates
auditing them as a coupled measurement. Shared authorship alone establishes
neither a benchmark defect nor intent. The severity mapping below is this
project's conservative review policy.

---

## Axis 1 — Task contamination

Seven binary labels. A task may carry any combination, or `CLEAN`.

### `APPROACH_LOCK`

F2P tests assert on a specific implementation strategy rather than
observable behaviour. An agent implementing the same behaviour
differently fails.

- **Evidence:** direct test/patch coupling showing that F2P acceptance depends
  on an implementation-specific choice not required by the issue. A weak
  identifier overlap, suggested fix, compiled-language hunk, or ordinary new
  test cannot create this label by itself.
- **Severity:** SEVERE.

### `OVER_TEST`

F2P tests assert on behaviour not described in the problem.

- **Evidence:** ≥1 `OFF_TOPIC` assertion, **or** an `UNRELATED` F2P
  test, **or** a modification adding `OFF_TOPIC` content.
- **Severity:** SEVERE under this project's conservative policy; the label
  still requires concrete out-of-scope test evidence.

### `OVER_PATCH`

Gold patch modifies behaviour not described in the problem.

- **Evidence:** ≥1 `UNRELATED` hunk that changes runtime behaviour.
  Pure ancillary edits (imports, dead-code removal) do not trigger.
- **Severity:** MINOR on its own; MODERATE when combined with
  `HIDDEN_CONTEXT` or `UNCLEAR_DESCRIPTION`.

### `UNCLEAR_DESCRIPTION`

Problem statement too ambiguous to derive expected behaviour.

- **Evidence:** classifier finds the problem text ambiguous enough that
  multiple incompatible solutions are reasonable. This label is not
  triggered by a fixed ambiguity-score threshold.
- **Severity:** MINOR.

### `HIDDEN_CONTEXT`

Problem framing relies on hidden cues (for example self-referential
phrasing like “see the patch”) rather than a standalone issue
specification.

- **Evidence:** concrete hidden-context cue in problem/hints metadata
  that cannot be acted on from problem text alone.
- **Severity:** MINOR on its own; may contribute to MODERATE when paired with
  `OVER_PATCH`.

### `WEAK_COVERAGE`

F2P tests do not exercise the patched code paths.

- **Evidence:** classifier evidence that acceptance criteria are not
  exercised by F2P tests or by gold-patch-covered behaviors.
- **Severity:** MINOR.

### `CLEAN`

No contamination labels apply. Emitted as a single label, never with
others — gives consumers an explicit "no contamination" signal.

---

## Axis 2 — Agent trajectory

Single label per `(task, agent)`.

### Passed (`resolved=True`)

| Label | Pattern |
| --- | --- |
| `agent_passed_genuine` | Explore → hypothesise → patch → test. Patch diverges from gold but solves the described problem. |
| `agent_passed_leak` | The trace directly shows prohibited reference-solution access and use in the final patch. Similarity or direct navigation alone is insufficient. |
| `agent_passed_package_leak` | The trace directly shows affected-package source being inspected and copied into the final patch. Installation alone is insufficient. |
| `agent_passed_test_aware` | The trace directly exposes hidden F2P names or expected values before allowed exploration could reveal them. |
| `agent_passed_trained_hack` | Cross-task or provenance evidence supports memorized exploit behaviour. A fast/canonical fix alone is insufficient. |

### Failed (`resolved=False`)

| Label | Pattern |
| --- | --- |
| `agent_failed_completed_intent` | Patch addresses the described behaviour but F2P tests reject it. The driver for `UNFAIR_FAILURE` when combined with `APPROACH_LOCK` / `OVER_TEST`. |
| `agent_failed_no_intent` | Agent never engaged the problem. Skill gap, not benchmark issue. |

### Unknown

| Label | Pattern |
| --- | --- |
| `agent_unknown` | Trajectory truncated, malformed, or otherwise insufficient. |

The trajectory classifier uses [`trajectory_analysis.md`](../bench_cleanser/prompts/trajectory_analysis.md)
as the system prompt and returns a strict
[`TrajectoryClassificationResponse`](../bench_cleanser/schemas.py) via
`LLMClient.query_structured`.

---

## Severity (bucket; Axis 1)

`Severity` is computed by pure set membership over the Axis-1 label set
in `bench_cleanser.classification.dual_taxonomy.compute_task_severity`.
No thresholds, no weights, no counts.

```
SEVERE   := APPROACH_LOCK ∈ labels  OR  OVER_TEST ∈ labels
MODERATE := OVER_PATCH ∈ labels AND
            (HIDDEN_CONTEXT ∈ labels OR UNCLEAR_DESCRIPTION ∈ labels)
MINOR    := any contamination label set that is neither SEVERE nor MODERATE
CLEAN    := labels = ∅  OR  labels = { CLEAN }
```

Severity is reproducible from the persisted report alone and frozen
across LLM upgrades.

---

## Evidence rule

A label without evidence is rejected by the classifier. Allowed
evidence sources per label:

| Label | Evidence sources |
| --- | --- |
| `APPROACH_LOCK` | Direct, non-weak test↔patch coupling plus reasoning showing a valid alternative implementation would fail. |
| `OVER_TEST` | `OFF_TOPIC` assertion text; `UNRELATED` test name; modified-test evidence line. |
| `OVER_PATCH` | `UNRELATED` `HunkVerdict` with reasoning. |
| `UNCLEAR_DESCRIPTION` | Problem text evidence showing incompatible interpretations or missing specification detail. |
| `HIDDEN_CONTEXT` | Hidden specification cues in problem/hints metadata (for example self-referential phrasing not actionable from issue text alone). |
| `WEAK_COVERAGE` | Evidence that acceptance criteria are untested or under-constrained by F2P tests. |

---

## Out of scope

- **Reward hacking** (gaming the eval harness, not the task).
- **Agent runtime flakes** (OOM, CI brownouts). Incomplete or contradictory
  outcome evidence is conservatively classified as `agent_unknown`; the
  separate validity-manifest layer records environment failure explicitly.
- **Hallucinated P2P regressions.** The agent's problem, not the task's.

A `CLEAN` verdict means the bench-cleanser axes turned up nothing —
not that the row is fit for every conceivable use.
