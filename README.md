# bench-cleanser

**Automated contamination detection for SWE-bench evaluation benchmarks.**

bench-cleanser is a multi-stage analysis pipeline that systematically audits SWE-bench tasks for evaluation fairness. It identifies cases where gold patches or fail-to-pass (F2P) tests exceed the problem description, producing evaluation criteria that penalize agents for correctly solving the *described* problem rather than for genuine engineering failures.

The tool operates across two taxonomic axes: **Task Contamination** (8 binary labels classifying *how* a task is unfair) and **Agent Trajectory** (8 labels classifying *how* an agent behaved on a task). Together, these axes distinguish between agent skill gaps and benchmark evaluation failures.

---

## Table of Contents

- [Motivation](#motivation)
- [Key Findings](#key-findings)
- [Architecture](#architecture)
- [Taxonomy](#taxonomy)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Output Format](#output-format)
- [Project Structure](#project-structure)
- [Development](#development)
- [License](#license)

---

## Motivation

SWE-bench Verified (500 tasks) and SWE-bench Pro are the primary benchmarks for evaluating AI software engineering agents. For a benchmark to produce meaningful leaderboard rankings, each task must satisfy a basic fairness contract: **the evaluation criteria (F2P tests) should test only the behavior described in the problem statement**.

In practice, many tasks violate this contract:

- A bug report describes a `TypeError` in a single method, but the F2P tests also assert on three unrelated edge cases that were never mentioned.
- The gold patch refactors a base class API that the problem statement never discusses, and the F2P tests require that specific refactoring to pass.
- A pre-existing test is silently modified to change its expected output, making the test appear legitimate while actually testing undescribed behavior.

An agent that reads the problem statement, correctly identifies and fixes the bug, and produces a valid solution will **fail** these tasks — not because of a skill gap, but because the evaluation criteria test behavior that was never specified. bench-cleanser identifies and classifies these cases.

---

## Key Findings

Results from a full analysis of SWE-bench Verified (500 tasks):

| Severity | Count | Percentage | Description |
|----------|------:|:----------:|-------------|
| **SEVERE** | 105 | 21.0% | Tasks with approach-locked tests or combined excess tests + excess patch |
| **MODERATE** | 85 | 17.0% | Tasks with sneaky test edits or standalone excess tests |
| **MINOR** | 78 | 15.6% | Tasks with excess patch alone or specification ambiguity |
| **CLEAN** | 232 | 46.4% | No contamination signals detected |

Over **half** of SWE-bench Verified tasks (53.6%) exhibit at least one contamination signal. Among them, 38% are MODERATE or SEVERE — meaning the evaluation criteria materially diverge from the problem description. Detailed case studies, forensic breakdowns, and presentation slides are included in this repository under `case_studies/` and `slides/`.

---

## Architecture

bench-cleanser processes each SWE-bench task through six analysis stages. Four of these stages use LLM-based classification; two are deterministic. The pipeline enforces a strict information barrier: the intent extraction stage (Stage 2) never sees the gold patch or test patch, preventing the LLM from reverse-engineering the solution.

```
                    ┌─────────────────────────────┐
                    │     SWE-bench Dataset        │
                    │  (problem_statement, patch,  │
                    │   test_patch, fail_to_pass)  │
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
                    │  Extract full function/test  │
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
│  (blind to gold patch)       │         │  Call graph, import map,    │
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

**Stage 1 — Parse.** Deterministic unified diff parsing. Extracts structured patch hunks and test hunks from the gold patch and test patch. Matches F2P test IDs to their corresponding diff hunks. Detects whether each test is `NEW` (added by the PR) or `MODIFIED` (pre-existing test with changes).

**Stage 1.5 — Code Visitation.** Clones the target repository at `base_commit` and uses Python AST analysis to extract full function/test source code. For each F2P test hunk, the pipeline resolves imports, identifies tested functions (including whether each is modified by the gold patch), builds call target maps, and extracts structured assertion data. This provides the code context that Stages 4A and 4B use for precise classification.

**Stage 2 — Intent Extraction.** An LLM reads *only* the problem statement (never the gold patch or test patch) and extracts: core requirement, behavioral contract, acceptance criteria (testable behaviors), out-of-scope items, and an ambiguity score. Additionally, the problem is decomposed into: the actual bug description, any reporter-suggested fix approach, legitimacy assessment, and mentioned code entities (files, functions, classes, variables, modules). This decomposition feeds the APPROACH_LOCK heuristic.

**Stage 3 — Structural Diff.** Deterministic AST-level analysis of the gold patch. Identifies changed blocks (functions, methods, classes) and test blocks. Resolves import paths and builds a call graph mapping tests to the functions they exercise. This structural context is provided to Stages 4A/4B alongside the LLM prompts.

**Stage 4A — Patch Matching.** Each gold patch hunk is classified against the extracted intent:
- `REQUIRED` — The hunk directly addresses the described problem.
- `ANCILLARY` — Supportive change (imports, whitespace, docstrings) that doesn't introduce new behavior.
- `UNRELATED` — Behavioral change beyond problem scope.

**Stage 4B — Test Matching.** Each F2P test is classified against the extracted intent:
- `ALIGNED` — Tests behavior described in the problem statement.
- `TANGENTIAL` — Tests related but not described behavior.
- `UNRELATED` — Tests behavior completely outside problem scope.

Each individual assertion within a test is further classified as `ON_TOPIC` or `OFF_TOPIC`. For modified (pre-existing) tests, the LLM additionally assesses whether the modifications align with the problem description (`modification_aligned`). Full pre-patch and post-patch test source is provided for context.

**Cross-Reference Analysis.** After Stages 4A and 4B complete, a deterministic cross-reference pass detects circular dependencies: cases where an F2P test exercises functions from an UNRELATED patch hunk. This means the test cannot pass without implementing out-of-scope code changes — a strong APPROACH_LOCK signal. Detection uses call-graph data from code visitation when available, falling back to identifier overlap heuristics otherwise.

**Stage 5 — Classification.** Combines all upstream signals into an 8-label multi-label classification with bucket-based severity. A fast heuristic pre-classifier fires candidate labels from binary signals (any OFF_TOPIC assertion triggers EXCESS_TESTS, any misaligned modified test triggers SNEAKY_EDIT, any circular dependency triggers APPROACH_LOCK, etc.). These candidates, along with the full per-hunk and per-test evidence, are passed to an LLM for refinement. The LLM can confirm, adjust confidence, or override heuristic candidates.

---

## Taxonomy

### Axis 1: Task Contamination Labels

Eight binary labels. A task can have zero or more contamination labels. If any contamination label is present, `CLEAN` is excluded. Severity is determined by **which labels are present**, not by scores or counts — one excess test contaminates the same as one hundred.

| Label | Definition |
|-------|-----------|
| `APPROACH_LOCK` | F2P tests require a specific implementation approach the problem doesn't determine. A correct-but-different solution would fail. Includes circular dependencies where tests require out-of-scope patch changes. |
| `EXCESS_TESTS` | F2P tests verify behavior not described in the problem. Tests go beyond acceptance criteria. Includes tests enforcing features the problem explicitly defers. |
| `SNEAKY_EDIT` | A pre-existing test was modified to assert on new behavior not in the problem statement. The test existed before the PR, making it look legitimate, but the PR author silently changed assertions or expected values. |
| `EXCESS_PATCH` | Gold patch contains behavioral code changes beyond what the problem asks for. New features, unrelated refactoring, scope expansion. Pure ancillary changes (imports, whitespace, docstrings) do **not** count. |
| `UNCLEAR_SPEC` | Problem statement is too ambiguous or actively misleading to determine the correct solution. Key information is missing, or the description points toward the wrong fix. |
| `HIDDEN_CONTEXT` | Essential solution information exists only in the hints text (code review comments, maintainer decisions) and not in the problem statement. Includes self-referential problems that reference their own patch or tests. |
| `UNDERSPEC` | F2P tests or gold patch don't fully cover stated acceptance criteria. A partial or incorrect fix can pass. This is a benchmark quality issue, not a fairness issue. |
| `CLEAN` | No contamination detected. Mutually exclusive with all other labels. |

### Severity Rules

Severity is determined by bucket rules — which labels are present determines the severity tier. No arithmetic, no weights, no thresholds.

| Severity | Trigger |
|----------|---------|
| **SEVERE** | `APPROACH_LOCK` is present, **OR** both `EXCESS_TESTS` and `EXCESS_PATCH` are present |
| **MODERATE** | `SNEAKY_EDIT` is present, **OR** `EXCESS_TESTS` alone (without `EXCESS_PATCH`) |
| **MINOR** | Any other single contamination label: `EXCESS_PATCH` alone, `UNCLEAR_SPEC`, `HIDDEN_CONTEXT`, or `UNDERSPEC` |
| **CLEAN** | No contamination labels |

### Axis 2: Agent Trajectory Labels

Per-agent classification of how the agent behaved on a task. Assigned by analyzing the full agent trajectory (sequence of actions, file edits, terminal commands) and comparing the agent's final patch against the gold patch.

**Passed labels** (agent resolved the task):

| Label | Description |
|-------|-------------|
| `agent_passed_genuine` | Legitimate problem-solving with progressive exploration, hypothesis formation, and iterative debugging |
| `agent_passed_leak` | Final patch matches the gold patch too closely; agent jumped directly to the correct file/function without exploration |
| `agent_passed_package_leak` | Agent installed a newer version of the target package via pip and copied the fix from site-packages |
| `agent_passed_test_aware` | Agent referenced F2P test names or expected values before discovering them through normal exploration |
| `agent_passed_trained_hack` | Agent applied a memorized template pattern without genuine task-specific reasoning |

**Failed labels** (agent did not resolve the task):

| Label | Description |
|-------|-------------|
| `agent_failed_completed_intent` | Agent's patch correctly addresses the described problem but fails F2P tests due to task contamination (approach mismatch, excess tests, etc.) |
| `agent_failed_no_intent` | Agent did not solve the problem; failure reflects a skill gap, not evaluation unfairness |

**Unknown:**

| Label | Description |
|-------|-------------|
| `agent_unknown` | Insufficient trajectory data to classify |

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

### Dependencies

```
datasets>=2.14.0
openai>=1.0.0
pyyaml>=6.0
tqdm>=4.65.0
azure-identity>=1.15.0
azure-identity-broker>=1.1.0
msal>=1.26.0
requests>=2.31.0
```

Optional: `rich` for enhanced progress display during pipeline execution.

---

## Configuration

Create a `config.yaml` in the project root:

```yaml
llm:
  base_url: "https://your-openai-endpoint.azure-api.net/"
  api_version: "2025-04-01-preview"
  model: "gpt-4o"
  max_tokens: 16384
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

### Configuration Reference

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `llm` | `base_url` | — | Azure OpenAI or compatible endpoint URL |
| `llm` | `api_version` | `2025-04-01-preview` | API version string |
| `llm` | `model` | `gpt-5.2-20251211` | Model deployment name |
| `llm` | `max_tokens` | `16384` | Maximum response tokens per LLM call |
| `llm` | `reasoning_effort` | `high` | Reasoning effort level (`low`, `medium`, `high`) |
| `llm` | `max_concurrent_requests` | `10` | Max parallel LLM API calls |
| `llm` | `retry_attempts` | `7` | Retry count on transient API failures |
| `llm` | `retry_delay_seconds` | `5.0` | Delay between retries (seconds) |
| `pipeline` | `concurrency` | `5` | Max parallel task processing |
| `pipeline` | `cache_dir` | `.cache/llm_responses` | LLM response cache directory |
| `pipeline` | `output_dir` | `output` | Output directory for reports and summaries |
| `code_visitation` | `repo_cache_dir` | `.cache/repos` | Git repo clone cache directory |
| `code_visitation` | `clone_timeout_seconds` | `120` | Timeout for git clone operations |
| `code_visitation` | `max_source_context_lines` | `200` | Max lines of source context per function |

Environment variables can be referenced in config values using `${VAR_NAME}` syntax.

---

## Usage

### Run the Analysis Pipeline

Analyze SWE-bench Verified (default, 500 tasks):

```bash
python run_pipeline.py --config config.yaml
```

Analyze a specific task:

```bash
python run_pipeline.py --instance-id django__django-11964
```

Analyze SWE-bench Pro:

```bash
python run_pipeline.py --dataset pro
```

Resume a previous run (skip tasks with existing reports):

```bash
python run_pipeline.py --resume
```

#### Pipeline CLI Reference

| Flag | Description |
|------|-------------|
| `--config FILE` | Path to config YAML (default: `config.yaml`) |
| `--dataset {verified,pro,live,both}` | Dataset to analyze (default: `verified`) |
| `--max-tasks N` | Limit number of tasks to process |
| `--instance-id ID` | Analyze a single task by instance ID |
| `--output DIR` | Override output directory |
| `--concurrency N` | Override parallel task count |
| `--resume / --no-resume` | Resume from existing reports or reprocess all |
| `-v, --verbose` | Enable DEBUG logging |

### Generate Deep Dive Reports

Produce detailed per-case markdown analysis of contaminated tasks:

```bash
# All SEVERE cases (default)
python run_deep_dive.py --reports-dir output/reports

# Specific severity level
python run_deep_dive.py --reports-dir output/reports --severity MODERATE

# Specific instances
python run_deep_dive.py --reports-dir output/reports \
  --instance-ids django__django-10999 astropy__astropy-14182

# Save to file
python run_deep_dive.py --reports-dir output/reports --output case_studies/deep_dive.md
```

### Generate Presentation Slides

Generate a MARP-compatible markdown slide deck:

```bash
python run_slides.py --reports-dir output/reports --output slides/findings.md

# Convert to HTML or PDF
npx @marp-team/marp-cli slides/findings.md
npx @marp-team/marp-cli --pdf slides/findings.md
```

### Run Trajectory Analysis

Classify agent behavior on contaminated tasks:

```bash
# With LLM classification
python run_trajectory_analysis.py \
  --reports-dir output/reports \
  --trajectory-source trajectory_data/ \
  --config config.yaml

# Heuristic-only (no LLM, faster)
python run_trajectory_analysis.py \
  --reports-dir output/reports \
  --trajectory-source trajectory_data/ \
  --no-llm

# From HuggingFace dataset
python run_trajectory_analysis.py \
  --reports-dir output/reports \
  --trajectory-source "your-org/trajectory-dataset" \
  --hf-split train
```

---

## Output Format

### Directory Layout

```
output/
├── reports/                   # One JSON file per task
│   ├── django__django-10999.json
│   ├── astropy__astropy-14182.json
│   └── ...
├── summary.csv                # Per-task severity, labels, key metrics
└── summary_stats.json         # Aggregated statistics
```

### Report Schema

Each task produces a JSON report containing the full analysis chain:

```json
{
  "instance_id": "django__django-11964",
  "severity": "SEVERE",
  "intent": {
    "instance_id": "django__django-11964",
    "core_requirement": "Fix ModelChoiceField to include invalid value in error message",
    "behavioral_contract": "...",
    "acceptance_criteria": ["..."],
    "out_of_scope": "...",
    "ambiguity_score": 0.2,
    "decomposition": {
      "bug_description": "ModelChoiceField.default_error_messages uses '%(value)s' but...",
      "suggested_fix": "",
      "legitimacy": "bug",
      "mentioned_files": ["django/forms/fields.py"],
      "mentioned_functions": ["validate"],
      "mentioned_classes": ["ModelChoiceField"],
      "mentioned_variables": ["invalid_choice"],
      "mentioned_modules": ["django.forms"]
    }
  },
  "excess_patch": {
    "total_hunks": 3,
    "required_count": 1,
    "ancillary_count": 1,
    "unrelated_count": 1,
    "has_excess": true,
    "hunks": [
      {
        "hunk_index": 0,
        "file_path": "django/forms/fields.py",
        "verdict": "required",
        "confidence": 0.92,
        "reasoning": "..."
      }
    ]
  },
  "excess_test": {
    "total_tests": 2,
    "aligned_count": 1,
    "tangential_count": 0,
    "unrelated_count": 1,
    "total_assertions": 5,
    "on_topic_assertions": 3,
    "off_topic_assertions": 2,
    "has_excess": true,
    "has_modified_tests": false,
    "tests": [
      {
        "test_name": "test_validate_invalid_choice",
        "intent_match": "aligned",
        "confidence": 0.88,
        "is_modified": false,
        "modification_aligned": true,
        "assertions": [
          {
            "statement": "self.assertIn('invalid_value', str(e))",
            "verdict": "on_topic",
            "reason": "Directly tests the reported bug fix"
          }
        ]
      }
    ]
  },
  "vague_spec": {
    "score": 0.2,
    "reasoning": "..."
  },
  "task_labels": [
    {
      "label": "excess_tests",
      "confidence": 0.85,
      "evidence": ["2 OFF_TOPIC assertions found"],
      "reasoning": "..."
    },
    {
      "label": "excess_patch",
      "confidence": 0.78,
      "evidence": ["1 UNRELATED hunks with behavioral changes"],
      "reasoning": "..."
    }
  ],
  "recommendations": [
    "EXCESS_PATCH: 1 hunk(s) modify code unrelated to the problem description.",
    "EXCESS_TEST: 2 OFF_TOPIC assertions beyond problem scope."
  ]
}
```

### Summary CSV Columns

| Column | Description |
|--------|-------------|
| `instance_id` | SWE-bench task identifier |
| `severity` | `CLEAN`, `MINOR`, `MODERATE`, or `SEVERE` |
| `task_labels` | Semicolon-separated contamination labels |
| `primary_label` | Highest-confidence label |
| `label_count` | Number of contamination labels assigned |
| `patch_hunks_total` | Total gold patch hunks |
| `patch_unrelated` | Count of UNRELATED hunks |
| `has_excess_patch` | Whether excess patch signal is present |
| `tests_total` | Total F2P tests |
| `tests_unrelated` | Count of UNRELATED tests |
| `has_excess_test` | Whether excess test signal is present |
| `has_modified_tests` | Whether any pre-existing test was modified |
| `vague_spec_score` | Ambiguity score (0.0 - 1.0) |
| `legitimacy` | Problem decomposition: bug / feature / enhancement |
| `suggested_fix` | Reporter's suggested fix approach (if any) |
| `mentioned_entities` | Code entities mentioned in problem statement |
| `recommendations` | Actionable findings |

---

## Project Structure

```
bench-cleanser/
│
├── run_pipeline.py                    # Entry point: main analysis pipeline
├── run_deep_dive.py                   # Entry point: per-case deep dive reports
├── run_slides.py                      # Entry point: MARP slide deck generation
├── run_trajectory_analysis.py         # Entry point: agent trajectory classification
├── config.yaml                        # Pipeline configuration
├── requirements.txt                   # Python dependencies
│
├── bench_cleanser/                    # Core library
│   ├── __init__.py                    # Package metadata (version 1.2.0)
│   ├── models.py                      # Data models, enums, serialization
│   ├── pipeline.py                    # Pipeline orchestrator (Stages 1-5)
│   ├── llm_client.py                  # Azure OpenAI / CloudGPT client
│   ├── cache.py                       # LLM response caching layer
│   ├── data_loader.py                 # HuggingFace dataset loader
│   ├── repo_manager.py               # Git repository cloning and management
│   ├── code_visitor.py                # Stage 1.5: full source extraction via AST
│   ├── static_analysis.py             # Import resolution, call graph, assertions
│   ├── deep_dive.py                   # Case study markdown generation
│   ├── presentation.py                # MARP slide deck generation
│   │
│   ├── analysis/                      # Analysis stages
│   │   ├── scope_analyzer.py          # Stage 2: intent extraction + problem decomposition
│   │   ├── structural_diff.py         # Stage 3: AST-level structural analysis
│   │   ├── patch_analyzer.py          # Stage 4A: gold patch hunk classification
│   │   ├── test_analyzer.py           # Stage 4B: F2P test + assertion classification
│   │   └── cross_ref.py              # Cross-reference: circular dependency detection
│   │
│   ├── classification/                # Taxonomy and scoring
│   │   ├── dual_taxonomy.py           # 8-label taxonomy, severity rules, LLM classifier
│   │   └── scorer.py                  # Stage 5: final report building
│   │
│   ├── trajectory/                    # Agent trajectory analysis
│   │   ├── analyzer.py                # Trajectory analysis orchestrator
│   │   ├── classifier.py             # LLM + heuristic trajectory classifier
│   │   └── models.py                  # Trajectory data structures
│   │
│   └── parsing/                       # Diff parsing
│       ├── patch_parser.py            # Unified diff parser for gold patches
│       └── test_parser.py             # Test patch parser + F2P test matching
│
├── tests/                             # Unit tests
│   └── test_scorer.py                 # Binary signals, serialization, cross-ref tests
│
├── case_studies/                      # Analysis artifacts
│   ├── severe_deep_dive.md            # Assertion-level deep dives for SEVERE cases
│   ├── top20_deep_dive.md             # Top-20 contaminated tasks detailed analysis
│   ├── severe_cases_forensic.md       # Forensic breakdown of severe contamination
│   └── django_11964_agent_trajectory_study.md
│
├── slides/                            # Presentation decks
│   ├── bench_cleanser_findings.md     # Main findings (MARP format)
│   └── v3_forensic_analysis.md        # Forensic analysis slides
│
├── scripts/                           # Utility scripts
│   └── v3_forensic_analysis.py        # Bulk forensic analysis runner
│
├── output_v3/                         # 500-task benchmark run results
│   ├── reports/                       # 500 JSON reports
│   ├── summary.csv                    # Per-task summary
│   └── summary_stats.json            # Aggregated statistics
│
└── analysis_v3/                       # Cross-reference analysis data
    └── forensic_results.json
```

---

## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

The test suite covers binary signal detection, report serialization roundtrips (including problem decomposition), assertion count properties, and cross-reference circular dependency detection.

### LLM Prompt Architecture

The pipeline uses six distinct LLM prompts, each designed for a specific analysis stage:

| Prompt | Location | Purpose |
|--------|----------|---------|
| Intent System Prompt | `analysis/scope_analyzer.py` | Extract acceptance criteria + problem decomposition from problem statement (blind to patch) |
| Test Intent System Prompt | `analysis/test_analyzer.py` | Classify each F2P test and its assertions against extracted intent |
| Patch Intent System Prompt | `analysis/patch_analyzer.py` | Classify each gold patch hunk against extracted intent |
| Task Classifier System Prompt | `classification/dual_taxonomy.py` | Assign multi-label contamination taxonomy from aggregated evidence |
| Agent Classifier System Prompt | `classification/dual_taxonomy.py` | Classify agent trajectory behavior |
| Trajectory Analysis System Prompt | `trajectory/classifier.py` | Full trajectory analysis with heuristic signal integration |

### Caching

LLM responses are cached to disk (default: `.cache/llm_responses/`). This allows interrupted pipeline runs to be resumed without re-querying the LLM for previously processed tasks. Cache keys are deterministic based on task ID and analysis stage.

### Adding Labels

To add a new contamination label:

1. Add the enum value to `TaskContaminationLabel` in `models.py`
2. Add the label definition and LLM prompt guidance to `LABEL_DEFINITIONS` in `dual_taxonomy.py`
3. Add a heuristic detection rule in `_heuristic_labels()` in `dual_taxonomy.py`
4. Update the severity bucket rules in `compute_task_severity()` if applicable
5. Add the label to `TASK_CLASSIFIER_SYSTEM_PROMPT` in `dual_taxonomy.py`

---

## License

Internal research tool. Not licensed for external distribution.
