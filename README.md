<p align="center">
  <strong>bench-cleanser</strong><br>
  <em>Automated Contamination Detection for SWE-bench Evaluation Benchmarks</em>
</p>

<p align="center">
  <a href="#key-findings">Findings</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="#taxonomy">Taxonomy</a> &bull;
  <a href="#ecosystem">Ecosystem</a> &bull;
  <a href="#case-studies">Case Studies</a> &bull;
  <a href="#usage">Usage</a>
</p>

---

## What is bench-cleanser?

bench-cleanser is a multi-stage analysis pipeline that audits SWE-bench tasks for evaluation fairness. It identifies cases where gold patches or fail-to-pass (F2P) tests exceed the problem description -- producing evaluation criteria that penalize agents for correctly solving the *described* problem rather than for genuine engineering failures.

The tool operates across two taxonomic axes:
- **Axis 1 -- Task Contamination** (8 binary labels): classifies *how* a task's evaluation criteria diverge from its problem statement
- **Axis 2 -- Agent Trajectory** (8 labels): classifies *how* an agent behaved on a task (genuine solve, memorization, leakage)

Together, these axes separate **benchmark design problems** from **agent capability gaps** and **training data leakage** -- the three confounded signals in raw SWE-bench scores.

---

## Why This Matters

> *"We found that 59.4% of the audited problems have flawed test cases that reject functionally correct submissions"*
> -- OpenAI, ["Why we no longer evaluate SWE-bench Verified"](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/) (2026)

OpenAI identified two categories of test flaws:
- **Narrow test cases** (35.5%): enforce specific implementation details, rejecting correct alternatives
- **Wide test cases** (18.8%): check additional functionality not specified in the problem description

bench-cleanser provides the automated framework to detect these flaws at scale. Our taxonomy maps directly to OpenAI's categories:

| OpenAI Category | bench-cleanser Labels | Detection Method |
|---|---|---|
| **Narrow test cases** | `APPROACH_LOCK` | Cross-reference analysis: F2P tests exercise UNRELATED patch hunks |
| **Wide test cases** | `WIDE_TESTS` | Per-assertion verdict: OFF_TOPIC assertions beyond acceptance criteria |
| **Modified test flaws** | `TEST_MUTATION` | Pre/post-patch diff: modified tests with misaligned changes |
| **Gold patch scope expansion** | `SCOPE_CREEP` | Per-hunk classification: UNRELATED behavioral hunks |
| **Training contamination** | `agent_passed_leak`, `agent_passed_trained_hack` | Trajectory analysis: gold patch similarity, memorized patterns |

Where OpenAI's audit was a one-time manual review of 138 tasks, bench-cleanser runs this analysis **automatically on every task** with full traceability from individual assertions to contamination labels.

---

## Key Findings

### SWE-bench Pro (731 tasks) -- Pipeline v5

v5 incorporates SWE-bench Pro's `requirements` and `interface` fields (evaluation-only context withheld from agents), enabling precise scope analysis.

| Severity | Count | Percentage | Description |
|----------|------:|:----------:|-------------|
| **SEVERE** | 98 | 13.4% | Approach-locked tests or combined wide tests + scope creep |
| **MODERATE** | 54 | 7.4% | Test mutation edits or standalone wide tests |
| **MINOR** | 449 | 61.4% | Scope creep alone or specification ambiguity |
| **CLEAN** | 130 | 17.8% | No contamination signals detected |

### SWE-bench Verified (500 tasks) -- Pipeline v3

| Severity | Count | Percentage |
|----------|------:|:----------:|
| **SEVERE** | 105 | 21.0% |
| **MODERATE** | 85 | 17.0% |
| **MINOR** | 78 | 15.6% |
| **CLEAN** | 232 | 46.4% |

### Contamination Penalty: Does It Actually Hurt Agents?

Cross-referencing a top agent's resolution status across 730 SWE-bench Pro instances with v5 contamination severity:

