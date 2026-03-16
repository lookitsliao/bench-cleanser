---
marp: true
theme: default
paginate: true
title: "SWE-bench Contamination Analysis — bench-cleanser v3 Findings"
math: katex
style: |
  section {
    font-size: 22px;
    line-height: 1.5;
  }
  h1 {
    color: #1a1a2e;
    font-size: 32px;
    border-bottom: 2px solid #e63946;
    padding-bottom: 8px;
  }
  h2 {
    color: #16213e;
    font-size: 26px;
  }
  h3 {
    color: #457b9d;
    font-size: 22px;
  }
  table {
    font-size: 15px;
    width: 100%;
  }
  th {
    background-color: #1a1a2e;
    color: white;
    padding: 6px 10px;
  }
  td {
    padding: 4px 10px;
  }
  code {
    font-size: 14px;
    background-color: #f0f0f0;
    padding: 2px 4px;
    border-radius: 3px;
  }
  pre code {
    font-size: 13px;
    background-color: transparent;
    padding: 0;
  }
  blockquote {
    font-size: 18px;
    border-left: 4px solid #e63946;
    padding-left: 16px;
    color: #555;
  }
  .severe { color: #e63946; font-weight: bold; }
  .moderate { color: #f4a261; font-weight: bold; }
  .minor { color: #e9c46a; font-weight: bold; }
  .clean { color: #2a9d8f; font-weight: bold; }
  .label { color: #6c5ce7; font-weight: bold; }
  .on-topic { color: #2a9d8f; }
  .off-topic { color: #e63946; }
  .highlight { background-color: #fff3cd; padding: 4px 8px; border-radius: 4px; }
  .footnote { font-size: 12px; color: #888; position: absolute; bottom: 30px; }
  .two-col { display: flex; gap: 40px; }
  .two-col > div { flex: 1; }
  .group-a { color: #e63946; }
  .group-b { color: #f4a261; }
  .group-c { color: #457b9d; }
  .group-d { color: #6c5ce7; }
  .group-e { color: #2a9d8f; }
  .axis2 { color: #e76f51; }
---

<!-- _class: lead -->
<!-- _paginate: false -->

# SWE-bench Contamination Analysis

## bench-cleanser v3 Findings

**Dual Taxonomy Pipeline | gpt-5.2 | 17-Label Task Classification + 8-Label Agent Trajectory**

March 2026

---

# Agenda

1. **The Problem** -- Why SWE-bench has contaminated evaluation criteria
2. **Pipeline Architecture** -- 6-stage automated detection methodology
3. **v3 Dual Taxonomy** -- Axis 1 (Task Labels) + Axis 2 (Agent Trajectory)
4. **Axis 1: Task Contamination Labels** -- 17 labels across 5 groups
5. **Axis 2: Agent Trajectory Labels** -- 8 labels for agent behavior classification
6. **Severity Scoring** -- Weighted label formula with recalibrated thresholds
7. **Case Study A** -- django-10999: Approach Mismatch
8. **Case Study B** -- astropy-13398: Deferred Requirement Enforced
9. **Case Study C** -- astropy-14182: Overtest + Scope Expansion
10. **Case Study D** -- astropy-14539: Overtest via Excess Regression Tests
11. **Top 20 Deep-Dive Findings** -- Precision analysis at MODERATE threshold
12. **Cross-Case Synthesis** -- Pattern taxonomy and recommendations
13. **Appendix** -- Formulas, thresholds, architecture

---

# The Problem: SWE-bench Contamination

SWE-bench evaluates AI agents on real-world software engineering tasks.
However, some tasks have **contaminated evaluation criteria**:

<div class="two-col">
<div>

### What goes wrong

- **Mispatch**: Gold patch implements changes not described in the issue
- **Mistest**: F2P tests verify behavior beyond the stated problem
- **Misleading descriptions**: Problem statement directs toward wrong approach
- **Structural issues**: Circular dependencies between tests and patches

</div>
<div>

### Why it matters

- Agent solves the *stated* problem but **fails** because gold patch took a different approach
- Tests assert on undescribed functionality -- agent can't know what to implement
- Leaderboard rankings reward contamination tolerance over engineering skill

</div>
</div>

> An agent that **perfectly solves** the stated problem can score **0%** on contaminated tasks.

---

# bench-cleanser v3: Pipeline Architecture

```
+-----------+   +-----------+   +--------+   +----------+   +--------+   +-----------+
|   PARSE   |-->|   CODE    |-->| INTENT |-->|  INTENT  |-->| TRIAGE |-->|   DUAL    |
|           |   | VISITATION|   | EXTRACT|   | MATCHING |   | SCORE  |   | TAXONOMY  |
+-----------+   +-----------+   +--------+   +----------+   +--------+   +-----------+
  Stage 1        Stage 1.5       Stage 2       Stage 4       Stage 5       Stage 5+
 Diff parse     Clone repo      LLM-based    Per-hunk EP   Combined      17 task labels
 Hunk split     AST analysis    ground truth  Per-assert ET  scoring      8 agent labels
 F2P match      Source code     from problem  VS scoring    & severity    v3 severity
```

| Stage | What it does | Output |
|-------|-------------|--------|
| 1 + 1.5 | Parse diffs, clone repo, extract code context | Structured hunks + AST |
| 2 | Extract ground-truth intent from problem statement | `IntentStatement` |
| 3 | Structural diff with code visitation | AST-level analysis |
| 4 | Match each hunk / assertion against intent | EP, ET, VS scores |
| 5 | Score and classify severity | `DualTaxonomyReport` |
| 5+ | Multi-label task classification (LLM) | Weighted labels + recalibrated severity |

---

# v3 Dual Taxonomy: Two Orthogonal Axes

<div class="two-col">
<div>

### Axis 1: Task Contamination (17 labels)

*What's wrong with the benchmark task itself*

- **Multi-label** -- tasks can have multiple issues
- **Agent-independent** -- doesn't depend on who solved it
- **5 groups**: Test, Patch, Description, Structural, Clean
- **Weighted** -- each label has a severity weight $w_i$

</div>
<div>

### Axis 2: Agent Trajectory (8 labels)

*How a specific agent behaved on the task*

- **Single primary label** per agent-task pair
- **Agent-specific** -- the same task can have different labels for different agents
- **Integrity score** -- 0.0 (pure leak) to 1.0 (genuine)
- **Cross-axis diagnostic** -- confirms Axis 1 findings

</div>
</div>

> **Key insight:** `agent_failed_completed_intent` + `mispatch_approach_mismatch` = strongest contamination confirmation. Agent solved the real problem but failed tests due to task contamination.

---

# Axis 1: Task Contamination Labels

### <span class="group-a">Group A -- Test Contamination</span>

| Label | Display Name | Weight | Definition |
|-------|-------------|--------|------------|
| <span class="label">`mistest_overtest`</span> | Overtest | 0.7 | F2P tests verify behavior/features NOT in problem statement |
| <span class="label">`mistest_undertest`</span> | Undertest | 0.2 | F2P tests don't fully cover stated criteria; partial fix can pass |
| <span class="label">`mistest_customtest`</span> | Custom Test | 0.9 | Tests so specific to gold patch that other valid solutions fail |
| <span class="label">`mistest_sneaky_modification`</span> | Sneaky Modification | 0.8 | Pre-existing test modified to assert on NEW undescribed behavior |
| <span class="label">`mistest_deferred_requirement`</span> | Deferred Requirement | 0.9 | Tests require features the problem explicitly defers |

**Detection signals:** OFF_TOPIC assertion ratio, UNRELATED test verdicts, deferral language in problem statement, `is_modified=True` + `modification_aligned=False`

---

# Axis 1: Task Contamination Labels (continued)

### <span class="group-b">Group B -- Patch Contamination</span>

| Label | Display Name | Weight | Definition |
|-------|-------------|--------|------------|
| <span class="label">`mispatch_overpatch`</span> | Overpatch | 0.5 | Gold patch includes changes beyond problem scope |
| <span class="label">`mispatch_underpatch`</span> | Underpatch | 0.2 | Gold patch doesn't fully address stated requirements |
| <span class="label">`mispatch_approach_mismatch`</span> | Approach Mismatch | **1.0** | Gold patch uses fundamentally different strategy than problem suggests |
| <span class="label">`mispatch_ancillary_bundling`</span> | Ancillary Bundling | 0.3 | Cleanup/refactoring bundled alongside fix |

### <span class="group-c">Group C -- Description Contamination</span>

| Label | Display Name | Weight | Definition |
|-------|-------------|--------|------------|
| <span class="label">`desc_misleading`</span> | Misleading Description | 0.7 | Problem statement actively directs toward wrong approach |
| <span class="label">`desc_incomplete`</span> | Incomplete Description | 0.4 | Problem missing key info to derive solution |
| <span class="label">`desc_hidden_in_hints`</span> | Hidden in Hints | 0.4 | Essential solution info only in hints, not problem |
| <span class="label">`desc_self_referential`</span> | Self-Referential | 0.5 | Problem references its own patch/tests to define behavior |

---

# Axis 1: Task Contamination Labels (continued)

### <span class="group-d">Group D -- Structural Contamination</span>

| Label | Display Name | Weight | Definition |
|-------|-------------|--------|------------|
| <span class="label">`scope_expansion`</span> | Scope Expansion | 0.6 | Fix modifies parent class or broader API than described |
| <span class="label">`circular_test_patch_dependency`</span> | Circular Dependency | 0.85 | F2P tests require out-of-scope patch changes to pass |

### <span class="group-e">Group E -- Clean</span>

| Label | Display Name | Weight | Definition |
|-------|-------------|--------|------------|
| <span class="label">`clean`</span> | Clean Task | 0.0 | No contamination -- fair evaluation |
| <span class="label">`hard_but_clean`</span> | Hard But Clean | 0.0 | Genuinely difficult but fairly evaluated |

### Co-occurrence Rules

- Multiple A-D labels **can co-occur** (e.g., `mispatch_approach_mismatch` + `mistest_customtest`)
- Group E is **exclusive** -- cannot co-occur with any A-D label
- Common pairs: `desc_incomplete` + `desc_hidden_in_hints`, `scope_expansion` + `mistest_overtest`

---

# Axis 2: Agent Trajectory Labels

| Label | Display Name | Integrity | Definition |
|-------|-------------|-----------|------------|
| <span class="axis2">`agent_passed_genuine`</span> | Genuine Solution | 1.0 | Legitimate problem-solving with progressive exploration |
| <span class="axis2">`agent_passed_leak`</span> | Gold Patch Leak | 0.0 | Patch matches gold too closely (similarity >= 0.90) |
| <span class="axis2">`agent_passed_package_leak`</span> | Package Leak | 0.1 | Agent pip-installed newer version and copied fix |
| <span class="axis2">`agent_passed_test_aware`</span> | Test-Aware | 0.2 | Agent referenced F2P test names/values before discovery |
| <span class="axis2">`agent_passed_trained_hack`</span> | Trained Hack | 0.5 | Applied memorized template without genuine reasoning |
| <span class="axis2">`agent_failed_completed_intent`</span> | Failed but Solved | N/A | Agent's patch addresses real problem but fails F2P tests |
| <span class="axis2">`agent_failed_no_intent`</span> | Failed Without Solving | N/A | Didn't solve the problem; failure reflects skill gap |
| <span class="axis2">`agent_unknown`</span> | Unknown | N/A | Insufficient trajectory data to classify |

### Cross-Axis Diagnostic

> `agent_failed_completed_intent` + `mispatch_approach_mismatch` = **strongest contamination confirmation**
> The agent correctly solved the stated problem but failed because the gold patch took a different approach.

---

# Severity Scoring: Weighted Labels

### v3 Formula (replaces v2 EP/ET/VS combination)

$$\text{severity}_{\text{task}} = 1 - \prod_{i \in \text{labels}} (1 - w_i \cdot c_i)$$

Where $w_i$ = label weight, $c_i$ = detection confidence (0-1).

### Key improvement over v2

| Signal | v2 Score | v3 Score | Why |
|--------|----------|----------|-----|
| `desc_incomplete` alone (w=0.4, c=0.8) | MODERATE (0.60) | **MINOR** (0.32) | Weak signal can't reach SEVERE alone |
| `mispatch_approach_mismatch` (w=1.0, c=0.9) | MODERATE (0.55) | **SEVERE** (0.90) | Strong signal correctly reaches SEVERE |
| EP=0.33 + ET=0.0 + VS=0.4 | MODERATE (0.60) | **Depends on labels** | v3 distinguishes contamination types |

### Thresholds (unchanged)

| Severity | Threshold |
|----------|-----------|
| <span class="clean">CLEAN</span> | score < 0.15 |
| <span class="minor">MINOR</span> | 0.15 <= score < 0.4 |
| <span class="moderate">MODERATE</span> | 0.4 <= score < 0.7 |
| <span class="severe">SEVERE</span> | score >= 0.7 |

---

# v2 vs v3 Taxonomy Comparison

| Aspect | v2 (3+5 taxonomy) | v3 (Dual Taxonomy) |
|--------|-------------------|-------------------|
| **Scoring axes** | EP + ET + VS | 17 task labels (weighted) |
| **Task classification** | 5 root causes | 17 labels in 5 groups (multi-label) |
| **Agent classification** | 6 leakage patterns | 8 trajectory labels |
| **Severity formula** | $1-(1-EP)(1-ET)(1-VS)$ | $1-\prod(1-w_i c_i)$ |
| **Weak signal handling** | VS alone can reach MODERATE | `desc_incomplete` capped at MINOR |
| **Strong signal handling** | EP=1.0 always SEVERE | `mispatch_approach_mismatch` correctly SEVERE |
| **Label granularity** | 5 root causes | 15 contamination + 2 clean labels |
| **Backward compatibility** | -- | v2 scores preserved in report |

> v3 preserves all v2 fields (EP, ET, VS, root causes) for backward compatibility while adding the richer dual taxonomy layer.

---

<!-- _class: lead -->

# Case Study A
## `django__django-10999`
### "The Regex That Solves a Different Problem"

**v3 Labels:** <span class="label">`mispatch_approach_mismatch`</span> + <span class="label">`desc_hidden_in_hints`</span>
**Combined Score:** <span class="severe">0.90+</span>

---

# Case A: Problem vs Gold Patch

<div class="two-col">
<div>

### Reporter's approach
Per-component signs: add `-?` to the lookahead

`(?=\d+:\d+)` --> `(?=-?\d+:-?\d+)`

`-1:15:30` = hours=-1, minutes=+15, seconds=+30

</div>
<div>

### Gold patch approach
Single leading sign: new `(?P<sign>-?)` group

Removes all per-component `-?` optionals

`-1:15:30` = hours=-1, minutes=-15, seconds=-30

</div>
</div>

### v3 Dual Taxonomy Labels

| Label | Confidence | Evidence |
|-------|-----------|----------|
| <span class="label">`mispatch_approach_mismatch`</span> | 0.92 | Problem prescribes lookahead fix; gold patch introduces sign group instead |
| <span class="label">`desc_hidden_in_hints`</span> | 0.80 | Maintainer decision ("leading minus negates entire value") only in hints |

> **Would an agent following the problem statement pass?** <span class="severe">NO.</span>
> The mantainer's single-sign decision was made in code review, not the problem statement.

---

<!-- _class: lead -->

# Case Study B
## `astropy__astropy-13398`
### "Tests Demand Refraction the Spec Defers"

**v3 Labels:** <span class="label">`mistest_deferred_requirement`</span> + <span class="label">`mistest_overtest`</span> + <span class="label">`scope_expansion`</span>
**Combined Score:** <span class="severe">0.95+</span>

---

# Case B: Deferred Requirement

The reporter explicitly states:

> *"I have yet to add refraction, but I can do so if it is deemed important."*

Yet the gold patch adds `add_refraction()` / `remove_refraction()` using `erfa.refco()`, and F2P tests named `test_..._with_refraction` require this code.

### v3 Labels

| Label | Confidence | Evidence |
|-------|-----------|----------|
| <span class="label">`mistest_deferred_requirement`</span> | 0.90 | Problem defers refraction; tests require it |
| <span class="label">`mistest_overtest`</span> | 0.75 | 16/31 assertions OFF_TOPIC |
| <span class="label">`scope_expansion`</span> | 0.70 | New file + 4 modified files, ~250 lines beyond problem scope |

An agent would need ~60 lines of ERFA refraction code using APIs the problem **never mentions**.

---

<!-- _class: lead -->

# Case Study C
## `astropy__astropy-14182`
### "Asked for a Writer, Tested the Reader"

**v3 Labels:** <span class="label">`mistest_overtest`</span> + <span class="label">`scope_expansion`</span>
**Combined Score:** <span class="severe">0.93+</span>

---

# Case C: 83% OFF_TOPIC Assertions

```python
def test_rst_with_header_rows():
    """Round-trip a table with header_rows specified"""

    # READER ASSERTIONS (OFF_TOPIC) -- problem only asks for writer
    tbl = QTable.read(lines, format="ascii.rst", header_rows=["name", "unit", "dtype"])
    assert tbl["wave"].unit == u.nm            # [0] OFF_TOPIC
    assert tbl["response"].unit == u.ct        # [1] OFF_TOPIC
    assert tbl["wave"].dtype == np.float64     # [2] OFF_TOPIC
    assert tbl["response"].dtype == np.float32 # [3] OFF_TOPIC
    assert tbl["ints"].dtype == np.int8        # [4] OFF_TOPIC

    # WRITER ASSERTION (ON_TOPIC)
    out = StringIO()
    tbl.write(out, format="ascii.rst", header_rows=["name", "unit", "dtype"])
    assert out.getvalue().splitlines() == lines # [5] ON_TOPIC
```

| Label | Confidence | Evidence |
|-------|-----------|----------|
| <span class="label">`mistest_overtest`</span> | 0.90 | 5/6 assertions test reader (not requested) |
| <span class="label">`scope_expansion`</span> | 0.70 | Gold patch modifies reader code not described in problem |

> A **100% correct** writer-only implementation scores **0%** -- reader test blocks the writer assertion.

---

<!-- _class: lead -->

# Case Study D
## `astropy__astropy-14539`
### "One-Character Fix, Nine Extra Assertions"

**v3 Labels:** <span class="label">`mistest_overtest`</span>
**Combined Score:** <span class="severe">0.87</span>

---

# Case D: Excess Regression Tests

**Problem:** `FITSDiff` reports false differences between identical files (Q-format VLAs).
**Fix:** Add `or "Q" in col.format` -- a one-character fix.

| Test | ON_TOPIC | OFF_TOPIC | What it tests |
|---|---|---|---|
| `test_identical_tables` | 2 | 0 | Q-format in identical comparison |
| `test_different_table_data` | 0 | <span class="off-topic">9</span> | Q-format in *diff detection* |

### v3 Labels

| Label | Confidence | Evidence |
|-------|-----------|----------|
| <span class="label">`mistest_overtest`</span> | 0.82 | 9/11 assertions test diff detection, not false positive fix |

The 9 OFF_TOPIC assertions verify that `FITSDiff` correctly **reports differences** for Q-format columns between *different* tables -- the problem only asks about false positives for *identical* files.

---

# Top 20 Deep-Dive: Pipeline Precision

The top 20 analysis (beyond Cases A-D) revealed precision issues in v2:

| Verdict | Count | Examples |
|---------|-------|---------|
| CONFIRMED | 1 | django-11964 (EP=1.0, approach mismatch) |
| LIKELY | 1 | django-10554 (EP=0.5, strategy mismatch) |
| POSSIBLE | 13 | Low-confidence signals, ambiguous |
| FALSE POSITIVE | 5 | Pipeline over-flagged (ancillary inflation, VS overweight) |

### v3 fixes the precision problem

| Issue | v2 Behavior | v3 Fix |
|-------|-------------|--------|
| VS alone drives MODERATE | 3 weak signals compound | `desc_incomplete` (w=0.4) capped at MINOR |
| Ancillary hunks inflate EP | ANCILLARY weighted 0.5 | `mispatch_ancillary_bundling` (w=0.3) separated |
| No label granularity | 5 root causes | 17 labels with tailored weights |
| Formula compounds weak signals | $1-(1-EP)(1-ET)(1-VS)$ | Only high-weight labels can reach SEVERE |

---

# Cross-Case Synthesis: v3 Pattern Taxonomy

### Pattern 1: Approach Mismatch (highest severity)
- **Labels:** `mispatch_approach_mismatch` + `desc_hidden_in_hints`
- **Cases:** A (django-10999), Case 1 (django-11964)
- **Signature:** Problem suggests fix X; gold patch implements fix Y; agent following problem fails

### Pattern 2: Deferred Requirement
- **Labels:** `mistest_deferred_requirement` + `scope_expansion`
- **Cases:** B (astropy-13398)
- **Signature:** Problem defers feature; tests require it

### Pattern 3: Scope Expansion / Overtest
- **Labels:** `mistest_overtest` + `scope_expansion`
- **Cases:** C (astropy-14182), D (astropy-14539)
- **Signature:** Tests verify unrequested functionality

### Pattern 4: Ancillary Inflation (false positive in v2)
- **Labels:** `mispatch_ancillary_bundling` or `clean`
- **Signature:** Cleanup hunks inflate EP score; v3 correctly downgrades to MINOR or CLEAN

---

# Recommendations

### 1. Label-Specific Remediation

| Label | Remediation |
|-------|-------------|
| <span class="label">`mispatch_approach_mismatch`</span> | Accept alternative valid solutions; test intent, not approach |
| <span class="label">`mistest_deferred_requirement`</span> | Remove assertions for explicitly deferred features |
| <span class="label">`mistest_overtest`</span> | Exclude OFF_TOPIC assertions from pass/fail |
| <span class="label">`mistest_customtest`</span> | Rewrite tests to verify behavior, not implementation |
| <span class="label">`scope_expansion`</span> | Separate regression tests from feature tests |
| <span class="label">`desc_hidden_in_hints`</span> | Include reviewer decisions in problem statements |
| <span class="label">`circular_test_patch_dependency`</span> | Decouple F2P tests from out-of-scope hunks |

### 2. Trajectory Auditing

- Flag `agent_passed_leak` and `agent_passed_package_leak` agents
- Cross-reference `agent_failed_completed_intent` with task labels to confirm contamination
- Use `agent_passed_trained_hack` to identify memorization vs. reasoning

### 3. v3 Pipeline for Ongoing Monitoring

> Run `process_single_task_v3()` with dual taxonomy for precise, multi-label diagnosis.

---

# Appendix: Severity Scoring Formula

### v3 Weighted Label Formula

$$\text{severity} = 1 - \prod_{i \in \text{labels}} (1 - w_i \cdot c_i)$$

### Label Weights

| Label | Weight | Can reach SEVERE alone? |
|-------|--------|------------------------|
| `mispatch_approach_mismatch` | **1.0** | Yes (at c >= 0.7) |
| `mistest_customtest` | **0.9** | Yes (at c >= 0.78) |
| `mistest_deferred_requirement` | **0.9** | Yes (at c >= 0.78) |
| `circular_test_patch_dependency` | **0.85** | Yes (at c >= 0.82) |
| `mistest_sneaky_modification` | **0.8** | Borderline (at c >= 0.88) |
| `mistest_overtest` | **0.7** | Borderline (at c = 1.0) |
| `desc_misleading` | **0.7** | Borderline (at c = 1.0) |
| `scope_expansion` | **0.6** | No (max = 0.6) |
| `mispatch_overpatch` | **0.5** | No (max = 0.5) |
| `desc_incomplete` | **0.4** | No (max = 0.4) |
| `desc_hidden_in_hints` | **0.4** | No (max = 0.4) |
| `mispatch_ancillary_bundling` | **0.3** | No (max = 0.3) |
| `mistest_undertest` / `mispatch_underpatch` | **0.2** | No (max = 0.2) |

---

# Appendix: Classification Granularity

### Per-hunk patch classification (unchanged from v2)

| Verdict | Definition | Weight in EP |
|---|---|---|
| **REQUIRED** | Directly implements the described fix | 0 |
| **ANCILLARY** | Supports the fix but isn't described (imports, infra) | 0.5 |
| **UNRELATED** | Changes behavior not in the problem | 1.0 |

### Per-assertion test classification (unchanged from v2)

| Verdict | Definition | Weight in ET |
|---|---|---|
| **ON_TOPIC** | Assertion checks described behavior | 0 |
| **OFF_TOPIC** | Assertion checks undescribed behavior | 1.0 |

### EP/ET/VS scores (preserved for backward compat)

$$\text{EP} = \frac{\text{UNRELATED} + 0.5 \times \text{ANCILLARY}}{\text{total hunks}}$$
$$\text{ET} = \frac{\text{OFF\_TOPIC} + 0.3 \times \text{tangential\_equiv} + \text{unrelated\_equiv}}{\text{total assertions}}$$

---

# Appendix: Project Architecture (v3)

```
bench_cleanser/
  models.py                 # Data models: v1 + v2 + v3 dual taxonomy enums
  pipeline.py               # Pipeline orchestrator (v1 + v2 + v3)
  llm_client.py             # Azure OpenAI client with retry + caching
  data_loader.py            # SWE-bench dataset loading
  analysis/
    scope_analyzer.py       # Stage 2: Intent extraction (LLM)
    patch_analyzer.py       # Stage 4A: Patch-intent matching
    test_analyzer.py        # Stage 4B: Test-intent matching
  classification/
    scorer.py               # Scoring: build_report (v1), build_report_v2, build_report_v3
    dual_taxonomy.py        # v3 Dual Taxonomy: 17 task labels + severity + agent classifier
    taxonomy.py             # Severity thresholds
  trajectory/
    models.py               # TrajectoryAnalysis + AgentTrajectoryLabel integration
    classifier.py           # LLM-primary + heuristic + cross-agent (v3 labels)
    analyzer.py             # Orchestrator with narrative generation

run_pipeline.py             # Pipeline CLI (--v2 or --v3)
run_deep_dive.py            # Deep-dive report CLI
run_trajectory_analysis.py  # Trajectory validation CLI
run_slides.py               # Slide deck generator CLI
```

---

# Appendix: Pipeline Configuration

```yaml
llm:
  model: "gpt-5.2-20251211"
  max_tokens: 16384
  reasoning_effort: "high"
  max_concurrent_requests: 10
  retry_attempts: 7

thresholds:
  clean_max: 0.15
  minor_max: 0.4
  moderate_max: 0.7

code_visitation:
  enabled: true
  max_source_context_lines: 200
```

**v3 scoring:** Dual taxonomy classifier runs after EP/ET/VS, producing `DualTaxonomyReport` with multi-label output and recalibrated severity.

**Backward compatibility:** v2 fields (EP, ET, VS, root causes) preserved in all v3 reports.

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Thank You

**bench-cleanser v3** -- Dual Taxonomy Contamination Detection for SWE-bench

Pipeline v3: `python run_pipeline.py --v3 --dataset verified`
Pipeline v2: `python run_pipeline.py --v2 --dataset verified`
Deep dives: `python run_deep_dive.py --reports-dir output/reports --severity SEVERE`
Trajectories: `python run_trajectory_analysis.py --reports-dir output/reports`

> The goal is not to make benchmarks easier -- it's to make them **fair**.
