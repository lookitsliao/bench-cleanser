---
marp: true
theme: default
paginate: true
title: "bench-cleanser: Automated Contamination Detection for SWE-bench"
math: katex
style: |
  section {
    font-size: 21px;
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
    font-size: 21px;
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
    font-size: 12px;
    background-color: transparent;
    padding: 0;
  }
  blockquote {
    font-size: 18px;
    border-left: 4px solid #e63946;
    padding-left: 16px;
    color: #333;
  }
  .severe { color: #e63946; font-weight: bold; }
  .moderate { color: #f4a261; font-weight: bold; }
  .minor { color: #e9c46a; font-weight: bold; }
  .clean { color: #2a9d8f; font-weight: bold; }
  .label { color: #6c5ce7; font-weight: bold; }
  .em { color: #e63946; font-weight: bold; }
  .dim { color: #888; font-size: 14px; }
  .highlight { background-color: #fff3cd; padding: 2px 6px; border-radius: 3px; }
  .stat { font-size: 36px; font-weight: bold; color: #e63946; }
---

# bench-cleanser

## Automated Contamination Detection for SWE-bench Benchmarks

April 2026 -- Pipeline v5

---

# Agenda

1. **The Problem** -- Why SWE-bench tasks need auditing
2. **Industry Context** -- OpenAI's SWE-bench Verified deprecation
3. **bench-cleanser** -- 6-stage pipeline architecture
4. **Dual Taxonomy** -- 8 task labels + 8 agent trajectory labels
5. **SWE-bench Pro** (731 tasks) -- v5 findings with full context
6. **Contamination Penalty** -- Does it actually hurt agents?
7. **Smoking Guns** -- Agent trajectory proofs
8. **v4 to v5** -- The pipeline fix and severity migration
9. **Ecosystem Positioning** -- How we fit in
10. **Recommendations** -- What to do about it

---

# The Problem: Three Confounded Signals

Raw SWE-bench scores blend three independent factors:

```
SWE-bench Score = f(Agent Skill, Benchmark Design, Training Leakage)

  Agent Skill          Benchmark Design        Training Leakage
  ───────────          ────────────────        ────────────────
  Genuine capability   Tests/patch exceed      Model memorized
  to solve software    problem description     gold patch or PR
  engineering tasks                            details
       │                      │                      │
       │               ┌──────┴──────┐        ┌──────┴──────┐
       │               │bench-cleanser│       │bench-cleanser│
       │               │  Axis 1     │        │  Axis 2     │
       │               └─────────────┘        └─────────────┘
       │
       └── The signal we actually want to measure
```

bench-cleanser disentangles **Axis 1** (task contamination) and **Axis 2** (training leakage) to isolate the genuine skill signal.

---

# Industry Context: OpenAI Deprecates SWE-bench Verified

> *"Improvements on SWE-bench Verified no longer reflect meaningful improvements in models' real-world software development abilities."*
> -- OpenAI, April 2026

### OpenAI's audit findings (138 tasks, 6 reviewers each)

| Issue | % of audited tasks |
|-------|-------------------:|
| **Narrow test cases** (enforce specific implementation details) | 35.5% |
| **Wide test cases** (check undescribed functionality) | 18.8% |
| **Miscellaneous issues** | 5.1% |
| **Total with material issues** | **59.4%** |

### OpenAI's contamination findings

All frontier models tested (GPT-5.2, Claude Opus 4.5, Gemini 3 Flash) could reproduce gold patches or verbatim problem statement details, indicating training data exposure.

**OpenAI now recommends SWE-bench Pro.** bench-cleanser has analyzed all 731 Pro tasks.

---

# OpenAI's Categories Map to Our Taxonomy

| OpenAI Finding | bench-cleanser Label | Detection Method |
|---|---|---|
| **Narrow test cases** | `APPROACH_LOCK` | Cross-reference: F2P tests exercise UNRELATED patch code |
| **Wide test cases** | `WIDE_TESTS` | Per-assertion: OFF_TOPIC assertions beyond acceptance criteria |
| Modified test flaws | `TEST_MUTATION` | Pre/post-patch diff: modified tests with misaligned changes |
| Gold patch scope expansion | `SCOPE_CREEP` | Per-hunk: UNRELATED behavioral hunks in gold patch |
| Training contamination | `agent_passed_leak` | Trajectory: gold patch similarity, memorized patterns |

### The difference

| | OpenAI Audit | bench-cleanser |
|---|---|---|
| **Scale** | 138 tasks, manual | 731 tasks, automated |
| **Granularity** | Task-level | Per-assertion, per-hunk |
| **Reproducibility** | Expert reviewers | Deterministic + LLM pipeline |
| **Traceability** | Category label | Full evidence chain to assertions |
| **Benchmark** | Verified only | Verified + Pro |

---

# bench-cleanser: 6-Stage Pipeline

```
                 +--------------------------+
                 |    SWE-bench Dataset      |
                 | (problem_statement, patch |
                 |  test_patch, requirements |   <-- Pro-specific fields
                 |  interface, fail_to_pass) |
                 +------------+-------------+
                              |
                 +------------v-------------+
           1     |         PARSE            |  Deterministic diff parsing
                 | Structured hunks, F2P    |  Multi-language support
                 +------------+-------------+
                              |
                 +------------v-------------+
           1.5   |    CODE VISITATION       |  Git clone + AST extraction
                 | Full function/test src   |  Imports, call targets
                 +------------+-------------+
                              |
            +--------+--------+--------+
            |                          |
 +----------v----------+  +-----------v-----------+
 |       INTENT        |  |    STRUCTURAL DIFF    |
 | problem_statement + |  | AST changed blocks    |   2 / 3
 | requirements +      |  | call graph, imports   |
 | interface           |  |                       |
 | (BLIND to patch)    |  |                       |
 +----------+----------+  +-----------+-----------+
            |                          |
            +--------+--------+--------+
                     |
 +-------------------+---------+---------+
 |                                       |
 +----------v----------+  +-------------v---------+
 |    PATCH MATCHING   |  |    TEST MATCHING      |
 | REQUIRED/ANCILLARY  |  | ALIGNED/TANGENTIAL    |  4A / 4B
 | /UNRELATED per hunk |  | /UNRELATED per test   |
 |                     |  | ON/OFF per assertion  |
 +----------+----------+  +-------------+---------+
            |                            |
            +--------+--------+----------+
                     |
        CROSS-REFERENCE ANALYSIS (deterministic)
        Circular dependency: test -> UNRELATED hunk
                     |
            +--------v--------+
      5     |  CLASSIFICATION |  Heuristic pre-classifier
            |  8-label dual   |  + LLM refinement
            |  taxonomy       |  Bucket-based severity
            +--------+--------+
                     |
            +--------v--------+
            |     OUTPUT      |  JSON reports, CSV
            +-----------------+  deep dives, slides
```

---

# The Information Barrier (Stage 2)

The most critical design decision: **the LLM never sees the gold patch** during intent extraction.

### What Stage 2 receives
- Problem statement
- Requirements (Pro evaluation-only field)
- Interface (Pro evaluation-only field)

### What it does NOT see
- Gold patch (the code changes)
- Test patch (the F2P tests)
- Hints text (not used for Pro)

### Why this matters
The extracted intent becomes the **reference standard** for Stages 4A and 4B. By keeping it blind to the gold patch, the intent reflects what the problem *describes*, not what the developer *happened to implement*.

This prevents the pipeline from self-contaminating: if the LLM saw the patch, it might rationalize all changes as "related to the problem," defeating the purpose of scope analysis.

---

# Taxonomy: Axis 1 -- Task Contamination Labels

8 binary labels. Zero or more per task. `CLEAN` is mutually exclusive with all others.

| Label | What it detects | How |
|-------|----------------|-----|
| `APPROACH_LOCK` | Tests require a specific approach the problem doesn't determine | Circular deps: test -> UNRELATED hunk |
| `WIDE_TESTS` | Tests verify undescribed behavior | OFF_TOPIC assertions, UNRELATED tests |
| `TEST_MUTATION` | Pre-existing test silently modified | MODIFIED test with misaligned changes |
| `SCOPE_CREEP` | Gold patch has behavioral changes beyond scope | UNRELATED hunks with behavioral code |
| `UNCLEAR_SPEC` | Problem statement too ambiguous | Ambiguity score >= 0.4 |
| `HIDDEN_CONTEXT` | Essential info only in hints text | Self-referential phrase detection |
| `WEAK_COVERAGE` | Tests don't fully cover stated criteria | Acceptance criteria without coverage |
| `CLEAN` | No contamination | All signals negative |

### Severity rules

| Severity | Rule |
|----------|------|
| <span class="severe">SEVERE</span> | `APPROACH_LOCK` **OR** (`WIDE_TESTS` + `SCOPE_CREEP`) |
| <span class="moderate">MODERATE</span> | `TEST_MUTATION` **OR** `WIDE_TESTS` alone |
| <span class="minor">MINOR</span> | Any other single label |
| <span class="clean">CLEAN</span> | No labels |

---

# Taxonomy: Axis 2 -- Agent Trajectory Labels

One label per agent-task pair. Classifies agent behavior, not task quality.

### Passed labels

| Label | Signal |
|-------|--------|
| `agent_passed_genuine` | Progressive exploration, hypothesis formation, iterative debugging |
| `agent_passed_leak` | Jumped directly to answer; patch matches gold too closely |
| `agent_passed_package_leak` | Installed newer package, copied fix from site-packages |
| `agent_passed_test_aware` | Referenced F2P test names before discovering them |
| `agent_passed_trained_hack` | Applied memorized template without task reasoning |

### Failed labels

| Label | Signal |
|-------|--------|
| `agent_failed_completed_intent` | Correct fix for stated problem, fails F2P tests (contamination victim) |
| `agent_failed_no_intent` | Did not solve the problem (genuine skill gap) |

### 3-tier detection
1. **Heuristic**: gold patch similarity, pip installs, test references
2. **LLM**: full trajectory analysis with heuristic context
3. **Cross-agent**: identical patches across agents = leakage

---

# SWE-bench Pro Results (v5, 731 tasks)

Pipeline v5 incorporates `requirements` + `interface` fields for precise scope analysis.

| Severity | Count | Percentage |
|----------|------:|:----------:|
| <span class="severe">SEVERE</span> | 98 | 13.4% |
| <span class="moderate">MODERATE</span> | 54 | 7.4% |
| <span class="minor">MINOR</span> | 449 | 61.4% |
| <span class="clean">CLEAN</span> | 130 | 17.8% |

### Label distribution

| Label | Count | % of tasks |
|-------|------:|:----------:|
| `weak_coverage` | 526 | 71.9% |
| `scope_creep` | 174 | 23.8% |
| `clean` | 130 | 17.8% |
| `wide_tests` | 98 | 13.4% |
| `approach_lock` | 84 | 11.5% |
| `test_mutation` | 31 | 4.2% |
| `unclear_spec` | 22 | 3.0% |

### Interpretation

Most contamination is MINOR (`weak_coverage`) -- requirements go slightly beyond the problem statement but agents aren't penalized. **13.4% SEVERE** represents genuine contamination where agents are unfairly blocked.

---

# Contamination Penalty: Does It Actually Hurt Agents?

Cross-referenced top agent resolution status (730 instances) with v5 contamination severity:

### By severity level

| Severity | Tasks | Resolved | Resolve Rate | vs CLEAN |
|----------|------:|--------:|:------------:|:--------:|
| <span class="clean">CLEAN</span> | 130 | 56 | 43.1% | -- |
| <span class="minor">MINOR</span> | 448 | 211 | 47.1% | +4.0pp |
| <span class="moderate">MODERATE</span> | 54 | 17 | 31.5% | **-11.6pp** |
| <span class="severe">SEVERE</span> | 98 | 35 | 35.7% | **-7.4pp** |

### By contamination label

| Label | Instances | Resolve Rate | vs clean |
|-------|----------:|:------------:|:--------:|
| clean | 130 | 43.1% | (baseline) |
| weak_coverage | 526 | 44.5% | +1.4pp |
| scope_creep | 174 | 47.1% | +4.0pp |
| approach_lock | 84 | 35.7% | -7.4pp |
| test_mutation | 31 | 29.0% | **-14.0pp** |
| wide_tests | 98 | 28.6% | **-14.5pp** |
| unclear_spec | 22 | 27.3% | **-15.8pp** |

---

# The Penalty Is in the Tests, Not the Patch

<span class="stat">-14.5pp</span> penalty for `wide_tests` (p < 0.05, statistically significant)

### Key insight

`scope_creep` alone causes **no penalty** -- agents can pass with a narrower correct fix if the tests don't enforce the extra scope.

The penalty comes from **test-level contamination**: agents cannot pass F2P tests that enforce behavior never specified in the problem statement.

### SEVERE tasks with vs without `wide_tests`

| Category | Tasks | Resolve Rate |
|----------|------:|:------------:|
| SEVERE with `wide_tests` | 44 | **25.0%** |
| SEVERE without `wide_tests` | 54 | 44.4% |
| `approach_lock` + `wide_tests` | 30 | **20.0%** |

This aligns with OpenAI's finding that **test design flaws** are the primary source of unfair failures. Agents can work around scope expansion but cannot pass tests that enforce unrequired behavior.

---

# Label Combination Patterns (SEVERE)

The penalty concentrates in multi-label combinations:

| Label Combination | Tasks | Resolve Rate |
|---|---:|:---:|
| approach_lock + scope_creep (no wide_tests) | 43 | 46.5% |
| approach_lock + wide_tests | 8 | **12.5%** |
| approach_lock + scope_creep + wide_tests | 11 | **18.2%** |
| scope_creep + wide_tests + test_mutation | 6 | 33.3% |

### Interpretation

- **Single-label SEVERE** (approach_lock + scope_creep, no tests): resolve rate comparable to CLEAN (46.5% vs 43.1%)
- **Multi-label with wide_tests**: resolve rates drop to 12-20%
- The interaction between approach_lock and wide_tests is multiplicative, not additive

`approach_lock` alone represents potential unfairness. When combined with `wide_tests`, it becomes **confirmed unfairness** -- the tests actively block correct solutions.

---

# Smoking Gun: navidrome/navidrome -- GetNowPlaying

**Instance:** `instance_navidrome__navidrome-97434...`
**Severity:** <span class="severe">SEVERE</span> | **Labels:** `approach_lock`, `scope_creep`

### The problem says:
> Fix GetNowPlaying so multiple concurrent plays are preserved instead of being overwritten.

### What the gold patch also does:
Changes `PlayerId` from `int` to `string`, rewrites scrobbler internals -- **unrequired by problem or requirements**

### Agent trajectory:
1. Correctly implemented `FindMatch`, `UserAgent` field, `Register` logic, DB migration
2. Did NOT touch scrobbler code or PlayerId (correctly -- problem doesn't mention these)
3. **Failed** `TestCore` because it exercises the unrequired scrobbler changes

**Classification:** `agent_failed_completed_intent`
**V4 severity:** CLEAN (false negative) | **V5 severity:** SEVERE (correct)

---

# Smoking Gun: flipt-io/flipt -- Snapshot Cache

**Instance:** `flipt-io__flipt-86906...`
**Severity:** <span class="severe">SEVERE</span> | **Labels:** `approach_lock`, `wide_tests`, `test_mutation`, `scope_creep`

### The problem says:
> Snapshot cache does not allow controlled deletion of references.

### What the F2P tests actually validate:
CSRF secure flag configuration -- **zero tests validate cache deletion**

```
Gold patch:  38 hunks | 0 REQUIRED | 26 ANCILLARY | 12 UNRELATED
F2P tests:   23 tests | 18 ALIGNED to patch | 5 UNRELATED to problem
                                               0 test the stated problem
```

### Agent trajectory:
Agent correctly implemented `Delete()` method with proper cache eviction. Failed because all F2P tests validate CSRF configuration. The only way to pass: memorize the gold patch.

> Full analysis: `case_studies/smoking_gun_flipt_snapshot_cache.md`

---

# Smoking Gun: ansible/ansible -- iptables

**Severity:** <span class="severe">SEVERE</span> | **Labels:** `wide_tests`, `test_mutation`, `approach_lock`

### Pattern: `TEST_MUTATION`

Pre-existing tests were **modified** -- not added -- to include `run_command.call_count` assertions. These assertions enforce a specific internal implementation detail (how many times the module calls `run_command`), which:

1. Is not mentioned in the problem statement
2. Is not required by any specification
3. Rejects any correct solution that uses a different number of internal calls

The modification of **existing** tests makes this especially insidious: the tests look like legitimate regression tests, but the PR author silently changed their assertions.

> Full analysis: `case_studies/smoking_gun_ansible_iptables.md`

---

# v4 to v5: The Pipeline Fix

### The problem with v4

Pipeline v4 only parsed `problem_statement`. SWE-bench Pro withholds `requirements` and `interface` from agents but provides them for evaluation.

Without these fields, the pipeline saw many gold patches as "exceeding scope" when the full specification actually justified the changes.

### v4 severity distribution (inflated false positives)

| Severity | v4 Count | v5 Count | Change |
|----------|--------:|--------:|:------:|
| SEVERE | 215+ | 98 | -54% |
| MODERATE | -- | 54 | -- |
| MINOR | -- | 449 | -- |
| CLEAN | -- | 130 | -- |

### v4 -> v5 severity migration

**76% of v4 SEVERE instances dropped severity** when the pipeline gained access to the full task specification. The remaining 98 SEVERE instances are confirmed genuine contamination.

### What changed in the code

- `TaskRecord`: added `requirements`, `interface` fields + `full_problem_context` property
- `scope_analyzer.py`: intent extraction now includes requirements/interface
- `dual_taxonomy.py`: classifier considers all three fields as complete specification
- `test_analyzer.py`: uses `full_problem_context` for test matching
- `trajectory/analyzer.py`: uses `full_problem_context` for trajectory context

---

# Cross-Benchmark Comparison

|  | SWE-bench Verified | SWE-bench Pro (v5) |
|--|-------------------:|:-------------------|
| **Total tasks** | 500 | 731 |
| **Languages** | Python only | Python, JS, Go, Java, Rust, TS, Ruby |
| **Pipeline version** | v3 | v5 (with requirements/interface) |
| **SEVERE** | 105 (21.0%) | 98 (13.4%) |
| **MODERATE** | 85 (17.0%) | 54 (7.4%) |
| **MINOR** | 78 (15.6%) | 449 (61.4%) |
| **CLEAN** | 232 (46.4%) | 130 (17.8%) |
| **MOD+SEV** | 190 (38.0%) | 152 (20.8%) |

### Interpretation

SWE-bench Pro has a **lower SEVERE rate** than Verified (13.4% vs 21.0%) -- contrary to v4 analysis which showed inflated rates. Pro's `requirements`/`interface` fields make scope determination more precise, and the Pro curation process appears to have removed some of the worst contamination cases.

However, Pro has **much more MINOR contamination** (61.4%) due to its multi-language, larger-commit nature. Most of this is `weak_coverage` (requirements slightly beyond problem statement) which does not meaningfully penalize agents.

---

# Ecosystem Positioning

### Three layers of SWE-bench integrity analysis

```
Layer 3: Agent Runtime Monitoring
   │  OpenAI's GPT-5.4-powered trajectory monitor
   │  Detects: circumventing restrictions, deception, reward hacking
   │  (complementary to our work)
   │
Layer 2: Benchmark Design Audit             <── bench-cleanser
   │  Task-level contamination detection
   │  Detects: narrow/wide tests, scope expansion, test mutations
   │  Per-assertion traceability, automated at scale
   │
Layer 1: Training Data Contamination
      The SWE-Bench Illusion (arxiv)
      Detects: model memorization of gold patches, benchmark answers
      (our Axis 2 trajectory analysis covers this)
```

### Why bench-cleanser is uniquely positioned

1. **OpenAI deprecated SWE-bench Verified** and recommends Pro. We've analyzed Pro.
2. **OpenAI's manual audit** covered 138 tasks. We cover 731 automatically.
3. **The arxiv paper** identified memorization. Our Axis 2 detects it in agent trajectories.
4. **No one else** provides per-assertion, per-hunk contamination traceability at scale.
5. **Quantified impact**: we've proven the -14.5pp penalty with statistical significance.

---

# Recommendations

### For benchmark maintainers

1. **Publish contamination labels** per task (we provide the data)
2. **Exclude SEVERE tasks** from leaderboard scoring, or report with/without
3. **Targeted remediation by label:**
   - `APPROACH_LOCK`: Accept alternative valid solutions
   - `WIDE_TESTS`: Remove OFF_TOPIC assertions
   - `TEST_MUTATION`: Revert silent test modifications
   - `SCOPE_CREEP`: Scope gold patches to stated problems
4. **Parse `requirements`/`interface`** when auditing Pro tasks

### For agent developers

5. **Report contamination-adjusted scores**: CLEAN-only resolve rates alongside headline numbers
6. **Trajectory audit** resolve results: investigate SEVERE resolves for training leakage
7. **Use `agent_failed_completed_intent`** to identify unfair failures vs skill gaps

### For the research community

8. **Standardize contamination reporting** alongside benchmark scores
9. **Adopt the narrow/wide test framework** (OpenAI + bench-cleanser consensus terminology)
10. **Build fresh benchmarks** with contamination-aware design (privately authored, per OpenAI's recommendation)

---

# Technical Specifications

### Pipeline performance
- **SWE-bench Pro (731 tasks)**: ~3 hours with 5 concurrent workers
- **LLM calls per task**: 3-6 (intent + patch + test + classifier)
- **Cache hit rate**: ~95% on resume runs

### Model configuration
- **Primary model**: gpt-5.4-pro-20260305 (Azure OpenAI)
- **Reasoning effort**: high
- **Max tokens**: 65,536 per response
- **Trajectory context**: 500k chars (full agent transcript)

### Accuracy
- Heuristic + LLM two-pass design catches both obvious and subtle contamination
- Cross-reference analysis (deterministic) provides structural evidence
- Information barrier prevents LLM self-contamination
- v4->v5 migration validated: 76% false positive reduction with full context

### Multi-language support
Python, Go, JavaScript, TypeScript, Java, Rust, Ruby -- test parsing, assertion extraction, and cross-reference detection

---

# Resources

- **Repository**: `github.com/v-liaozhu/bench-cleanser`
- **Output**: `output_pro_v5/` (Pro v5), `output_v3/` (Verified)
- **Case Studies**: `case_studies/` (smoking guns + 25 Pro SEVERE deep dives)
- **This Deck**: `slides/bench_cleanser_full_findings.md`

### Key numbers

| Metric | Value |
|--------|-------|
| Total tasks analyzed | 1,231 |
| SWE-bench Pro SEVERE rate (v5) | 13.4% |
| SWE-bench Verified SEVERE rate | 21.0% |
| `wide_tests` resolve penalty | -14.5pp (p<0.05) |
| SEVERE+wide_tests resolve rate | 25.0% |
| v4->v5 false positive reduction | 76% |
| Pipeline stages | 6 |
| Task contamination labels | 8 |
| Agent trajectory labels | 8 |
| Languages supported | 7 |

### References
- OpenAI, "Why we no longer evaluate SWE-bench Verified" (2026)
- OpenAI, "How we monitor internal coding agents for misalignment" (2026)
- Li et al., "The SWE-Bench Illusion" (arxiv, 2025)