```
Severity     Tasks   Resolved   Failed   Resolve Rate   vs CLEAN
──────────   ─────   ────────   ──────   ────────────   ────────
CLEAN          130         56       74        43.1%        ---
MINOR          448        211      237        47.1%      +4.0pp
MODERATE        54         17       37        31.5%     -11.6pp
SEVERE          98         35       63        35.7%      -7.4pp
─────────────────────────────────────────────────────────────────
OVERALL        730        319      411        43.7%
```

The penalty concentrates in **test-related contamination**:

```
Label            Instances   Resolve Rate   vs clean baseline
───────────────  ─────────   ────────────   ─────────────────
clean                  130        43.1%     (baseline)
weak_coverage              526        44.5%     +1.4pp
scope_creep           174        47.1%     +4.0pp
approach_lock           84        35.7%     -7.4pp
test_mutation             31        29.0%     -14.0pp
wide_tests            98        28.6%     -14.5pp  (p<0.05)
unclear_spec            22        27.3%     -15.8pp
```

**Key insight**: `scope_creep` alone causes **no penalty** (agents can pass with a narrower correct fix). The penalty comes from **test-level contamination** (`wide_tests`, `test_mutation`) -- agents cannot pass F2P tests that enforce behavior never specified in the problem. This aligns with OpenAI's finding that test design flaws, not patch complexity, are the primary source of unfair failures.

Among SEVERE tasks, those **with** `wide_tests` resolve at 25.0% vs 44.4% **without** -- the combination `approach_lock + wide_tests` drops to 12.5-20%.

---

## Architecture

bench-cleanser processes each SWE-bench task through six analysis stages. The pipeline enforces a strict **information barrier**: the intent extraction stage never sees the gold patch or test patch, preventing the LLM from reverse-engineering the solution.

```
                    ┌─────────────────────────────┐
                    │     SWE-bench Dataset        │
                    │  (problem_statement, patch,  │
                    │   test_patch, fail_to_pass,  │
                    │   requirements, interface)   │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
              1     │          PARSE               │  Deterministic
                    │  Extract structured hunks    │  diff parsing
                    │  from gold patch + test      │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
             1.5    │     CODE VISITATION          │  Git clone +
                    │  Clone repo at base_commit   │  AST extraction
                    │  Extract full function/test  │  (multi-language)
                    │  source via Python AST       │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                                       │
┌─────────────▼───────────────┐         ┌─────────────▼───────────────┐
│          INTENT              │         │     STRUCTURAL DIFF         │
│  Extract acceptance criteria │   2     │  AST-level changed block    │  3
│  + problem decomposition     │         │  + test block extraction    │
│  from problem statement ONLY │  LLM    │                             │
│  ██ BLIND to gold patch ██   │         │  Call graph, import map,    │
└─────────────┬───────────────┘         │  tested function resolution │
              │                         └─────────────┬───────────────┘
              │                                       │
              └───────────────────┬───────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                                       │
┌─────────────▼───────────────┐         ┌─────────────▼───────────────┐
│      PATCH MATCHING          │         │       TEST MATCHING         │
│  Classify each gold patch    │  4A     │  Classify each F2P test     │  4B
│  hunk against intent:        │         │  against intent:            │
│  REQUIRED / ANCILLARY /      │  LLM    │  ALIGNED / TANGENTIAL /     │  LLM
│  UNRELATED                   │         │  UNRELATED                  │
│                              │         │  Per-assertion: ON_TOPIC /  │
│  Uses structural diff +      │         │  OFF_TOPIC                  │
│  call graph context          │         │  Modified test detection    │
└─────────────┬───────────────┘         └─────────────┬───────────────┘
              │                                       │
              └───────────────────┬───────────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │   CROSS-REFERENCE ANALYSIS   │  Deterministic
                    │  Detect circular deps        │
                    │  between UNRELATED hunks     │
                    │  and F2P tests via call graph │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
              5     │     CLASSIFICATION           │  Heuristic rules
                    │  8-label dual taxonomy       │  + LLM refinement
                    │  Bucket-based severity        │
                    │  Heuristic → LLM pipeline    │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │         OUTPUT               │
                    │  JSON reports, summary CSV,  │
                    │  deep dives, MARP slides     │
                    └─────────────────────────────┘
```

### Stage Details

