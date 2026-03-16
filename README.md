# bench-cleanser

Automated contamination detection for SWE-bench benchmarks. Identifies tasks where gold patches or fail-to-pass (F2P) tests exceed the problem description, producing unfair evaluation criteria for software engineering agents. Features a **dual taxonomy** classification system (v3), LLM-primary trajectory validation, and weighted severity scoring for systematic diagnosis.

## Problem

SWE-bench Verified (500 tasks) and SWE-bench Pro are the primary benchmarks for evaluating software engineering agents. However, some tasks have **contaminated evaluation criteria** that penalize agents for correctly solving the *described* problem:

- **Excess patches**: Gold patches include refactoring, style changes, or features not described in the problem statement
- **Excess tests**: F2P tests assert on behavior not described in the problem (off-topic assertions)
- **Vague specifications**: Problem statements too ambiguous to determine a unique correct solution
- **Approach mismatches**: Gold patch takes a fundamentally different strategy than the problem suggests
- **Deferred requirements**: Tests enforce features the problem explicitly defers

Agents that correctly solve the *described* problem may fail these tasks because evaluation criteria test *undescribed* behavior. bench-cleanser quantifies this contamination at per-hunk and per-assertion granularity, classifies contamination using a structured multi-label taxonomy, and validates agent trajectories for leakage.

## Architecture

### v3 Pipeline (Recommended): Dual Taxonomy

The v3 pipeline extends v2 with a structured **dual taxonomy** system that classifies contamination along two orthogonal axes:

- **Axis 1 (Task Contamination):** What's wrong with the benchmark task itself — multi-label, agent-independent
- **Axis 2 (Agent Trajectory):** How a specific agent behaved on the task — single primary label per agent-task pair

```
Stage 1:   PARSE              Extract diffs from gold patch + test patch
Stage 1.5: CODE VISITATION     Clone repo, extract full test/function source (optional)
Stage 2:   INTENT              Extract ground-truth intent from problem statement (LLM)
Stage 3:   STRUCTURAL DIFF     AST-level function/class change analysis
Stage 4:   INTENT MATCHING     Classify hunks + tests against intent (LLM)
Stage 5:   DUAL TAXONOMY       Multi-label task classification + weighted severity scoring
```

Stage 5 replaces v2's combined-score formula with a weighted label system. Each contamination label has a defined weight reflecting its impact on evaluation fairness. Severity is computed from the assigned labels rather than from raw signal arithmetic.

### v2 Pipeline: Intent-Matching (Backward Compatible)

The v2 pipeline remains available and is preserved for backward compatibility:

```
Stage 1-4: (same as v3)
Stage 5:   TRIAGE & REPORT     4-category scoring + actionable recommendations
Stage 6:   ROOT CAUSE          LLM-based root-cause classification (for non-CLEAN tasks)
```

---

## Dual Taxonomy (v3)

### Axis 1: Task Contamination Labels

17 labels in 5 groups. Multiple labels can co-occur per task. Group E labels are exclusive with Groups A–D.

#### Group A — Test Contamination

| Label | Display Name | Definition | Weight |
|-------|-------------|------------|--------|
| `mistest_overtest` | Overtest | F2P tests verify behavior/features NOT in problem statement. Detection: OFF_TOPIC assertion ratio >= 0.3; UNRELATED test verdicts. | 0.7 |
| `mistest_undertest` | Undertest | F2P tests don't fully cover stated acceptance criteria; a partial fix can pass. Less severe — makes task easier, not harder. | 0.2 |
| `mistest_customtest` | Custom Test | Tests assert on implementation details so specific to the gold patch that other valid solutions would fail. Tests lock in one approach rather than testing the behavioral contract. | 0.9 |
| `mistest_sneaky_modification` | Sneaky Modification | Pre-existing test modified to assert on NEW undescribed behavior. The test already existed so it appears legitimate, but the PR author silently altered it. Detection: `is_modified=True` + `modification_aligned=False`. | 0.8 |
| `mistest_deferred_requirement` | Deferred Requirement | Tests require features the problem explicitly defers ("I have yet to add X", "future work", "TODO"). An agent told NOT to implement X will fail tests that require X. | 0.9 |

#### Group B — Patch Contamination

| Label | Display Name | Definition | Weight |
|-------|-------------|------------|--------|
| `mispatch_overpatch` | Overpatch | Gold patch includes changes beyond problem scope: new features, unrelated refactoring, functionality additions not described. | 0.5 |
| `mispatch_underpatch` | Underpatch | Gold patch doesn't fully address stated requirements. Some acceptance criteria remain unfixed yet F2P tests still pass. | 0.2 |
| `mispatch_approach_mismatch` | Approach Mismatch | Gold patch takes a fundamentally different strategy than the problem suggests. Problem describes fix X, gold patch implements fix Y. An agent following the problem would fail. | **1.0** |
| `mispatch_ancillary_bundling` | Ancillary Bundling | Cleanup/refactoring bundled alongside the fix: whitespace, imports, docstrings, dead code removal. Not needed to solve the problem. | 0.3 |

#### Group C — Description Contamination

| Label | Display Name | Definition | Weight |
|-------|-------------|------------|--------|
| `desc_misleading` | Misleading Description | Problem statement actively directs toward a wrong approach: suggests a specific fix that is not what the gold patch does. | 0.7 |
| `desc_incomplete` | Incomplete Description | Problem missing key information: no reproduction steps, no affected file, no root cause. Multiple valid interpretations possible. | 0.4 |
| `desc_hidden_in_hints` | Hidden in Hints | Essential solution info exists only in hints text: function names, root cause diagnosis, or maintainer design decisions not in the problem statement. | 0.4 |
| `desc_self_referential` | Self-Referential | Problem references its own patch/tests to define behavior: "see the test case of the patch", "attached PR". | 0.5 |

