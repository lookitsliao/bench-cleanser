# Smoking Gun Case Study: navidrome/navidrome GetNowPlaying

## Instance Identification

| Field | Value |
|---|---|
| Instance ID | `instance_navidrome__navidrome-97434c1789a6444b30aae5ff5aa124a96a88f504` |
| Repository | `navidrome/navidrome` |
| Language | Go |
| Pipeline Version | v5 (with requirements+interface parsing) |
| Severity | **SEVERE** |
| Labels | `approach_lock` (0.84), `scope_creep` (0.93) |
| V4 Severity | **CLEAN** (false negative -- pipeline missed this without requirements context) |

---

## 1. Problem Statement (Agent-Visible)

> **[Bug]: GetNowPlaying endpoint only shows the last play**
>
> The Subsonic `GetNowPlaying` endpoint currently displays only the last reported play instead of maintaining multiple active entries. This happens because player identification relies on `userName`, `client`, and a loosely defined `type` field, which can cause collisions and overwrite entries from different sessions or devices.
>
> **Expected Behavior:** `GetNowPlaying` should list all active plays concurrently, providing one entry for each active player with correct metadata.

**Scope implied by problem statement:** Fix the player matching logic so multiple concurrent plays are preserved instead of being overwritten.

---

## 2. Requirements (Evaluation-Only, Withheld from Agent)

The requirements are highly prescriptive about implementation details:

- `Player` struct must expose `UserAgent string` field (JSON tag `userAgent`) replacing old `Type` field
- `PlayerRepository` interface must define `FindMatch(userName, client, typ string) (*Player, error)`
- `FindMatch` must return a `Player` only when stored `userName`, `client`, `typ` exactly match
- `Register` must accept `userAgent` argument instead of `typ`
- `Register` must use `FindMatch` for matching
- `Register` must return `nil` transcoding value
- If matching player found: update `LastSeen` timestamp
- If no match: create and persist new `Player`

**Key observation:** The requirements dictate specific struct field names, method signatures, parameter types, and matching semantics. This goes far beyond the problem statement's "fix player matching" intent.

---

## 3. Interface (Evaluation-Only, Withheld from Agent)

New public interface:

- `FindMatch(userName, client, typ string) (*Player, error)` on `PlayerRepository`
- Supersedes prior `FindByName` method

---

## 4. Why V4 Classified This as CLEAN

In v4, the pipeline saw only the problem statement: "fix GetNowPlaying so multiple plays are preserved." This is a clear, well-scoped bug report. The pipeline found:

- Problem is clear and unambiguous
- One F2P test (`TestCore`)
- No obvious excess

Without seeing the requirements (which dictate specific struct fields and method signatures), the pipeline concluded the task was clean. **This was a false negative.**

---

## 5. What V5 Reveals: The Scope Creep

With full requirements/interface context, v5's analysis reveals the gold patch modifies **20 hunks** across multiple files, with 4 behavioral hunks marked UNRELATED:

### Domain 1: Player Matching Fix (Requested)
- `model/player.go` -- Rename `Type` to `UserAgent`, add `FindMatch` to interface
- `persistence/player_repository.go` -- Implement `FindMatch`
- `server/subsonic/media_annotation.go` -- Use `FindMatch` in `Register`

### Domain 2: Scrobbler/PlayerId Plumbing (NOT Requested)
| File | Change | Relation to Problem |
|---|---|---|
| `core/scrobbler/scrobbler.go` | Changes `PlayerId` type from `int` to `string` | UNRELATED |
| `server/subsonic/album_lists.go` | Changes `GetNowPlaying` to use synthetic index-based `PlayerId` | UNRELATED |
| `server/subsonic/media_annotation.go` hunk 3 | Changes scrobbler NowPlaying plumbing | UNRELATED |
| Additional subsonic routing changes | Various ID type changes | UNRELATED |

The problem says "fix player matching so multiple plays are preserved." It does NOT say "change PlayerId from int to string" or "rewrite the scrobbler NowPlaying API." These are scope-expanding changes the gold patch makes beyond the stated fix.

---

## 6. Approach Lock: Circular Test-Patch Dependency

Cross-reference analysis detected **1 circular dependency**:

```
Test 'TestCore' -> exercises code from 2 UNRELATED hunk(s)
  - core/scrobbler/scrobbler.go hunk 0 (PlayerId int->string)
  - server/subsonic/media_annotation.go hunk 3 (scrobbler plumbing)
```

The single F2P test `TestCore` exercises code paths that depend on the UNRELATED scrobbler/PlayerId changes. An agent that correctly fixes the player matching bug but does NOT also change `PlayerId` from `int` to `string` will fail `TestCore` because the test path traverses the scrobbler code that the gold patch modified.

**The approach lock here is structural:** The test doesn't just check player matching -- it exercises the full playback pipeline including scrobbler integration that the gold patch also modified.

---

## 7. The V4-to-V5 Severity Migration