**Stage 1 -- Parse.** Deterministic unified diff parsing. Extracts structured patch hunks and test hunks. Matches F2P test IDs to their corresponding diff hunks. Detects whether each test is `NEW` (added by the PR) or `MODIFIED` (pre-existing test with changes). Supports Python, Go, JavaScript/TypeScript, Java, Rust, and Ruby.

**Stage 1.5 -- Code Visitation.** Clones the target repository at `base_commit`. Uses Python AST analysis to extract full function/test source code. For each F2P test hunk: resolves imports, identifies tested functions (including whether each is modified by the gold patch), builds call target maps, and extracts structured assertion data.

**Stage 2 -- Intent Extraction.** An LLM reads *only* the problem statement, requirements, and interface (never the gold patch or test patch) and extracts: core requirement, behavioral contract, acceptance criteria, out-of-scope items, ambiguity score, and a problem decomposition. For SWE-bench Pro, the `requirements` and `interface` fields provide the full evaluation-only specification that agents never see.

**Stage 3 -- Structural Diff.** Deterministic AST-level analysis of the gold patch. Identifies changed blocks and test blocks. Resolves import paths and builds a call graph mapping tests to the functions they exercise.

**Stage 4A -- Patch Matching.** Each gold patch hunk classified against extracted intent as `REQUIRED` (directly addresses problem), `ANCILLARY` (supportive, no new behavior), or `UNRELATED` (behavioral change beyond scope).

**Stage 4B -- Test Matching.** Each F2P test classified as `ALIGNED`, `TANGENTIAL`, or `UNRELATED`. Each individual assertion further classified as `ON_TOPIC` or `OFF_TOPIC`. For modified tests, the LLM assesses whether modifications align with the problem statement.

**Cross-Reference Analysis.** Deterministic detection of circular dependencies: cases where an F2P test exercises functions from an UNRELATED patch hunk. This means the test cannot pass without implementing out-of-scope changes -- a strong `APPROACH_LOCK` signal.

**Stage 5 -- Classification.** Heuristic pre-classifier fires candidate labels from binary signals. These candidates, with full per-hunk and per-test evidence, are passed to an LLM for refinement. The LLM can confirm, adjust confidence, or override candidates.

---

## Taxonomy

### Axis 1: Task Contamination Labels

Eight binary labels. A task can have zero or more. If any contamination label is present, `CLEAN` is excluded.

| Label | Definition | OpenAI Equivalent |
|-------|-----------|-------------------|
| `APPROACH_LOCK` | F2P tests require a specific implementation approach the problem doesn't determine. A correct-but-different solution would fail. | Narrow test cases |
| `WIDE_TESTS` | F2P tests verify behavior not described in the problem statement. | Wide test cases |
| `TEST_MUTATION` | A pre-existing test was modified to assert on new behavior. The test existed before the PR, making it look legitimate, but assertions were silently changed. | (not separately categorized) |
| `SCOPE_CREEP` | Gold patch contains behavioral code changes beyond problem scope. New features, unrelated refactoring, scope expansion. | (not separately categorized) |
| `UNCLEAR_SPEC` | Problem statement is too ambiguous or actively misleading to determine the correct solution. | Miscellaneous issues |
| `HIDDEN_CONTEXT` | Essential solution information exists only in hints text, not in the problem statement. | (not applicable to Pro) |
| `WEAK_COVERAGE` | F2P tests don't fully cover stated acceptance criteria. A partial fix can pass. | (benchmark quality, not fairness) |
| `CLEAN` | No contamination detected. Mutually exclusive with all others. | -- |

### Severity Rules

Severity is determined by **which labels are present** -- no arithmetic, no weights, no thresholds.

| Severity | Trigger |
|----------|---------|
| **SEVERE** | `APPROACH_LOCK` present, **OR** both `WIDE_TESTS` and `SCOPE_CREEP` present |
| **MODERATE** | `TEST_MUTATION` present, **OR** `WIDE_TESTS` alone |
| **MINOR** | Any other single label |
| **CLEAN** | No contamination labels |

### Axis 2: Agent Trajectory Labels

Per-agent classification of how the agent behaved on a task.

**Passed labels** (agent resolved):