#### Group D — Structural Contamination

| Label | Display Name | Definition | Weight |
|-------|-------------|------------|--------|
| `scope_expansion` | Scope Expansion | Fix modifies parent class or broader API than described. Problem describes a specific-case bug but patch changes a base class or public API affecting additional code paths. | 0.6 |
| `circular_test_patch_dependency` | Circular Dependency | F2P tests require out-of-scope patch changes to pass. Agent solving only the described problem would have tests fail due to missing unrelated changes. | 0.85 |

#### Group E — Clean

| Label | Display Name | Definition | Weight |
|-------|-------------|------------|--------|
| `clean` | Clean Task | No contamination. Problem is clear, gold patch addresses exactly the stated problem, tests verify the described behavioral contract. | 0.0 |
| `hard_but_clean` | Hard But Clean | Genuinely difficult task but fairly evaluated. Difficulty is inherent (domain knowledge, multi-file, complex debugging), not from contamination. | 0.0 |

#### Label Co-occurrence

- Multiple A–D labels can co-occur on the same task
- Group E labels are mutually exclusive with A–D labels
- Common pairs: `mispatch_approach_mismatch` + `mistest_customtest`, `desc_incomplete` + `desc_hidden_in_hints`, `scope_expansion` + `mistest_overtest`

### Axis 2: Agent Trajectory Labels

8 labels, single primary label per agent-task pair.

| Label | Display Name | Definition | Integrity |
|-------|-------------|------------|-----------|
| `agent_passed_genuine` | Genuine Solution | Agent derived solution through legitimate problem-solving with progressive exploration | 1.0 |
| `agent_passed_leak` | Gold Patch Leak | Patch matches gold too closely (similarity >= 0.90); jumped to correct file without search | 0.0 |
| `agent_passed_package_leak` | Package Leak | Agent pip-installed newer version and copied fix from site-packages | 0.1 |
| `agent_passed_test_aware` | Test-Aware | Agent referenced F2P test names/values before discovering them through exploration | 0.2 |
| `agent_passed_trained_hack` | Trained Hack | Agent applies memorized template without genuine problem-specific reasoning | 0.5 |
| `agent_failed_completed_intent` | Failed but Solved | Agent's patch addresses the real problem but fails F2P tests due to task contamination | N/A (confirms Axis 1) |
| `agent_failed_no_intent` | Failed Without Solving | Agent didn't solve the problem; failure reflects skill gap, not unfairness | N/A |
| `agent_unknown` | Unknown | Insufficient trajectory data to classify | N/A |

**Cross-axis diagnostic:** `agent_failed_completed_intent` + `mispatch_approach_mismatch` = strongest contamination confirmation. The agent solved the described problem but failed because the gold patch uses a different approach.

### Severity Scoring

v3 severity is computed from weighted label confidences:

$$\text{severity}_\text{task} = 1 - \prod_{i \in \text{labels}} (1 - w_i \cdot c_i)$$

where $w_i$ = label weight, $c_i$ = detection confidence (0.0–1.0).

**Key property:** Weak signals cannot compound to SEVERE. `desc_incomplete` alone (w=0.4) can never reach SEVERE even at confidence 1.0. Only high-weight labels can drive SEVERE:

| Weight | Labels |
|--------|--------|
| **1.0** | `mispatch_approach_mismatch` |
| **0.9** | `mistest_customtest`, `mistest_deferred_requirement` |
| **0.85** | `circular_test_patch_dependency` |
| **0.8** | `mistest_sneaky_modification` |
| **0.7** | `mistest_overtest`, `desc_misleading` |
| **0.6** | `scope_expansion` |
| **0.5** | `mispatch_overpatch`, `desc_self_referential` |
| **0.4** | `desc_incomplete`, `desc_hidden_in_hints` |
| **0.3** | `mispatch_ancillary_bundling` |
| **0.2** | `mistest_undertest`, `mispatch_underpatch` |
| **0.0** | `clean`, `hard_but_clean` |

Severity thresholds (configurable):
- **CLEAN**: severity < 0.15
- **MINOR**: 0.15 <= severity < 0.4
- **MODERATE**: 0.4 <= severity < 0.7
- **SEVERE**: severity >= 0.7

### Classification Granularity (Shared Across v2/v3)

Each gold patch hunk is classified as:
- **REQUIRED** — Directly implements the described fix
- **ANCILLARY** — Supports the fix but isn't described (imports, infrastructure)
- **UNRELATED** — Changes behavior not described in the problem

Each F2P test is classified as:
- **ALIGNED** — Test targets the described problem
- **TANGENTIAL** — Test partially targets the problem
- **UNRELATED** — Test doesn't target the described problem

Each test assertion is classified as:
- **ON_TOPIC** — Assertion checks behavior described in the problem
- **OFF_TOPIC** — Assertion checks behavior NOT described in the problem

---

## v2 Taxonomy (Backward Compatible)

### 4 Verdict Categories

| Category | Description | Recommended Action |
|----------|-------------|-------------------|
| **EXCESS_PATCH** | Gold patch includes changes beyond what the task describes | Filter UNRELATED hunks from evaluation |
| **EXCESS_TEST** | F2P tests verify behavior beyond the task description | Exclude OFF_TOPIC assertions from pass/fail |
| **VAGUE_SPEC** | Problem statement is ambiguous; multiple valid solutions exist | Interpret results with caution |
| **CLEAN** | No contamination detected | No action needed |

### 5 Root-Cause Categories

