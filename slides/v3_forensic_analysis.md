---
marp: true
theme: default
paginate: true
title: "bench-cleanser v3 Forensic Analysis — 500 SWE-bench Verified Tasks"
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
    font-size: 14px;
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
    font-size: 12px;
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
  .two-col { display: flex; gap: 30px; }
  .two-col > div { flex: 1; }
  .highlight { background-color: #fff3cd; padding: 4px 8px; border-radius: 4px; }
  .footnote { font-size: 12px; color: #888; position: absolute; bottom: 30px; }
  .red { color: #e63946; }
  .green { color: #2a9d8f; }
  .orange { color: #f4a261; }
  .blue { color: #457b9d; }
  .purple { color: #6c5ce7; }
---

<!-- _class: lead -->
<!-- _paginate: false -->

# SWE-bench Contamination Forensics

## v3 Dual Taxonomy — 500-Task Full Analysis

**Evidence-backed findings from every task in SWE-bench Verified**
**Pipeline: gpt-5.2 | 17 Task Labels | 500 Reports | Forensic Case Studies**

March 2026

---

# Executive Summary

<div class="two-col">
<div>

### Key Findings

- **53.6% of tasks** (268/500) have at least one contamination label
- **21% classified SEVERE** — real barrier to fair agent evaluation
- Most contamination is **structural**, not malicious — it's how OSS PRs naturally work
- **Top 3 contamination types**: ancillary bundling (108), overtest (102), undertest (99)
- Tasks with **5+ labels** are unsalvageable for benchmarking

</div>
<div>

### What This Means

- Leaderboard scores overweight "contamination tolerance" vs engineering skill
- An agent that **perfectly solves** the stated problem fails ~21% of tasks
- **Partial restoration is possible**: 15.6% MINOR severity tasks need only minor cleanup
- Labels give reviewers **actionable triage** — know exactly what's wrong with each task

</div>
</div>

> Of 500 SWE-bench Verified tasks, only **232 (46.4%)** are genuinely clean evaluations.

---

# Agenda

1. **Severity Distribution** — The full picture at 500 tasks
2. **Label Taxonomy** — What each label means in plain English
3. **Label Distribution** — Which contamination types dominate
4. **Co-occurrence Patterns** — How labels cluster together
5. **Per-Project Breakdown** — Which projects are most contaminated
6. **Forensic Case Studies** (8 detailed cases with evidence chains)
7. **Hunk & Assertion Forensics** — Gold patch and test quality metrics
8. **Edge Cases & Calibration** — Where the classifier is uncertain
9. **Downstream Lessons** — What we learned, methodology improvements
10. **Reviewer Triage Guide** — How to use the CSV for manual assessment

---

# 1. Severity Distribution — 500 Tasks

| Severity | Count | % | What It Means |
|----------|-------|---|---------------|
| <span class="clean">CLEAN</span> | 232 | 46.4% | Fair task. Problem, patch, and tests all aligned. |
| <span class="minor">MINOR</span> | 78 | 15.6% | Small issues (slight undertest, minor bundling). Usable with awareness. |
| <span class="moderate">MODERATE</span> | 85 | 17.0% | Meaningful contamination. Agent might fail unfairly on this task. |
| <span class="severe">SEVERE</span> | 105 | 21.0% | Major contamination. Agent solving the stated problem would likely fail. |

### Score Distribution

| Metric | Value |
|--------|-------|
| Mean combined score | 0.311 |
| Median | 0.216 |
| 25th percentile | 0.000 (clean) |
| 75th percentile | 0.602 |
| Maximum | 0.998 |

> Bimodal distribution: tasks are either clean (score 0) or moderately-to-heavily contaminated (0.3-1.0).

---

# 2. Label Taxonomy — Plain English Guide

### Group A: Test Contamination — "Do the tests check the right thing?"

| Label | Plain English | Impact |
|-------|-------------|--------|
| `mistest_overtest` | Tests check things **beyond** what the problem asked for | Agent solves stated problem but fails extra tests |
| `mistest_undertest` | Tests **don't fully cover** the problem — partial fix passes | Makes task easier, not harder. Less severe. |
| `mistest_customtest` | Tests are so specific to **one implementation approach** that other valid fixes fail | Agent's correct-but-different solution rejected |
| `mistest_sneaky_modification` | A **pre-existing test was quietly changed** to check new undescribed behavior | Hidden trap — test looks old but requirements are new |
| `mistest_deferred_requirement` | Tests require features the problem says are **for later** ("TODO", "future work") | Agent told not to build it, but tests demand it |

---

# 2. Label Taxonomy (continued)

### Group B: Patch Contamination — "Does the gold patch match the problem?"

| Label | Plain English | Impact |
|-------|-------------|--------|
| `mispatch_overpatch` | Gold patch includes **functional changes beyond** the problem scope | Agent needs to guess undescribed changes |
| `mispatch_underpatch` | Gold patch **doesn't fully fix** the stated problem, yet tests pass | Inconsistent: described problem remains |
| `mispatch_approach_mismatch` | Gold patch uses a **completely different strategy** than problem suggests | Agent follows problem description and gets wrong answer |
| `mispatch_ancillary_bundling` | Gold patch bundles **cleanup** (whitespace, imports) alongside the fix | Agent must replicate cosmetic changes |

### Group C: Description Contamination — "Is the problem statement trustworthy?"

| Label | Plain English | Impact |
|-------|-------------|--------|
| `desc_misleading` | Problem actively suggests a **wrong** approach or root cause | Agent misled into wrong solution |
| `desc_incomplete` | Problem is **missing key info** — no repro steps, ambiguous requirements | Agent lacks information to solve correctly |
| `desc_hidden_in_hints` | Critical info (function names, root cause) is **only in hints**, not problem | With hints it's easy; without hints it's a guessing game |
| `desc_self_referential` | Problem says **"see the patch"** to understand what to do | Task is circular: solution defines requirements |

---

# 2. Label Taxonomy (continued)

### Group D: Structural Contamination — "Is the scope well-bounded?"

| Label | Plain English | Impact |
|-------|-------------|--------|
| `scope_expansion` | Fix changes a **broader API or parent class** than described | Agent must know to change something upstream |
| `circular_test_patch_dependency` | Tests need **unrelated patch changes** to pass — circular dependency | Even with correct core fix, tests fail |

### Group E: Clean

| Label | Plain English |
|-------|-------------|
| `clean` | No issues. Problem, patch, and tests are all fair and aligned. |
| `hard_but_clean` | Genuinely hard task, but evaluated fairly. Difficulty is inherent, not from contamination. |

---

# 3. Label Distribution — Full 500-Task Census

| Rank | Label | Count | Avg Confidence | What Drives It |
|------|-------|-------|----------------|----------------|
| 1 | <span class="green">clean</span> | 214 | 0.82 | Properly scoped PRs |
| 2 | `mispatch_ancillary_bundling` | 108 | 0.70 | OSS PRs bundle cleanup with fixes |
| 3 | `mistest_overtest` | 102 | 0.74 | Regression suites test more than the issue |
| 4 | `mistest_undertest` | 99 | 0.70 | Sparse test suites miss acceptance criteria |
| 5 | `desc_hidden_in_hints` | 57 | 0.70 | Maintainer comments reveal the fix |
| 6 | `desc_incomplete` | 53 | 0.57 | Bug reports lack repro steps |
| 7 | `mistest_customtest` | 53 | 0.65 | Tests lock in one implementation |
| 8 | `mistest_sneaky_modification` | 46 | 0.70 | Pre-existing tests quietly changed |
| 9 | `mispatch_overpatch` | 40 | 0.67 | PRs add features alongside fixes |
| 10 | `scope_expansion` | 32 | 0.59 | Fix touches broader API |
| 11 | `desc_misleading` | 21 | 0.68 | Wrong root cause in bug report |
| 12 | `mispatch_approach_mismatch` | 13 | 0.68 | Problem says X, patch does Y |
| 13 | `mispatch_underpatch` | 7 | 0.82 | Patch doesn't fully fix issue |
| 14 | `desc_self_referential` | 3 | 0.64 | "See attached PR" |
| 15 | `hard_but_clean` | 2 | 0.61 | Hard but fair |
| 16 | `mistest_deferred_requirement` | 1 | 0.60 | Tests require deferred feature |

---

# 4. Co-occurrence Patterns — How Labels Cluster

### Top 10 Label Pairs (count of tasks where both appear)

| Label Pair | Count | Interpretation |
|-----------|-------|----------------|
| ancillary_bundling + overtest | 37 | PR bundles cleanup AND tests check extra things |
| customtest + overtest | 33 | Tests both go beyond scope AND lock in one approach |
| ancillary_bundling + undertest | 32 | Cleanup bundled AND tests don't fully cover the problem |
| overtest + sneaky_modification | 25 | Extra tests AND pre-existing tests quietly modified |
| overtest + undertest | 25 | Tests simultaneously over-check some things and under-check others |
| ancillary_bundling + overpatch | 23 | Both cleanup and functional over-scoping |
| ancillary_bundling + scope_expansion | 20 | Cleanup bundled with broader API changes |
| ancillary_bundling + customtest | 20 | Cleanup with implementation-locked tests |
| hidden_in_hints + incomplete | 20 | Problem is vague AND hints have the answer |
| ancillary_bundling + sneaky_modification | 18 | Cleanup with quietly changed tests |

### Most common label sets (tasks with identical label combinations)

| Label Combination | Count |
|-------------------|-------|
| (clean — no contamination) | 216 |
| `mistest_undertest` alone | 25 |
| `mispatch_ancillary_bundling` alone | 19 |
| `desc_hidden_in_hints` alone | 13 |
| `mistest_customtest` + `mistest_overtest` | 11 |

---

# 5. Per-Project Breakdown

| Project | Tasks | Contamination Rate | Top Contamination Label |
|---------|-------|--------------------|------------------------|
| **django** | 231 | <span class="green">35.5%</span> | ancillary_bundling (31) |
| **sympy** | 75 | <span class="severe">81.3%</span> | overtest (34) |
| **sphinx-doc** | 44 | <span class="severe">79.5%</span> | undertest (15) |
| **matplotlib** | 34 | <span class="severe">76.5%</span> | undertest (14) |
| **scikit-learn** | 32 | <span class="moderate">53.1%</span> | overtest (14) |
| **astropy** | 22 | <span class="moderate">50.0%</span> | ancillary_bundling (8) |
| **pydata/xarray** | 22 | <span class="moderate">54.5%</span> | undertest (7) |
| **pytest-dev** | 19 | <span class="moderate">47.4%</span> | overtest (5) |
| **pylint-dev** | 10 | <span class="severe">80.0%</span> | ancillary_bundling (5) |
| **psf/requests** | 8 | <span class="moderate">62.5%</span> | undertest (2) |

### Key Observation

**Django is the cleanest** (35.5% contamination) — large, well-maintained project with disciplined PRs.
**SymPy is the most contaminated** (81.3%) — complex symbolic math PRs frequently bundle extra changes and overly specific tests.

---

# 6a. Case Study: The Perfectly Clean Task

## `django__django-14373` — <span class="clean">CLEAN</span> (score 0.000)

**Problem**: Fix `DateFormat.Y()` to return a zero-padded 4-digit year for years < 1000.

**Why it's clean**:

| Check | Result |
|-------|--------|
| Problem statement | Precise: "Y specifier is supposed to always return a four-digit year padded with zeros" |
| Gold patch | 1 hunk, REQUIRED, changes `DateFormat.Y()` to use `'%04d' % self.data.year` |
| Tests | 1 test, ALIGNED: `test_Y_format_year_before_1000` — checks exactly the stated behavior |
| Modified tests | None |
| Scope | Narrow — only `DateFormat.Y()` |

> **Lesson**: Clean tasks have 1:1:1 alignment — one clear problem, one targeted patch, one focused test.

---

# 6b. Case Study: Approach Mismatch

## `django__django-11964` — <span class="severe">SEVERE</span> (score 0.976) | 4 labels

**Problem**: Model fields using `TextChoices`/`IntegerChoices` return Enum member objects instead of primitive values when instance is freshly created (vs retrieved from DB).

**What went wrong**:

| Label | Evidence |
|-------|----------|
| `mispatch_approach_mismatch` (conf 0.90) | Problem describes a **storage-level** inconsistency (Enum member vs primitive in `__dict__`). Gold patch changes `Choices.__str__()` — a completely different axis. |
| `mispatch_overpatch` (conf 0.75) | Changing `__str__()` affects stringification for ALL `Choices` usages project-wide, not just model field access. |
| `mistest_overtest` (conf 0.60) | Tests verify `str(ChoicesMember)` behavior directly rather than model field coercion. |
| `desc_misleading` (conf 0.50) | Report mixes "differing type" issue with `str()` output — misleading about root cause. |

**The trap for agents**: An agent reading the problem would try to fix value coercion at the model field level. The gold patch instead monkey-patches `__str__`, which is a band-aid that doesn't fix the underlying type inconsistency.

> Gold patch hunks scored **1.0 EP** (all UNRELATED). Zero required code for the stated problem.

---

# 6c. Case Study: The 9-Label Catastrophe

## `scikit-learn__scikit-learn-14629` — <span class="severe">SEVERE</span> (score 0.998) | 9 labels

**Problem**: `cross_val_predict(..., method='predict_proba')` fails with `AttributeError` on `MultiOutputClassifier` because it tries to access `estimator.classes_`.

**Every contamination type at once**:

| Label | What went wrong |
|-------|----------------|
| `mispatch_approach_mismatch` | Problem says fix `_validation.py` to read `estimators_[i].classes_`. Gold patch instead adds `.classes_` to `MultiOutputClassifier`. |
| `desc_misleading` | Problem points to `_validation.py` as the fix location — gold patch changes `multioutput.py`. |
| `desc_hidden_in_hints` | Hints: *"I think this bug is in MultiOutputClassifier... add `classes_` like ClassifierChain"* — this is the actual solution but only in hints. |
| `mistest_overtest` | Test checks `MultiOutputClassifier.classes_` property — not `cross_val_predict` at all. |
| `mistest_customtest` | Test requires `.classes_` to be a `list` with length `n_outputs` — locks in one specific implementation. |
| `mistest_undertest` | No test calls `cross_val_predict` with `predict_proba` on `MultiOutputClassifier`! |
| `mispatch_overpatch` | Adds new public API (`classes_` attribute) — broader than fixing the error. |
| `mispatch_ancillary_bundling` | Includes indentation-only cleanup in `fit()` unrelated to the bug. |
| `scope_expansion` | Changes `MultiOutputClassifier` class API globally, not just `cross_val_predict` interop. |

> **Excess Patch: 1.0** (2 hunks, 0 required, 2 unrelated). **Excess Test: 1.0** (1 test, 0 aligned, 1 unrelated).
> An agent following the problem statement would fix `_validation.py` — and score **zero**.

---

# 6d. Case Study: Problem Says Parser, Fix is Printer

## `sympy__sympy-21612` — <span class="severe">SEVERE</span> (score 0.994) | 5 labels

**Problem**: "Latex parsing of fractions yields wrong expression... `((a**3 + b)/c)/1/(c**2)`. Missing brackets in the denominator."

**The misdirection**:

> Problem says: **"LaTeX parsing"** is broken.
> Hints reveal: *"This is a printing, not a parsing error."*
> Gold patch: Changes **`sympy/printing/str.py`** — the string printer, not the parser.

| Label | Evidence |
|-------|----------|
| `desc_misleading` (0.85) | Problem frames bug as "parsing yields wrong expression" — it's actually a str-printing parenthesization issue. |
| `mispatch_approach_mismatch` (0.90) | Gold patch modifies the string printer to handle `Pow` in `Mul` context. Problem implies parser fix. |
| `desc_hidden_in_hints` (0.75) | Hints contain the correction: "This is a printing, not a parsing error." |
| `mispatch_overpatch` (0.70) | Fix expands parenthesization rules for all Mul/Pow printing, not just LaTeX fractions. |
| `mistest_overtest` (0.95) | Tests verify `str()` output of constructed Mul/Pow expressions — nothing about LaTeX parsing. |

> **Lesson**: When the problem statement misidentifies the component (parser vs printer), agents pursuing the stated approach have zero chance.

---

# 6e. Case Study: The Answer is in the Hints

## `django__django-15382` — <span class="moderate">MODERATE</span> (score 0.492) | 2 labels

**Problem**: Filtering with `~Exists(Manager.objects.none())` collapses the WHERE clause due to `EmptyResultSet`.

**What the hints reveal** (not in the problem statement):

```python
# Hints provide the EXACT fix code:
except EmptyResultSet:
    if self.negated:
        return '%s = %s', (1, 1)
```

| Label | Evidence |
|-------|----------|
| `desc_hidden_in_hints` (0.95) | Hints provide the exact fix code, exact file location (`Exists.as_sql`), and exact test name (`test_negated_empty_exists`). |
| `desc_incomplete` (0.45) | Problem only shows the symptom (missing WHERE). Doesn't define correct behavior for negated empty exists. |

**The fairness question**: Without hints, this is a difficult diagnostic task requiring understanding SQL compilation internals. With hints, it's copy-paste. SWE-bench uses hints — but should the benchmark score differentiate?

> **Patch: 1 hunk, REQUIRED.** **Test: 1 test, ALIGNED.** But the solution pathway is fully given in hints.

---

# 6f. Case Study: Sneaky Test Modification

## `pylint-dev__pylint-4661` — <span class="severe">SEVERE</span> (score 0.789) | 3 labels

**Problem**: Change pylint's default data directory to XDG-compliant path.

**The hidden trap**:

| Label | Evidence |
|-------|----------|
| `mistest_sneaky_modification` (0.85) | Pre-existing test `test_pylint_home` was **modified** and flagged as **UNRELATED** (`mod_aligned=False`). The test was altered to enforce behavior not in the problem statement. |
| `mispatch_ancillary_bundling` (0.65) | 5 hunks total, only 1 REQUIRED. 4 hunks are ancillary (imports, type-checking, config). |
| `desc_incomplete` (0.45) | Problem omits Windows behavior, migration path, and directory creation details. |

**Why sneaky modification is dangerous**: The test `test_pylint_home` **already existed** in the test suite. It looks like a stable, reliable test. But the PR silently altered its assertions to require new behavior. An agent would have no signal that this "old" test now demands something beyond the problem spec.

> **Gold patch**: 5 hunks, 1 required, 4 ancillary.
> **F2P tests**: 1 test, 0 aligned, 1 unrelated, **modified=True**.

---

# 6g. Case Study: Implementation-Locked Testing

## `sympy__sympy-14976` — <span class="severe">SEVERE</span> (score 0.702) | Single label

**Problem**: `lambdify(..., modules='mpmath')` should convert SymPy `Rational` constants to mpmath high-precision numbers, not bare Python integer division.

**What makes this the sole single-label SEVERE case**:

The test asserts:
```python
assert p.doprint(Rational(1, 2)) == 'mpmath.mpf(1)/mpmath.mpf(2)'
```

This locks in **one specific representation**. Other valid fixes:
- `mpmath.mpf(0.5)` — directly convert to mpf float
- `mpmath.mpq(1, 2)` — use mpmath's rational type
- `mpmath.mpf(1) / 2` — wrap only numerator

All would satisfy the stated requirement (high-precision computation) but fail the test.

| Label | Confidence | Key Evidence |
|-------|-----------|--------------|
| `mistest_customtest` | 0.78 | Test asserts exact string `'mpmath.mpf(1)/mpmath.mpf(2)'` — only one valid codegen representation accepted |

> **Lesson**: When a single label drives SEVERE, it means **one specific contamination type is so strong** that it alone makes the task unfair.

---

# 6h. Case Study: Scope Expansion

## `django__django-13794` — <span class="severe">SEVERE</span> (score 0.808) | 3 labels

**Problem**: Fix the `add` template filter to concatenate a string with a lazy string (`gettext_lazy`).

**What actually happened**:

| Label | Evidence |
|-------|----------|
| `scope_expansion` (0.75) | Problem is about the template `add` filter. Gold patch adds `__add__`/`__radd__` to `django/utils/functional.py` — the core lazy proxy used everywhere in Django. |
| `mispatch_overpatch` (0.60) | `__add__`/`__radd__` on lazy proxy changes `+` behavior for ALL lazy objects, not just template filter usage. |
| `mispatch_approach_mismatch` (0.50) | Natural fix: coerce lazy to str in the `add` filter. Actual fix: change fundamental lazy proxy behavior. |

**The scope problem**: Agent reads "fix the `add` template filter" and modifies the filter code. Gold patch instead goes to `django/utils/functional.py` — a foundational utility module — and adds new dunder methods. The fix works, but it's at a completely different scope than described.

> Agent must independently decide to change a core utility module that the problem statement never mentions.

---

# 7. Hunk & Assertion Forensics

## Gold Patch Quality (1,220 hunks across 500 tasks)

| Hunk Verdict | Count | % | Meaning |
|--------------|-------|---|---------|
| **REQUIRED** | 820 | 67.2% | Directly implements the stated fix |
| **ANCILLARY** | 298 | 24.4% | Cleanup, imports, whitespace — not needed for fix |
| **UNRELATED** | 102 | 8.4% | New features, refactoring beyond scope |

> **1 in 3 hunks** (32.8%) in gold patches is NOT required to solve the stated problem.

## F2P Test Quality (1,578 tests, 1,000 assertions)

| Test Verdict | Count | % |
|--------------|-------|---|
| **ALIGNED** | 1,381 | 87.5% |
| **TANGENTIAL** | 124 | 7.9% |
| **UNRELATED** | 73 | 4.6% |

| Assertion Category | Count | % |
|--------------------|-------|---|
| **ON_TOPIC** | 381 | 38.1% |
| **OFF_TOPIC** | 301 | 30.1% |
| *(no assertions parsed)* | 318 | 31.8% |

> **30% of parsed assertions** check behavior not described in the problem statement.

---

# 7b. Modified Tests — The Hidden Danger

## 54 tasks out of 500 (10.8%) have modified pre-existing tests

When a pre-existing test is modified by the same PR that fixes the bug:
- The test **looks legitimate** (it already existed)
- But its assertions **may have been changed** to require new behavior
- Agent has no way to know the test was altered

**Modified test + misaligned with task = `mistest_sneaky_modification`**

This was detected in **46 tasks** (8 had modified tests that remained aligned).

### The scale of hidden requirements

Of the 54 modified-test cases:
- **46** (85%) had modifications that added behavior beyond the problem statement
- **8** (15%) had modifications that stayed aligned with the stated requirements

> Modified tests are the hardest contamination to detect without our pipeline's structural analysis.

---

# 8. Confidence & Calibration Analysis

## Per-Label Classifier Confidence

| Label | Count | Mean Conf | Min | Max | Low-conf (<0.5) |
|-------|-------|-----------|-----|-----|-----------------|
| `clean` | 214 | **0.818** | 0.70 | 0.93 | 0 |
| `mispatch_underpatch` | 7 | **0.821** | 0.70 | 0.90 | 0 |
| `mistest_overtest` | 102 | **0.736** | 0.45 | 0.96 | 4 |
| `mistest_undertest` | 99 | **0.702** | 0.44 | 0.95 | 7 |
| `mispatch_ancillary_bundling` | 108 | **0.700** | 0.55 | 0.86 | 0 |
| `desc_hidden_in_hints` | 57 | **0.701** | 0.45 | 0.95 | 4 |
| `mistest_sneaky_modification` | 46 | **0.697** | 0.45 | 0.85 | 3 |
| `mispatch_approach_mismatch` | 13 | **0.682** | 0.50 | 0.90 | 0 |
| `desc_misleading` | 21 | **0.680** | 0.45 | 0.90 | 1 |
| `mispatch_overpatch` | 40 | **0.666** | 0.45 | 0.85 | 2 |
| `mistest_customtest` | 53 | **0.654** | 0.44 | 0.85 | 2 |
| `desc_self_referential` | 3 | **0.640** | 0.45 | 0.75 | 1 |
| `scope_expansion` | 32 | **0.592** | 0.44 | 0.75 | 6 |
| `desc_incomplete` | 53 | **0.567** | 0.40 | 0.80 | 16 |

**Highest confidence**: `clean` (0.82) and `mispatch_underpatch` (0.82) — clearest signals.
**Lowest confidence**: `desc_incomplete` (0.57) — ambiguity is inherently hard to quantify.

---

# 8b. Edge Cases

## Near-threshold classifications

**5 tasks classified CLEAN but with score > 0.1** (all from `mistest_undertest` alone):

| Task | Score | Label |
|------|-------|-------|
| `django__django-16938` | 0.148 | mistest_undertest |
| `django__django-15022` | 0.144 | mistest_undertest |
| `matplotlib__matplotlib-20859` | 0.140 | mistest_undertest |
| `django__django-12708` | 0.124 | mistest_undertest |
| `django__django-13297` | 0.110 | mistest_undertest |

These have minor undertest but the weight (0.2) keeps the score below the MINOR threshold (0.15). This is **correct behavior** — slight undertest makes a task easier, not harder, so it shouldn't be flagged as contaminated.

**No SEVERE tasks with score < 0.5** — no anomalous low-score SEVERE classifications.
This indicates robust calibration: the classifier doesn't produce contradictory severity vs score assignments.

---

# 9. Downstream Lessons Learned

## What the v3 Pipeline Taught Us

<div class="two-col">
<div>

### Methodology Improvements

1. **Multi-label >>  single-label**: Tasks have 2.3 labels on average. A single severity miss much nuance.

2. **Ancillary bundling is the #1 contamination** (108 tasks) — not because it's the worst, but because it's how OSS works. PRs naturally include cleanup.

3. **Description problems** are common (131 tasks with desc_* labels) and **independently verifiable** — you can check problem vs hints vs patch without running code.

4. **Modified tests are the sneakiest** — 46 tasks have quietly modified pre-existing tests. No structural signal visible to agents.

</div>
<div>

### What's Restorable vs Not

**Restorable** (human reviewer can fix):
- `mispatch_ancillary_bundling` — strip ancillary hunks
- `mistest_undertest` — add missing test coverage
- `desc_hidden_in_hints` — promote hints into problem text

**Hard to restore**:
- `mispatch_approach_mismatch` — fundamental strategy mismatch
- `mistest_customtest` — need to rewrite tests for behavioral contract
- `scope_expansion` — would need different gold patch

**Not restorable** (exclude from benchmark):
- 9-label cases (scikit-14629 etc.)
- `circular_test_patch_dependency`
- Tasks with both approach_mismatch AND desc_misleading

</div>
</div>

---

# 9b. v3 Performance Assessment

## Is v3 better than v2?

| Dimension | v2 (root-cause taxonomy) | v3 (dual taxonomy) | Verdict |
|-----------|------------------------|---------------------|---------|
| **Label granularity** | 5 root-cause categories | 17 task labels + 8 agent labels | v3 far more actionable |
| **Multi-label support** | Single root cause | Zero or more per task | v3 captures complexity |
| **Severity accuracy** | Threshold-based on EP/ET/VS scores | Weighted label formula | v3 better calibrated |
| **False positive rate** | Unknown (no per-label validation) | 0 low-conf clean, 16 low-conf desc_incomplete | v3 has visible confidence |
| **Reviewer actionability** | "contamination level high/low" | "tests lock in one implementation approach" | v3 tells you exactly what's wrong |
| **Coverage** | All 500 tasks | All 500 tasks | Same |
| **Runtime (500 tasks)** | ~15 min | ~78 min (2 extra LLM calls per task) | v3 slower but acceptable |

> **Verdict**: v3 is strictly better. The multi-label system surfaces issues v2 missed entirely, and every label comes with evidence and confidence that a reviewer can validate.

---

# 9c. Key Statistical Takeaways

### The Numbers That Matter

| Metric | Value | Significance |
|--------|-------|-------------|
| Tasks with 3+ labels | **91** (18.2%) | These need structural fixes, not just triage |
| Tasks with approach mismatch | **13** (2.6%) | The strongest signal — agent cannot solve these correctly |
| Projects with >75% contamination | **4** (sympy, sphinx, matplotlib, pylint) | These projects need project-level remediation |
| Ancillary hunks in gold patches | **298 / 1,220** (24.4%) | Nearly 1 in 4 hunks is cleanup |
| Off-topic assertions | **301 / 682** (44.1%) | Almost half of classified assertions check wrong stuff |
| Modified tests with misaligned changes | **46 / 54** (85%) | When tests are modified, they're almost always sneaky |

### If the benchmark were cleaned

Removing SEVERE tasks: **395 tasks survive** (79%)
Removing SEVERE + MODERATE: **310 tasks survive** (62%)
Tasks with zero contamination labels: **232 tasks** (46.4%)

---

# 10. Reviewer Triage Guide

## How to Use the `triage_review.csv`

The CSV file (`output_v3/triage_review.csv`) is sorted by triage priority. Each row has:

| Column | What It Tells You |
|--------|-------------------|
| `triage_priority` | 1 = review immediately (SEVERE), 2 = review soon (MODERATE), 3 = low priority, 4 = clean |
| `primary_label` | The single most impactful contamination label for this task |
| `all_labels` | All labels (tasks can have multiple) |
| `plain_english` | Human-readable explanation of what's wrong with this task |
| `evidence_summary` | Key evidence snippets from the LLM classifier |
| `patch_hunks` | R/A/U breakdown of gold patch hunks |
| `test_breakdown` | Aligned/Tangential/Unrelated test breakdown |
| `has_modified_tests` | True if pre-existing tests were modified — check sneaky modification |

### Recommended Review Workflow

1. **Start with Priority 1** (105 SEVERE tasks) — these are the strongest contamination signals
2. **Check `primary_label`** — tells you what type of problem to look for
3. **Read `plain_english`** — understand the issue without reading code
4. **Validate with `evidence_summary`** — confirm or dispute the classification
5. **Decision**: Remove from benchmark / Fix / Accept as-is

---

# 11. Recommendations

## For SWE-bench Maintainers

1. **Remove the 13 `mispatch_approach_mismatch` tasks** — these are structurally unsolvable from the problem statement alone

2. **Strip ancillary hunks** from gold patches for the 108 `mispatch_ancillary_bundling` tasks — this is automatable

3. **Promote hints to problem text** for the 57 `desc_hidden_in_hints` tasks, or create separate "with hints" / "without hints" scoring

4. **Audit modified tests** — 46 tasks have sneaky test modifications; these need manual review to verify test changes align with stated requirements

5. **Add missing test coverage** for the 99 `mistest_undertest` tasks — write tests that verify the stated acceptance criteria

## For Agent Developers

1. **Expect ~21% of tasks to be unsolvable** from the problem statement alone
2. **Weight leaderboard scores** by contamination severity — a "70% solve rate" on clean tasks is more impressive than "90%" on contaminated tasks
3. **Use hints aggressively** — 57 tasks have critical solution info only in hints

---

# Appendix: Label Reference Card

| Label | One-Line Summary | Restorable? |
|-------|-----------------|-------------|
| `mistest_overtest` | Tests check beyond scope | Rewrite tests |
| `mistest_undertest` | Tests don't cover problem | Add tests |
| `mistest_customtest` | Tests lock in one approach | Rewrite to behavioral |
| `mistest_sneaky_modification` | Old test quietly changed | Manual review |
| `mistest_deferred_requirement` | Tests demand deferred feature | Remove deferred tests |
| `mispatch_overpatch` | Patch does more than asked | Strip extra hunks |
| `mispatch_underpatch` | Patch doesn't fully fix | Extend patch |
| `mispatch_approach_mismatch` | Problem says X, patch does Y | Remove from benchmark |
| `mispatch_ancillary_bundling` | Cleanup bundled with fix | Auto-strip ancillary |
| `desc_misleading` | Wrong approach suggested | Rewrite problem |
| `desc_incomplete` | Missing info in problem | Add missing context |
| `desc_hidden_in_hints` | Answer only in hints | Promote to problem |
| `desc_self_referential` | "See the patch" | Rewrite problem |
| `scope_expansion` | Fix broader than described | May need new patch |
| `circular_test_patch_dependency` | Circular test-patch need | Remove from benchmark |

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Thank You

## Explore the Data

- **Full 500-task results**: `output_v3/reports/`
- **Triage CSV**: `output_v3/triage_review.csv`
- **Forensic analysis data**: `analysis_v3/forensic_results.json`
- **Analysis scripts**: `scripts/v3_forensic_analysis.py`

### bench-cleanser v3 — Making SWE-bench evaluations fair and transparent.