| Label | Description |
|-------|-------------|
| `agent_passed_genuine` | Legitimate problem-solving with progressive exploration |
| `agent_passed_leak` | Patch matches gold too closely; jumped directly to answer |
| `agent_passed_package_leak` | Installed newer package via pip and copied fix |
| `agent_passed_test_aware` | Referenced F2P test names/values before discovering them |
| `agent_passed_trained_hack` | Applied memorized template without genuine reasoning |

**Failed labels** (agent did not resolve):

| Label | Description |
|-------|-------------|
| `agent_failed_completed_intent` | Patch correctly addresses the described problem but fails F2P tests due to task contamination |
| `agent_failed_no_intent` | Did not solve the problem; genuine skill gap |

---

## Ecosystem

### Where bench-cleanser fits

Three distinct contamination vectors affect SWE-bench scores. Each requires a different detection approach:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SWE-bench Score = f(A, B, C)                     │
├─────────────────────┬──────────────────────┬────────────────────────┤
│  A. Agent Skill     │ B. Benchmark Design  │ C. Training Leakage   │
│                     │                      │                       │
│  Genuine capability │ Tests/patch exceed   │ Model memorized gold  │
│  to solve software  │ problem description  │ patch or PR details   │
│  engineering tasks  │                      │                       │
│                     │  ┌────────────────┐  │                       │
│                     │  │ bench-cleanser │  │                       │
│                     │  │  Axis 1        │  │                       │
│                     │  └────────────────┘  │                       │
│                     │                      │  ┌──────────────────┐ │
│                     │                      │  │ bench-cleanser   │ │
│                     │                      │  │  Axis 2          │ │
│                     │                      │  └──────────────────┘ │
├─────────────────────┴──────────────────────┴────────────────────────┤
│  Related Work                                                       │
│  • OpenAI SWE-bench Verified audit (manual, 138 tasks)             │
│  • The SWE-Bench Illusion (arxiv: model memorization analysis)     │
│  • OpenAI agent misalignment monitoring (runtime behavior)         │
└─────────────────────────────────────────────────────────────────────┘
```

| Approach | Scope | Method | Ours |
|----------|-------|--------|------|
| OpenAI SWE-bench Verified audit | 138 tasks, manual | 6 expert reviewers per task | Automated, all tasks, per-assertion traceability |
| The SWE-Bench Illusion (arxiv) | Model memorization | Training data overlap analysis | Our Axis 2 trajectory analysis covers this |
| OpenAI agent monitoring | Runtime behavior | GPT-5.4 monitor on agent trajectories | Complementary: we audit the benchmark, they audit the agent |
| **bench-cleanser** | **All tasks, automated** | **6-stage pipeline, dual taxonomy** | **Task design + agent behavior, full traceability** |

### Key differentiators

1. **Automated and scalable.** OpenAI's manual audit required 6 expert reviewers per task across 138 tasks. bench-cleanser processes 731 tasks automatically with per-assertion granularity.
2. **Full traceability.** Every contamination label traces back to specific assertions, patch hunks, and cross-reference dependencies. This enables targeted remediation.
3. **Dual-axis separation.** By independently classifying task contamination (Axis 1) and agent behavior (Axis 2), we disentangle benchmark design problems from training data leakage -- the two confounded signals OpenAI identified.
4. **SWE-bench Pro support.** We parse the `requirements` and `interface` fields (evaluation-only context withheld from agents) to distinguish scope expansion from intended behavior.
5. **Quantified impact.** We've computed the contamination penalty per label, showing that `wide_tests` causes a statistically significant -14.5pp resolve rate penalty (p<0.05).

---

## Case Studies

### Smoking Gun: navidrome/navidrome -- GetNowPlaying (`SEVERE`)

**The problem says:** Fix player matching so multiple concurrent plays are preserved.

**What the gold patch also does:** Changes `PlayerId` from `int` to `string` and rewrites scrobbler internals (unrequired).

**What happened to a top agent:**
- Agent correctly implemented `FindMatch`, `UserAgent` field, `Register` logic, and DB migration
- Agent did NOT modify scrobbler code or PlayerId type (correctly -- problem doesn't mention these)
- Agent **failed** `TestCore` because TestCore exercises the unrequired scrobbler changes

**Classification:** `agent_failed_completed_intent` -- the agent solved the stated problem but failed due to approach_lock.

This instance was **CLEAN in v4** (false negative) and correctly **SEVERE in v5** after adding requirements/interface parsing.

> Full analysis: [`case_studies/smoking_gun_navidrome_nowplaying.md`](case_studies/smoking_gun_navidrome_nowplaying.md)

### Smoking Gun: flipt-io/flipt -- Snapshot Cache (`SEVERE`)

**The problem says:** Snapshot cache does not allow controlled deletion of references.

**What the gold patch actually does:** Adds CSRF secure flag, config schema changes, HTTP middleware -- zero F2P tests validate cache deletion.

**38 hunks**: 0 REQUIRED, 26 ANCILLARY, 12 UNRELATED. **23 tests**: 18 ALIGNED to patch, 5 UNRELATED. **Zero F2P tests test the stated problem.**

**Agent result:** Agent correctly implemented cache deletion. Failed because all F2P tests validate CSRF configuration.

> Full analysis: [`case_studies/smoking_gun_flipt_snapshot_cache.md`](case_studies/smoking_gun_flipt_snapshot_cache.md)

### Smoking Gun: ansible/ansible -- iptables (`SEVERE`)

**The problem says:** Fix iptables module to handle specific parameters correctly.

**What the gold patch does:** Modifies pre-existing tests to add `run_command.call_count` assertions that enforce a specific internal implementation.

**Pattern:** `TEST_MUTATION` -- test modifications make tests look legitimate while actually testing undescribed behavior.

> Full analysis: [`case_studies/smoking_gun_ansible_iptables.md`](case_studies/smoking_gun_ansible_iptables.md)

### Additional case studies

- [`case_studies/smoking_gun_openlibrary_wikidata.md`](case_studies/smoking_gun_openlibrary_wikidata.md)
- [`case_studies/smoking_gun_vuls_macos.md`](case_studies/smoking_gun_vuls_macos.md)
- [`case_studies/smoking_gun_flipt_agent_trajectory.md`](case_studies/smoking_gun_flipt_agent_trajectory.md)
- [`case_studies/pro_severe/`](case_studies/pro_severe/) -- 25 SEVERE case studies from SWE-bench Pro

---

## v4 to v5: The Pipeline Fix

Pipeline v4 only parsed `problem_statement` and `hints_text` from SWE-bench Pro tasks. SWE-bench Pro has three evaluation-only fields withheld from agents:

| Field | Visibility | Content |
|---|---|---|
| `problem_statement` | Agent sees this | Narrow bug report or feature request |
| `requirements` | Withheld from agent | Detailed implementation requirements |
| `interface` | Withheld from agent | New public interface specifications |

Without `requirements` and `interface`, the pipeline incorrectly flagged many tasks as SEVERE because the gold patch appeared to exceed the narrow `problem_statement` -- when in fact the full specification (which agents don't see) justified the scope.

### v4 to v5 severity migration

```
                  v5 CLEAN   v5 MINOR   v5 MODERATE   v5 SEVERE