| Root Cause | Description | v3 Equivalent |
|------------|-------------|---------------|
| **APPROACH_MISMATCH** | Gold patch solves the problem via a different approach than described | `mispatch_approach_mismatch` |
| **DEFERRED_REQUIREMENT** | Tests/patch encode decisions made during code review, not in the issue | `mistest_deferred_requirement` |
| **SCOPE_EXPANSION** | Gold patch includes refactoring or features beyond the described fix | `scope_expansion` + `mispatch_overpatch` |
| **IMPLICIT_CONSENSUS** | Patch reflects undocumented team consensus not in the problem statement | `desc_hidden_in_hints` |
| **INFRASTRUCTURE_LEAK** | Solution derived from package installation or external data, not reasoning | `agent_passed_package_leak` (Axis 2) |

### v2 Scoring Formula

```
excess_patch_score = (unrelated_hunks + 0.5 * ancillary_hunks) / total_hunks
excess_test_score  = (off_topic + 0.3 * tangential_equiv + unrelated_equiv) / total_assertions
combined_score     = 1 - (1 - excess_patch) * (1 - excess_test) * (1 - vague_spec)
```

---

## Installation

```bash
git clone <repo-url>
cd bench-cleanser
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
# source .venv/bin/activate

pip install -r requirements.txt
```

### Requirements

- **Python 3.12+**
- **Azure OpenAI access** (CloudGPT) with Azure CLI authentication (`az login`)
- **rich** (optional) — enhanced terminal progress display during batch runs

### Dependencies

| Package | Purpose |
|---------|---------|
| `datasets` | HuggingFace datasets for loading SWE-bench |
| `openai` | Azure OpenAI API client |
| `pyyaml` | Configuration file parsing |
| `tqdm` | Progress bars (fallback when rich not installed) |
| `azure-identity` | Azure AD authentication |
| `azure-identity-broker` | Token brokering for Azure |
| `msal` | Microsoft Authentication Library |
| `requests` | HTTP client |

## Configuration

Edit `config.yaml` to match your environment:

```yaml
llm:
  base_url: "https://cloudgpt-openai.azure-api.net/"
  api_version: "2025-04-01-preview"
  model: "gpt-5.2-20251211"
  max_tokens: 16384
  reasoning_effort: "high"        # Controls model reasoning depth
  max_concurrent_requests: 10
  retry_attempts: 7               # Exponential backoff retries on transient errors
  retry_delay_seconds: 5.0        # Base delay between retries (capped at 60s)

pipeline:
  concurrency: 3                  # Parallel task processing
  cache_dir: ".cache/llm_responses"
  output_dir: "output"

thresholds:
  clean_max: 0.15
  minor_max: 0.4
  moderate_max: 0.7

code_visitation:
  enabled: true                   # Clone repos for full source context
  repo_cache_dir: ".cache/repos"
  clone_timeout_seconds: 120
  max_source_context_lines: 200
```

### Authentication

bench-cleanser authenticates to Azure OpenAI via Azure CLI:

```bash
az login
```

## Usage

### Contamination Pipeline

#### Full batch analysis (v3 pipeline — recommended)

```bash
python run_pipeline.py --v3 --dataset verified --max-tasks 500
```

#### Full batch analysis (v2 pipeline)

```bash
python run_pipeline.py --v2 --dataset verified --max-tasks 500
```

#### Single task analysis

```bash
python run_pipeline.py --v3 --instance-id django__django-15916
```

#### SWE-bench Pro

```bash
python run_pipeline.py --v3 --dataset pro --max-tasks 500
```

#### Resume from checkpoint

```bash
python run_pipeline.py --v3 --dataset verified --resume
```

#### v1 pipeline (legacy)

```bash
python run_pipeline.py --dataset verified --max-tasks 100
```

#### Pipeline CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--v3` | Use v3 dual taxonomy pipeline (recommended) | v1 |
| `--v2` | Use v2 intent-matching pipeline | v1 |
| `--config PATH` | Path to configuration YAML file | `config.yaml` |
| `--dataset {verified,pro,live,both}` | Which SWE-bench dataset(s) to analyze | `verified` |
| `--max-tasks N` | Maximum tasks per dataset | `500` |
| `--instance-id ID` | Analyze a single instance (overrides `--dataset`) | -- |
| `--output DIR` | Override output directory | from config |
| `--concurrency N` | Parallel task processing | from config |
| `--split SPLIT` | Dataset split for SWE-bench Live | -- |
| `--resume` | Resume from checkpoint — skip tasks with existing reports | off |
| `--no-resume` | Reprocess all tasks (default) | on |
| `-v, --verbose` | Enable DEBUG logging | off |

### Deep-Dive Reports

Auto-generate Case A–D style markdown reports from completed pipeline JSON:

```bash
python run_deep_dive.py --reports-dir output_v3/reports --severity SEVERE \
    --output case_studies/auto/deep_dive_auto.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `--reports-dir DIR` | Directory containing per-task JSON reports | required |
| `--severity {SEVERE,MODERATE,MINOR,CLEAN}` | Filter by severity level | `SEVERE` |
| `--instance-ids ID [ID ...]` | Specific instance IDs to include | all matching severity |
| `--output PATH` | Output markdown file path | `deep_dive.md` |
| `--config PATH` | Configuration YAML file | `config.yaml` |

Deep dives include: dataset record tables, verbatim problem statements, annotated gold patches, line-by-line assertion analysis, pipeline verdict breakdowns, dual taxonomy label assignments with evidence, independent LLM analysis, and cross-case synthesis.

### Trajectory Validation

Analyze agent trajectories for leakage patterns using LLM-primary classification:

```bash
python run_trajectory_analysis.py --reports-dir output_v3/reports \
    --trajectory-source huggingface --output trajectory_analysis.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `--reports-dir DIR` | Directory containing per-task JSON reports | required |
