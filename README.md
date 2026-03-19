# bench-cleanser

Automated contamination detection for SWE-bench benchmarks. Identifies tasks where gold patches or fail-to-pass (F2P) tests exceed the problem description, producing unfair evaluation criteria for software engineering agents.

## Problem

SWE-bench Verified (500 tasks) and SWE-bench Pro are the primary benchmarks for evaluating software engineering agents. Some tasks have **contaminated evaluation criteria** that penalize agents for correctly solving the *described* problem:

- **Approach Lock**: Tests require a specific implementation approach the problem doesn't determine
- **Excess Tests**: F2P tests verify behavior not described in the problem statement
- **Sneaky Edits**: Pre-existing tests silently modified to assert on undescribed behavior
- **Excess Patch**: Gold patch includes behavioral changes beyond problem scope
- **Unclear Spec**: Problem statement too ambiguous to determine the correct solution
- **Hidden Context**: Essential info exists only in hints text, not the problem statement

Agents that correctly solve the *described* problem may fail these tasks because evaluation criteria test *undescribed* behavior.

## Pipeline Architecture

```
Stage 1:   PARSE              Extract diffs from gold patch + test patch
Stage 1.5: CODE VISITATION     Clone repo, extract full test/function source
Stage 2:   INTENT              Extract intent + decompose problem statement (LLM, blind to patch)
Stage 3:   STRUCTURAL DIFF     AST-level function/class change analysis
Stage 4A:  PATCH MATCHING      Classify each gold patch hunk vs intent (LLM)
Stage 4B:  TEST MATCHING       Classify each F2P test + assertions vs intent (LLM)
Stage 5:   CLASSIFICATION      8-label taxonomy + bucket-based severity
```

### Stage 2: Intent Extraction + Problem Decomposition

The LLM sees ONLY the problem statement (never the gold patch) and extracts:
- Acceptance criteria (testable behaviors)
- Problem decomposition: bug description vs. reporter's suggested fix vs. legitimacy
- Code entities: files, functions, classes, variables mentioned in the problem

### Stages 4A/4B: Intent Matching

Each gold patch hunk is classified as REQUIRED / ANCILLARY / UNRELATED.
Each F2P test is classified as ALIGNED / TANGENTIAL / UNRELATED with per-assertion ON_TOPIC / OFF_TOPIC verdicts.

Code visitation and structural analysis provide full function source and call graph context.

### Stage 5: Dual Taxonomy

8 binary contamination labels. Severity determined by bucket rules, not arithmetic.

## Taxonomy

### Axis 1: Task Contamination Labels

| Label | Definition |
|-------|-----------|
| `APPROACH_LOCK` | F2P tests require a specific implementation approach the problem doesn't determine. A correct-but-different solution would fail. |
| `EXCESS_TESTS` | F2P tests verify behavior not described in the problem. Tests go beyond acceptance criteria. |
| `SNEAKY_EDIT` | Pre-existing test modified to assert on new behavior not in the problem statement. |
| `EXCESS_PATCH` | Gold patch contains behavioral changes beyond what the problem asks for. Pure ancillary (imports, whitespace) does NOT count. |
| `UNCLEAR_SPEC` | Problem statement too ambiguous or misleading to determine the correct solution. |
| `HIDDEN_CONTEXT` | Essential solution info exists only in hints text, not in the problem. |
| `UNDERSPEC` | F2P tests don't fully cover stated acceptance criteria. Partial fix can pass. (Benchmark quality issue, not fairness issue.) |
| `CLEAN` | No contamination detected. Exclusive — cannot co-occur with other labels. |

### Severity Rules

Severity is determined by **which labels are present**, not by scores or counts. One excess test contaminates the same as one hundred.

| Severity | Trigger |
|----------|---------|
| **SEVERE** | `APPROACH_LOCK` present, OR both `EXCESS_TESTS` and `EXCESS_PATCH` present |
| **MODERATE** | `SNEAKY_EDIT` present, OR `EXCESS_TESTS` alone |
| **MINOR** | `EXCESS_PATCH` alone, `UNCLEAR_SPEC`, `HIDDEN_CONTEXT`, or `UNDERSPEC` alone |
| **CLEAN** | No contamination labels |

### Axis 2: Agent Trajectory Labels

Per-agent classification of how the agent behaved on a task:

| Label | Description |
|-------|-------------|
| `agent_passed_genuine` | Legitimate problem-solving with progressive exploration |
| `agent_passed_leak` | Patch matches gold too closely; jumped to answer |
| `agent_passed_package_leak` | Installed newer package and copied fix |
| `agent_passed_test_aware` | Referenced F2P test names/values before discovering them |
| `agent_passed_trained_hack` | Applied memorized template without genuine reasoning |
| `agent_failed_completed_intent` | Patch addresses real problem but fails F2P tests |
| `agent_failed_no_intent` | Did not solve the problem at all |
| `agent_unknown` | Insufficient trajectory data |

## Quick Start

### Configuration

Create `config.yaml`:

```yaml
llm:
  base_url: "https://cloudgpt-openai.azure-api.net/"
  api_version: "2025-04-01-preview"
  model: "gpt-5.2-20251211"
  max_tokens: 16384
  reasoning_effort: "high"
  max_concurrent_requests: 10

pipeline:
  concurrency: 5
  cache_dir: ".cache/llm_responses"
  output_dir: "output"

code_visitation:
  repo_cache_dir: ".cache/repos"
  clone_timeout_seconds: 120
  max_source_context_lines: 200
```

### Run Pipeline

```bash
python run_pipeline.py --config config.yaml --dataset swebench_verified.json
```

### Run Deep Dive (top-N analysis)

```bash
python run_deep_dive.py --reports-dir output/reports --top 20
```

### Generate Slides

```bash
python run_slides.py --reports-dir output/reports --output slides/deck.md
```

### Run Trajectory Analysis

```bash
python run_trajectory_analysis.py --reports-dir output/reports --trajectories traj_dir/
```

## Project Structure

```
bench_cleanser/
├── __init__.py
├── models.py                      # Core data models, enums, serialization
├── llm_client.py                  # Azure OpenAI / CloudGPT client
├── cache.py                       # Response caching
├── repo_manager.py                # Git repo cloning and management
├── code_visitor.py                # Stage 1.5: full source extraction via AST
├── static_analysis.py             # Import resolution, call target analysis
├── pipeline.py                    # Pipeline orchestrator (Stages 1-5)
├── deep_dive.py                   # Per-case deep dive report generation
├── presentation.py                # MARP slide deck generation
├── analysis/
│   ├── scope_analyzer.py          # Stage 2: intent extraction + problem decomposition
│   ├── structural_diff.py         # Stage 3: AST-level structural analysis
│   ├── patch_analyzer.py          # Stage 4A: gold patch hunk classification
│   └── test_analyzer.py           # Stage 4B: F2P test classification
├── classification/
│   ├── dual_taxonomy.py           # Label definitions, severity rules, LLM classifier
│   └── scorer.py                  # Stage 5: final report building
├── trajectory/
│   ├── analyzer.py                # Trajectory analysis orchestrator
│   ├── classifier.py              # Trajectory LLM classifier
│   └── models.py                  # Trajectory data models
└── parsing/
    ├── patch_parser.py            # Unified diff parser
    └── test_parser.py             # Test patch parser, F2P matching
```

## Requirements

```
pip install -r requirements.txt
```

Python 3.12+. Dependencies: `openai`, `pyyaml`, `tqdm`, `rich` (optional, for progress display).
