# bench-cleanser

**A high-confidence contamination detector for SWE-bench benchmarks.**

bench-cleanser analyzes SWE-bench Verified and SWE-bench Lite tasks to identify and classify instances where the evaluation is unfair to agents. It detects cases where fail-to-pass (F2P) tests and gold patches exceed the scope of what the task description actually asks for, penalizing agents for not reproducing out-of-scope changes they were never asked to make.

## The Problem

SWE-bench is an influential benchmark for evaluating software engineering agents. However, rigorous scrutiny reveals that some tasks contain **contaminated evaluation criteria** -- tests and patches that go beyond the task description. An agent that correctly solves the described problem can still be marked as failing because the benchmark expects additional, undescribed changes.

This is not a minor issue. It systematically distorts benchmark scores and misleads the research community about agent capabilities.

## Case Study: `pylint-dev__pylint-8898`

This task demonstrates the problem clearly.

### What the task asks

Fix a bug where pylint's `bad-names-rgxs` option crashes when a regex contains a comma inside a quantifier (e.g., `{1,3}`). The CSV splitter naively splits on all commas, mangling the regex.

**Problem statement excerpt:**
> *"bad-names-rgxs mangles regular expressions with commas... Since pylint splits on commas in this option, if there are any commas in the regular expression, the result is mangled before being parsed."*

### What a correct fix looks like

Add a smarter CSV splitter that skips commas inside `{}` braces. The gold patch does this by introducing `_check_regexp_csv()` in `pylint/utils/utils.py` -- this part is entirely in-scope.

### Where the evaluation becomes unfair

The **fail-to-pass test** that the agent is graded on is `test_csv_regex_error`. This test **already existed and passed** before the PR. The gold patch sneakily modifies it:

**Before (at base commit):**
```python
def test_csv_regex_error(capsys):
    with pytest.raises(SystemExit):
        Run(
            [str(EMPTY_MODULE), r"--bad-names-rgx=(foo{1,3})"],
            exit=False,
        )
    output = capsys.readouterr()
    assert (
        r"Error in provided regular expression: (foo{1 beginning at index 0: "
        r"missing ), unterminated subpattern"
        in output.err
    )
```

**After (in gold patch):**
```python
def test_csv_regex_error(capsys):
    with pytest.raises(SystemExit):
        Run(
            [str(EMPTY_MODULE), r"--bad-names-rgx=(foo{1,}, foo{1,3}})"],
            exit=False,
        )
    output = capsys.readouterr()
    assert (
        r"Error in provided regular expression: (foo{1,} beginning at index 0: "
        r"missing ), unterminated subpattern"
        in output.err
    )
```

The test input changed from `(foo{1,3})` to `(foo{1,}, foo{1,3}})`. The expected error message changed from `(foo{1` to `(foo{1,}`. **Neither of these changes is described in or implied by the task description.** The task says "fix comma handling in regex CSV splitting." It does not say "also change the existing error test to use a different malformed input."

An agent that correctly implements the comma-aware splitter will make `test_csv_regex_comma_in_quantifier` pass (these are new tests in PASS_TO_PASS). But it may produce different error output for the sneakily modified `test_csv_regex_error` input, because the exact error message depends on implementation details of how the new splitter processes `(foo{1,}, foo{1,3}})`.

**The agent is graded on reproducing a test modification it was never asked to make.**

### Why this matters at scale

This is not an isolated case. Across 500+ tasks in SWE-bench Verified and Lite, this pattern recurs in various forms:
- Tests modified to expect different behavior than originally specified
- Gold patches that include refactors, style changes, or feature additions bundled with the fix
- F2P tests that verify implementation details the task description never mentions
- Circular dependencies where F2P tests can only pass if out-of-scope patch changes are reproduced exactly

Every such task inflates the apparent difficulty of the benchmark and penalizes agents that solve the actual problem correctly.

## Contamination Taxonomy

bench-cleanser classifies contamination into 7 categories:

| ID | Category | Description |
|----|----------|-------------|
| C1 | **OVERTEST** | F2P tests verify functionality beyond the task scope |
| C2 | **OVERPATCH** | Gold patch contains changes beyond the required fix |
| C3 | **SNEAKY_TEST_MOD** | Pre-existing tests are modified in the F2P set |
| C4 | **SCOPE_CREEP** | The PR bundles multiple independent changes |
| C5 | **TEST_DESC_MISALIGN** | Tests assert on specific behavior not described in the problem statement |
| C6 | **CIRCULAR_DEPENDENCY** | F2P tests require out-of-scope patch changes to pass |
| C7 | **AMBIGUOUS_SPEC** | Problem statement too vague to determine a unique correct solution |

### Severity Levels

Each task receives a composite contamination score and is classified as:

- **CLEAN** (score < 0.2): Task is fair, evaluation criteria match the description
- **MINOR** (0.2 - 0.5): Mild issues that may not affect most correct solutions
- **MODERATE** (0.5 - 0.8): Questionable task, likely unfair to some correct solutions
- **SEVERE** (score >= 0.8): Task is dirty, agents are graded on out-of-scope criteria