| `--trajectory-source {huggingface,local}` | Source of trajectory data | `huggingface` |
| `--output PATH` | Output markdown file path | `trajectory_analysis.md` |
| `--config PATH` | Configuration YAML file | `config.yaml` |
| `--no-llm` | Disable LLM classification (heuristic-only fallback) | LLM enabled |

The trajectory classifier uses a three-tier approach with **LLM as primary**:
1. **Heuristic signal extraction**: Patch similarity, pip install commands, test name references
2. **LLM analysis** (primary): Full trajectory context + heuristic signals analyzed by LLM for leakage classification with detailed reasoning
3. **Cross-agent comparison**: Identical patches across agents suggest gold patch leakage

Axis 2 labels: `agent_passed_genuine`, `agent_passed_leak`, `agent_passed_package_leak`, `agent_passed_test_aware`, `agent_passed_trained_hack`, `agent_failed_completed_intent`, `agent_failed_no_intent`, `agent_unknown`

### Slide Deck

Generate MARP markdown slides from pipeline results:

```bash
python run_slides.py --reports-dir output_v3/reports \
    --output slides/bench_cleanser_findings.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `--reports-dir DIR` | Directory containing per-task JSON reports | required |
| `--deep-dive PATH` | Deep-dive markdown to incorporate | -- |
| `--trajectory PATH` | Trajectory analysis markdown to incorporate | -- |
| `--output PATH` | Output MARP markdown file | `slides/findings.md` |

## Output

### Per-task JSON Report (v3)

Each analyzed task produces a JSON report in `<output_dir>/reports/`:

```json
{
  "instance_id": "django__django-15916",
  "severity": "MODERATE",
  "combined_score": 0.55,
  "task_labels": [
    {
      "label": "mistest_overtest",
      "confidence": 0.72,
      "evidence": ["3/6 OFF_TOPIC assertions", "1 UNRELATED test"],
      "reasoning": "F2P tests exercise inheritance behavior beyond the described feature"
    },
    {
      "label": "mispatch_ancillary_bundling",
      "confidence": 0.60,
      "evidence": ["2 ANCILLARY hunks (cleanup/infra)"],
      "reasoning": "Import reorganization bundled with the core fix"
    }
  ],
  "agent_labels": {
    "SWE-agent": {
      "label": "agent_passed_genuine",
      "confidence": 0.85,
      "evidence": ["Progressive exploration", "Solution derived from problem analysis"],
      "reasoning": "Agent followed logical debugging path"
    }
  },
  "intent": {
    "core_requirement": "Allow ModelForm Meta to specify formfield_callback",
    "behavioral_contract": "BEFORE: ... AFTER: ...",
    "acceptance_criteria": [
      "modelform_factory preserves base form's callback"
    ],
    "out_of_scope": "Inheritance behavior of factory-produced forms",
    "ambiguity_score": 0.3
  },
  "excess_patch": {
    "score": 0.0,
    "total_hunks": 1,
    "required": 1,
    "ancillary": 0,
    "unrelated": 0,
    "hunks": [
      {
        "hunk_index": 0,
        "file": "django/forms/models.py",
        "verdict": "REQUIRED",
        "confidence": 0.95,
        "reason": "Directly implements the described fix"
      }
    ]
  },
  "excess_test": {
    "score": 0.33,
    "total_tests": 1,
    "aligned": 0,
    "tangential": 1,
    "unrelated": 0,
    "total_assertions": 3,
    "on_topic": 2,
    "off_topic": 1,
    "has_modified_tests": false,
    "tests": [...]
  },
  "vague_spec": {
    "score": 0.3,
    "reasoning": "Mostly clear with minor edge cases undefined"
  },
  "root_causes": ["DEFERRED_REQUIREMENT"],
  "root_cause_reasoning": {
    "DEFERRED_REQUIREMENT": "Tests encode decisions made during code review..."
  },
  "recommendations": [
    "EXCESS_TEST: 1/3 assertions test behavior beyond problem scope."
  ]
}
```

### Summary CSV

Generated at `<output_dir>/summary.csv`.

**v3 columns:**
```
instance_id, severity, combined_score, excess_patch_score, excess_test_score,
vague_spec_score, patch_hunks_total, patch_required, patch_ancillary,
patch_unrelated, tests_total, tests_aligned, tests_tangential, tests_unrelated,
assertions_total, assertions_on_topic, assertions_off_topic,
has_modified_test, task_labels, primary_label, label_count,
root_causes, recommendations
```

The `task_labels` column uses semicolon-separated label names, `primary_label` is the highest weighted confidence label, and `label_count` is the total number of assigned labels.

**v2 columns** (backward compatible):
```
instance_id, severity, combined_score, excess_patch_score, excess_test_score,
vague_spec_score, ..., root_causes, recommendations
```

### Summary Statistics

Generated at `<output_dir>/summary_stats.json` with severity distribution, mean/median combined scores, per-category averages, root-cause distribution, and **label distribution** (v3: count per `TaskContaminationLabel`).

## Project Structure

```
bench_cleanser/
  __init__.py
  models.py                      # Data models, enums (v1 + v2 + v3 dual taxonomy)
  pipeline.py                    # Pipeline orchestrator (v1/v2/v3 batch/single)
  llm_client.py                  # Azure OpenAI client with retry and caching
  cache.py                       # Disk-based LLM response cache
  data_loader.py                 # SWE-bench dataset loading (Verified, Pro, Live)
  deep_dive.py                   # Auto-generate Case A-D style deep-dive reports
  presentation.py                # MARP slide deck generator
  repo_manager.py                # Git repo cloning and management
  code_visitor.py                # Source code extraction from cloned repos
  static_analysis.py             # Python AST: imports, calls, assertions
  analysis/
    scope_analyzer.py            # Stage 2: Intent extraction (LLM)
    structural_diff.py           # Stage 3: AST-level structural analysis
    patch_analyzer.py            # Stage 4A: Patch-intent matching (LLM)
    test_analyzer.py             # Stage 4B: Test-intent matching (LLM)
    cross_ref.py                 # Cross-reference analysis (v1)
  classification/
    scorer.py                    # Stage 5: Scoring and report building (v1/v2/v3)
    dual_taxonomy.py             # v3 dual taxonomy classifier (Axis 1 + Axis 2)
    taxonomy.py                  # Category/verdict definitions and thresholds
  parsing/
    patch_parser.py              # Unified diff parser (gold patch)
    test_parser.py               # Test patch parser + F2P matching
  trajectory/
    __init__.py
    models.py                    # Trajectory data models (LeakagePattern, AgentTrajectoryLabel)
    loader.py                    # Load trajectories from HuggingFace or local JSONL
    classifier.py                # Three-tier classifier (heuristic + LLM-primary + cross-agent)
    analyzer.py                  # Orchestrator: analyze, summarize, generate narratives