This instance demonstrates the most important pipeline improvement: **detecting contamination that was invisible without requirements context**.

### Why V4 missed it
- V4 saw only: "fix GetNowPlaying to show multiple plays" (clear problem)
- V4 saw: 1 test, no modified tests, no obvious excess
- V4 classified: CLEAN (0.87 confidence)

### Why V5 catches it
- V5 sees the full requirements: specific struct fields, method signatures, matching semantics
- V5 can compare gold patch scope against requirements scope
- V5 identifies: scrobbler/PlayerId changes are NOT in requirements
- V5 identifies: `TestCore` exercises those unrequired changes
- V5 classifies: SEVERE (`approach_lock` + `scope_creep`)

**This is the exact scenario the pipeline fix was designed for:** SWE-bench Pro tasks where the narrow problem statement makes everything look clean, but the withheld requirements reveal scope expansion in the gold patch.

---

## 8. Contamination Diagnosis

This task exhibits the **scope_creep + approach_lock** pattern:

1. **The problem statement is clear and solvable** -- fix player matching to preserve concurrent plays
2. **The gold patch goes beyond the fix** -- it also changes PlayerId from int to string and rewrites scrobbler plumbing
3. **The F2P test exercises the excess changes** -- TestCore traverses the unrequired scrobbler modifications
4. **An agent solving the stated problem will fail** unless it also reproduces the scrobbler changes

Unlike the flipt case (where ALL tests are unrelated), this case is more subtle:
- The test IS related to the problem (it tests playback)
- But the test path ALSO depends on out-of-scope gold patch changes
- The excess patch creates a hidden dependency the agent cannot derive from the problem statement

---

## 9. Significance for Pipeline Validation

This case is the strongest evidence that the v4-to-v5 pipeline fix was necessary:

| Aspect | V4 (blind) | V5 (full context) |
|---|---|---|
| Severity | CLEAN | **SEVERE** |
| Labels | clean (0.87) | approach_lock (0.84), scope_creep (0.93) |
| False result | **False negative** | Correct detection |
| Root cause | Pipeline only saw problem_statement | Pipeline sees requirements+interface |

Without the `requirements` field, the pipeline cannot distinguish between "gold patch correctly fixes the problem" and "gold patch fixes the problem AND adds unrequired changes." The requirements make the intended scope explicit, allowing the pipeline to detect scope expansion.

---

## 10. Agent Trajectory Analysis: Real-World Contamination Impact

### Agent Behavior Summary

A top-performing coding agent was tasked with this instance. The agent's trajectory reveals it **correctly identified and implemented all requirements derivable from the problem statement**, yet still failed the F2P test due to the approach lock.

### What the Agent Did (Correct Implementation)

The agent's approach was methodical and aligned with the problem:

1. **Explored the codebase** -- Read `model/player.go`, `persistence/player_repository.go`, `server/subsonic/media_annotation.go`, and related files to understand the existing player matching logic

2. **Identified the root cause** -- Recognized that `Register()` uses `FindByName()` which matches only on `userName+client`, causing collisions when different player types share the same `userName+client` pair

3. **Implemented the fix:**
   - Added `UserAgent string` field to the `Player` struct (replacing `Type`)
   - Added `FindMatch(userName, client, typ string) (*Player, error)` to the `PlayerRepository` interface
   - Implemented `FindMatch` in the persistence layer with exact three-field matching
   - Updated `Register()` to use `FindMatch` instead of `FindByName`
   - Created a database migration to rename the `type` column to `user_agent`
   - Updated JSON serialization tags

4. **Ran tests** -- The agent ran the test suite and observed failures

### What the Agent Did NOT Do (Correctly)

The agent did NOT modify:
- `core/scrobbler/scrobbler.go` (PlayerId type change)
- `server/subsonic/album_lists.go` (GetNowPlaying synthetic IDs)
- Any scrobbler plumbing or ID type changes

This is the correct behavior -- the problem statement says nothing about changing PlayerId from `int` to `string` or rewriting scrobbler internals.

### Why the Agent Failed

The agent's implementation satisfies every requirement derivable from the problem statement. But `TestCore` exercises the full playback pipeline, which traverses both the player-matching code (which the agent correctly fixed) AND the scrobbler/PlayerId code (which the gold patch changed but the problem statement doesn't mention).

Because the agent didn't reproduce the unrequired `PlayerId int->string` change, `TestCore` fails at the scrobbler integration boundary -- not at the player matching logic the agent was asked to fix.

### Classification: `agent_failed_completed_intent`

The agent completed the stated intent (fix player matching) but failed the F2P test due to approach_lock on unrequired gold patch changes. This is the textbook contamination harm pattern.

---

## 11. Cross-Benchmark Contamination Penalty Analysis

To quantify whether contamination actually hurts agent performance at scale, we cross-referenced the top agent's resolution status across all 730 matched SWE-bench Pro instances with the v5 contamination severity classifications.

