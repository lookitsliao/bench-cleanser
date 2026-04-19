# Severe Case Audit Protocol — v6 Pipeline Output (Revised v2)

## Purpose

This document defines the methodology for the human expert audit of all 107 SEVERE-classified cases from the bench-cleanser v6 pipeline. The goal is to produce a defensible, high-confidence validation of each severity classification.

## Scope

- **Input**: 107 cases classified as SEVERE by the automated pipeline
- **Output**: A human verdict for each case, recorded in `audit_tracker.csv`
- **Auditor**: Human expert working with AI assistant for structured review

---

## Core Framework: The 1:1:1 Principle

The fundamental evaluation principle:
- **Problem:Test** should be approximately **1:1** — tests should evaluate what the problem asks
- **Problem:Patch** should be **1:≥1** — overpatch alone is NOT contamination
- **Problem:Test:Patch** alignment is what matters — contamination occurs when tests require code changes not derivable from the problem statement

**Key insight**: A large gold patch with many unrelated hunks (scope_creep) is NOT automatically contamination. It only becomes contamination when F2P tests REQUIRE those unrelated hunks to pass.

---

## Verdict Options

| Verdict | Meaning | When to Use |
|---------|---------|-------------|
| `CONFIRMED_SEVERE` | The pipeline classification is correct | Clear evidence of benchmark contamination that would materially affect solver evaluation |
| `DOWNGRADE_MODERATE` | Real issues exist but not severe enough | Contamination signals are present but limited in scope or impact |
| `DOWNGRADE_MINOR` | Only minor issues | Surface-level concerns that don't meaningfully affect evaluation |
| `DOWNGRADE_CLEAN` | No contamination found | Pipeline was wrong; the task is well-constructed |
| `ESCALATE` | Needs deeper investigation | Ambiguous evidence; revisit after more context |

---

## Audit Checklist (Per Case)

For each case, the auditor evaluates the following dimensions **in order**:

### Step 0: Check Trajectory Evidence (MANDATORY — DO FIRST)
- [ ] Query Docent API for agent resolution rates across all models
- [ ] Record: total runs, passes, fails, resolution rate
- [ ] If **0% resolution** (all agents fail): strong presume-contaminated — needs careful analysis to explain WHY all fail before considering DOWNGRADE_CLEAN
- [ ] If **>50% resolution**: strong presume-clean — contamination unlikely unless tests have subtle bias
- [ ] If **1-49% resolution**: ambiguous — examine which models pass/fail and why

**CRITICAL**: A DOWNGRADE_CLEAN verdict on a 0% resolution case requires extraordinary justification explaining why every strong LLM agent fails despite the task being "clean". Common valid reasons:
- Task requires deep domain expertise beyond current LLMs (rare)
- Task requires codebase-specific knowledge that agents can't easily discover (possible but must be demonstrated)