tests/
  test_scorer.py                 # Unit tests for scoring logic (v1/v2/v3)
run_pipeline.py                  # Pipeline CLI entry point
run_deep_dive.py                 # Deep-dive report CLI entry point
run_trajectory_analysis.py       # Trajectory validation CLI entry point
run_slides.py                    # MARP slide deck CLI entry point
config.yaml                      # Pipeline configuration
cloudgpt.py                      # Azure AD token provider
requirements.txt                 # Python dependencies
```

## Error Handling

bench-cleanser is designed to **fail loud** rather than produce incorrect results:

- **LLM failures**: All transient errors (HTTP 500, rate limits, timeouts, connection errors) are retried with exponential backoff (base delay 5s, capped at 60s, up to 7 attempts). Non-retryable errors propagate immediately.
- **No silent fallbacks**: If all LLM retries are exhausted, the pipeline raises `RuntimeError` rather than returning empty or degenerate results. Pipeline errors are surfaced as `SEVERE` reports with `PIPELINE_ERROR:` prefixes so they are visible in summary statistics.
- **SDK retry disabled**: The OpenAI SDK's built-in retry mechanism is disabled (`max_retries=0`) to prevent dual-layer retry storms. All retry logic is handled by bench-cleanser's own backoff implementation.
- **Caching**: Successful LLM responses are cached to disk. Subsequent runs reuse cached results, reducing API calls and enabling incremental reruns after transient failures.

## Testing

```bash
python -m pytest tests/ -v
```

## v1 vs v2 vs v3 Comparison

| Aspect | v1 (7-category) | v2 (4-verdict + root cause) | v3 (dual taxonomy) |
|--------|------------------|----------------------------|---------------------|
| **Task taxonomy** | 7 overlapping categories | 4 non-overlapping verdicts + 5 root causes | 17 multi-label task contamination labels (Axis 1) |
| **Agent taxonomy** | — | LeakagePattern (6 values) | 8 agent trajectory labels with integrity scores (Axis 2) |
| **Label categories** | OVERTEST, OVERPATCH, etc. | EXCESS_PATCH, EXCESS_TEST, VAGUE_SPEC, CLEAN | 5 groups: Test (A), Patch (B), Description (C), Structural (D), Clean (E) |
| **Root causes** | — | 5 categories | Absorbed into Axis 1 labels with defined weights |
| **Granularity** | Hunk-level | Hunk + assertion-level | Hunk + assertion-level + multi-label |
| **Ground truth** | Scope analysis | Intent extraction with acceptance criteria | Intent extraction + weighted label assignment |
| **Scoring** | Category confidence | `1 - (1-EP)(1-ET)(1-VS)` | $1 - \prod(1 - w_i \cdot c_i)$ per label |
| **Severity calibration** | Weak signals compound | Weak signals compound to SEVERE | Only high-weight labels (w >= 0.7) can drive SEVERE |
| **False positive rate** | High | ~10% precision at MODERATE | Reduced: `desc_incomplete` alone cannot reach SEVERE |
| **Output** | Category confidence scores | Actionable per-hunk/per-assertion verdicts + root causes | Multi-label task report + per-agent trajectory label |
| **Backward compat** | — | Preserved in v3 | Full v2 fields in `DualTaxonomyReport` |
| **Trajectory validation** | — | LLM-primary leakage classification | v3 Axis 2 labels (8 structured categories) |

---

## Case Studies: 4 High-Confidence SEVERE Contamination Cases

> **Pipeline:** bench-cleanser v2 (no-fallback mode), gpt-5.2-20251211 (Azure)
> **Dataset:** [`princeton-nlp/SWE-bench_Verified`](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified), test split
> **Purpose:** Exhaustive, assertion-level traceability for the 4 strongest SEVERE contamination signals

---

### Case A: `django__django-10999` — "The Regex That Solves a Different Problem"

**v3 Labels:** `mispatch_approach_mismatch` (1.0), `desc_misleading` (0.7)

#### A.1 HuggingFace Dataset Record

| Field | Value |
|---|---|
| **instance_id** | `django__django-10999` |
| **repo** | `django/django` |
| **base_commit** | `36300ef336e3f130a0dadc1143163ff3d23dc843` |
| **version** | `3.0` |
| **created_at** | `2019-02-16T07:44:50Z` |
| **difficulty** | `<15 min fix` |
| **environment_setup_commit** | `419a78300f7cd27611196e1e464d50fd0385ff27` |
| **FAIL_TO_PASS** | `["test_negative (utils_tests.test_dateparse.DurationParseTests)", "test_parse_postgresql_format (utils_tests.test_dateparse.DurationParseTests)"]` |
| **PASS_TO_PASS** | 10 tests covering `test_days`, `test_fractions_of_seconds`, `test_hours_minutes_seconds`, `test_iso_8601`, `test_minutes_seconds`, `test_parse_python_format`, `test_seconds`, etc. |
| **patch file** | `django/utils/dateparse.py` |
| **test_patch file** | `tests/utils_tests/test_dateparse.py` |

#### A.2 Verbatim Problem Statement

> **Fix parse_duration() for some negative durations**
>
> The https://docs.djangoproject.com/en/2.1/_modules/django/utils/dateparse/ defines:
>
> ```python
> standard_duration_re = re.compile(
>     r'^'
>     r'(?:(?P<days>-?\d+) (days?, )?)?'
>     r'((?:(?P<hours>-?\d+):)(?=\d+:\d+))?'
>     r'(?:(?P<minutes>-?\d+):)?'
>     r'(?P<seconds>-?\d+)'
>     r'(?:\.(?P<microseconds>\d{1,6})\d{0,6})?'
>     r'$'
> )
> ```
>
> that doesn't match to negative durations, because of the `<hours>` definition final (lookahead) part does not have `-?` in it. The following will work:
>
> `r'((?:(?P<hours>-?\d+):)(?=-?\d+:-?\d+))?'`
>
> (Thanks to Konstantin Senichev for finding the fix.)

**Key observation:** The reporter provides a *specific regex fix* — add `-?` to the lookahead, changing `(?=\d+:\d+)` to `(?=-?\d+:-?\d+)`. This is an explicit, concrete, character-level prescription.

#### A.3 Hints Text (from GitHub Discussion)

> *Please give an example valid that's not working. There are some tests for negative values.*
>
> *Right, this should have been fixed by #27699 which is included in 1.11.x.*
>
> *Example cases, can be discussed:*
> - `parse_duration('-00:01:01') => plus 61 seconds`, so it is not `-(00:01:01)` but `(-00):(+01):(+01)`
> - `parse_duration('00:-01:-01') => None`, leading zeros will prevent parsing
> - `parse_duration('-01:01') => minus 59 seconds`
> - `parse_duration('-01:-01') => minus 61 seconds`
>
> *The fix presented would allow the second line to be parsed (which would help with generated durations). And some instructions in the function/documentation/wiki would be useful, to clarify how the minus sign affects in duration.*
>
> *The fix from #27699 may not be entirely correct. I agree with your first and third examples. I'd expect a leading minus sign to negate the entire value so they would be minus 61 seconds. I think the second and fourth examples are invalid. I don't think a minus sign after a colon is valid.*
>
> *Thanks for the extra details. I agree with Tim that everything but a leading `-` seems like an invalid value that happened to work because of an inappropriate pattern as it was never tested.*

**Critical detail from hints:** The Django maintainers (Tim Graham) explicitly resolved the semantic debate: *"everything but a leading `-` seems like an invalid value."* This means the gold patch's approach (single leading sign) reflects the **maintainer decision** that was made during code review, NOT what was in the original problem statement.

#### A.4 Complete Gold Patch (with annotation)

```diff
diff --git a/django/utils/dateparse.py b/django/utils/dateparse.py
--- a/django/utils/dateparse.py
+++ b/django/utils/dateparse.py
@@ -29,9 +29,10 @@
 standard_duration_re = re.compile(
     r'^'
     r'(?:(?P<days>-?\d+) (days?, )?)?'
-    r'((?:(?P<hours>-?\d+):)(?=\d+:\d+))?'   # <- REMOVED: -? from hours, unchanged lookahead
-    r'(?:(?P<minutes>-?\d+):)?'               # <- REMOVED: -? from minutes
-    r'(?P<seconds>-?\d+)'                     # <- REMOVED: -? from seconds
+    r'(?P<sign>-?)'                           # <- ADDED: new sign group at front
+    r'((?:(?P<hours>\d+):)(?=\d+:\d+))?'      # <- hours no longer allows -?
+    r'(?:(?P<minutes>\d+):)?'                  # <- minutes no longer allows -?
+    r'(?P<seconds>\d+)'                        # <- seconds no longer allows -?
     r'(?:\.(?P<microseconds>\d{1,6})\d{0,6})?'
     r'$'
 )