### Resolve Rate by Severity Level

| Severity | Tasks | Resolved | Failed | Resolve Rate | vs CLEAN |
|---|---:|---:|---:|---:|---:|
| CLEAN | 130 | 56 | 74 | 43.1% | --- |
| MINOR | 448 | 211 | 237 | 47.1% | +4.0% |
| MODERATE | 54 | 17 | 37 | 31.5% | -11.6% |
| SEVERE | 98 | 35 | 63 | 35.7% | -7.4% |
| **OVERALL** | **730** | **319** | **411** | **43.7%** | |

### Resolve Rate by Contamination Label

| Label | Instances | Resolved | Resolve Rate | vs clean |
|---|---:|---:|---:|---:|
| clean | 130 | 56 | 43.1% | (baseline) |
| weak_coverage | 526 | 234 | 44.5% | +1.4% |
| scope_creep | 174 | 82 | 47.1% | +4.0% |
| approach_lock | 84 | 30 | 35.7% | -7.4% |
| test_mutation | 31 | 9 | 29.0% | -14.0% |
| wide_tests | 98 | 28 | 28.6% | -14.5% |
| unclear_spec | 22 | 6 | 27.3% | -15.8% |

### Key Findings

1. **The most harmful contamination labels are test-related.** `wide_tests` (-14.5%), `test_mutation` (-14.0%), and `unclear_spec` (-15.8%) show the steepest resolve rate drops. The `wide_tests` penalty is statistically significant (chi-square = 5.05, p < 0.05).

2. **SEVERE instances with `wide_tests` are dramatically harder.** Among SEVERE tasks, those with `wide_tests` have a 25.0% resolve rate vs 44.4% without -- nearly half the success rate. The combination of `approach_lock + wide_tests` drops to 20.0%.

3. **`scope_creep` alone is not harmful.** Tasks labeled `scope_creep` without test contamination actually resolve slightly *above* the clean baseline (47.1%). This makes sense: if the gold patch includes extra changes but the tests don't enforce them, agents can still pass with a correct narrower fix.

4. **MINOR severity tasks resolve ABOVE baseline.** MINOR tasks (mostly `weak_coverage` only) resolve at 47.1%, slightly above CLEAN. This confirms that the `weak_coverage` label (requirements slightly beyond problem statement) does not meaningfully penalize agents -- the pipeline correctly classifies these as low-severity.

5. **The penalty concentrates in label combinations.** Single-label SEVERE instances are not dramatically harder. The penalty is strongest when multiple contamination signals compound:

| Label Combination (SEVERE) | Tasks | Resolve Rate |
|---|---:|---:|
| approach_lock + scope_creep | 43 | 46.5% |
| approach_lock + wide_tests | 8 | 12.5% |
| approach_lock + scope_creep + wide_tests | 11 | 18.2% |
| scope_creep + wide_tests + test_mutation | 6 | 33.3% |

### Interpretation

The contamination penalty is **real but nuanced**. Aggregate severity-level comparisons (CLEAN vs SEVERE) show a 7.4pp gap that is not statistically significant on its own (chi-square = 1.26, n.s.). However, this masks a strong interaction effect:

- **Test-contaminated SEVERE tasks** (with `wide_tests`) penalize agents by ~18pp relative to baseline
- **Non-test-contaminated SEVERE tasks** perform comparably to CLEAN tasks

This pattern aligns with the theoretical prediction: agents can often work around gold patch scope expansion (scope_creep) but **cannot pass F2P tests that enforce unrequired behavior** (wide_tests, test_mutation). The navidrome instance exemplifies this -- the agent's correct fix fails because TestCore exercises unrequired scrobbler changes, not because the agent's implementation is wrong.

---

## 12. Conclusion

**Classification: GENUINE SEVERE CONTAMINATION (previously missed as false negative)**

This task has a clear, solvable problem statement. But the gold patch bundles the fix with unrequired scrobbler/PlayerId type changes, and the F2P test exercises those unrequired changes. An agent that correctly fixes player matching but uses the existing `int` PlayerId type will fail `TestCore`.

**Agent validation:** A top agent correctly implemented all stated requirements (FindMatch, UserAgent field, Register logic, migration) but failed `TestCore` because it didn't reproduce the unrequired scrobbler/PlayerId changes. This is classified as `agent_failed_completed_intent` -- the strongest possible evidence that the contamination is real and harmful.

**Benchmark-wide impact:** Across 730 SWE-bench Pro instances, tasks with `wide_tests` contamination resolve at 28.6% vs the 43.1% clean baseline -- a 14.5pp penalty that scales to ~14 incorrectly-failed instances among the 98 wide_tests tasks alone.

This case validates the pipeline refactoring: the v4 parse bug (missing `requirements`/`interface`) caused this genuine contamination to be classified as CLEAN. The v5 pipeline correctly detects it as SEVERE.