Common INVALID reasons for DOWNGRADE_CLEAN on 0% resolution:
- "Cross-refs are compilation artifacts" (if agents can't compile, that IS a problem)
- "Overpatch doesn't affect tests" (if true, agents should pass — but they don't)
- "Same pattern as Case X" (each case needs individual analysis)

### Step 1: Understand the Task
- [ ] Read the original problem statement (SWE-bench Pro)
- [ ] Understand what the task is asking (bug fix, feature, refactor?)
- [ ] Note the legitimacy classification (bug vs feature_request vs enhancement)

### Step 2: Evaluate Patch vs Problem Alignment (Scope Creep)
- [ ] Review total hunks vs unrelated hunks ratio
- [ ] For each UNRELATED hunk: Does the pipeline's reasoning hold up?
- [ ] Could any "unrelated" hunks actually be necessary for the fix?
- [ ] Key question: **Would a correct solution require these unrelated changes?**
- [ ] Remember: overpatch alone ≠ contamination

### Step 3: Evaluate Test Contamination (THIS IS THE CRITICAL STEP)
- [ ] Check total tests vs unrelated tests
- [ ] Check for modified tests (`has_modified_tests`)
- [ ] **CHECK for pre-staged tests via `before_repo_set_cmd`** — pipeline may report `is_modified: false` when tests ARE modified through git checkout from gold commit
- [ ] Check `test_patch` size — if >0, tests ARE modified regardless of `is_modified` flag
- [ ] Review test assertions: do they assert on values derivable from the spec, or do they require exact gold patch implementation details?
- [ ] Key question: **Do the tests fairly evaluate the described problem, or do they test unrelated behavior?**

### Step 4: Evaluate Cross-Reference Dependencies
- [ ] Check for circular dependencies (tests requiring unrelated patch hunks)
- [ ] **Distinguish compilation dependencies from behavioral dependencies** — compilation deps in monolithic builds (TypeScript, Go) may be real barriers even if not "behavioral"
- [ ] If agents can't compile without unrelated changes, that IS contamination (the task is unsolvable as stated)
- [ ] Key question: **Are there tests that REQUIRE unrelated code changes to pass?**

### Step 5: Evaluate Labels
- [ ] Review each label's evidence and reasoning
- [ ] Check label confidence scores
- [ ] Key labels for SEVERE:
  - `scope_creep` (high unrelated hunks) — patch includes changes beyond the problem
  - `approach_lock` — tests enforce a specific implementation, not just correctness
  - `test_mutation` — existing tests were modified to pass with the gold patch
  - `wide_tests` — tests cover behavior beyond the problem scope
  - `unclear_spec` — problem statement is too vague to evaluate

### Step 6: Reconcile with Trajectory Evidence
- [ ] Does the verdict align with empirical resolution rates?
- [ ] If proposing DOWNGRADE_CLEAN on a 0% case: document specific explanation for total agent failure
- [ ] If proposing CONFIRMED_SEVERE on a >50% case: verify the contamination mechanism doesn't prevent successful solutions
- [ ] Look at one or more agent trajectories for representative models to understand failure mode

### Step 7: Render Verdict
- [ ] Weigh all evidence, with trajectory data as primary empirical anchor
- [ ] Record verdict with clear reasoning (2-3 sentences)
- [ ] Include resolution rate in verdict reason
- [ ] Flag any observations or patterns

---

## Decision Framework

### Strong CONFIRMED_SEVERE signals:
- **0% resolution rate across all strong LLMs** (strongest empirical signal)
- Tests assert on values not derivable from the problem statement
- Tests require implementation of unrelated features/hunks
- Task/patch mismatch (problem describes Feature A, patch implements Feature B)
- Pre-staged test modifications (via `before_repo_set_cmd`) that pipeline missed

### Strong DOWNGRADE_CLEAN signals:
- **>50% resolution rate** — agents CAN solve this task
- All F2P tests are clearly aligned with the stated problem
- Unrelated hunks are genuine overpatch that tests don't depend on
- Cross-refs are demonstrably false positives (compilation artifacts in monolithic builds where the agent CAN still compile and pass tests)

### Ambiguous (requires careful analysis):
- 1-49% resolution rate — some agents pass but many don't
- Compilation dependencies that might be real barriers
- Tests that are partially aligned but with some scope broadening
- "Mechanical" test mutations (constructor signatures, shared struct changes)

### Known Contamination Patterns:
1. **Task/Patch Mismatch** (Case 5): Problem describes one feature, gold patch implements a different feature. Most severe — 0% solvable.
2. **Approach Lock via Pre-staged Tests** (Case 4): Tests pre-staged from gold commit assert on exact implementation values not in spec. 
3. **Compilation Barrier** (Cases 9, 14, etc.): Unrelated changes required for compilation in monolithic projects. Must verify if agents can work around this.
4. **Test Assertion Lock**: Tests assert on exact naming conventions, data structures, or behavioral details not specified in the problem.

---

## File Locations

| File | Purpose |
|------|---------|
| `audits/severe/audit_tracker.csv` | Master status tracker |
| `audits/severe/trajectory_summary.json` | Agent trajectory resolution data (Docent API) |
| `audits/severe/notes/case_NNN.md` | Per-case audit notes |
| `output_pro_v6/reports/instance_*.json` | Pipeline reports |
| `output_pro_v6/summary.csv` | Summary metrics |
| `scripts/severe_audit.py` | CLI audit helper |

---

## Trajectory Data Access

Agent trajectories are accessed via Docent API (collection `196681cc-76fc-44f2-b3ce-d55eba81c0c6`).
Pre-fetched summary is stored in `audits/severe/trajectory_summary.json`.

To refresh trajectory data for a specific case:
```python
from docent import Docent
client = Docent(api_key=API_KEY, api_url='https://api.docent.transluce.org')
results = client.execute_dql(COLLECTION_ID, dql="SELECT ... FROM agent_runs WHERE ...")
```

---

## Known Pipeline Gaps (from audit)

1. **Test modification via `before_repo_set_cmd`**: SWE-bench Pro pre-stages test files from gold commit. Pipeline's `is_modified` check misses this. Check `test_patch` field instead.
2. **Cross-reference granularity**: Pipeline uses file-level matching, not function-level. Produces false positives in large files where tests import a shared module but only use specific exports.
3. **Identifier-overlap fallback**: Cross-ref engine falls back to string matching on domain terms, producing false positives on common identifiers.

---

## Progress Tracking

After each audit session, run:
```
python scripts/severe_audit.py status
```

This shows:
- Total cases audited vs remaining
- Breakdown by verdict
- Next case number to audit