```

The gold patch **does not** add `-?` to the lookahead as suggested. Instead, it:

1. **Introduces a new named group** `(?P<sign>-?)` at the front of the pattern
2. **Removes** all `-?` optionals from `hours`, `minutes`, and `seconds` groups
3. **Leaves the lookahead `(?=\d+:\d+)` unchanged** — the exact lookahead the reporter said was broken

This fundamentally changes the semantics: instead of allowing per-component negative signs (`-1:15:-30`), the grammar now enforces a single leading sign that applies to all components.

#### A.5 Complete Test Patch

```diff
diff --git a/tests/utils_tests/test_dateparse.py b/tests/utils_tests/test_dateparse.py
--- a/tests/utils_tests/test_dateparse.py
+++ b/tests/utils_tests/test_dateparse.py
@@ -113,9 +113,12 @@ def test_negative(self):
         test_values = (
             ('-4 15:30', timedelta(days=-4, minutes=15, seconds=30)),
             ('-172800', timedelta(days=-2)),
-            ('-15:30', timedelta(minutes=-15, seconds=30)),
-            ('-1:15:30', timedelta(hours=-1, minutes=15, seconds=30)),
+            ('-15:30', timedelta(minutes=-15, seconds=-30)),         # <- CHANGED expected value
+            ('-1:15:30', timedelta(hours=-1, minutes=-15, seconds=-30)),  # <- CHANGED expected value
             ('-30.1', timedelta(seconds=-30, milliseconds=-100)),
+            ('-00:01:01', timedelta(minutes=-1, seconds=-1)),        # <- ADDED new test case
+            ('-01:01', timedelta(seconds=-61)),                       # <- ADDED new test case
+            ('-01:-01', None),                                        # <- ADDED new test case (invalid)
         )
         for source, expected in test_values:
             with self.subTest(source=source):