v4 SEVERE           17         54           12            98
v4 MODERATE          9         43           --            --
v4 MINOR            --        350           --            --
v4 CLEAN            --         --           --            --
```

76% of v4 SEVERE instances dropped severity when full context was available. The remaining 98 SEVERE instances are **genuine contamination** -- confirmed by both full-context analysis and agent trajectory validation.

---

## Installation

### Requirements

- Python 3.12+
- Azure OpenAI API access (or compatible OpenAI endpoint)

### Setup

```bash
git clone https://github.com/v-liaozhu/bench-cleanser.git
cd bench-cleanser
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Optional: `docent-python` for Docent agent trajectory loading.

---

## Configuration

Create a `config.yaml` in the project root:

```yaml
llm:
  base_url: "https://your-openai-endpoint.azure-api.net/"
  api_version: "2025-04-01-preview"
  model: "gpt-5.4-pro-20260305"
  max_tokens: 65536
  reasoning_effort: "high"
  max_concurrent_requests: 10
  retry_attempts: 7
  retry_delay_seconds: 5.0

pipeline:
  concurrency: 5
  cache_dir: ".cache/llm_responses"
  output_dir: "output"

code_visitation:
  repo_cache_dir: ".cache/repos"
  clone_timeout_seconds: 120
  max_source_context_lines: 200
```