## How It Works

### 7-Stage Pipeline

1. **Parse**: Extract structured data from SWE-bench records (patch hunks, test functions, F2P/P2P lists)
2. **Code Visitation**: Clone repos at `base_commit`, retrieve full test source, AST-analyze test functions, identify tested source code, and build `CodeContext` for each F2P test
3. **Scope Analysis**: LLM analyzes the problem statement *without seeing the gold patch* to determine what the task actually asks for
4. **Patch Analysis**: Each gold patch hunk is classified as in-scope, borderline, or out-of-scope
5. **Test Analysis**: Each F2P test is checked for scope alignment and sneaky modifications, using full pre/post-patch source, tested function code, call graph, and structured assertions when available
6. **Cross-Reference**: Detect circular dependencies using real call-graph data from code visitation (falls back to identifier overlap heuristics without code context)
7. **Classify**: Compute per-category confidence scores and overall severity

### Key Design Principles

- **Unanchored scope analysis**: The LLM never sees the gold patch when determining task scope. This prevents rationalization bias.
- **Full code visitation**: Repos are cloned at `base_commit` to retrieve complete test source, tested source code, imports, fixtures, and call graphs. This gives the LLM far richer context than diff-only analysis.
- **Deterministic signals first**: Before expensive LLM calls, we compute cheap deterministic signals (e.g., "does this F2P test name exist in the test_patch with removal lines?" catches Category C3 with near-perfect precision).
- **Per-hunk granularity**: Gold patches are analyzed hunk-by-hunk, not as monoliths. This pinpoints exactly which changes exceed scope.
- **AST-powered static analysis**: Test functions are analyzed via Python AST to extract call targets, resolve imports, identify tested functions, and structure assertions.
- **Graceful degradation**: If repo cloning or AST parsing fails, the pipeline falls back to diff-only analysis automatically.
- **Cached**: All LLM responses are cached by content hash. Re-runs skip already-analyzed tasks. Cloned repos are cached for reuse across runs.

## Usage

```bash
# Install
pip install -r requirements.txt

# Configure (edit config.yaml with your LLM endpoint)
cp config.yaml my_config.yaml

# Run on both benchmarks (500 Verified + 500 Lite)
python run_pipeline.py --config my_config.yaml --output results/

# Run on a specific benchmark
python run_pipeline.py --config my_config.yaml --dataset verified --output results/

# Run on a single task (for debugging/verification)
python run_pipeline.py --config my_config.yaml --instance-id pylint-dev__pylint-8898 --output results/

# Disable code visitation (diff-only mode, faster but less accurate)
# Set code_visitation.enabled: false in config.yaml
```

### Output

- `results/reports/` -- Per-task JSON contamination reports
- `results/summary.csv` -- Aggregate classification table
- `results/summary_stats.json` -- Distribution statistics

## Configuration

See `config.yaml` for all options. Key settings:

```yaml
llm:
  base_url: "https://your-endpoint/v1"
  api_key: "${LLM_API_KEY}"
  model: "your-model"
  reasoning_effort: "high"

pipeline:
  concurrency: 5
  cache_dir: ".cache/llm_responses"

code_visitation:
  enabled: true
  repo_cache_dir: ".cache/repos"
  clone_timeout_seconds: 120
  max_source_context_lines: 200
```

## Architecture

```
bench_cleanser/
  models.py              # Data models (PipelineConfig, CodeContext, etc.)
  data_loader.py         # SWE-bench dataset loading from HuggingFace
  repo_manager.py        # Git clone caching and management
  code_visitor.py        # Source code retrieval from cloned repos
  static_analysis.py     # AST-based test analysis (calls, imports, assertions)
  pipeline.py            # 7-stage orchestration
  llm_client.py          # LLM API client with retry logic
  cache.py               # Content-hash-based response caching
  parsing/
    patch_parser.py      # Gold patch diff parsing
    test_parser.py       # Test patch diff parsing
  analysis/
    scope_analyzer.py    # Stage 3: LLM scope analysis
    patch_analyzer.py    # Stage 4: Per-hunk classification
    test_analyzer.py     # Stage 5: F2P test alignment analysis
    cross_ref.py         # Stage 6: Circular dependency detection
  classification/
    taxonomy.py          # Contamination category definitions
    scorer.py            # Composite scoring and severity classification
```

## Results (SWE-bench Verified, first 100 tasks)

| Severity | Count | Percentage |
|----------|-------|------------|
| CLEAN    | 9     | 9.0%       |
| MINOR    | 67    | 67.0%      |
| MODERATE | 11    | 11.0%      |
| SEVERE   | 12    | 12.0%      |

Mean contamination score: **0.418**

Top contamination categories detected:
- AMBIGUOUS_SPEC: 99 tasks (most common -- problem statements often underspecify)
- OVERPATCH: 20 tasks
- OVERTEST: 8 tasks
- SCOPE_CREEP: 6 tasks
- TEST_DESC_MISALIGN: 6 tasks
- SNEAKY_TEST_MOD: 5 tasks
- CIRCULAR_DEPENDENCY: 1 task