```

**Changed expectations:**
- Old: `'-15:30'` -> `timedelta(minutes=-15, seconds=30)` (only minutes negative)
- New: `'-15:30'` -> `timedelta(minutes=-15, seconds=-30)` (both negative — sign applies to all)

This is the crux: the test patch **changes the expected behavior** of existing test cases to match the gold patch's sign-group approach.

#### A.6 Pipeline Verdict Detail

##### Intent Extraction (Stage 2)

| Field | Value |
|---|---|
| **core_requirement** | Update `parse_duration()`'s `standard_duration_re` so it matches negative durations with an hours component |
| **behavioral_contract** | BEFORE: `parse_duration()` fails for some negative durations because the hours lookahead only allows `\d+:\d+`. AFTER: those strings match via a lookahead that allows optional `-` signs |
| **acceptance_criteria** | (1) `standard_duration_re`'s hours-group lookahead allows optional minus signs in minutes:seconds, (2) `parse_duration()` successfully parses duration strings with negative components that were previously rejected |
| **out_of_scope** | No changes to ISO 8601 parsing, no changes to how timedelta values are computed/normalized, no documentation or unrelated refactoring |
| **ambiguity_score** | 0.3 |

##### Patch Verdict (Stage 4A)

| Hunk | File | Verdict | Confidence | Reasoning |
|---|---|---|---|---|
| 0 | `django/utils/dateparse.py` | **UNRELATED** | 0.92 | The problem explicitly requests adding `-?` to the lookahead. The gold patch instead introduces a new `(?P<sign>-?)` group and removes all per-component `-?` optionals. The lookahead is left unchanged. |

##### Scoring Breakdown

| Component | Score | Derivation |
|---|---|---|
| excess_patch | **1.000** | 1 UNRELATED / 1 total = 1.0 |
| excess_test | **0.000** | 0 off-topic / 1 total assertions |
| vague_spec | **0.300** | LLM assessment: mostly clear, minor edge cases |

$$\text{combined} = 1 - (1 - 1.0)(1 - 0.0)(1 - 0.3) = 1 - 0 = \mathbf{1.000}$$

#### A.7 Independent Deep Analysis

**Why the gold patch is different from the problem statement:**

The reporter's fix: `r'((?:(?P<hours>-?\d+):)(?=-?\d+:-?\d+))?'` — adds `-?` to the lookahead. This would allow patterns like `-1:-15:-30` to match, where each component independently has a sign.

The gold patch's fix: `r'(?P<sign>-?)((?:(?P<hours>\d+):)(?=\d+:\d+))?...'` — introduces a single leading sign. Under this grammar, `parse_duration('-1:15:30')` returns `timedelta(hours=-1, minutes=-15, seconds=-30)` (all components negated), whereas the reporter's fix would give `timedelta(hours=-1, minutes=15, seconds=30)`.

**Would an agent following the problem statement pass the tests?** Almost certainly NO. An agent implementing the described lookahead fix would produce different parsed values than the test expects.

**Contamination verdict: CONFIRMED — HIGH CONFIDENCE.**

---

### Case B: `astropy__astropy-13398` — "Tests Demand Refraction That the Spec Explicitly Defers"

**v3 Labels:** `mistest_deferred_requirement` (0.9), `mistest_overtest` (0.7), `mispatch_overpatch` (0.5), `mispatch_ancillary_bundling` (0.6)

#### B.1 HuggingFace Dataset Record

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-13398` |
| **repo** | `astropy/astropy` |
| **base_commit** | `6500928dc0e57be8f06d1162eacc3ba5e2eff692` |
| **version** | `5.0` |
| **created_at** | `2022-06-24T15:22:11Z` |
| **difficulty** | `1-4 hours` |
| **FAIL_TO_PASS** | `["test_itrs_topo_to_altaz_with_refraction", "test_itrs_topo_to_hadec_with_refraction", "test_cirs_itrs_topo", "test_itrs_straight_overhead"]` |
| **PASS_TO_PASS** | 68 tests in `test_intermediate_transformations.py` |
| **patch files** | `__init__.py`, `intermediate_rotation_transforms.py`, `itrs.py`, `itrs_observed_transforms.py` (new file) |

#### B.2 Verbatim Problem Statement (Key Excerpts)

> **A direct approach to ITRS to Observed transformations that stays within the ITRS.**
>
> We have experienced recurring issues raised by folks that want to observe satellites [...] I came up with a more direct approach.
>
> **"I have yet to add refraction, but I can do so if it is deemed important."**

This last sentence is the critical line for contamination analysis.

#### B.3 Gold Patch Summary

The gold patch is large (4 files, 8 hunks, ~250 lines added) and includes a new file `itrs_observed_transforms.py` (145 lines) that implements full refraction support via `erfa.refco()` — functionality explicitly deferred in the problem statement.

#### B.4 Test Analysis

| Test | ON_TOPIC | OFF_TOPIC |
|---|---|---|
| `test_itrs_topo_to_altaz_with_refraction` | 6 | 6 |
| `test_itrs_topo_to_hadec_with_refraction` | 6 | 6 |
| `test_cirs_itrs_topo` | 0 | 4 |
| `test_itrs_straight_overhead` | 3 | 0 |
| **Total** | **15** | **16** |

The smoking gun is the test names themselves: two F2P tests are literally named `*_with_refraction`. The problem statement says "I have yet to add refraction."

#### B.5 Scoring Breakdown

| Component | Score | Derivation |
|---|---|---|
| excess_patch | 0.5625 | (1 UNRELATED + 0.5 x 7 ANCILLARY) / 8 |
| excess_test | 0.7661 | 16 OFF_TOPIC / 31 total + UNRELATED test penalty |
| vague_spec | 0.5500 | Moderately ambiguous |