| Key | Default | Description |
|-----|---------|-------------|
| `llm.model` | `gpt-5.4-pro-20260305` | Model deployment name |
| `llm.reasoning_effort` | `high` | Classification quality over latency |
| `pipeline.concurrency` | `5` | Parallel task processing |
| `code_visitation.enabled` | `true` | Git clone + AST extraction |

---

## Usage

### Run the analysis pipeline

```bash
# SWE-bench Pro (recommended)
python run_pipeline.py --dataset pro --config config.yaml

# SWE-bench Verified
python run_pipeline.py --dataset verified

# Single task
python run_pipeline.py --instance-id django__django-11964

# Resume interrupted run
python run_pipeline.py --dataset pro --resume
```

### Generate reports

```bash
# Deep dive case studies (SEVERE by default)
python run_deep_dive.py --reports-dir output_pro_v5/reports

# Specific severity or instances
python run_deep_dive.py --reports-dir output_pro_v5/reports --severity MODERATE
python run_deep_dive.py --reports-dir output_pro_v5/reports --instance-ids <id1> <id2>

# MARP slide deck
python run_slides.py --reports-dir output_pro_v5/reports --output slides/findings.md
npx @marp-team/marp-cli slides/findings.md --pdf
```

### Agent trajectory analysis

```bash
# Full trajectory analysis with LLM
python run_trajectory_analysis.py \
  --reports-dir output_pro_v5/reports \
  --trajectory-source trajectory_data/ \
  --config config.yaml

# Load from Docent collection
python run_trajectory_analysis.py \
  --reports-dir output_pro_v5/reports \
  --trajectory-source 032fb63d-4992-4bfc-911d-3b7dafcb931f \
  --docent-api-key dk_... \
  --model-filter "Gemini 2.5 Pro Preview" \
  --output trajectory_analysis.md

# Load from HuggingFace
python run_trajectory_analysis.py \
  --reports-dir output_pro_v5/reports \
  --trajectory-source SWE-bench-Live/SWE-agent-trajectories \
  --hf-split train

# Heuristic-only (no LLM, faster)
python run_trajectory_analysis.py \
  --reports-dir output_pro_v5/reports \
  --trajectory-source trajectory_data/ \
  --no-llm
```

### Monitor a running pipeline

```bash
python monitor_pipeline.py --output-dir output_pro_v5 --total 731
```

---

## Output Format

### Per-task JSON report

```json
{
  "instance_id": "instance_navidrome__navidrome-97434...",
  "severity": "SEVERE",
  "intent": {
    "core_requirement": "Fix GetNowPlaying to show all active plays",
    "acceptance_criteria": ["..."],
    "ambiguity_score": 0.15
  },
  "scope_creep": {
    "total_hunks": 20,
    "required_count": 8,
    "unrelated_count": 4,
    "has_excess": true,
    "hunks": [{ "verdict": "unrelated", "confidence": 0.91, "reasoning": "..." }]
  },
  "wide_test": {
    "total_tests": 1,
    "on_topic_assertions": 12,
    "off_topic_assertions": 3,
    "has_excess": true,
    "tests": [{ "intent_match": "tangential", "assertions": [...] }]
  },
  "task_labels": [
    { "label": "approach_lock", "confidence": 0.84, "evidence": ["..."] },
    { "label": "scope_creep", "confidence": 0.93, "evidence": ["..."] }
  ]
}
```

### Directory layout

```
output_pro_v5/
├── reports/                     # One JSON file per task (731 files)
│   ├── instance_navidrome__navidrome-97434....json
│   └── ...
├── summary.csv                  # Per-task severity, labels, key metrics
└── summary_stats.json           # Aggregated statistics
```

---

## Project Structure