$$\text{combined} = 1 - (1 - 0.5625)(1 - 0.7661)(1 - 0.55) = \mathbf{0.954}$$

**Contamination verdict: CONFIRMED — HIGH CONFIDENCE.**

---

### Case C: `astropy__astropy-14182` — "Asked for a Writer Fix, Tested the Reader"

**v3 Labels:** `mistest_overtest` (0.9), `mistest_customtest` (0.7), `scope_expansion` (0.6)

#### C.1 HuggingFace Dataset Record

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-14182` |
| **repo** | `astropy/astropy` |
| **FAIL_TO_PASS** | `["astropy/io/ascii/tests/test_rst.py::test_rst_with_header_rows"]` |
| **hints_text** | (empty) |

#### C.2 Verbatim Problem Statement

> **Please support header rows in RestructuredText output**
>
> ```python
> >>> tbl.write(sys.stdout, format="ascii.rst", header_rows=["name", "unit"])
> ```
> Currently raises: `TypeError: RST.__init__() got an unexpected keyword argument 'header_rows'`

The request is unambiguous: make the **writer** accept `header_rows`. No mention of reading RST.

#### C.3 Gold Patch

The gold patch implements **writer** support AND **reader** support (a `read()` method with dynamic `start_line`). The reader functionality was never requested.

#### C.4 Test Analysis

| # | Assertion | Verdict | Reason |
|---|---|---|---|
| 0 | `assert tbl["wave"].unit == u.nm` | **OFF_TOPIC** | Tests RST **reader** unit parsing |
| 1 | `assert tbl["response"].unit == u.ct` | **OFF_TOPIC** | Reader unit parsing |
| 2 | `assert tbl["wave"].dtype == np.float64` | **OFF_TOPIC** | Reader dtype parsing |
| 3 | `assert tbl["response"].dtype == np.float32` | **OFF_TOPIC** | Reader dtype parsing |
| 4 | `assert tbl["ints"].dtype == np.int8` | **OFF_TOPIC** | Reader dtype parsing |
| 5 | `assert out.getvalue().splitlines() == lines` | **ON_TOPIC** | Tests writer output |

**5/6 assertions test the reader.** A 100% correct implementation of the stated problem would score 0% — the test errors on the reader call before reaching the writer assertion.

#### C.5 Scoring Breakdown

$$\text{combined} = 1 - (1 - 0.333)(1 - 0.833)(1 - 0.4) = \mathbf{0.933}$$

**Contamination verdict: CONFIRMED — HIGH CONFIDENCE.** The most clear-cut contamination case.

---

### Case D: `astropy__astropy-14539` — "One-Character Fix, Nine Extra Assertions"

**v3 Labels:** `mistest_overtest` (0.8), `mistest_sneaky_modification` (0.7)

#### D.1 HuggingFace Dataset Record

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-14539` |
| **repo** | `astropy/astropy` |
| **FAIL_TO_PASS** | `["test_identical_tables", "test_different_table_data"]` |

#### D.2 Verbatim Problem Statement

> **`io.fits.FITSDiff` may sometimes report differences between identical files**
>
> This may be caused by improper handling of VLAs (variable-length arrays).

#### D.3 Gold Patch

One-line fix: `"P" in col.format` -> `"P" in col.format or "Q" in col.format`. Perfectly aligned with the problem.

#### D.4 Test Analysis

| Test | Verdict | ON_TOPIC | OFF_TOPIC |
|---|---|---|---|
| `test_identical_tables` | ALIGNED (modified) | 2 | 0 |
| `test_different_table_data` (x3 instances) | TANGENTIAL | 0 | 9 |
| **Total** | | **2** | **9** |

The 9 OFF_TOPIC assertions in `test_different_table_data` test Q-format diff detection (comparing genuinely different tables), not the false-positive bug described in the problem.

#### D.5 Scoring Breakdown

$$\text{combined} = 1 - (1 - 0.0)(1 - 0.818)(1 - 0.3) = \mathbf{0.873}$$

**Contamination verdict: CONFIRMED — MEDIUM-HIGH CONFIDENCE.**

---

### Cross-Case Synthesis

#### Contamination Pattern Taxonomy (v3 Labels)

| Pattern | Cases | v3 Labels |
|---|---|---|
| **Approach Mismatch** | A | `mispatch_approach_mismatch`, `desc_misleading` |
| **Deferred Requirement** | B | `mistest_deferred_requirement`, `mistest_overtest` |
| **Feature Split** | C | `mistest_overtest`, `mistest_customtest`, `scope_expansion` |
| **Sneaky Test Modification** | D | `mistest_overtest`, `mistest_sneaky_modification` |

#### Impact on SWE-bench Evaluation

1. **An agent that perfectly solves the stated problem can score 0%.** Case C demonstrates this: a correct writer-only implementation fails because the test errors on the reader assertion first.

2. **Knowledge of the gold patch is required.** In Case A, the problem provides a specific fix. The gold patch implements a different fix decided during code review. An agent would need to "know" the maintainer discussion.

3. **Background knowledge substitutes for the problem statement.** Cases B and D require domain knowledge not mentioned in the problem description.

#### Scoring Formula Validation

| Case | EP | ET | VS | v2 Combined | v3 Severity (projected) |
|---|---|---|---|---|---|
| A | 1.000 | 0.000 | 0.300 | **1.000** | SEVERE |
| B | 0.5625 | 0.7661 | 0.550 | **0.954** | SEVERE |
| C | 0.333 | 0.833 | 0.400 | **0.933** | SEVERE |
| D | 0.000 | 0.818 | 0.300 | **0.873** | SEVERE |