```
bench-cleanser/
│
├── run_pipeline.py                    # Main analysis pipeline
├── run_deep_dive.py                   # Per-case deep dive reports
├── run_slides.py                      # MARP slide deck generation
├── run_trajectory_analysis.py         # Agent trajectory classification
├── monitor_pipeline.py                # Live pipeline monitoring dashboard
├── config.yaml                        # Pipeline configuration
├── requirements.txt                   # Python dependencies
│
├── bench_cleanser/                    # Core library
│   ├── models.py                      # Data models, enums, serialization
│   ├── pipeline.py                    # Pipeline orchestrator (Stages 1-5)
│   ├── llm_client.py                  # Azure OpenAI client
│   ├── cache.py                       # LLM response caching
│   ├── data_loader.py                 # HuggingFace dataset loader
│   ├── repo_manager.py               # Git repository management
│   ├── code_visitor.py                # Stage 1.5: AST source extraction
│   ├── static_analysis.py            # Import resolution, call graph
│   ├── deep_dive.py                   # Case study markdown generation
│   ├── presentation.py               # MARP slide generation
│   │
│   ├── analysis/                      # Analysis stages
│   │   ├── scope_analyzer.py          # Stage 2: intent extraction
│   │   ├── structural_diff.py        # Stage 3: AST structural diff
│   │   ├── patch_analyzer.py          # Stage 4A: patch hunk classification
│   │   ├── test_analyzer.py           # Stage 4B: test + assertion classification
│   │   └── cross_ref.py              # Cross-reference dependency detection
│   │
│   ├── classification/                # Taxonomy and scoring
│   │   ├── dual_taxonomy.py           # 8-label taxonomy, severity rules
│   │   └── scorer.py                  # Final report building
│   │
│   └── trajectory/                    # Agent trajectory analysis
│       ├── analyzer.py                # Orchestrator
│       ├── classifier.py             # 3-tier classifier (heuristic/LLM/cross-agent)
│       ├── loader.py                  # Data loading (JSONL, JSON, HuggingFace, Docent)
│       └── models.py                  # Trajectory data structures
│
├── tests/                             # Unit tests
├── case_studies/                      # Smoking gun analyses + 25 Pro SEVERE cases
├── slides/                            # MARP presentation decks
├── output_v3/                         # SWE-bench Verified run (500 reports)
├── output_pro_v5/                     # SWE-bench Pro v5 run (731 reports)
└── scripts/                           # Analysis utilities
```

---

## Development

### Running tests

```bash
python -m pytest tests/ -v
```

### Adding a new contamination label

1. Add enum value to `TaskContaminationLabel` in `models.py`
2. Add label definition to `LABEL_DEFINITIONS` in `dual_taxonomy.py`
3. Add heuristic detection rule in `_heuristic_labels()` in `dual_taxonomy.py`
4. Update `compute_task_severity()` bucket rules if applicable
5. Add label to `TASK_CLASSIFIER_SYSTEM_PROMPT` in `dual_taxonomy.py`

### LLM prompt architecture

| Prompt | File | Stage | Information Barrier |
|--------|------|-------|---------------------|
| Intent extraction | `scope_analyzer.py` | 2 | BLIND to gold patch |
| Patch classification | `patch_analyzer.py` | 4A | Sees intent + patch |
| Test classification | `test_analyzer.py` | 4B | Sees intent + tests |
| Task classifier | `dual_taxonomy.py` | 5 | Sees all signals |
| Agent classifier | `dual_taxonomy.py` | 5 | Sees trajectory |
| Trajectory analysis | `trajectory/classifier.py` | -- | Sees full trajectory |

---

## References

- OpenAI. ["Why we no longer evaluate SWE-bench Verified."](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/) 2026.
- OpenAI. ["How we monitor internal coding agents for misalignment."](https://openai.com/index/how-we-monitor-internal-coding-agents-misalignment/) 2026.
- Li et al. ["The SWE-Bench Illusion."](https://arxiv.org/html/2506.12286v3) arXiv, 2025.
- Jimenez et al. ["SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"](https://arxiv.org/abs/2310.06770) ICLR 2024.

---

## License

Internal research tool. Not licensed for external distribution.
