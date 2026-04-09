## Trajectory Analysis Results

### Overview

- **Total trajectories analyzed:** 101
- **GENUINE_SOLUTION:** 9 (8.9%)
- **GOLD_PATCH_LEAK:** 12 (11.9%)
- **PARTIAL_MATCH:** 79 (78.2%)
- **TEST_AWARE:** 1 (1.0%)

### Per-Instance Results

#### `instance_NodeBB__NodeBB-18c45b44613aecd53e9f60457b9812049ab2998d-v0495b863a912fbff5749c67e860612b91825407c`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.82 | 0.00 | 0 | 0 | Methodical and plausible repository exploration with a correct high-level diagnosis, but the attempt |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the current socket-based invitation flow and related API infrastructure, inferred that REST endpoints/controllers/OpenAPI docs needed to be added, began planning those edits, but appears to have stopped before completing or validating the implementation.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a largely legitimate, exploratory debugging process rather than leakage. The agent starts by surveying the repository, then inspects the existing invitation implementation across sockets, API files, controllers, routes, and OpenAPI docs. It explicitly reasons that the missing work is to add API endpoints, controller methods, API-layer functions, and schema entries. That is a sensible derivation from the problem statement and codebase structure, not a suspicious jump to the exact gold edit locations. It also looked at existing tests, but there is no evidence it cited hidden fail-to-pass test names, asserted unseen expected values, or used test-only knowledge before discovering relevant files. There is no indication of package installation or copying from external sources. However, the run did not actually produce a substantive patch in the provided record—the final patch is empty, and there is no evidence of completed edits, test execution, or iteration. Because the failure appears to come from an incomplete implementation rather than from hidden-test contamination or an otherwise-correct patch that mismatched the benchmark, this is best classified as a genuine but unsuccessful attempt, i.e. failed_no_intent rather than failed_completed_intent.

</details>

#### `instance_NodeBB__NodeBB-445b70deda20201b7d9a68f7224da751b3db728c-v4fbcfae8b15e4ce5d132c408bca69ebb9cf146ed`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.76 | 0.00 | 0 | 0 | Reasonable repository-driven diagnosis with a near-correct fix plan, but incomplete execution and no |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the codebase and tests, inferred the validation/defaulting inconsistencies in chats and users APIs, formed a fix plan matching the intended behavior, but did not convert that plan into an applied patch or completed test-verified solution.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a largely legitimate debugging flow: the agent started from the problem statement, explored the repository structure, identified the relevant API files (`src/api/chats.js` and `src/api/users.js`), searched for the named methods, and inspected tests to understand expected behavior. It then articulated a concrete fix plan that lines up closely with the real issue: adding invalid-data checks for missing identifiers and pagination inputs, and defaulting certain parameters from `caller`. There are no clear leakage indicators such as immediately jumping to the exact target file without exploration, installing packages, copying from external code, or citing hidden test names/expected values in advance. The one mildly suspicious element is that its planned changes are very close to the gold patch, including the `listMessages` adjustment that is somewhat beyond the user-facing problem description, but that can plausibly be explained by normal code/test exploration. Crucially, however, there is no actual final patch in the trajectory and no evidence that the agent implemented or validated its proposed edits. Since the agent did not resolve the task and the failure does not appear caused by benchmark contamination or unfair test mismatch, this is best classified as a failed attempt rather than leakage.

</details>

#### `instance_NodeBB__NodeBB-70b4a0e2aebebe8f2f559de6680093d96a697b2f-vnan`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.86 | 0.00 | 0 | 0 | Methodical and evidence-driven: the agent explored the codebase, formed a concrete hypothesis from e |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement pointed the agent toward `sortedSetsCardSum`; the agent explored the existing database implementations, noticed that score-range logic already existed in `sortedSetCount`, generalized that logic into `sortedSetsCardSum` across all backends, then updated a higher-level caller (`getCounts`) to use the new aggregation capability and validated the behavior with self-constructed tests.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a credible, stepwise debugging and implementation process rather than shortcutting to a memorized answer. The agent begins by exploring repository structure and the existing implementation, then specifically inspects `sortedSetCount` and `sortedSetsCardSum` across the database backends to understand current behavior and how score filtering is already implemented elsewhere. It then inspects the higher-level caller (`getCounts`) and correctly identifies the inefficiency and missing aggregation support. After that, it creates reproduction/testing scripts, implements backend-specific changes for Redis/Postgres/Mongo, updates the helper usage, and iterates on a self-created test expectation when it notices a mistake in its own data. Those are all hallmarks of genuine problem-solving. There is no sign that it referenced the hidden fail-to-pass test name or asserted hidden expected values before discovery. There is also no evidence of package installation or copying code from an external source. While the likely final patch may overlap substantially with the gold patch, that overlap is expected for a narrowly specified bugfix spanning the exact relevant backends and caller, and the trajectory does not show the suspicious “jump straight to exact gold locations with no search” pattern typical of leakage.

</details>

#### `instance_NodeBB__NodeBB-76c6e30282906ac664f2c9278fc90999b27b1f48-vd59a5728dfc977f44533186ace531248c2917516`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.89 | 0.00 | 0 | 0 | The agent performed coherent but entirely misdirected exploration, strongly anchored to the contamin |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to have latched onto contaminated benchmark metadata or gold-patch scope-creep about daily flag limits, explored that unrelated subsystem in depth, and never reoriented to the actual plugin activation validation bug, leading to a complete miss on the real task.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The agent did not work on the stated plugin-identifier validation bug at all. Instead, from Step 1 onward it explicitly reframed the task as implementing daily flag limits for posts/users, then explored only the flags subsystem, defaults, meta config, database counters, error translations, and API support for remaining flag counts. That thematic focus closely matches the unrelated dominant content in the provided gold patch contamination (post/user flag-per-day limits and related translations), not the real requirement to validate plugin IDs in `Plugins.toggleActive`. There is no evidence of package leakage or test-name awareness, and no final patch was produced. So the failure is not a genuine near-miss on the real task; it is a failure to even pursue the correct intent. The strongest signal is not classic direct copy-paste leakage, but contamination-driven anchoring on gold-patch scope creep: the agent appears to have internalized or been steered by the wrong PR description/problem framing associated with the contaminated patch.

</details>

#### `instance_NodeBB__NodeBB-b1f9ad5534bb3a44dab5364f659876a4b7fe34c1-vnan`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.97 | 0.00 | 0 | 0 | The agent showed targeted, confirmatory exploration consistent with prior knowledge of the full cont |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to have recalled or accessed a broader contaminated patch/PR involving both vote-visibility UI changes and sorted-set count changes, then used superficial repository exploration to validate and apply that remembered solution rather than deriving the fix solely from the benchmark prompt.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows strong evidence that the agent was operating from knowledge of the broader gold patch rather than solving only the stated task. The benchmark problem is narrowly about extending `sortedSetsCardSum` in the three database adapters to support optional `min`/`max` bounds. However, from Step 0 the agent states it will fix both "vote visibility controls and database performance issues," introducing an unrelated feature area that is absent from the problem statement but present in the gold patch. It then deliberately inspects and plans edits to `public/src/client/topic/votes.js`, `src/controllers/topics.js`, and `src/controllers/accounts/helpers.js`—all exact files touched by the gold patch, and mostly outside the required scope. In Step 16 it explicitly enumerates six changes, four of which are unrelated to the benchmark requirements and align closely with the gold patch's unrelated hunks (`voteVisibility` in topic data, `canSeeVotes`, conditional vote handlers, suppressing vote-related alerts, and the accounts helper optimization). This is not consistent with genuine debugging from the provided task description. There is no sign of test-name leakage or package leakage, and the agent did perform some exploratory reads, but that exploration appears confirmatory rather than discovery-driven. Given the severe contamination context and the agent's early lock-on to unrelated gold-patch content, this is best classified as a passed solution with gold-patch leakage.

</details>

#### `instance_NodeBB__NodeBB-b398321a5eb913666f903a794219833926881a8f-vd59a5728dfc977f44533186ace531248c2917516`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.75 | 0.00 | 0 | 0 | Systematic repository exploration and feature-driven debugging, with no clear leakage indicators in  |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the requirements, explored the relevant chat/privilege/profile code paths, tried to reproduce the bug, then formulated an implementation plan centered on `canMessageUser`, privilege checks, middleware, and profile API exposure.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The visible trajectory looks like legitimate problem-solving rather than benchmark leakage. The agent began by exploring the repository structure, then examined the messaging/chat implementation, privileges system, profile/user-data flow, middleware checks, and the existing privileged-user helper. It also attempted to reproduce the issue with scripts before falling back to source inspection when that failed, which is a natural debugging pattern. The agent's plan evolved from understanding the current code to implementing the new `chat:privileged` behavior step by step. There is no evidence that it referenced hidden test names or values, no indication of package installation or copying from site-packages, and no sign that it immediately jumped to an exact gold-patch-shaped solution without search. While the task is contamination-prone and the gold patch contains some unrelated hunks, the provided trajectory does not show those suspicious behaviors. The main limitation is that the final patch itself is not shown, so patch-similarity analysis is incomplete; still, based on trajectory evidence alone, this is best classified as a genuine pass.

</details>

#### `instance_NodeBB__NodeBB-cfc237c2b79d8c731bbfc6cadf977ed530bfd57a-v0495b863a912fbff5749c67e860612b91825407c`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.93 | 0.00 | 0 | 0 | Legitimate exploratory debugging with scope drift into broader feature areas, but no completed fix a |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the feature request, inspected the user data and picture-related code, noticed existing avatar background logic, then expanded into adjacent frontend/socket/template areas as if trying to implement the broader product feature. That scope expansion prevented it from delivering the narrower server-side export fix that the fail-to-pass tests required.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows normal exploratory behavior rather than leakage. The agent began by reading relevant user/avatar files, identified that `src/user/data.js` already contained an `iconBackgrounds` array and the username-based background-color logic, and then broadened its search into socket handlers, client account-edit code, templates, and config plumbing. That exploration is consistent with a genuine attempt to understand the feature request. However, there is no evidence that the agent formed and executed the key fix required by the tests: defining `User.getIconBackgrounds` on the exported `User` object and routing the icon background lookup through that function so it remains publicly accessible. The agent produced no patch at all, so this is not a case where it addressed the true issue but failed due to benchmark contamination or hidden test mismatch. It simply did not complete the implementation. There are also no signs of benchmark leakage: it did not jump straight to the exact fix, did not mention hidden test names or expected values, did not install a package containing the solution, and did not produce a patch suspiciously close to the gold patch.

</details>

#### `instance_NodeBB__NodeBB-f2082d7de85eb62a70819f4f3396dd85626a0c0a-vd59a5728dfc977f44533186ace531248c2917516`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.82 | 0.00 | 0 | 0 | Genuine repo-guided implementation attempt that targeted the right migration, but likely missed deta |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the relevant API/controller/route/socket/client files, investigated privilege and response-handling behavior, searched for usages of the legacy socket methods, and then attempted to migrate those flows to new Write API endpoints; it likely failed on implementation details or coverage gaps rather than from lack of intent.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory looks like a genuine implementation attempt rather than leakage. The agent began by exploring the repository structure, then specifically inspected API routes, write controllers, the posts module, privileges, helpers, and call sites of the legacy socket methods. That is the expected workflow for solving this task from first principles. It also tried to understand behavior by creating a script, hit configuration issues, and fell back to reading analogous code paths and auth/response helpers. Its stated plan matches the problem requirements: add new Write API endpoints, add controllers, register routes, remove the obsolete raw socket method, and update client callers. It even noticed a likely implementation pitfall around deleted-post privilege checks and re-examined the privilege layer. There are no signs of benchmark leakage: no package installation, no reference to hidden test names or values, no direct jump to the exact gold fix without exploration, and no evidence of copying from an external source. Because the run ultimately did not resolve the task and the final patch artifact is missing, I cannot verify exact code similarity or the precise failure mode. Still, the trajectory clearly targets the real problem and appears to be a legitimate but incomplete/mismatched implementation, so the best label is a failed attempt with completed intent rather than no intent.

</details>

#### `instance_ansible__ansible-3889ddeb4b780ab4bac9ca2e75f8c1991bcabe83-v0f01c69f1e2528b935359cfe578530722bca2c59`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.78 | 0.00 | 0 | 0 | Systematic, test-driven, and exploratory; appears to have genuinely tried to implement the requested |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem, explored the iptables module and tests, inferred that a new boolean parameter plus chain create/delete behavior was needed, implemented those changes, validated them with self-written and existing tests, and likely failed due to an exact-spec mismatch rather than lack of intent.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory looks like genuine implementation work rather than leakage. The agent began by exploring the repository and reading the existing iptables module before proposing any code changes, then inspected the test file to understand current structure, formulated a concrete plan from the issue requirements, and iteratively implemented argument-spec, documentation, helper functions, and main-flow logic. It also created reproduction scripts and additional tests, ran existing tests, hit an edge-case bug in its own test setup, debugged it, and continued refining the implementation. Those are strong signs of authentic problem-solving. There are no signs that it jumped straight to the exact gold edit locations without context, no evidence of package installation or code copying, and no references to hidden F2P test names or magic expected values before exploration. The task was not resolved, but the trajectory strongly suggests the agent was addressing the real requested feature and likely missed the benchmark's exact expected behavior or interface details rather than failing to understand the problem. Because the final patch text is unavailable, I cannot compare similarity against the gold patch directly; however, the process evidence points away from leakage and toward a real but imperfect implementation.

</details>

#### `instance_ansible__ansible-42355d181a11b51ebfc56f6f4b3d9c74e01cb13b-v1055803c3a812189a1133297f7f5468579283f86`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.83 | 0.00 | 0 | 0 | Methodical, codebase-driven debugging and implementation with reproduction and dependency tracing; b |

**Causal chain (Claude Opus 4.1 - paper):** The agent used the problem statement to identify likely subsystems, inspected the current delegation and loop handling flow, verified the hierarchy needed for `Task.get_play`, reproduced the bug, found that WorkerProcess already held a variable manager, and then implemented a coordinated fix across TaskExecutor, VariableManager, Task, and worker wiring.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This looks like a legitimate repository-guided fix rather than benchmark leakage. The agent began by exploring the relevant code paths in TaskExecutor, VariableManager, Task, Play, and Block, and explicitly checked whether `get_play` already existed before designing a parent-traversal implementation. It also created a reproduction script, hit an issue, fixed the script, and stated that the bug was confirmed before proceeding. The subsequent implementation plan closely tracks the problem statement, but that is not suspicious here because the prompt itself specifies the new public interfaces, the files, and several behavioral requirements. Importantly, the trajectory does not show classic leak indicators: no direct jump to an exact gold patch without inspection, no pip install or copying from external packages, no references to hidden F2P test names or values, and no evidence of memorized boilerplate being applied blindly. In fact, some planned edit locations/approach details differ from the gold patch wording, which argues against direct patch recall. The only caveat is that the final patch content is not shown, so certainty cannot be maximal; however, based on the exploration and reasoning pattern, this is best classified as a genuine pass.

</details>

#### `instance_ansible__ansible-489156378c8e97374a75a544c7c9c2c0dd8146d1-v390e508d27db7a51eece36bb6d9698b63a5b638a`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.82 | 0.00 | 0 | 0 | Mostly genuine investigation with an incomplete implementation attempt, plus a small hint of prior k |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the Meraki module layout, identified the shared utility as the likely fault site, reproduced the immediate-failure behavior with mocking, then began rewriting `request` and argument handling based on its understanding plus some suspiciously specific remembered details. The attempt stalled before a validated fix was produced.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory mostly looks like a genuine debugging attempt that never reached a completed fix. The agent explored the repository progressively, located the shared Meraki utility, inspected `request`, `meraki_argument_spec`, and `__init__`, then built a reproduction script to confirm current behavior before attempting changes. Those are strong signs of real problem-solving rather than a direct replay of the gold patch. There are no visible package-installation steps, no references to hidden test names, and no evidence of copying code from elsewhere. The one mild contamination cue is that the agent explicitly cited exact implementation details not stated in the public problem statement—most notably the new parameters `rate_limit_retry_time` and `internal_error_retry_time`, the default values 165 and 60, and progressive backoff multipliers. Those details line up with the gold patch and suggest some prior knowledge or memorized context. However, because the agent did not complete or submit a working patch, and there is no final code to compare for patch similarity, this does not rise to a successful leakage classification. The failure appears to be an incomplete/inadequate implementation rather than a case where the agent meaningfully solved the benchmark but was blocked by contaminated tests.

</details>

#### `instance_ansible__ansible-709484969c8a4ffd74b839a673431a8c5caa6457-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.86 | 0.00 | 0 | 0 | Exploratory and methodical debugging with a real, over-broad fix attempt; no meaningful leakage sign |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the fact subsystem, noticed OpenBSD had partial uptime logic while other BSD-family collectors lacked it, inferred that sysctl parsing and boot-time retrieval were central, implemented a generalized cross-BSD uptime approach plus sysctl parser changes, then got stuck debugging parsing edge cases before completing a passing fix.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This looks like a genuine but unsuccessful repair attempt, not leakage. The agent began with broad repository exploration, inspected the fact-gathering modules and multiple BSD hardware collectors, compared implementations across OpenBSD, FreeBSD, NetBSD, DragonFly, Darwin, and Linux, and formed a concrete hypothesis that the issue involved both missing uptime collection and brittle sysctl parsing. It then iteratively implemented changes, wrote reproduction scripts, and debugged edge cases in its own parsing logic. That behavior is inconsistent with benchmark leakage: it did not jump straight to the exact gold fix, did not reference hidden test names or expected hidden values, and did not install or copy from external packages. In fact, its proposed scope diverged notably from the gold patch by adding uptime support to FreeBSD, NetBSD, and Darwin rather than only making the targeted OpenBSD/sysctl changes. The trajectory ends with the agent still struggling on regex parsing for colon-rich sysctl lines, which strongly suggests real problem-solving rather than access to a memorized answer. Because the work was aligned with the real bug and requirements but did not finish in a passing state, the best fit is a partial, legitimate attempt: agent_failed_completed_intent.

</details>

#### `instance_ansible__ansible-984216f52e76b904e5b0fa0fb956ab4f1e0a7751-v1055803c3a812189a1133297f7f5468579283f86`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.76 | 0.00 | 0 | 0 | Genuine exploratory implementation attempt guided by the prompt's detailed requirements, but incompl |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement gave highly specific implementation targets, so the agent methodically inspected those components and planned edits matching the stated requirements. It appears to have started implementing the core refactor but stopped before producing or validating a complete working fix, leading to failure.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a legitimate, problem-driven attempt rather than leakage. The agent began by exploring exactly the files and methods named in the problem statement: plugin loader, errors, display, task executor, action base, and template handling. It summarized the required changes in a way that closely follows the user-visible requirements, then described implementing them incrementally. There are no signs of package leakage, no pip installs, no references to hidden test names or expected values, and no suspicious jump to an otherwise non-obvious location beyond what the prompt itself directly specified. However, the task was not resolved, and the available trajectory shows no completed patch output, no test execution/iteration, and no evidence that the key `_configure_module` change was actually finished and validated. Because the failure does not appear to stem from benchmark contamination or an unfair hidden-test mismatch, but instead from an incomplete/non-working implementation, this is best classified as a non-leak failure rather than a 'completed intent' contamination case.

</details>

#### `instance_ansible__ansible-c616e54a6e23fa5616a1d56d243f69576164ef9b-v1055803c3a812189a1133297f7f5468579283f86`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.91 | 0.00 | 0 | 0 | Genuine exploratory debugging of a plausible sub-bug, but too narrow and incomplete for the actual t |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement pointed to module_common and import resolution bugs, leading the agent to inspect module_common.py, focus on recursive_finder, observe a possible '__init__' package-handling defect, reproduce that specific failure locally, and iterate on a small fix. It became stuck in that narrow debugging path and never expanded to the larger refactor the task actually required.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like genuine but unsuccessful debugging rather than leakage. The agent began by exploring the repository and the named target file, then inspected the recursive_finder path, ModuleInfo-related code, and adjacent helper classes before forming a concrete hypothesis. Its hypothesis was narrow: it concluded that package handling was incorrectly trying to resolve a literal '__init__' module name, and it iterated on that idea after reproducing an error and encountering secondary issues such as templar setup problems and an IndexError. This is consistent with real problem-solving. However, the actual task required a much broader redesign: queue-based dependency processing, new locator abstractions for legacy vs collection module_utils, redirect handling, synthesized package __init__.py files, six import normalization, improved unresolved-module error messages, deprecation/tombstone handling, and payload inclusion rules. The agent never moved toward that architecture and instead stayed within the old recursive_finder implementation. That mismatch strongly suggests it did not solve the real benchmark task and instead chased one plausible symptom. There are no meaningful signs of benchmark leakage: it did not cite hidden test names or values, did not install packages, did not copy code from elsewhere, and its approach is not suspiciously similar to the gold patch. In fact, it diverged from the gold patch by trying to patch the old recursive flow rather than replacing it.

</details>

#### `instance_ansible__ansible-d33bedc48fdd933b5abd65a77c081876298e2f07-v0f01c69f1e2528b935359cfe578530722bca2c59`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.90 | 0.00 | 0 | 0 | Genuine debugging-oriented exploration that identified part of the problem, but the agent failed to  |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement pointed the agent to `ensure_type`; from there it traced the configuration retrieval path, investigated how tags are represented and copied, reproduced the tag-loss behavior, and then examined boolean conversion as another reported symptom. The run ended before implementation, so the failure stems from incomplete execution rather than from taking the wrong contaminated approach.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows normal, grounded exploration of the codebase rather than answer-driven behavior. The agent started from the problem statement, navigated to the obvious relevant area (`config/manager.py` and `ensure_type`), then broadened its investigation to `get_option`, `get_config_value`, template handling, the data tag implementation, and `convert_bool.boolean`. It also appears to have created or updated a local repro script to understand how tags are applied and inspected, which is consistent with genuine debugging. There are no signs of benchmark leakage: it did not cite hidden F2P test names or exact expected values, did not pip-install anything, did not jump to unrelated files from the gold patch without motivation, and did not produce a suspiciously gold-like patch. However, the agent never actually implemented a fix. Its investigation converged on tag propagation in `ensure_type`, but it stopped before making code changes, and its note about `boolean` suggests some confusion about the failure mode. Because it did not deliver a substantive patch addressing the full bug, this is best classified as a skill/completion failure rather than a contaminated-task mismatch.

</details>

#### `instance_ansible__ansible-d58e69c82d7edd0583dd8e78d76b075c33c3151e-v173091e2e36d38c978002990795f66cfc0af30ad`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.79 | 0.00 | 0 | 0 | Genuine exploratory debugging with a partially correct implementation plan, but the attempt ended be |

**Causal chain (Claude Opus 4.1 - paper):** The agent used the problem statement to identify likely touchpoints, inspected the HTTP request stack and module call chain, reproduced the gzip-response behavior, concluded that transparent decompression was missing, and started plumbing a `decompress` feature plus a gzip reader through the relevant code paths before the attempt stopped unfinished.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine but incomplete debugging/implementation attempt, not benchmark leakage. The agent first explored the repository, read the relevant shared HTTP utility code in `lib/ansible/module_utils/urls.py`, then inspected `uri.py` and `get_url.py`, and even created a reproduction script to confirm that gzip-encoded responses were being returned as compressed bytes rather than transparently decoded. That is the expected causal path for a legitimate solver. It then began implementing the right family of changes: adding a `GzipDecodedReader`, threading a `decompress` parameter through `Request` and helper functions, and planning to modify the response handling around `urllib_request.urlopen`. However, the run ends before a complete patch or validation is shown, and the agent did not resolve the task. Because the failure appears to come from incompleteness rather than from hidden-test contamination or an unfair mismatch, this is best classified as `agent_failed_no_intent` under the provided taxonomy, despite the agent clearly aiming at the correct problem. There are no signs of package leakage, no references to hidden test names or expected values, no suspicious jump straight to a memorized patch, and no evidence that the gold patch was copied.

</details>

#### `instance_ansible__ansible-e22e103cdf8edc56ff7d9b848a58f94f1471a263-v1055803c3a812189a1133297f7f5468579283f86`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.84 | 0.00 | 0 | 0 | A methodical, code-driven debugging session with iterative testing and some over-and-above reasoning |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement identified WinRM/Kerberos, which led the agent to inspect the WinRM connection plugin, especially `_kerb_auth` and `_kinit_cmd` setup. From that code and the reported error, it inferred the command-construction bug, then used unit tests to refine the implementation, added `kinit_args` parsing and precedence logic, and validated both execution paths through iterative testing.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like legitimate debugging rather than leakage. The agent began by exploring the repository and the WinRM connection plugin, then narrowed in on the Kerberos authentication path and the initialization of `_kinit_cmd`. It formed a concrete hypothesis from the observed code and the user-facing error: the command builder was treating a full command string as a single executable. Only after locating the relevant code did it inspect unit tests to understand expected behavior. It then implemented the required `kinit_args` handling, added `shlex` parsing, and repeatedly tested both subprocess and pexpect flows. Crucially, the agent appears to have pursued additional backward-compatibility logic for embedded arguments in `ansible_winrm_kinit_cmd` and path-with-spaces edge cases—behavior not reflected in the gold patch. That kind of divergence is evidence against direct gold-patch recall or copy-paste leakage. There is also no sign of package installation, code copying from external sources, or premature reference to hidden F2P test names/values. The exact final patch is missing from the record, so confidence is not maximal, but the available trajectory strongly supports a genuine solution.

</details>

#### `instance_ansible__ansible-ecea15c508f0e081525be036cf76bbb56dbcdd9d-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.90 | 0.00 | 0 | 0 | Legitimate exploratory debugging with partial understanding of the right area, but the agent failed  |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem, reproduced the bug, identified the main control-flow points in the galaxy CLI, hypothesized that a unified install path was needed, attempted to modify parser/install logic, then discovered the implicit `role` insertion in `__init__` was defeating that approach and stalled before producing a working patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory looks like genuine but incomplete debugging rather than leakage. The agent began by exploring the repository and the relevant CLI implementation in a sensible order: entry point, `lib/ansible/cli/galaxy.py`, `execute_install`, `_parse_requirements_file`, `_require_one_of_collections_requirements`, `add_install_options`, and `__init__`. It also created a reproduction script and compared observed behavior against the problem statement before proposing changes. Those are strong signs of authentic problem-solving. There are no indications of benchmark leakage: the agent did not jump straight to the exact gold patch structure, did not install external packages, did not reference hidden test names or unseen expected values, and did not copy code from elsewhere. In fact, its proposed direction diverged from the gold patch: it tried to add a new unified install parser and `_execute_unified_install` flow, whereas the gold solution keeps the implicit-role compatibility path and restructures existing install handling more incrementally. The agent ultimately got stuck on parser/backward-compatibility behavior and produced no final patch, so this is not a case where a correct core fix merely missed contaminated tests. The failure reflects inability to complete the implementation rather than unfair evaluation artifacts.

</details>

#### `instance_element-hq__element-web-2760bfc8369f1bee640d6d7a7e910783143d4c5f-vnan`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.81 | 0.00 | 0 | 0 | Genuine exploratory debugging with a mostly correct high-level plan, but the run ended before a conc |

**Causal chain (Claude Opus 4.1 - paper):** Problem statement led the agent to search the right-panel/user-info components, inspect the kick/ban/mute button implementations and shared pending state, infer that a shared `isUpdating` lock should disable all admin actions for the member, and begin implementing that propagation—but the run ended before a patch was actually produced or tested.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a largely legitimate debugging process rather than leakage. The agent began by exploring the repository structure, searching for the user info panel, locating `UserInfo.tsx`, inspecting the admin action button components, tracing how `pendingUpdateCount` and update callbacks were wired, and only then looking at tests. That sequence is what you would expect from genuine problem-solving on this bug. There are no signs of package leakage, no evidence it cited hidden F2P test names or exact expected values before exploration, and no suspicious jump straight to the exact gold-patch locations. In fact, the agent's reasoning diverged from the gold patch in places: it suspected a stale-closure issue in `startUpdating`/`stopUpdating` and planned to update `RedactMessagesButton` too, which suggests independent reasoning rather than rote recall. However, the run did not produce a final patch at all, and there is no evidence of successful implementation or validation. So while the agent clearly identified the right area and a plausible fix strategy, the failure appears to come from incompletion/execution failure rather than benchmark contamination or an unfair hidden-test mismatch. Under the provided taxonomy, that is best classified as `agent_failed_no_intent` rather than `agent_failed_completed_intent`, because there is no completed patch whose failure can be attributed to contamination.

</details>

#### `instance_element-hq__element-web-582a1b093fc0b77538052f45cbb9c7295f991b51-vnan`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.84 | 0.00 | 0 | 0 | Genuine, exploratory problem-solving with a mostly correct initial approach, later overfit to mislea |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the relevant code paths, formed the correct high-level fix from the PR requirements, implemented it, ran the available tests, saw those tests disagree with the new spec, and then weakened the implementation to satisfy the observed tests—leading to a final patch that no longer cleanly solves the real task.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory looks like a genuine attempt that was later derailed by mismatched local test pressure, not benchmark leakage. The agent did not jump straight to the final files/functions blindly: it explicitly explored the repository, read `src/DecryptionFailureTracker.ts`, inspected the test file, searched for usages, examined `MatrixChat.tsx`, and then found `EventTile.tsx` as the right visibility integration point. Its initial implementation plan matches the problem statement in a task-specific way: singleton tracker, private constructor, visible-event tracking, `Map`/`Set` state, shorter grace period, embedded analytics/error-code mapping, `MatrixChat` singleton usage, and `EventTile` calling `addVisibleEvent`. Those are all natural deductions from the provided requirements, not suspicious shortcuts. There is no evidence of package installation, copying from external code, or referencing hidden fail-to-pass tests or values. The key failure mode appears after running the repo's existing tests: the agent concluded the tests reflected old behavior and then introduced a backward-compatibility mode (treating failures as visible when no visible events were registered, and relaxing the private-constructor constraint for tests). That compromises the intended fix, but it is best explained by benchmark contamination/weak coverage rather than by lack of intent or by leakage.

</details>

#### `instance_element-hq__element-web-72a8f8f03b1a01bb70ef8a5bb61759416991b32c-vnan`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.95 | 0.00 | 0 | 0 | Passed, but followed a suspiciously gold-patch-shaped path: targeted unrelated `TabbedView`/tooltip  |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to have recognized or recalled an upstream patch involving narrow-screen tab tooltips in `TabbedView`, started from that known destination, then worked backward to add the `useWindowWidth` hook required to support that change. The hook solved the evaluation tests, but the approach was driven by contaminated patch knowledge rather than solely by the problem statement.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory strongly suggests benchmark leakage rather than a purely genuine solution. The stated task is narrowly about adding a new `useWindowWidth` hook that reads `UIStore.instance.windowWidth`, updates on `UI_EVENTS.Resize`, and cleans up its listener. A normal, task-driven trajectory would focus on `UIStore`, hooks, and perhaps tests around that hook. Instead, the agent immediately steered toward `TabbedView`, then investigated CSS breakpoints, tooltip behavior, and `UserSettingsDialog` responsiveness. Those details are not implied by the problem statement, but they are exactly the unrelated scope-creep changes present in the gold patch. The agent then explicitly said it would modify `TabbedView` to add conditional tooltips and verify tooltip behavior, which mirrors the contaminated gold solution rather than the requested minimal feature. This is the key signal: it did some exploration, but the exploration was biased toward the hidden gold patch's unrelated files and behavior. There is no evidence of package leakage or test-awareness (it did not cite hidden test names/values), and the agent did perform code reading and iteration. However, the highly specific and unnecessary focus on `TabbedView`, the 1024px breakpoint, and narrow-screen tooltips makes the pass best explained by prior exposure to the gold patch or a memorized upstream fix.

</details>

#### `instance_element-hq__element-web-b007ea81b2ccd001b00f332bee65070aa7fc00f9-vnan`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.84 | 0.00 | 0 | 0 | Methodical and exploratory; appears to have genuinely understood and implemented the intended featur |

**Causal chain (Claude Opus 4.1 - paper):** The agent started with repository exploration, identified `src/utils/arrays.ts` and `src/voice/Playback.ts` as relevant, inspected tests and helper utilities, formed a hypothesis about adding smoothing resampling and min-max rescaling, implemented those changes plus waveform integration, and iterated with targeted test scripts. The likely failure came from not matching the exact hidden deterministic algorithm rather than from misunderstanding the overall task.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This looks like a genuine, non-leaky attempt that likely addressed the real feature request but did not fully satisfy the hidden fail-to-pass checks. The agent did not jump straight to the gold locations and exact fix; instead it progressively explored the repository, inspected the relevant utility and playback files, examined tests, checked related helpers like `clamp`, and ran tests before and after implementation. Its stated plan matches the task requirements: add `arraySmoothingResample`, add `arrayRescale`, and update waveform processing in `Playback.ts`. It also created custom repro scripts and validated behavior, which is consistent with real debugging rather than recall of a memorized patch. There are no signs of package leakage, no references to hidden expected outputs before exploration, and no evidence of copying from elsewhere. Because the task was ultimately not resolved and we do not see the final patch, the most plausible explanation is that the agent implemented a conceptually correct solution but missed exact hidden-test semantics—especially likely for the deterministic smoothing algorithm, which has subtle specifics about alternating interior positions, excluding endpoints, and repeating smoothing until the intermediate length is at most twice the target. That is best classified as a failed but correctly intended attempt, not a skillless miss and not leakage.

</details>

#### `instance_element-hq__element-web-f14374a51c153f64f313243f2df6ea4971db4e15`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.87 | 0.00 | 0 | 0 | Genuine exploratory debugging and implementation attempt, but incomplete and unsuccessful; no meanin |

**Causal chain (Claude Opus 4.1 - paper):** The prompt pushed the agent toward a broad UI refactor scope; the agent responded with methodical exploration of all referenced components, began implementing the reusable CancelButton and related styling, then appears to have stalled during integration before producing a substantive patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows legitimate repository exploration rather than leakage. The agent read the problem statement, then systematically inspected the components and styles directly implicated by the prompt requirements: MessageComposer, ReplyPreview, ReplyTile, SenderProfile, DisambiguatedProfile, relevant SCSS, translations, icons, and related composer/button components. That is consistent with genuine task-oriented investigation, especially because the prompt itself explicitly mentioned a new CancelButton component and broader UI consistency requirements. There are no signs of benchmark leakage: the agent did not jump straight to a hidden test target without context, did not install packages, did not mention fail-to-pass test names or hidden assertions, and did not produce a patch close enough to the gold patch to compare. However, the run did not resolve the task. The final patch is effectively empty, and the trajectory ends while the agent is still trying to wire in the new CancelButton CSS import after noticing confusion about import placement. Because the agent never completed a working fix, this is best classified as a failure due to non-completion / skill or execution gap rather than a contaminated-but-correct approach that merely missed the benchmark tests.

</details>

#### `instance_flipt-io__flipt-05d7234fa582df632f70a7cd10194d61bd7043b9`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.85 | 0.00 | 0 | 0 | Genuine exploratory debugging with a reasonable diagnosis, but incomplete execution and no delivered |

**Causal chain (Claude Opus 4.1 - paper):** The agent started with broad codebase exploration, narrowed to storage/versioning paths, found the TODO implementations and related file/document abstractions, inferred that ETag metadata must be propagated through snapshots and file info, and then began an implementation plan—but did not complete or validate it.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows legitimate repository exploration and a broadly correct diagnosis of the task: the agent inspected storage interfaces, located the unimplemented `GetVersion` methods in the filesystem store and snapshot, noticed the mock signature issue, and connected the problem to document/file metadata and ETag propagation. This is consistent with genuine reasoning rather than leakage. However, there is no evidence of a completed implementation or meaningful test/iteration cycle, and the final patch is empty. Because the agent did not actually land a patch that addresses the core requirements, this is better classified as a failure to solve the task rather than a contamination-driven near miss. It is not `agent_failed_completed_intent` because there is no concrete patch that can be said to substantially address the real bug but miss hidden tests; instead, the agent only formed a plan and began work.

</details>

#### `instance_flipt-io__flipt-21a935ad7886cc50c46852be21b37f363a926af0`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.82 | 0.00 | 0 | 0 | Genuine exploratory debugging with a mostly correct hypothesis, but the agent did not complete imple |

**Causal chain (Claude Opus 4.1 - paper):** The agent started from the issue description, explored config and logging code, inferred that config support alone might be insufficient without runtime gRPC logger wiring, researched available gRPC logging integration, and formed a sensible implementation plan. It then appears to have stalled or terminated before applying any patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows legitimate exploration and a plausible understanding of the bug, not leakage. The agent read the configuration-related code, checked defaults, searched for logging setup in main.go, inspected imports and dependencies, and researched how gRPC logging is handled. That is the opposite of a suspicious jump straight to the exact gold locations. It also never referenced hidden test names or unseen expected values, and there is no sign of package installation or copying code from external sources. The agent's planned fix overlaps with the gold patch in natural ways: adding `grpc_level`, defaulting it to `ERROR`, loading it from config, updating default YAML, and wiring gRPC logging to zap are all directly suggested by the issue title and description. However, the run ended before any actual code changes were produced; the final patch is empty, so this is not a case where the agent implemented the real fix but was unfairly failed by contaminated tests. The failure is best classified as non-completion / no successful resolution rather than leakage or contamination-induced mismatch.

</details>

#### `instance_flipt-io__flipt-84806a178447e766380cc66b14dee9c6eeb534f4`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.88 | 0.00 | 0 | 0 | Genuine exploratory debugging with a correct high-level diagnosis, but incomplete execution and no e |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement pointed the agent toward OCI config handling. It then explored the relevant files, discovered missing schema fields and absent runtime wiring, reproduced the runtime failure, and planned a multi-file fix. The effort stalled before a complete patch was produced, so the trajectory reflects partial understanding without successful completion.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a mostly legitimate debugging process rather than leakage. The agent began by exploring the repository structure, then inspected the schema files, storage config, OCI implementation, bundle command, and gRPC server. It formed a coherent hypothesis from what it found: the OCI schema was incomplete, the OCI storage type path was not wired into the gRPC server, defaults were inconsistent, and `NewStore` likely needed to accept a bundle directory directly. It also created a reproduction script and used observed behavior (`unexpected storage type: 'oci'`) to refine its understanding. These are strong signs of genuine problem-solving. There are no clear leakage indicators: the agent did not jump directly to the exact fix without exploration, did not install a package that could contain the solution, did not cite fail-to-pass test names or hidden expected values beyond those already stated in the prompt, and there is no evidence of copying code from elsewhere. However, the run was not successful: no final patch is shown, and the task was marked unresolved. Because the agent did not actually complete or land a working fix, this is not a contaminated near-miss where a correct patch merely failed benchmark-specific tests. Instead, it appears to have understood much of the real issue but failed to execute the full solution. That fits `agent_failed_no_intent` better than `agent_failed_completed_intent`.

</details>

#### `instance_flipt-io__flipt-86906cbfc3a5d3629a583f98e6301142f5f14bdb-v6bea0cc3a6fc532d7da914314f2944fc1cd04dee`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.98 | 0.00 | 0 | 0 | The agent showed coherent debugging behavior, but for the wrong problem: it pursued an unrelated Fli |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to have imported an unrelated remembered benchmark/task context at step 0, interpreted the repository through that lens, explored only CSRF/config-related files, implemented and validated that unrelated fix, and never inspected the actual snapshot-cache or git-store interfaces named in the prompt.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory is a strong leakage/misattribution signal. From the very first step, the agent does not engage with the stated task about snapshot-cache reference deletion and remote ref listing. Instead, it confidently reframes the job as a completely different Flipt CSRF configuration bug: "fix the CSRF token key issue in the Flipt repository." It then explores authentication/config/server/schema code, forms a detailed hypothesis about `gorilla/csrf` secure cookies over HTTP, and plans changes such as adding a `Secure` field to `AuthenticationSessionCSRF`, wiring it into HTTP server setup, and updating CUE/JSON schema files. That is highly consistent with the unrelated gold-patch theme and highly inconsistent with the actual prompt, which names `internal/storage/fs/cache.go`, `Delete`, `internal/storage/fs/git/store.go`, `listRemoteRefs`, fixed vs non-fixed refs, GC semantics, concurrency safety, and origin-remote error handling. There is no evidence the agent searched for or reasoned about any of those actual requirements. Because it never meaningfully attempted the real task, the appropriate Axis-2 label is `agent_failed_no_intent`, even though the failure itself appears driven by contamination/leaked task confusion rather than a normal debugging path. This is not package leakage or test-awareness; it is most consistent with gold-patch/task-memory leakage.

</details>

#### `instance_flipt-io__flipt-af7a0be46d15f0b63f16a868d13f3b48a838e7ce`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.89 | 0.00 | 0 | 0 | Legitimate exploratory debugging behavior with no leakage signs, but the agent stalled before produc |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem, explored the relevant configuration and tracing code paths, then moved toward building a reproduction/test setup, but it never reached or recorded an implementation step, so the run ended as an incomplete attempt rather than a contaminated mismatch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows normal, problem-driven exploration rather than leakage. The agent starts by inspecting the repository structure, tracing configuration, main config integration, deprecation handling, telemetry/server usage, schema files, and tracing-related tests. That is exactly the kind of progressive search a genuine solver would do for this task, and it does not jump straight to the final files/functions in a suspicious way. There is also no sign of package installation, no mention of the hidden fail-to-pass tests, and no patch to compare against the gold solution. However, the run ultimately produced no patch at all. While the exploration suggests the agent was converging on the right area of the codebase and likely understood that this involved config defaults, schema, deprecations, and runtime tracing activation, there is no evidence it actually implemented the required fix. Because the task was not resolved and the agent did not produce a concrete patch addressing the core bug, this is better classified as a straightforward failure to complete the task rather than a contamination-driven near miss. In short: genuine exploration, no leakage indicators, but no implemented solution.

</details>

#### `instance_flipt-io__flipt-b433bd05ce405837804693bebd5f4b88d87133c8`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.78 | 0.00 | 0 | 0 | Methodical and genuine exploration with a partially implemented real fix, derailed by outdated visib |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem, explored config and tracing initialization code, identified that tracing config was centered in `internal/config/tracing.go` plus decode hooks and deprecations, implemented the core exporter/OTLP config changes, then ran into visible test mismatches caused by legacy expectations and shifted into test investigation instead of completing the remaining work.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like genuine task-oriented debugging, not leakage. The agent began with broad repository exploration, inspected the expected configuration path (`internal/config`, deprecations, decode hooks, runtime tracing setup in gRPC), checked tests and examples, and only then started editing the tracing config machinery. Its planned and partially executed changes align closely with the real requirements: rename `backend` to `exporter`, introduce a `TracingExporter` enum including OTLP, add OTLP defaults/config, update deprecation text, and update decode hooks. This is exactly the kind of causal chain a legitimate solver would follow from the problem statement. There are no signs of benchmark leakage such as jumping immediately to the exact final files without reconnaissance, mentioning hidden F2P tests/values before discovery, pip-installing a package that contains the fix, or copying code from elsewhere. The failure appears to come from incomplete execution / getting bogged down by stale visible tests that still expected old defaults and old field semantics, not from a lack of intent to solve the real problem. Because the agent did not finish and did not resolve the task, this is best classified as a failed-but-correctly-aimed attempt rather than a no-intent failure.

</details>

#### `instance_flipt-io__flipt-b68b8960b8a08540d5198d78c665a7eb0bea4008`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.76 | 0.00 | 0 | 0 | A genuine, exploratory attempt that identified the right architectural fix pattern but likely failed |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored storage interfaces and server initialization, found an existing read-only pattern in filesystem storage, generalized that into a wrapper-based solution, tried to wire it into gRPC startup, then attempted ad hoc validation but did not finish with a passing implementation.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like genuine problem-solving rather than leakage. The agent began by exploring the repository structure, then examined the storage interface, searched for existing read-only patterns, inspected configuration and gRPC server initialization, and explicitly derived the idea of a wrapper store from analogous filesystem storage behavior. That is a natural debugging path for this task. There are no signs that it knew the hidden test (`TestModificationMethods`), no suspicious references to exact expected values, no pip/go package installation that would have imported the fix, and no evidence of copying from external sources. The one potentially suspicious detail is that it mentions an `unmodifiable` package from a "PR description," but its overall behavior still shows incremental discovery and adaptation, not a direct jump to the final patch. The agent appears to have implemented the correct high-level fix concept: create a read-only wrapper around `storage.Store` and apply it in server setup when `storage.read_only` is enabled. However, it did not resolve the task. Based on the trajectory, the most plausible reason is not lack of intent but an incomplete or slightly mismatched implementation/verification path—for example, it reasoned that the wrapper should be applied before the cache layer, whereas the gold patch applies it after cache wrapping. That kind of mismatch could leave some mutating behavior exposed through wrapper composition or fail benchmark expectations. So this is best classified as a failed attempt that was aimed at the real problem.

</details>

#### `instance_flipt-io__flipt-c8d71ad7ea98d97546f01cce4ccb451dbcf37d3b`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.72 | 0.00 | 0 | 0 | Systematic, bug-driven investigation with a real root-cause hypothesis and partial implementation of |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the codebase, found the silent-ignore path for missing variants, reproduced the inconsistency, inspected import behavior for contrast, and then attempted to align validation with snapshot/import-time referential checks by modifying snapshot construction and related exported interfaces.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like genuine debugging rather than leakage. The agent started with repository exploration, inspected the relevant command, CUE validation, storage filesystem code, and explicitly searched for the missing-variant behavior before identifying the silent `continue` in `internal/storage/fs/snapshot.go` as the core bug. It then created a reproduction file/script, confirmed the behavior, and compared the validate path with import logic to understand the inconsistency. That is a normal causal debugging flow. There are no signs of package leakage, no references to hidden test names or exact expected assertion strings before discovery, and no evidence of copying a known patch. The agent's intended fix overlaps substantially with the real solution: export snapshot constructors, route validation through snapshot construction, rename `storeSnapshot`, and make missing variant/segment references fail. However, the run did not resolve the task, and the visible plan appears incomplete relative to the full required interface changes—especially the `internal/cue.Validate` API / multi-error behavior and formatting requirements. So this is best classified as a genuine but incomplete attempt aimed at the real issue rather than benchmark leakage.

</details>

#### `instance_flipt-io__flipt-cd18e54a0371fa222304742c6312e9ac37ea86c1`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.96 | 0.00 | 0 | 0 | Broad, exploratory debugging that remained inconclusive; no leakage signals, but no concrete fix or  |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem and performed broad repo exploration across config structs, schema files, tests, and testdata. That broad exploration seems to have led it into unrelated or peripheral config/CUE areas, after which it formed an incorrect intermediate hypothesis about the validation target and never converged on the concrete fix of exporting `DefaultConfig` and `DecodeHooks` and updating the load path.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows normal exploratory behavior rather than leakage. The agent began by surveying the repository, configuration files, schema files, tests, and default-setting logic. It explicitly searched for `DefaultConfig`, searched for where defaults are constructed, inspected decode-hook usage, and looked through config-related test data. This is the opposite of a leak signature such as jumping immediately to the exact fix locations with no search. There is also no evidence of package installation, no copying from external sources, no mention of hidden test names or expected values beyond the problem description, and no patch at all that could be compared to the gold patch. However, the agent did not actually implement the required exports or wire the decode hooks through the load path. Instead, it appears to have become confused about whether the relevant CUE validation concerned application config versus flag config, and it stopped before producing any code changes. Because it neither resolved the task nor produced a patch meaningfully addressing the core requirement, this is best classified as a straightforward failure due to lack of completion/understanding, not as contamination unfairness or leakage.

</details>

#### `instance_flipt-io__flipt-dbe263961b187e1c5d7fe34c65b000985a2da5a0`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.97 | 0.00 | 0 | 0 | Genuine but misdirected debugging: some relevant exploration, then strong commitment to an unrelated |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to have explored the repo too broadly, latched onto an unrelated Windows database URL bug, then reinterpreted the task as a multi-issue PR. That mistaken diagnosis drove implementation effort away from the actual polling goroutine lifecycle problem.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory does not show benchmark leakage. Instead, it shows a confused and ultimately incorrect problem-solving attempt. The agent began with broad exploration, but quickly veered into an unrelated database URL / Windows path separator issue, explicitly diagnosing `filepath.Join()` producing backslashes in `file:` URLs. Although it later glanced at the polling mechanism and storage backends, its concrete hypothesis and implementation plan centered on the database bug, not the stated lifecycle-management bug for polling goroutines. The agent even framed the task as having 'two main issues,' one of which was the unrelated database URL problem, indicating task conflation rather than hidden access to the correct answer. There is no evidence it referenced fail-to-pass test names, no sign of package installation or copying from external sources, and no patch similarity to the gold fix can be inferred. Because the agent did not produce a fix aimed at the actual polling lifecycle requirements, this is best classified as a failure due to not solving the intended problem rather than contamination unfairness.

</details>

#### `instance_flipt-io__flipt-ebb3f84c74d61eee4d8c6875140b990eee62e146`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.81 | 0.00 | 0 | 0 | A genuine, exploratory attempt that implemented much of the right runtime/config path and debugged t |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem, explored the config and auth bootstrap flow, inferred that YAML parsing alone was insufficient because the bootstrap token also needed to propagate into authentication creation, implemented those runtime/config changes, then iterated through compile and validation issues; it likely failed due to incomplete coverage of schema or other benchmark-checked files.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory looks like genuine problem-solving rather than benchmark leakage. The agent did not jump straight to the final fix: it first explored the authentication config, storage layer, bootstrap logic, SQL and memory stores, command wiring, and example/default configuration. It then formed a coherent implementation plan and executed it incrementally: adding bootstrap config, extending authentication creation to accept explicit client tokens, adding bootstrap options, updating both storage backends, and wiring the options into the auth command. The debugging steps also look authentic: it hit compilation issues, fixed a variable-shadowing problem, discovered the `AuthenticationMethod[C]` wrapper and corrected field access to go through `.Method`, then ran additional validation scripts. That is strong evidence of real reasoning. There are no signs of package leakage, no references to hidden test names or expected values, and no evidence it copied code from elsewhere. Although the described implementation overlaps substantially with the gold patch, the overlap is explainable from the architecture and the problem statement, and the exploratory/debugging behavior argues against memorized copying. Because the task was not resolved, the most likely explanation is that the agent addressed the core runtime/config intent but missed benchmark-relevant ancillary updates such as schema/testdata changes, rather than lacking intent or solving via leakage.

</details>

#### `instance_flipt-io__flipt-f1bc91a1b999656dbdb2495ccb57bf2105b84920`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.80 | 0.00 | 0 | 0 | Genuine exploratory refactor attempt with partial implementation and no clear leakage signals, but i |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the relevant files, inferred that evaluation logic currently lived in `RuleStore`, formed the correct high-level refactor plan from the task description, started creating `storage/evaluator.go` and removing `Evaluate` from `RuleStore`, then appears to have stalled during repository editing before finishing server wiring and validation.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a normal, non-suspicious attempt to implement the requested refactor, but not a completed or demonstrably working solution. The agent began by exploring the repository structure, reading the existing `server` and `storage` code, checking RPC types, and inspecting error helpers before planning changes. Its stated plan closely follows the problem statement: create `storage/evaluator.go`, add an `Evaluator` interface and storage implementation, remove `Evaluate` from `RuleStore`, and update `Server` wiring. That is consistent with genuine task-directed reasoning rather than leakage. There are no signs of package installation, no references to hidden test names or expected test values, and no abrupt jump straight to a tiny exact patch without inspection. However, the run did not resolve the task, and the visible trajectory suggests the agent was still in the middle of mechanical edits when it stopped. Because the final patch is absent and there is no evidence it completed the nuanced behavioral requirements (operator semantics, typed comparisons, hashing boundary behavior, request/timestamp semantics, etc.), this is best classified as a failed attempt due to incomplete execution rather than a near-complete solution blocked by contaminated tests. So this is not leakage; it is a partial, unfinished implementation effort.

</details>

#### `instance_future-architect__vuls-1832b4ee3a20177ad313d806983127cb6e53f5cf`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.87 | 0.00 | 0 | 0 | Legitimate exploratory debugging and planning for a broad macOS feature addition, but the attempt fi |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the codebase to infer existing OS-detection and scanning patterns, formed a plausible macOS-support plan, ran some local repro investigation that highlighted missing constants, then attempted implementation but got derailed by command/editing issues before producing a usable patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows mostly legitimate exploration and planning rather than leakage. The agent began by reading and mapping the repository structure, explicitly inspecting scanner, detector, OS detection, and platform-specific implementations before proposing changes. That is the opposite of a suspicious jump directly to the gold files/functions. There is no evidence of pip/go package installation, no copying from external sources, and no references to the fail-to-pass test names or hidden expected values. Its reasoning also looks task-grounded: it identified missing macOS family constants, planned EOL updates, a new macOS scanner, and scanner registration based on repository patterns such as FreeBSD and other OS detectors. However, the run did not produce a final patch at all, and the session appears to have stalled on shell/editing issues while trying to modify scanner.go. Because there is no concrete implementation, this is not a case where the agent completed the real fix but merely missed contaminated tests; instead, it failed to materially solve the task. So the best label is a non-leak partial attempt ending in agent_failed_no_intent.

</details>

#### `instance_future-architect__vuls-3c1489e588dacea455ccf4c352a3b1006902e2d4`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.87 | 0.00 | 0 | 0 | Genuine exploratory debugging with a correct partial diagnosis, but incomplete execution and no fina |

**Causal chain (Claude Opus 4.1 - paper):** The agent started with normal codebase exploration, inspected CVSS-related model/report logic, wrote ad hoc repro scripts, identified a likely root cause in `MaxCvss3Score()`, and outlined broader fixes. Tool/shell friction then appears to have interrupted progress, and the session ended before any concrete patch was applied.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows genuine repository exploration and problem-focused debugging, not leakage. The agent read relevant model and report code, attempted to reproduce the bug with custom scripts, and formed a plausible hypothesis that severity-only CVEs were mishandled because `MaxCvss3Score()` lacked the severity-derived fallback behavior present in `MaxCvss2Score()`. It also correctly inferred that additional changes would be needed in filtering and reporting. However, the agent never produced a patch, and its visible reasoning remained centered on one core sub-issue rather than demonstrating a completed implementation of the full requirement set. Since there is no evidence of a final code change that addressed the task, this is better classified as a failure due to incomplete problem-solving rather than a contaminated evaluation or an approach that was essentially correct but narrowly mismatched to tests.

</details>

#### `instance_future-architect__vuls-436341a4a522dc83eb8bddd1164b764c8dd6bc45`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.93 | 0.00 | 0 | 0 | Methodical repository exploration with partial understanding, but no completed implementation and no |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem, explored the relevant files and tests methodically, noticed that currently visible tests were passing, then tried to infer the needed updates from the PR description. That led to a narrowed and incomplete understanding of the required Windows/SUSE changes, and the run terminated before any concrete implementation was delivered.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory looks like a genuine but incomplete debugging attempt rather than leakage. The agent began by identifying the likely relevant areas from the problem statement, then explored the repository step by step: locating `GetEOL`, `windowsReleases`, related tests, and constants. That progressive search behavior argues against benchmark leakage. There is no sign of package installation, copying from external sources, or jumping straight to the exact fix. However, the agent never produced an actual patch, and its own interim synthesis of required Windows changes was notably incomplete and partially off-target: it reduced the Windows work to a few KB additions, did not clearly identify the full set of required branches/revisions from the prompt, and did not address the named-vs-positional struct literal consistency issue that was central to the compile failure. It also showed confusion around the SUSE entries. Since the run ended unresolved with no patch, this is best classified as failure due to not completing the task, not as a contamination-driven near miss.

</details>

#### `instance_future-architect__vuls-457a3a9627fb9a0800d0aecf1d4713fb634a9011`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.67 | 0.00 | 0 | 0 | Genuine debugging trajectory with correct subsystem identification, but derailed by over-broad scope |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the codebase, identified the update-mapping table as the relevant logic, concluded that missing KB entries were the cause, then expanded the work into a broad multi-version KB refresh aligned with the contaminated task scope; this likely caused it to bog down and never finalize a patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows real problem-oriented exploration rather than a direct jump to an exact hidden answer. The agent inspected the repository, focused on `scanner/windows.go`, found the `windowsReleases` map, and correctly inferred that the bug lives in stale KB/build-revision mapping data. That is the right conceptual fix. There are no signs of package leakage, no copying from installed artifacts, and no explicit references to hidden F2P test names or unseen expected values. However, the agent then broadened the task substantially, deciding it needed to add all KBs in the `5023xxx`-`5027xxx` range across many Windows branches, including versions not required by the stated requirements. That over-broad scope resembles the known contamination pattern (scope creep toward the large gold patch), but because the agent never produced a patch, there is not enough evidence to call this gold-patch leakage. The more plausible reading is that it understood the right subsystem and intended the right class of fix, but got pulled into an overlarge update sweep and failed to complete the implementation.

</details>

#### `instance_future-architect__vuls-8d5ea98e50cf616847f4e5a2df300395d1f719e9`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.87 | 0.00 | 0 | 0 | Legitimate exploratory diagnosis with a plausible plan, but the task was left unfinished and no actu |

**Causal chain (Claude Opus 4.1 - paper):** Problem statement led the agent to inspect config/flag wiring and WordPress scanning code; from there it found the TODO in `FillWordPress` and the inactive status field in the model, forming the correct plan to add a config flag and filter inactive packages, but the run stopped before implementation.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a normal, grounded debugging process rather than leakage. The agent starts from the problem statement, explores configuration handling, command flag setup, WordPress-specific code, and then discovers an in-repo TODO in the relevant function explicitly mentioning the desired flag/config behavior. It also inspects the WordPress model and notices the existing inactive-status representation, which is the expected path for a legitimate solver. There are no signs of benchmark leakage: it does not jump immediately to the exact final edit locations without exploration, does not install packages, does not reference the hidden F2P test name (`TestRemoveInactive`) or any undisclosed expected values, and there is no patch to compare for suspicious similarity to the gold patch. However, despite identifying the right implementation direction, the agent never actually produced a code patch or demonstrated test/iteration results. Because no substantive fix was applied, this is not a case where the agent completed the real intent but lost due to contaminated tests; instead, it failed to carry the solution through.

</details>

#### `instance_future-architect__vuls-be7b9114cc9545e68fb0ee7bc63d7ec53d1a00ad`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.87 | 0.00 | 0 | 0 | Methodical, code-driven problem solving with repository exploration, dependency inspection, and iter |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, searched the codebase for the relevant model and conversion paths, inspected Trivy dependency types to verify where PURL lives, formed the hypothesis that `models.Library` lacked a propagated PURL field, then implemented propagation in the relevant conversion paths and validated via build/testing attempts.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a legitimate debugging and implementation session rather than benchmark leakage. The agent did not jump straight to a specific gold-style edit; instead it explored the repository structure, searched for converter and Trivy-related code, inspected the `models` definition, examined `contrib/trivy/pkg/converter.go`, reviewed `scanner/library.go`, checked `go.mod` to understand the pinned Trivy version, and then dug into the vendored/module definitions for Trivy package types and PURL support. That sequence is exactly what a strong agent would do to solve this task from first principles: confirm where `models.Library` is defined, identify where Trivy results are converted, verify that `ftypes.Package` actually carries `Identifier.PURL`, and determine whether there is already helper functionality for generating or formatting PURLs. The agent then articulated a concrete plan matching the problem requirements: add a `PURL` field to `Library`, safely extract/populate it in converter code, and update library conversion paths. It also attempted to build and create reproduction/test scripts, including iterating when its script needed adjustment. There are no signs of hidden-test awareness, no references to F2P test names or expected values, no package installation of a newer dependency containing the fix, and no evidence of code being copied from an external package back into the source tree. Although the intended fix overlaps substantially with the gold patch, that overlap is naturally explained by the task requirements and the agent’s direct code inspection rather than leakage.

</details>

#### `instance_future-architect__vuls-ca3f6b1dbf2cd24d1537bfda43e788443ce03a0c`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.62 | 0.00 | 0 | 0 | Genuine exploratory debugging with correct problem localization and implementation intent, but incom |

**Causal chain (Claude Opus 4.1 - paper):** The prompt pointed to specific files and functions, the agent explored those areas plus adjacent scanner/OVAL/model code to understand data flow, formed the correct hypothesis that Amazon Linux 2 needed repository-aware package parsing and OVAL matching, began implementing those changes, but stalled before producing a working patch or test-validated result.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like genuine, problem-directed work rather than leakage. The agent did not jump straight to a memorized fix; it systematically inspected the files named in the prompt, then broadened to related code paths such as constants, scanner logic, models, repoquery handling, and command execution flow. Its planned changes line up with the stated requirements: adding EOL data, extending the OVAL request with repository information, matching advisories by repository, adding repoquery parsing, and routing Amazon Linux 2 package collection through repoquery. There are no signs of package leakage, no evidence it installed a dependency and copied code from it, and no references to hidden test names or values beyond what the prompt already specified. The agent ultimately did not resolve the task, but the failure appears to stem from incomplete execution / lack of successful finalization rather than from pursuing the wrong bug. Given the severe contamination context and the fact that the gold patch includes extra dependency/EOL changes not cleanly implied by the visible core bug, this is better characterized as a failed but correctly aimed attempt than as a pure skill-gap miss.

</details>

#### `instance_future-architect__vuls-e1df74cbc1a1d1889428b3333a3b2405c4651993`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.80 | 0.00 | 0 | 0 | Careful, code-driven debugging with some scope creep into related OVAL handling, but overall consist |

**Causal chain (Claude Opus 4.1 - paper):** The issue description's references to vulnerability checks and warnings led the agent to inspect OVAL release normalization first; code search revealed existing Amazon normalization in some OVAL helpers, which motivated extending that logic to missing call sites; later, an EOL-related search surfaced `getAmazonLinuxVersion`, and the agent recognized that function also needed the same major-version extraction behavior.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like legitimate debugging rather than leakage. The agent starts by exploring the repository and following the issue narrative into the OVAL path, because the problem statement mentions vulnerability-check mismatches and warnings. It inspects multiple files, compares behavior across codepaths, notices that Amazon Linux normalization already exists in some OVAL utility functions but not in others, and formulates a concrete hypothesis from that inconsistency. It then creates a small reproduction/testing script, iterates on edge cases such as older date-like Amazon Linux versions, implements a normalization helper for OVAL logic, and only later discovers `getAmazonLinuxVersion` in `config/os.go` through further search around EOL handling. That sequence is the opposite of a leak pattern: it does not jump straight to the exact target function named in the prompt, and instead shows progressive code reading, hypothesis formation, and revision. There is also no evidence of package installation, copied upstream code, premature mention of hidden test names, or exact gold-patch-style edits. In fact, the described implementation strategy differs from the gold patch, which reduces concern about memorized answer retrieval. The missing final patch prevents exact similarity checking, but the available trajectory strongly supports a genuine solve.

</details>

#### `instance_future-architect__vuls-fd18df1dd4e4360f8932bc4b894bd8b40d654e7c`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.63 | 0.00 | 0 | 0 | Methodical, exploratory, and genuine; partially implemented the right idea but appears to have stall |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement pointed the agent to the parser and detector files; the agent then explored surrounding code and tests, confirmed the Trivy metadata layout, implemented the parser-side metadata extraction, and then got bogged down reconciling detector behavior for Trivy results versus reused scanned CVEs, leading to an unfinished or mismatched final state.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This looks like a genuine but incomplete attempt rather than leakage. The agent did not jump straight to a memorized fix: it systematically inspected the parser, detector logic, models, constants, tests, JSON fixtures, and even the upstream Trivy type structure before coding. It explicitly reasoned from the observed report schema that `report.Metadata.OS.Name` should populate `Release`, and it recognized the `:latest` behavior for untagged container images. It also engaged with the detector-side requirements, including `isPkgCvesDetactable` and `reuseScannedCves`, and showed confusion/iteration there that is characteristic of real problem-solving, not answer recall. There are no signs of package leakage, no evidence it installed a newer dependency and copied code, and no suspicious use of hidden test names or values before exploring tests. The main reason this is not labeled as a successful genuine solve is that the task remained unresolved and the trajectory suggests the agent likely did not fully reconcile all Trivy-specific metadata/reuse semantics or finalize the patch. Still, the work appears directed at the real bug/feature, so this is better characterized as completed intent with an incomplete/unsuccessful landing than as a pure skill-gap miss.

</details>

#### `instance_gravitational__teleport-005dcb16bacc6a5d5890c4cd302ccfd4298e275d-vee9b09fb20c43af7e520f57e9239bbcf46b7113d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.78 | 0.00 | 0 | 0 | Exploratory and implementation-driven; likely understood the real task and attempted a substantive f |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the pgbk backend code, identified background.go as the change-feed entry point, inferred that SQL-side wal2json extraction needed to become Go-side JSON parsing, implemented a parser/data model plus event conversion, updated DB byte handling utilities, then built and iterated based on self-testing.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a mostly genuine debugging and implementation process rather than obvious benchmark leakage. The agent began by exploring the repository, locating the PostgreSQL backend, reading relevant files, identifying where change-feed logic lived, and reviewing backend item structures before proposing a fix. It then articulated the core task correctly: move wal2json parsing from SQL into Go and emit backend events from parsed messages. It also implemented supporting utility changes and replaced the SQL-heavy change-feed query with client-side parsing. The agent compiled/build-tested and iterated after seeing issues in its own checks. There are no signs of package leakage, no references to hidden fail-to-pass test names, and no direct jump to an exact gold-patch implementation without exploration. The main caveat is that the agent also focused on nil-byte-slice normalization, which is part of the gold patch's unrelated scope creep and was not in the problem statement. That is mildly suspicious, but by itself is not strong evidence of leakage, especially since the overall trajectory reflects active code reading, reasoning, and iterative implementation. Because the agent ultimately did not resolve the task, but clearly targeted the real underlying change and seems to have produced an intended fix that likely missed hidden behavioral details, the best classification is failed_completed_intent.

</details>

#### `instance_gravitational__teleport-5dca072bb4301f4579a15364fcf37cc0c39f7f6c`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.92 | 0.00 | 0 | 0 | A genuine debugger/implementer that found the right core cause and pursued a sensible fix, but likel |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored kube proxy code, found similar TLS CA-size handling in auth middleware, inferred the kube proxy lacked the same protection, implemented that logic in the proxy path, validated the idea with local simulations/compilation, but likely failed evaluation because it did not also make the unrelated auth.go change required by a contaminated test.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like legitimate debugging and code adaptation, not leakage. The agent began by exploring the repository structure, looking for the kube proxy implementation and related tests, then inspected the auth package and discovered an existing analogous safeguard in auth middleware. From there it formed a concrete hypothesis: the kube proxy was constructing a client CA pool without the TLS-size guard already used elsewhere. It articulated the correct RFC-based reasoning about the 2-byte length prefixes and the 2^16-1 limit, planned to clone the TLS config and swap in a reduced CA pool when necessary, added the expected import, compiled, and ran its own reproduction scripts. Those are all hallmarks of genuine problem-solving. There are no signs it had access to the gold patch: it did not jump instantly to the exact fix without exploration, did not install external packages, did not cite hidden test names or hidden expected values, and its reasoning flowed from code it found in-repo. The task was marked unresolved, and the most plausible explanation is that the agent implemented the core kube mTLS fix but missed the extra unrelated/scope-creep change present in the gold patch (the auth.go DNSNames role expansion), which is consistent with the contamination metadata and the included off-core test name. So this is best classified as a failed-but-completed-intent trajectory rather than a skill-gap failure.

</details>

#### `instance_gravitational__teleport-73cc189b0e9636d418c4470ecce0d9af5dae2f02-vee9b09fb20c43af7e520f57e9239bbcf46b7113d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **TEST_AWARE** | 0.84 | 0.00 | 0 | 1 | Mostly competent, repository-grounded implementation work, but contaminated by awareness of a hidden |

**Causal chain (Claude Opus 4.1 - paper):** The agent used the problem statement to focus on Teleport's certificate identity code, explored analogous AWS/Azure implementations, discovered that event/protobuf definitions already had GCP-related fields, and then mirrored the existing encode/decode pattern into `tlsca`. Along the way, it showed awareness of the hidden test name `TestGCPExtensions`, suggesting benchmark contamination influenced the trajectory even though the implementation path itself was technically grounded.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows substantial legitimate debugging and code comprehension: the agent identified `lib/tlsca/ca.go` as the likely implementation point from the feature request, searched for existing AWS/Azure patterns, inspected ASN.1 OID conventions, checked `Subject()`/`FromSubject()`, and traced related event/protobuf structs before outlining a concrete implementation plan. That is consistent with real task-specific reasoning rather than a direct jump to a memorized patch. However, there is a strong contamination signal: the agent explicitly referenced `TestGCPExtensions`, which is a fail-to-pass evaluation test name not present in the problem statement. Because hidden test names are not something the agent should know through normal repository exploration, this indicates test awareness. I do not see evidence of package leakage or of copying code from installed artifacts, and the available trajectory does not show enough patch text to support a high-confidence gold-patch similarity claim. So the best fit is that the agent solved the task largely through legitimate reasoning, but with benchmark leakage in the form of hidden test awareness.

</details>

#### `instance_gravitational__teleport-8302d467d160f869b77184e262adbe2fbc95d9ba-vce94f93ad1030e3136852817f2423c1b3ac37bc4`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.76 | 0.00 | 0 | 0 | Genuine exploratory debugging with a mostly correct implementation plan, partial alignment to the re |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the repository, inspected Touch ID API and platform-specific files, checked tsh command handling, consulted an in-repo RFD/PR-related document for requirements, then began implementing a diagnostics-based availability redesign and CLI updates. Progress stopped before a completed, validated patch was produced, likely exacerbated by inability to reproduce on Linux.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like legitimate, problem-directed exploration rather than benchmark leakage. The agent started by locating the Touch ID implementation, Darwin/non-Darwin variants, and tsh command integration, then formed a concrete hypothesis about availability checks, diagnostics, and CLI wiring. It did not jump straight to a single target file, did not install packages, did not reference hidden F2P test details, and did not copy code from elsewhere. Its planned changes substantially overlap the real solution, but that overlap is plausibly explained by normal code reading plus consulting in-repo documentation/RFD material, which it explicitly mentions. The agent also showed genuine reasoning, including recognizing platform limitations on Linux and thinking through caching and command exposure. However, it appears not to have completed or validated a final patch, and one visible reasoning point diverged from gold: it argued against switching to `kSecAccessControlTouchIDAny`, which is actually part of the gold fix. So this is best classified as a failed attempt with real intent and partial alignment to the true fix, not as leak-driven success.

</details>

#### `instance_gravitational__teleport-89f0432ad5dc70f1f6a30ec3a8363d548371a718`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.82 | 0.00 | 0 | 0 | A genuine, exploratory agent that identified the right abstraction and call-site pattern, began impl |

**Causal chain (Claude Opus 4.1 - paper):** Problem statement led the agent to search for unbounded HTTP body reads; it inspected utils and HTTP helper code, searched for `ioutil.ReadAll` in HTTP contexts, inferred the need for a bounded read helper plus constants/error, started updating multiple call sites, then hit cleanup/build issues before completing the task.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a legitimate debugging and implementation process rather than benchmark leakage. The agent began by restating the task, explored the repository structure, inspected `lib/utils/utils.go` and `lib/httplib/httplib.go`, searched for `ioutil.ReadAll` usages, and explicitly distinguished unrelated filesystem reads from relevant HTTP request/response body reads. It then formulated a concrete plan: add `utils.ReadAtMost`, introduce request/response size constants, add `ErrLimitReached`, and replace unbounded body reads in relevant call sites. This is consistent with genuine reasoning from the problem statement. There are no signs of package leakage, no references to hidden test names or expected values, and no suspicious jump directly to the exact gold patch locations without exploration. In fact, the agent appears to inspect and modify more files than the gold patch, which argues against rote memorization. The task was ultimately unresolved and the final patch is not present, but the visible trajectory indicates the agent was addressing the real issue and iterating on compile errors (unused imports) rather than missing the core problem entirely. Therefore this is best classified as a failed but substantively correct-intent attempt, not a leakage case.

</details>

#### `instance_gravitational__teleport-96019ce0be7a2c8e36363f359eb7c943b41dde70`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.82 | 0.00 | 0 | 0 | Genuine repo exploration followed by a strong but misplaced hypothesis that chased scope-crept proxy |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the proxy stack, noticed `trace.WriteError` produced plain JSON, inferred that Kubernetes error responses needed `Status` objects and custom error writers, and then started modifying `httplib`/forwarder plumbing instead of focusing on `authenticate`'s access-denied classification logic.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows real exploration rather than a direct jump to the exact fix: the agent inspected Kubernetes proxy code, the forwarder, httplib, and trace error handling before forming a hypothesis. That argues against a clean gold-patch leak or test-aware behavior. However, the agent then latched onto a broader and largely different problem than the benchmark's core requirement. Instead of centering on `authenticate` and the distinction between `trace.IsAccessDenied(err)` and non-auth errors, it concluded that the main issue was Kubernetes `metav1.Status` error serialization, HTTP 500 behavior, and injectable custom error writers. Those details align with unrelated/scope-crept portions of the gold patch and were not required by the stated `TestAuthenticate`-style objective. Because the agent's work focused on the wrong layer and there is no evidence it implemented the crucial `authenticate` classification change, this is best classified as `agent_failed_no_intent`: the failure reflects a misdiagnosis/non-solution, not a basically correct fix blocked by contaminated tests. There is no evidence of package leakage, no use of hidden test names/values, and no direct copy-from-package behavior.

</details>

#### `instance_gravitational__teleport-af5e2517de7d18406b614e413aca61c319312171-vee9b09fb20c43af7e520f57e9239bbcf46b7113d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.96 | 0.00 | 0 | 0 | Legitimate early-stage repository exploration with no leakage signals, but the agent failed to advan |

**Causal chain (Claude Opus 4.1 - paper):** The agent began by locating likely protocol-detection and listener setup code, traced the SSH proxy/server initialization path, but stopped before proposing or implementing any concrete changes.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows ordinary initial codebase exploration, not leakage. The agent read the problem, then progressively inspected the multiplexer, searched for `ProxyHelloSignature`, located its definition, and moved on to proxy/service listener setup and the SSH server construction path. This is exactly the kind of exploratory behavior expected from a model trying to understand where protocol detection and connection wrapping happen. There are no signs that it jumped straight to the exact gold edit sites with a ready-made patch, no references to fail-to-pass test names or hidden expected values, and no package installation or copying from external code. However, the agent never actually formulated and applied a fix: the final patch is empty, and there is no evidence of implementation, testing, or iteration. Because it did not produce a patch that even partially addresses the core requirement, this is best classified as a straightforward failure to solve the task rather than an 'intent-complete but mismatched to contaminated tests' case.

</details>

#### `instance_gravitational__teleport-b5d8169fc0a5e43fee2616c905c6d32164654dc6`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.74 | 0.00 | 0 | 0 | Methodical, task-aware exploration with a plausible fix strategy, but incomplete or unsuccessful exe |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the migration/regression description, mapped it to Teleport's role and auth subsystems, inspected the relevant files one by one, and then attempted to implement a fix centered on preserving the admin-role path for OSS users.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like genuine repository-driven debugging rather than leakage. The agent began from the problem statement, identified the likely subsystems involved (OSS migration logic, admin role handling, user creation, build type behavior), and then explicitly explored those areas in sequence: constants, migration code, the role-construction function, user creation paths, and role deletion logic. That is the expected search pattern for this bug. The planned implementation steps also track the stated root cause: stop using a separate ossuser role, modify migration around admin, create a downgraded admin-role constructor, protect the admin role from deletion, and update legacy user creation to assign admin. Those edits are close to the real fix, but they are also directly motivated by the prompt, so similarity is not itself suspicious. There are no signs of package installation, no copying from site-packages, no references to hidden test names or values, and no abrupt jump to obscure files without exploration. Because the run did not resolve the task and the final patch content is missing, I cannot confirm whether the agent implemented all required details (for example trusted-cluster mapping or migrated-label skip logic). Still, the available trajectory shows clear intent to solve the actual bug, so this is best classified as a genuine-but-unsuccessful attempt rather than leakage.

</details>

#### `instance_gravitational__teleport-baeb2697c4e4870c9850ff0cd5c7a2d08e1401c9-vee9b09fb20c43af7e520f57e9239bbcf46b7113d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.71 | 0.00 | 0 | 0 | Mixed behavior: mostly normal repository exploration for the core task, but with a suspiciously spec |

**Causal chain (Claude Opus 4.1 - paper):** The agent began with normal codebase exploration around keystore test helpers and backend config structs, then appears to have been steered by hidden knowledge of the upstream patch/PR and expanded its work to the unrelated pkcs11 label-handling change that was not inferable from the stated task.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows substantial surface-level exploration of the repository, which is a genuine-problem-solving signal. The agent looked through testhelpers.go, config structs, tests, and integration files before planning the central HSMTestConfig implementation. However, a strong leakage indicator appears later: it pivots to an unrelated pkcs11 `FindKeyPair` change and explicitly says 'the PR description mentions that the key lookup logic should call `FindKeyPair` without a label to ensure compatibility with devices that don't support labeled key pairs.' That requirement is not present in the provided problem statement, but it matches an unrelated hunk in the gold patch almost exactly. This is not normal task-driven reasoning from the stated issue; it suggests access to broader gold-patch knowledge or contaminated PR context. There is no evidence of package leakage or test-name awareness, and the agent did not simply jump straight to the file without exploration, so this is not the strongest possible leak case. Still, the hidden-scope-creep knowledge is specific enough that the passed run is best classified as leakage rather than purely genuine reasoning.

</details>

#### `instance_gravitational__teleport-c782838c3a174fdff80cafd8cd3b1aa4dae8beb2`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.82 | 0.00 | 0 | 0 | Methodical explorer with correct high-level understanding, but incomplete execution and no concrete  |

**Causal chain (Claude Opus 4.1 - paper):** A highly detailed problem statement guided the agent to the relevant subsystems; it then inspected those files, formed the correct high-level plan, began implementing required changes, and stalled before completing the critical cache/collections logic or producing a final patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine but incomplete attempt rather than leakage. The agent began by exploring the repository and the specific areas implicated by the problem statement: the ClusterConfig type, cache watch policies, reverse tunnel version checks, service helpers, and cache collections. That is the expected workflow for a legitimate solver on this task. It did not jump straight to an opaque final diff, did not install external packages, did not reference the hidden fail-to-pass test name, and did not cite secret expected values. Its planned changes closely track the requirements in the prompt, but that is not suspicious here because the prompt itself is unusually specific and explicitly names the new interfaces and behaviors to implement. The key issue is that the agent never completed the implementation: the final patch is empty, and the trajectory stops mid-edit while working through collections.go. Because there is no finished patch, there is not enough evidence that it actually addressed the full bug end-to-end; it merely showed partial understanding and started editing the right areas. That makes this a failure due to incompletion/skill-execution gap rather than benchmark leakage or contamination-driven unfair failure.

</details>

#### `instance_gravitational__teleport-dd3977957a67bedaf604ad6ca255ba8c7b6704e9`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.88 | 0.00 | 0 | 0 | Broad, exploratory, and ultimately non-convergent; the agent appears confused by surrounding Telepor |

**Causal chain (Claude Opus 4.1 - paper):** The problem description pointed toward proxy principals and Kubernetes/local access, which led the agent to inspect service, kube, and reversetunnel code. From there it expanded into adjacent infrastructure areas also touched by the upstream PR scope, but it never narrowed down to a concrete implementation in `getAdditionalPrincipals`, so the session ended without a fix.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The agent appears to have read the problem and begun a legitimate repository exploration, but it never converged on or implemented the core fix. Its trajectory starts broadly and then branches into multiple areas of the Teleport codebase: `lib/service`, `lib/srv`, kube-related code, reversetunnel, constants, roles, `TeleportProcess`, `NewTLSServer`, and `kubeClusters`. Some of those areas overlap with the gold patch's unrelated scope-creep changes, but there is no evidence of benchmark leakage in the stronger sense: the agent did not jump straight to the exact target function and patch it, did not reference hidden test names or expected values, did not install an external package, and did not produce a patch resembling the gold solution. Instead, it looks like the agent got lost in broad exploration and possibly followed the contaminated PR scope rather than isolating the real requirement in `getAdditionalPrincipals`. Because it produced no patch and did not test or iterate, this is best classified as a failure due to not actually solving the task, not as a contaminated near-miss or answer leak.

</details>

#### `instance_gravitational__teleport-fb0ab2b9b771377a689fd0d0374777c251e58bbf`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.83 | 0.00 | 0 | 0 | Genuine but incomplete exploratory attempt; no leakage signals, but the agent did not finish or vali |

**Causal chain (Claude Opus 4.1 - paper):** The agent used the problem statement to identify watcher metrics and rolling-buffer support as the main work, explored the relevant code paths across metrics, auth gRPC watcher emission, and the TUI/reporting layer, then started implementing a broad PR-style fix. The effort appears to have stalled before completion or validation.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a broadly legitimate exploration process rather than leakage. The agent began by reading and searching through the repository for metrics, watcher, gRPC server, and top-command reporting code, progressively identifying likely integration points. This is the opposite of a suspicious direct jump: it inspected metrics.go, watcher-related files, grpcserver.go, NewGRPCServer, top_command.go, helper functions, and report structures before editing. It also planned changes that align with the problem statement and with the eventual gold areas: metric constants, TagResource, a CircularBuffer in utils, watcher metrics in grpcserver, registration in NewGRPCServer, and a resourceLabel helper. However, the run does not show completed edits, test execution, debugging, or a final patch; it appears to stop mid-implementation while preparing to add an import. Because the task was not resolved and there is no evidence that the agent actually produced a sufficiently complete patch addressing the required interfaces and behavior, this is better classified as a straightforward failure/incomplete attempt rather than a contaminated false negative. There are no signs of package leakage, no references to hidden test names or expected values, and no evidence of gold-patch copying.

</details>

#### `instance_internetarchive__openlibrary-0dc5b20fa186f9714f8a838178597e69f549d026-v2d9a6c849c60ed19fd0858ce9e40b7cc8e097e59`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.78 | 0.00 | 0 | 0 | A genuine, exploratory debugging attempt that partially implemented the intended feature, but misint |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the relevant parser and tests, inspected MARC 880 linkage behavior with ad hoc scripts, implemented alternate-name support and tag-aware parsing, debugged its code, then drifted into an over-broad interpretation of 700/720 author handling and incorrect name normalization, which likely caused the unresolved outcome.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine debugging and implementation attempt rather than leakage. The agent started by exploring the repository, locating `openlibrary/catalog/marc/parse.py`, reading related functions (`read_author_person`, `read_authors`, `read_contributions`), then inspecting tests, MARC parsing internals, and binary test data to understand how 880 linkages work. It even wrote small inspection scripts to observe current behavior on alternate-script MARC records. That is consistent with legitimate problem-solving. The agent then formed a concrete hypothesis: add alternate-script handling to personal-name parsing, propagate tag information, and update call sites. It implemented changes, hit a bug due to variable shadowing / wrong assumptions about a helper, fixed that, and re-tested. However, it appears to have over-generalized the change by adding 700/720 fields directly into `authors` in `read_authors`, which broader tests showed was incompatible with existing behavior. It also explicitly changed normalization logic to preserve commas after noticing current outputs like `Lyons, Daniel`, even though the task requirements and gold patch normalize away separator characters such as commas. So the failure does not look like lack of effort or random flailing; it looks like a real attempt that partially addressed the target bug but missed the benchmark’s expected behavior due to scope/interpretation errors. There are no strong signs of benchmark leakage: no package installs, no direct jump to an exact gold-style patch, no unexplained use of hidden expected values, and the final behavior differs materially from the gold patch.

</details>

#### `instance_internetarchive__openlibrary-2fe532a33635aab7a9bfea5d977f6a72b280a30c-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.93 | 0.00 | 0 | 0 | Methodical and evidence-driven debugging with normal code exploration, implementation, and test iter |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the bug report, searched the codebase for Amazon import logic, inspected `vendors.py`, verified the missing language extraction and metadata cleaning behavior, implemented both required changes, tested with mocks and edge cases, adjusted the mock shape when serialization initially failed, and then reran relevant tests until the task passed.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a normal, progressive debugging and implementation process rather than benchmark leakage. The agent began from the problem statement, searched for Amazon-related code, inspected the relevant adapter and cleaning function, looked through tests and related language-handling code, and then formed an explicit two-part hypothesis: serialization was not extracting languages, and cleaning was dropping them. It then implemented a fix, tested it, found an issue in its mock setup, corrected that, and reran tests and edge cases. This is the expected shape of genuine problem-solving. There is no sign that it jumped immediately to the exact lines in `serialize` and `clean_amazon_metadata_for_load` without exploration; in fact, the trace includes multiple repository-navigation and validation steps. There is also no evidence of package leakage: no pip install of a newer package, no copying from site-packages, and no mention of importing a patched upstream implementation. The agent did inspect tests, but only after code exploration, which is standard debugging behavior and not test-aware leakage. Importantly, the gold patch contains an unrelated `affiliate_server.py` hunk; the agent explicitly checked that integration and concluded it was already correct, which argues against memorized or copied gold-patch reproduction. Overall, the behavior is consistent with a strong model solving a straightforward feature bug through legitimate reasoning.

</details>

#### `instance_internetarchive__openlibrary-3f580a5f244c299d936d73d9e327ba873b6401d9-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.84 | 0.00 | 0 | 0 | Behavior is consistent with prior knowledge of the upstream patch/PR: targeted, confirmation-oriente |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to recognize or reconstruct the original upstream PR as a RUF012 mutable-class-attribute cleanup, uses that framing to target the same files/hunks as the gold patch, then applies the expected immutability conversions; the autocomplete portion is enough to pass the evaluation tests.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory does not look like a clean, requirement-driven solve from the benchmark statement alone. Before doing meaningful debugging, the agent framed the task as an upstream-style "RUF012 linter warning" cleanup and then explicitly said it would inspect the files "mentioned in the PR description." It proceeded to enumerate the exact unrelated scope-creep files and class attributes that appear in the gold patch: `openlibrary/core/bookshelves.py` (`PRIMARY_KEY`, `PRESET_BOOKSHELVES`, `PRESET_BOOKSHELVES_JSON`), `openlibrary/core/edits.py` (`TYPE`, `STATUS`, `MODES`), and `openlibrary/plugins/worksearch/autocomplete.py` (`fq`). Those bookshelves/edits changes are not derivable from the benchmark problem's core autocomplete requirements and are precisely the kind of extra hunks introduced by contamination. That makes the solve look much more like recall of the upstream patch/PR context than genuine local reasoning from the provided behavior spec. There is no sign of package leakage, and the agent did perform some file reads and a lint reproduction step, but those actions seem to confirm a preselected answer rather than discover it.

</details>

#### `instance_internetarchive__openlibrary-431442c92887a3aece3f8aa771dd029738a80eb1-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.76 | 0.00 | 0 | 0 | Exploratory and partially informed, with some gold-patch-aligned planning, but ultimately incomplete |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to have started from a broader search-query bug context, explored the Solr/worksearch code to understand how Luqum trees are transformed, identified that a child-replacement helper would be needed, and then planned a set of changes aligned with that broader bug—but it stopped before producing a concrete patch or validating it.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows real exploration and understanding of the Luqum/query-conversion area rather than a direct jump to a finished patch: the agent inspected repository structure, searched search-related code, opened `query_utils.py` and `plugins/worksearch/schemes/works.py`, looked for `WORK_FIELD_TO_ED_FIELD`, and explicitly sought tests and a reproduction. That argues against strong leakage such as jumping straight to the exact helper implementation, package-copying, or test-aware behavior. However, the agent never actually completed a patch, and the recorded final patch is empty, so there is no evidence that it successfully addressed the benchmark requirement in code. The one suspicious element is that its planned change list closely tracks the broader gold patch scope—`Callable` typing, `alternative_title` as a lambda OR query, callable handling in field conversion, and root-node replacement handling—which goes beyond the narrow benchmark problem statement. Still, because the agent explored the relevant files before formulating that plan, and because there is no produced patch to compare for near-identity, this is better treated as an incomplete/partial attempt than as clear gold-patch leakage. Since it did not actually deliver a fix, this fits `agent_failed_no_intent` rather than `agent_failed_completed_intent`.

</details>

#### `instance_internetarchive__openlibrary-5fb312632097be7e9ac6ab657964af115224d15d-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.70 | 0.00 | 0 | 0 | Genuine exploratory debugging with a sensible implementation plan, but the recorded attempt appears  |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem, explored the relevant Wikidata, model, and template files, noticed the disabled `wikidata()` path and missing helper methods, attempted to implement backend/profile support and then moved on to UI integration, but the run appears to have ended before a final patch was delivered.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like genuine repository-driven problem solving rather than benchmark leakage. The agent explored the codebase progressively: it inspected the Wikidata model, templates, author model, searched for the `wikidata` method, examined tests only after locating the relevant implementation areas, and looked for existing icon assets and template structure before proposing changes. It formed a plausible hypothesis from code inspection (`Author.wikidata()` had an early `return None`, `WikidataEntity` lacked the needed profile methods) and then attempted an implementation plan spanning backend logic and infobox rendering. There are no signs of package leakage, no evidence it referenced hidden test expectations before opening tests, and no suspicious jump directly to the exact gold patch without exploration. However, the recorded run did not actually produce a final patch, and the task was not resolved. Because the available evidence shows an incomplete/undelivered fix rather than a completed patch that merely mismatched contaminated F2P expectations, the safest failed label is `agent_failed_no_intent` rather than `agent_failed_completed_intent`.

</details>

#### `instance_internetarchive__openlibrary-60725705782832a2cb22e17c49697948a42a9d03-v298a7a812ceed28c4c18355a091f1b268fe56d86`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.84 | 0.00 | 0 | 0 | Broad, exploratory, and scope-creep-prone; touched relevant model code but failed to execute the min |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to have interpreted the task as a broad Safe Mode feature request, explored multiple UI/account/search/cookie code paths, got pulled into scope-creep investigation, and then started with an unrelated template change instead of implementing the required `User.get_safe_mode()` accessor.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory looks more like genuine but misdirected exploration than benchmark leakage. The agent did not jump straight to `openlibrary/plugins/upstream/models.py` and add the exact `get_safe_mode()` method; instead it performed a long exploratory sweep across accounts, templates, privacy pages, search-result rendering, cover handling, login cookie logic, and preference-related model code. That is consistent with trying to understand a broader Safe Mode feature rather than reproducing a memorized minimal fix. There are no signs of package leakage, no references to the hidden fail-to-pass test name or assertions, and no final patch resembling the gold patch. The one notable contamination-adjacent signal is that the agent drifted into the same kind of scope creep present in the gold patch (templates, cookies, search/content-moderation behavior), but because it never actually produced the core model change and its first concrete implementation step was an unrelated account template edit, this is better explained as task misunderstanding or distraction than as answer leakage. Since the agent did not deliver a patch that clearly addressed the real requirement, this is `agent_failed_no_intent`, not `agent_failed_completed_intent`.

</details>

#### `instance_internetarchive__openlibrary-7edd1ef09d91fe0b435707633c5cc9af41dedddf-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.67 | 0.00 | 0 | 0 | Methodical, codebase-driven refactor attempt with genuine reasoning; likely a near-correct implement |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the existing autocomplete and OLID-related code, checked tests and model helpers to infer expected behavior, formed a refactor plan around a shared autocomplete base plus unified OLID extraction/conversion, implemented that plan, and locally sanity-checked it. The likely cause of failure is mismatch on exact hidden-test expectations or implementation details, not leakage or aimless debugging.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine implementation attempt rather than leakage. The agent begins by exploring the repository, reading the existing autocomplete endpoints, utility functions, route registrations, tests, and model behavior before proposing a concrete plan. That plan tracks the issue requirements closely: add generalized OLID utilities, refactor autocomplete logic into a shared base, and adapt the specific endpoints. It then reports implementing those changes, running doctests, import checks, and ad hoc validation scripts. There are no signs of benchmark leakage: no direct jump to a final patch without inspection, no package installation, no copying from site-packages, and no suspicious early references to hidden test assertions. Because the run ultimately did not resolve the task and the actual final diff is unavailable, I cannot verify whether the implementation exactly matched the gold patch or whether it simply had a bug. Still, the trajectory strongly suggests the agent understood and attempted to solve the real problem in the right files and with the right architecture, so this fits best as a failed-but-completed-intent case rather than a no-intent failure.

</details>

#### `instance_internetarchive__openlibrary-8a9d9d323dfcf2a5b4f38d70b1108b030b20ebf3-v13642507b4fc1f8d234172bf8129942da2c2ca26`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.89 | 0.00 | 0 | 0 | Genuine exploratory debugging with a reasonable hypothesis, but the agent stalled before implementat |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement pushed the agent toward CLI/import-pipeline integration, so it explored `manage_imports.py`, import classes, partner batch import flow, and API staging format. It then found the existing ISBNdb provider and identified needed transformations, but it stalled before implementing changes.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows ordinary, non-leaky exploration rather than answer memorization. The agent started broadly, inspected the import pipeline, provider directory, existing `scripts/providers/isbndb.py`, partner batch import code, tests, and API views before forming a hypothesis. That is the opposite of a suspicious jump straight to the exact gold-edit region. It also did not install external packages, did not copy code from site-packages, and did not reveal hidden expected values before exploration. Reading the local test file after inspecting the provider is normal debugging behavior here, not strong test-awareness leakage. However, the agent never produced a patch at all. Its stated plan over-focused on `manage_imports.py` CLI integration, while the evaluated fail-to-pass tests were centered on provider parsing/normalization behavior in `scripts/providers/isbndb.py`. Because there is no implemented patch, there is no basis to say it completed the real intent but merely missed contaminated tests; instead, it failed to carry the fix through. So this is best classified as a genuine but unsuccessful attempt, i.e. `agent_failed_no_intent` rather than any leakage category.

</details>

#### `instance_internetarchive__openlibrary-92db3454aeaa02f89b4cdbc3103f7e95c9759f92-v2c55207218fb8a0138425cbf7d9675272e240b90`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.72 | 0.00 | 0 | 0 | Exploratory and competent on the surface, but it appears to have reconstructed the larger contaminat |

**Causal chain (Claude Opus 4.1 - paper):** The agent began with legitimate repository exploration, but appears to have anchored on the broader upstream reading-log filtering PR rather than the narrow benchmark requirement; that led it toward implementing the larger contaminated solution pattern, which still satisfied the evaluation.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows substantial real exploration, so this is not a simple case of the agent instantly jumping to the target files or blatantly referencing hidden tests. However, the strongest signal is the agent's shift from the narrow benchmark requirement (align Solr boolean clause limit with a backend constant) to the much broader contaminated upstream approach reflected in the gold patch. After inspecting bookshelves, reading-log views, templates, Solr integration, models, ratings, and `mybooks.py`, the agent explicitly planned to: update `docker-compose.yml`, add `FILTER_BOOK_LIMIT`, add `LoggedBooksData`, and add `q` filtering support to `get_users_logged_books`. Those latter changes are far beyond what is needed for the stated task and mirror the scope-crept upstream patch structure. That makes the behavior look less like benchmark-specific reasoning and more like recall of a larger memorized fix pattern associated with the contaminated PR. I do not see evidence of package leakage or explicit test awareness, and the missing final patch prevents a higher-confidence direct gold-copy finding. So the best fit is that the agent passed, but via a contaminated memorized approach rather than clean, task-local reasoning.

</details>

#### `instance_internetarchive__openlibrary-9bdfd29fac883e77dcbc4208cab28c06fd963ab2-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.84 | 0.00 | 0 | 0 | Legitimate code inspection and partial bug fixing, but it missed the main parser-behavior change nee |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, inspected the two relevant files, wrote a reproduction script, found a handful of concrete helper-function bugs, and started patching those issues; it appears to have anchored on local fixes and did not reach the larger parser-logic change required to solve the task.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This looks like a genuine but incomplete debugging attempt, not leakage. The agent began with normal exploration, inspected the relevant modules, read the transformation and query-processing functions, and even created a small reproduction script to understand the parser behavior. From that investigation it identified several real code defects that do overlap with parts of the gold patch: incorrect `.value` handling for LCC/DDC ranges, a case-sensitivity bug in field alias remapping, and bugs in `fully_escape_query`. However, the trajectory never shows the agent discovering or implementing the core parser rewrite in `luqum_parser` that is needed for greedy field binding and boolean-operator preservation between fielded clauses. That omission is important because those are central requirements of the task and central to the gold patch. So although the agent had some correct local insights, its failure is better explained by missing the main solution path than by benchmark contamination or unfair F2P mismatch. There are no signs of package leakage, test-awareness, or suspiciously direct copying of the gold patch.

</details>

#### `instance_internetarchive__openlibrary-b67138b316b1e9c11df8a4a8391fe5cc8e75ff9f-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.72 | 0.00 | 0 | 0 | Genuine repository exploration and root-cause-oriented refactor attempt; targeted the correct proble |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement explicitly pointed the agent toward MARC parsing abstractions and 880 alternate-script handling. The agent inspected the relevant code and tests, confirmed the current baseline, inferred that structured field interfaces and 880 linkage support were missing, then implemented those core changes plus targeted parser updates. The attempt likely failed because the task's required patch was broader than the subset it completed.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a genuine debugging and implementation attempt rather than leakage. The agent began with broad repository exploration, then narrowed to the MARC modules named in the problem statement, read the relevant source files (`marc_base.py`, `marc_binary.py`, `marc_xml.py`, `parse.py`, `get_subjects.py`), inspected tests, and ran the existing suite before changing code. Its stated plan closely tracks the explicit requirements in the prompt: introduce `MarcFieldBase`, adapt binary/XML field classes, add `get_control`/`get_linkage`, update `read_subjects`, and improve 880 handling. Those are all core parts of the real bug. There is no sign of package installation, copying from external sources, or jumping straight to an obscure file/function without exploration. The only mild overlap with the gold patch is in the same high-level architectural changes, but the prompt itself essentially specifies those changes, so that is not strong leak evidence. Because the run ultimately did not resolve the task, and because the agent appears to have implemented only part of the broader refactor/normalization work covered by the gold patch and wide F2P tests, this looks like a legitimate but incomplete attempt to solve the true issue rather than a benchmark leak or pure miss.

</details>

#### `instance_internetarchive__openlibrary-bb152d23c004f3d68986877143bb0f83531fe401-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.72 | 0.00 | 0 | 0 | Genuine, repo-driven implementation attempt with meaningful exploration and iteration, but likely in |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the coverstore codebase, inferred that tar-based archival needed to be replaced with zip-based batching plus deterministic ID/path helpers, implemented those components across the archive and DB layers, validated with self-authored and repository tests, then iterated on runtime and URL issues. It likely failed because its implementation surface did not exactly match the benchmark's expected locations/signatures.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a largely genuine software-engineering process rather than leakage. The agent began by exploring the relevant repository areas (`archive.py`, schema, db layer, tests, coverlib, config), then formed an implementation plan from the problem statement, and iteratively added the requested pieces: schema changes, `Cover`, `Batch`, zip-based archival support, database updates, and URL handling. It also wrote and ran its own validation scripts, hit an implementation issue (`config.data_root`), fixed it, tested edge cases, and adjusted URL generation. Those are all strong signs of real reasoning and debugging. At the same time, the run did not resolve the benchmark, and there are hints the implementation likely diverged from the evaluator's expected interface: the agent mentions adding `CoverDB` to `db.py` instead of `archive.py`, speaks of updating a standalone `is_uploaded` function rather than clearly implementing the specified `Uploader` class, and never explicitly mentions the `schema.py` changes or some exact interface-level details the hidden tests likely depend on. Given the severe contamination context and wide/weak test scope, this looks more like a substantial but not evaluator-exact attempt to solve the real problem than a pure miss. There is no evidence of package leakage, gold-patch copying, or hidden-test awareness.

</details>

#### `instance_internetarchive__openlibrary-d109cc7e6e161170391f98f9a6fa1d02534c18e4-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.79 | 0.00 | 0 | 0 | Genuine repository exploration and task-specific reasoning, but the implementation effort appears un |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the spec, explored the list-related implementation and templates, formed a correct high-level hypothesis about where annotated-seed support must be added, and began planning edits in those files, but it did not complete or validate the implementation.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine but incomplete attempt rather than leakage. The agent began by exploring the repository, then inspected the main list model, list plugin code, edit/view templates, and existing tests. Its proposed changes closely follow the public problem statement: adding annotated seed types, extending `Seed`, updating `List` methods, adjusting input normalization, and exposing notes in templates. Those are exactly the areas a legitimate solver would identify from the specification, so the overlap with the gold patch is expected and not suspicious. There are no signs of package leakage, no pip installs, no copying from site-packages, and no references to hidden expected values or F2P test names before exploration. Just as importantly, the visible plan does not show suspicious gold-patch recall: it omits several downstream gold changes (e.g. Solr/export/worksearch/macro/CSS details), which argues against memorized access to the final patch. However, the agent ultimately did not resolve the task and no completed patch or successful test iteration is shown. Because there is insufficient evidence that it actually landed a working patch that addressed the real failure mode, this is better classified as a normal unsuccessful attempt due to incompleteness/skill gap rather than a contaminated 'completed intent' miss.

</details>

#### `instance_internetarchive__openlibrary-fdbc0d8f418333c7e575c40b661b582c301ef7ac-v13642507b4fc1f8d234172bf8129942da2c2ca26`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.77 | 0.00 | 0 | 0 | Repository-guided debugging with a plausible, problem-specific centralization fix; likely addressed  |

**Causal chain (Claude Opus 4.1 - paper):** Issue about placeholder values surviving normalization led the agent to inspect import-related code paths, find where records are parsed and loaded, discover that `load()` calls `normalize_import_record()`, infer that placeholder cleanup belongs there, and then plan to centralize the logic and remove duplicated cleanup from upstream callers.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks mostly like genuine debugging rather than benchmark leakage. The agent did not jump straight to editing the exact target function; it explored the import flow, inspected related modules, searched for `parse_data`, `load`, and `normalize_import_record`, reproduced the issue, and then articulated a concrete hypothesis: cleanup should live in `normalize_import_record`, with duplicated cleanup removed from callers. That is a sensible causal path from the problem statement. There are no signs of package leakage, no references to hidden test names or unseen expected values, and no evidence of copying code from elsewhere. The one mild concern is that the agent's plan matched the broader gold-patch structure quite closely, including removing cleanup from `from_isbn` and `importapi`, even though the user-facing problem only required normalization behavior. But the agent appears to have arrived at that by tracing the call chain and noticing duplicated logic, not by obviously recalling the gold patch. Because the run is marked unresolved and no final patch is shown, I cannot label it as a clean successful solve; however, the trajectory strongly suggests the agent understood and attempted the real fix. So this is best classified as a failure despite completed intent, not as no-intent or leak-driven behavior.

</details>

#### `instance_navidrome__navidrome-29b7b740ce469201af0a0510f3024adc93ef4c8e`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.90 | 0.00 | 0 | 0 | Superficially methodical, but guided by suspiciously precise prior knowledge of the benchmark's gold |

**Causal chain (Claude Opus 4.1 - paper):** The agent began with nominal repo exploration, but almost immediately focused on `HTTPClient`, inferred hidden/scope-creep requirements absent from the prompt, then implemented both the stated `SimpleCache` change and the unrelated `cached_http_client.go` refactor in a way that mirrors the gold patch, after which it ran tests and confirmed success.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows some real exploration and validation, but the core solution path is strongly contaminated by gold-patch-specific scope creep. The visible problem statement is narrowly about adding configurable `SizeLimit` and `DefaultTTL` to `SimpleCache`. Despite that, the agent immediately pivoted to `cached_http_client.go` and later asserted a highly specific requirement set involving replacing `ttlcache.Cache` with `SimpleCache[string]`, storing a `ttl` field on `HTTPClient`, and rewriting `Do` to use `GetWithLoader` with request serialization/deserialization. Those details are not implied by the stated bug report, yet they align closely with the provided gold patch's unrelated hunks. The strongest signal is Step 24, where the agent enumerates 15 exact acceptance criteria that effectively restate the gold patch line by line, including the `SizeLimit: 100` behavior in `HTTPClient`. That goes well beyond normal debugging-derived inference for this task. There is no evidence of package leakage or explicit hidden-test-name leakage, but the trajectory suggests the agent was operating from leaked benchmark knowledge or a memorized solution pattern specific to this instance rather than purely from the prompt and repository evidence.

</details>

#### `instance_navidrome__navidrome-5001518260732e36d9a42fb8d4c054b28afab310`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.88 | 0.00 | 0 | 0 | Methodical and requirement-driven exploration with a plausible implementation plan, but the run term |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the requirements, explored the existing property and LastFM codepaths, inferred the architectural changes needed, attempted to set up reproduction/tests, then switched to direct implementation planning when test setup looked cumbersome. The trajectory appears to end before code was actually produced or validated.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a largely genuine debugging and implementation attempt rather than leakage. The agent began by exploring the relevant areas of the codebase in a sensible order: existing property models, datastore interfaces, persistence repositories, LastFM usage, session-key handling, migrations, and request/context utilities. It explicitly connected the observed `LastFMSessionKey_<userID>` pattern to the problem statement and then outlined a reasonable implementation plan that closely matches the stated requirements: add a migration, define `UserPropsRepository`, extend `DataStore`, implement persistence support, and refactor LastFM session-key storage to use contextual user scoping. However, the run ends before any actual patch is shown, and the task was not resolved. Because there is no concrete patch, there is no basis to claim the agent completed the real fix but merely failed due to contaminated evaluation details. Likewise, there are no signs of leakage: it did not jump straight to the exact files without exploration, did not install packages, did not reference hidden tests or expected values, and did not emit a suspiciously gold-like patch. So this is best classified as a genuine but incomplete attempt that ultimately did not solve the task.

</details>

#### `instance_navidrome__navidrome-66b74c81f115c78cb69910b0472eeb376750efc4`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.90 | 0.00 | 0 | 0 | Methodical and genuine exploration with partial implementation, but it failed because it did not fin |

**Causal chain (Claude Opus 4.1 - paper):** The agent started from the problem statement, explored the relevant persistence/auth/config code paths, verified the bug empirically with custom scripts, implemented the AES-GCM utility layer, and then began broader integration work but stopped before producing a complete patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory looks like genuine, incremental problem-solving rather than leakage. The agent did not jump straight to a finished patch or to obscure files; it explored the user model, repository implementation, configuration, migrations, property storage, and authentication code before making changes. It also created and ran repro scripts to confirm that passwords were currently stored in plaintext, which is exactly the kind of debugging step expected from a legitimate solver. The agent then implemented the encryption utility first and appears to have tested it locally, which aligns with the explicit requirements in the prompt. There are no signs of package leakage, no evidence of installing a newer Navidrome or related package and copying code back, no references to hidden test names or hidden expected constants, and no suspicious gold-patch-level specificity such as immediately adding the exact migration/property-key machinery without investigation. However, the task was not resolved: the final patch is empty/incomplete, and the trajectory ends while the agent is only beginning to modify configuration after implementing the utility layer. Because it did not complete the repository/auth integration required by the problem, this is best classified as a failure due to incomplete execution/skill gap rather than contamination unfairness.

</details>

#### `instance_navidrome__navidrome-69e0a266f48bae24a11312e9efbe495a337e4c84`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.92 | 0.00 | 0 | 0 | Genuine exploratory debugging behavior, but incomplete execution: the agent investigated the right a |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement pointed the agent to the relevant subsystems; it explored those files and related tests to build understanding, then tried to reproduce behavior with a debug script, but never translated that investigation into code changes.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows normal, task-directed exploration rather than leakage. The agent started from the problem statement, inspected the named implementation areas (`core/artwork/artwork.go`, artwork ID model code, auth/JWT handling, public endpoints, helper usages, and tests), and then attempted to create a debug script to understand current behavior. This is the opposite of a suspicious jump-to-fix pattern. There is no evidence of package installation, no reference to hidden F2P test names or secret expected values, and no patch at all—so there is nothing to compare for gold-patch similarity. However, the agent also never progressed from exploration into an implementation. Since it produced no fix and did not actually modify the code to address the JWT/id-vs-size refactor, this is not a case where the agent completed the real intent but merely missed contaminated tests. It simply failed to carry the task through to a solution.

</details>

#### `instance_navidrome__navidrome-b3980532237e57ab15b2b93c49d5cd5b2d050013`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.84 | 0.00 | 0 | 0 | Careful, exploratory debugger that identified the core issue and pursued a plausible full fix, but d |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored relevant code, reproduced the failure mode around agent registration without an API key, concluded that constructor defaults alone were insufficient, and expanded the fix to include config/registration changes so Last.FM could operate out of the box.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a genuine debugging process rather than benchmark leakage. The agent began with broad repository exploration, then inspected the configuration layer, the Last.FM agent, metadata flow, registration hooks, and the Last.FM client before forming a hypothesis. It created reproduction scripts to confirm the actual runtime behavior: with no API key, the Last.FM agent was not registered; with an API key, it was. From that evidence it inferred the need for a default/shared API key, preserving the configured language/default language behavior, and changing registration semantics so Last.FM could be enabled without a user-supplied key. That reasoning is consistent with the codebase and the problem, not with answer memorization. There are no signs of package leakage, no references to hidden test names or expected values, and no direct jump to the exact solution without exploration. Although the approach overlaps the gold patch in adding an `enabled` flag and adjusting startup behavior, the agent appears to have derived that from observed behavior in the repo rather than from leaked knowledge. Since the run did not resolve the task and no final patch is shown, the best fit is that the agent had the correct intent and addressed the real issue, but still failed the evaluation due to incomplete execution, implementation mismatch, or contamination-related expectation mismatch.

</details>

#### `instance_navidrome__navidrome-d0dceae0943b8df16e579c2d9437e11760a0626a`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.93 | 0.00 | 0 | 0 | Methodical repository exploration with genuine task-oriented reasoning, but the agent stalled before |

**Causal chain (Claude Opus 4.1 - paper):** The agent followed the PR description and repository structure to inspect the relevant Subsonic, sharing, persistence, response, and public URL codepaths, identified the missing endpoints, and appeared to prepare for testing, but it stopped before implementing any changes.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows normal exploratory behavior rather than leakage. The agent began by reading the Subsonic API structure, then progressively inspected the exact subsystems one would reasonably need for this feature: API routing, share model/core logic, persistence, response types, public URL helpers, and dependency wiring. It explicitly noticed that `getShares` and `createShare` were still marked as not implemented and then continued gathering context. That sequence reflects legitimate problem decomposition. There are no signs of benchmark leakage: no direct jump to a completed fix, no package installation, no mention of hidden test names or expected snapshot values, no suspiciously specific constants, and no patch to compare against the gold solution. However, the agent never actually produced a patch, ran through an implementation, or demonstrated a completed fix. Because it did not resolve the task and did not even reach a concrete attempted solution, this is best classified as a straightforward failure to solve rather than a contaminated-but-correct intent failure.

</details>

#### `instance_navidrome__navidrome-d8e794317f788198227e10fb667e10496b3eb99a`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.80 | 0.00 | 0 | 0 | Genuine exploratory debugging and planning, but incomplete execution; no meaningful evidence of leak |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the requirements, surveyed the relevant artwork and handler code paths, formed a coherent fix plan around centralizing ErrUnavailable and placeholder behavior, but the recorded session stops before a concrete validated patch is produced.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a normal, non-leaky investigation pattern: the agent explicitly started by exploring the repository, then inspected the artwork interface, model types/errors, empty-ID reader, source selection, cache warmer, constants, and both HTTP/Subsonic handlers before proposing changes. Its planned edits track the problem statement closely and reflect genuine task-specific understanding: add ErrUnavailable, centralize placeholder fallback in GetOrPlaceholder, remove per-reader placeholder logic, convert artwork-ID plumbing to model.ArtworkID, and update handlers to map unavailability to not-found behavior. There are no signs of benchmark leakage: no direct jump to hidden-test-specific behavior, no package installation, no reference to the fail-to-pass test names, and no suspiciously exact gold-patch copy evidence. However, the recorded run ends without an actual final patch or test/verification evidence, so there is no basis to say it completed the fix or that contamination caused a near-miss. The failure is better explained as incomplete implementation or execution rather than unfairness from benchmark leakage.

</details>

#### `instance_protonmail__webclients-2dce79ea4451ad88d6bfe94da22e7f2f988efa60`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.90 | 0.00 | 0 | 0 | Legitimate exploratory behavior with a sensible plan, but the agent did not follow through with an i |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, explored the relevant mail UI and helper files, formed a plausible implementation plan based on the provided PR-style requirements, but stopped before producing and testing any substantive code.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows normal, progressive repository exploration rather than a leaked-answer pattern. The agent started by inspecting the mail app structure, then drilled into the exact areas implicated by the task: list components, row/column layouts, the existing VerifiedBadge, helper logic in elements.ts, message header components, shared Recipient interfaces, and the badge asset. That is the kind of search path a legitimate agent would take for this feature request. The later plan to create ItemSenders, ProtonBadgeType, isProtonSender, and getElementSenders is not suspicious because those names and files were explicitly supplied in the problem statement itself. There is no evidence of package installation, no references to hidden F2P test names or assertions, and no concrete patch to compare against the gold patch for similarity. Crucially, the agent never appears to actually implement or validate a fix: the final patch is empty, and there is no testing or iteration. So while the agent seems to have understood the intended direction, it did not complete a solution and there is not enough evidence that it even produced a partial patch addressing the tested helper behavior. This makes the failure best explained by incomplete execution / skill gap rather than benchmark leakage or contamination-driven mismatch.

</details>

#### `instance_protonmail__webclients-32ff10999a06455cb2147f6873d627456924ae13`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.95 | 0.00 | 0 | 0 | Surface-level exploration followed by a highly specific, overbroad fix plan that tracks the contamin |

**Causal chain (Claude Opus 4.1 - paper):** The agent did broad repository exploration, then appears to pivot from the stated issue to a hidden larger PR context. That hidden context drove it toward unrelated compose/header/recipient refactors that match the contaminated upstream patch, and the weak evaluation coverage allowed the resulting overbroad fix path to still pass.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This does not look like a clean, task-derived fix. The user-visible requirement was narrow: change the Contact Group Details modal label from “members” to localized singular/plural “email address(es).” A genuine solution would likely focus on ContactGroupDetailsModal and i18n/pluralization. Instead, after some nominal exploration, the agent began pursuing a much broader set of changes that align strikingly with the contaminated gold patch: updating useContactModals to support onCompose, moving action buttons into the modal header, inspecting ContactViewEmails and ContactGroupLabels, plumbing onCloseContactDetailsModal, and even looking at RecipientItemGroup / RecipientItemSingle / RecipientDropdownItem in the mail app. Those files and concepts are not implied by the problem statement. The strongest evidence is the agent explicitly mentioning the 'simple' prop as something 'mentioned in the PR' even though that prop is nowhere in the provided task description; that hidden concept appears in the gold patch. The step-by-step implementation plan also mirrors the gold patch’s scope-creep almost exactly. There are no package-leak signals and no explicit F2P test-name leakage, so this is best classified as gold-patch leakage rather than package leak or test-aware behavior. The pass is therefore not strong evidence of genuine problem solving.

</details>

#### `instance_protonmail__webclients-369fd37de29c14c690cb3b1c09a949189734026f`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.97 | 0.00 | 0 | 0 | Legitimate exploratory analysis with no implementation follow-through; failed due to non-completion/ |

**Causal chain (Claude Opus 4.1 - paper):** The agent parsed the requirements, explored the calendar app structure and existing holidays-calendar code paths to build context, recognized that multiple components would need changes, but then stopped before making any edits or validating a fix.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a normal exploratory start but no actual problem resolution. The agent clearly read the task and then systematically inspected the relevant parts of the repository: main containers, setup flow, calendar UI, settings, feature flags, and existing holidays-related helpers/modal code. That exploration is consistent with genuine problem-solving rather than leakage. However, the agent never progressed to implementation: there is no code edit, no patch content, no test execution, and no iteration on failures. Because it produced no fix at all, this is not a case where the agent addressed the real issue but lost to contaminated fail-to-pass tests; instead, it simply failed to carry out the required changes. There are also no leakage indicators: it did not jump directly to the exact files/functions from the gold patch without search, did not install packages, did not reference hidden test names or expected values, and did not produce a suspiciously gold-like patch. The failure reflects inability or incompletion, not unfair benchmark contamination.

</details>

#### `instance_protonmail__webclients-428cd033fede5fd6ae9dbc7ab634e010b10e4209`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.76 | 0.00 | 0 | 0 | Methodical exploration with a plausible hypothesis and partial implementation plan, but the agent di |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement led the agent to inspect the photo recovery hook, then the links-listing layer and folder API to understand how regular vs. trashed items are loaded. From that inspection it inferred a `ShowAll`-style plumbing change and related recovery updates, briefly examined move-link typing, then began implementing those changes but stopped before finishing the core recovery logic or validating against tests.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows mostly legitimate exploration rather than a direct jump to the answer. The agent started from the problem statement, navigated into the drive/photos store, inspected `usePhotosRecovery.ts`, then followed dependencies into `useLinksListing`, the folder query API, move-link actions/interfaces, and the trash-listing path. That is a plausible debugging path for this bug. It also formulated a coherent hypothesis: add a listing mode that includes trashed items, use trash cache state during recovery, and update related request plumbing. However, the run never reached a completed patch or any test/validation cycle; the final patch is empty, and the agent stopped mid-implementation after planning a few edits. Because there is no actual delivered patch addressing the recovery state machine, error propagation, and resume behavior, this is not a case where the agent essentially solved the real bug but lost to contaminated tests. The strongest suspicious detail is that it explicitly identified the unrelated `SignatureAddress` -> `NameSignatureEmail` rename, which matches a scope-creep hunk in the gold patch and is not motivated by the user-facing problem statement. Still, without a finished patch, test-aware references, package installation, or copy-paste behavior, that is only a weak leakage signal. Overall this looks like partial understanding plus non-completion, so the failure is best classified as no-intent/completion rather than unfair benchmark mismatch.

</details>

#### `instance_protonmail__webclients-5f0745dd6993bb1430a951c62a49807c6635cd77`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.87 | 0.00 | 0 | 0 | Legitimate early codebase exploration, but the run ended before any implementation or debugging; no  |

**Causal chain (Claude Opus 4.1 - paper):** The agent began with broad repository exploration, identified relevant Bitcoin/payment constants and types, and moved toward inspecting Bitcoin components, but stopped before making edits or running tests, so no real fix path materialized.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a normal, non-suspicious start: the agent read the task, then began exploring the repository structure, constants, payment method types, API helpers, and existing Bitcoin-related components. This is consistent with genuine problem setup rather than leakage. However, the run never progressed to implementation, testing, or iteration, and the final patch is empty. There is no evidence that the agent solved the core issue, nor even that it formed and executed a concrete fix strategy. Just as importantly, there are no leakage indicators: it did not jump directly to the exact gold locations without search, did not install external packages, did not mention fail-to-pass test names or hidden expected values, and produced no patch resembling the gold solution. Because the agent did not meaningfully attempt or complete the repair, this is best classified as a straightforward failure due to incompletion / lack of demonstrated problem-solving, not benchmark contamination unfairness.

</details>

#### `instance_protonmail__webclients-708ed4a299711f0fa79a907cc5847cfd39c0fc71`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.69 | 0.00 | 0 | 0 | Mostly exploratory and test-driven, but with suspicious gold-patch-like scope creep; it partially im |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the summer2023 offer code, then appears to have adopted a scope-expanded plan matching the contaminated PR/gold patch rather than the narrow prompt. It implemented a real eligibility change, but mis-handled the 'no previous subscription known' case (`lastSubscriptionEnd` absent/0), discovered that via tests, and did not complete the correction before ending.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The agent shows substantial legitimate workflow elements: it explored the repository, inspected the relevant summer2023 files, formed an eligibility hypothesis, edited code, and ran tests. It clearly engaged with the real bug and even diagnosed the reason its own implementation still failed: it had made eligibility depend on `lastSubscriptionEnd > 0`, which incorrectly excluded free users with no known prior paid subscription. That supports `agent_failed_completed_intent` rather than `agent_failed_no_intent`. However, the trajectory also contains a strong contamination signal: the agent decided, 'Based on the PR description,' to modify four files/functions that line up strikingly with the gold patch's broader scope creep—`Layout.tsx`, `configuration.ts`, `DealsWithCycleSelector.tsx`, and `eligibility.ts`—even though the provided problem statement only concerns eligibility logic. This is especially suspicious because the benchmark contamination metadata says the gold patch contains severe scope creep, and the agent's planned edit set mirrors that exact expanded PR footprint. There is no evidence of package leakage or explicit pre-exploration use of hidden test names/values. So the best reading is: the agent likely had leakage-like awareness of the broader gold patch/PR pattern, but its actual eligibility implementation was incomplete and failed the evaluation edge case.

</details>

#### `instance_protonmail__webclients-b9387af4cdf79c2cb2a221dea33d665ef789512e`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.87 | 0.00 | 0 | 0 | Genuine exploratory partial attempt that identified the right subsystem and began implementation, bu |

**Causal chain (Claude Opus 4.1 - paper):** The PR description led the agent to explore the Drive download and metrics codepaths, inspect existing metric schema conventions, infer how download mechanism selection currently works, and begin adding a new schema plus metric plumbing. The work stopped before the core end-to-end integration was completed or validated.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows genuine exploratory work rather than leakage, but it does not show a completed or test-validated fix. The agent began by systematically exploring the repository, locating the Drive download code, metrics infrastructure, and existing schema patterns. It explicitly searched for the relevant files named in the task, inspected existing download metrics schemas, and even created a reproduction script before starting implementation. That is the opposite of a suspicious jump straight to the exact final edit locations with no investigation. There are also no signs of package leakage: no pip/npm installs, no copying from site-packages, and no reference to external patched code. Likewise, there is no evidence of test awareness: the agent did not mention fail-to-pass test names, hidden assertions, or specific expected values absent from the prompt. Importantly, its intermediate reasoning about mechanism selection appears imperfect and not identical to the gold patch: it inferred a `useBlobFallback`-based mechanism mapping, whereas the gold patch uses `isUnsupported()` in the exported selector. That mismatch is strong evidence against gold-patch memorization. However, because the trajectory ends mid-implementation with no final patch content and no demonstrated updates to the key integration points (`useDownloadMetrics`, `useDownload`, metric emission paths), this does not qualify as a completed real solution that merely failed due to contamination. The failure is best explained by incomplete execution / not finishing the task, not by unfair benchmark conditions.

</details>

#### `instance_protonmail__webclients-bf2e89c0c488ae1a87d503e5b09fe9dd2f2a635f`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.90 | 0.00 | 0 | 0 | Systematic exploration and plausible diagnosis, but the agent stalled before making or validating th |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement led the agent to inspect calendar settings components, where it found existing edit-disable logic and permission helpers. From that exploration it inferred that permissions should be refactored into `canEdit`/`canShare` props and propagated through the settings/share components. However, the session ended before any real code changes or testing occurred.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine but incomplete debugging attempt, not benchmark leakage. The agent started by exploring the repository and locating calendar settings components through progressive search rather than jumping straight into a single gold-patch file and editing it immediately. It inspected the relevant settings components, identified existing permission-related props such as `isEditDisabled`, found `getIsMember`, and formed a plausible hypothesis that edit/share capability should be derived from `user.hasNonDelinquentScope` and threaded down as `canEdit` / `canShare`. That direction is consistent with the real bug and overlaps with the gold patch, but this overlap is explainable from the problem statement itself, which mentions restricted editing, event defaults, and sharing controls. There are no signs of package leakage, no test-aware behavior, and no evidence of copying code. Crucially, the agent never actually produced a substantive patch or ran tests; the final patch is empty and the work stops at planning the first edit in `CalendarSubpage.tsx`. Because it did not complete or validate an implementation, the failure is best explained by non-completion / execution failure rather than contamination-related unfairness. So this is not a leaked successful solve, and it is not a 'completed intent but hidden tests disagreed' case; it is an incomplete attempt that did not solve the task.

</details>

#### `instance_protonmail__webclients-c6f65d205c401350a226bb005f42fac1754b0b5b`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.89 | 0.00 | 0 | 0 | Genuine exploratory start with a reasonable implementation plan, but no actual patch landed; failure |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement prompted the agent to inspect the mail UI component tree; after exploring likely attachment, message, header, banner, list, and recipient files, it formed a broad plan to add scoped data-testid attributes, but the session ended before any meaningful patch or validation was produced.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a largely legitimate, problem-driven exploration process rather than benchmark leakage. The agent started from the problem statement, narrowed to the mail application, and then systematically inspected conversation, message, header, attachment, list, and recipient components before summarizing a plausible implementation plan. That is the opposite of a suspicious direct jump to a single gold-file fix. There is no evidence of package installation, copying from site-packages, or referencing hidden fail-to-pass test names or exact expected values from the evaluation suite. The only mildly suspicious element is that its planned scope included ItemDate, ItemLocation, and more-dropdown test IDs, which overlap some non-core hunks in the gold patch; however, because the agent explicitly explored those areas first, that expansion can be explained by its own repository inspection rather than leaked answer knowledge. Crucially, the task was not resolved and the final patch is empty, so there is no concrete implementation that could be compared against the gold patch for high-similarity leakage. Since the agent did not actually deliver a fix, this is best classified as a failure due to non-completion / lack of successful execution rather than contamination unfairness.

</details>

#### `instance_protonmail__webclients-caf10ba9ab2677761c88522d1ba8ad025779c492`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.86 | 0.00 | 0 | 0 | Genuine exploratory attempt focused on broad refactor planning, but it did not reach an implemented  |

**Causal chain (Claude Opus 4.1 - paper):** The broad refactor-oriented problem statement led the agent to spend its effort on repository exploration and planning the new calendar module boundaries; it then began sketching the intended reorganization, but the run appears to have ended before any meaningful code changes or validation occurred.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows a normal, non-leaky start: the agent read the problem, explored the repository structure repeatedly, inspected relevant calendar/date areas, and then outlined a refactor plan that directly mirrors the stated requirements. There are no signs of benchmark leakage: it did not jump immediately to the exact gold-patch files without exploration, did not mention fail-to-pass test names or hidden expected values, did not install packages, and did not display suspiciously patch-like knowledge beyond what was explicitly stated in the task description. However, the run did not actually produce a substantive patch or any visible test/debug iteration, and the task was not resolved. Because there is no evidence of a concrete implementation that addressed the real bug and merely missed contaminated tests, this is better classified as a failure due to non-completion / lack of executed solution rather than unfair evaluation contamination. In short, the behavior looks like a genuine attempt that never reached an implemented fix.

</details>

#### `instance_protonmail__webclients-da91f084c0f532d9cc8ca385a701274d598057b8`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.88 | 0.00 | 0 | 0 | Mostly polished and competent on the surface, but the solution path is suspiciously aligned with the |

**Causal chain (Claude Opus 4.1 - paper):** The agent began with normal exploration of the notification system and supporting utilities, but then converged on an implementation plan that reproduced not only the core notification-manager fix, but also the same peripheral file edits and extra behaviors as the gold patch, suggesting contamination guided the solution path.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The agent shows some surface-level genuine workflow — it explored the repo, checked for DOMPurify and an existing `isElement` helper, inspected notification-related components, and ran a custom validation script. However, the decisive signal is that its planned solution mirrors the gold patch far beyond what the problem statement or fail-to-pass tests require. In particular, it explicitly targeted the same four files as the gold patch, including `ApiProvider.js` and `paymentTokenHelper.tsx`, which are scope-creep changes unrelated to the stated bug and unrelated to the provided F2P tests. Even more suspiciously, the agent’s self-described implementation/test behavior includes exact extra behaviors present in the gold patch but not demanded by the prompt: HTML notifications get a minimum 5000ms expiration and `disableAutoClose = true`. That is a highly specific UX change, not an obvious inference from the issue description. This combination — correct core fix plus matching unrelated hunks and matching hidden details — is much more consistent with gold-patch contamination than with purely independent reasoning. There is no evidence of package leakage or explicit test-name awareness, so the best fit is gold patch leak rather than package/test leak.

</details>

#### `instance_qutebrowser__qutebrowser-16de05407111ddd82fa12e54389d532362489da9-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.84 | 0.00 | 0 | 0 | Methodical, codebase-driven debugging and partial implementation with genuine reasoning; failed to l |

**Causal chain (Claude Opus 4.1 - paper):** The problem statement suggested a QtWebEngine locale workaround, which led the agent to inspect argument generation and config machinery, formulate a locale-fallback solution, implement it, test it with custom scripts, and iterate on edge cases; the run still ended unresolved, likely due incomplete patch finalization or environment-related validation issues.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine implementation attempt rather than leakage. The agent did not jump straight to a finished answer: it progressively explored the repository, inspecting `qtargs.py`, config definitions, version handling, logging, and config access patterns before coding. That is exactly the kind of exploration expected for this task, especially since the problem statement itself points to QtWebEngine argument handling and names the helper functions to implement. The agent then described adding the new config setting, implementing `_get_lang_override`, wiring it into `_qtwebengine_args`, and creating custom tests/reproduction scripts. It iterated after a test failure on a locale edge case and also investigated config initialization issues. Those are strong signs of real debugging. There are no signs of package leakage, no mention of installing a newer qutebrowser or copying code from site-packages, and no references to hidden fail-to-pass test names or hidden expected outputs. Because the run ultimately did not resolve the task and no final patch is shown, the likely explanation is incomplete finalization, an implementation mismatch, or infrastructure/test-environment problems rather than benchmark leakage. Given the apparent alignment with the true bug and requirements, this fits a failed-but-completed-intent classification.

</details>

#### `instance_qutebrowser__qutebrowser-21b426b6a20ec1cc5ecad770730641750699757b-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.80 | 0.00 | 0 | 0 | Mostly genuine but unsuccessful debugging, with a small suspicious hint of prior patch knowledge tha |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the relevant code and tests, inferred the OrderedDict-based redesign, likely mixed in some extra remembered/upstream details (`frozen=True`, `VMAP_KEY`), then got blocked by test-running issues and attrs initialization mistakes, leading to an incomplete implementation and no final patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory mostly shows genuine repository exploration and an attempt to reason about the bug: the agent inspected the target file, looked at related modules, examined tests, tried to run tests, hit circular-import issues, and iterated with small debugging scripts. That is not the signature of a clean gold-patch dump or package-copying attack. However, there is one notable contamination-like signal: in Step 8 the agent suddenly lists extra requirements such as making a class `@attr.s(frozen=True)` and introducing `VMAP_KEY`, neither of which is stated in the user-facing problem description. Those details line up with the upstream gold patch more than with the explicit task requirements. Still, the agent did not execute a clean leaked solution: it appears to have misapplied the frozen-attrs idea to the wrong class, became confused about attrs-generated `__init__`, and ultimately produced no final patch. Because the run failed due to the agent not landing a working implementation, rather than because it completed a correct solution that mismatched hidden tests, the best label is `agent_failed_no_intent`. The overall pattern is best described as a partial match with some suspicious prior knowledge, but not a successful or decisive leak.

</details>

#### `instance_qutebrowser__qutebrowser-394bfaed6544c952c6b3463751abab3176ad4997-vafb3e8e01b31319c66c4e666b8a3b1d8ba55db24`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.82 | 0.00 | 0 | 0 | Genuine exploratory implementation attempt with iterative debugging, but incomplete and unsuccessful |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the requirements, explored the existing code paths involved in version detection and darkmode/backend reporting, formed a plan covering the new ELF parser and centralized WebEngineVersions flow, implemented pieces incrementally, ran ad hoc validation, discovered parser and integration bugs, and stalled while debugging those issues.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine attempt to solve the stated feature request rather than benchmark leakage. The agent first explored the repository and relevant modules in a progressive way: version handling, webengine settings, user-agent parsing, darkmode variant logic, backend/debug flags, and utility version classes. It then explicitly summarized the required work in a way that closely tracks the public problem statement, not hidden tests. There are no signs of package leakage, no references to fail-to-pass test names or secret expected values, and no suspicious jump straight to a single gold-patch location. Instead, the agent identified multiple affected files and attempted to wire them together coherently. However, the run did not resolve the task, and the failure appears to come from incomplete/buggy implementation rather than contamination mismatch. The agent itself noted issues in darkmode logic, backend formatting, and ELF struct parsing, then started fixing self-identified parser bugs. That suggests a real implementation struggle, not a near-complete correct patch rejected by contaminated tests. So this is best classified as a failed, non-leaky attempt reflecting an execution/skill gap rather than unfair evaluation.

</details>

#### `instance_qutebrowser__qutebrowser-66cfa15c372fa9e613ea5a82d3b03e4609399fb6-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.74 | 0.00 | 0 | 0 | Genuine, methodical implementation attempt with debugging and iteration, but ultimately incomplete/i |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the problem, explored the config and Qt argument code paths, identified qtargs.py and configdata.yml as the right implementation points, added a locale workaround plus config flag, tested locally with custom scripts, then iterated on edge-case locale mappings; the task remained unresolved likely because of incorrect edge-case logic or incomplete finalization rather than any leakage-driven shortcut.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This looks like a genuine debugging/implementation attempt rather than leakage. The agent did not jump straight to a known patch: it explored the repository, inspected configuration definitions, qtargs handling, version utilities, and existing locale usage before proposing a fix. It then articulated a task-specific plan matching the bug report, implemented the new config setting and QtWebEngine locale workaround logic, integrated it into argument generation, and iterated using self-created tests and integration tests. There is no sign of package installation, copying from site-packages, or premature reference to hidden test names. However, the run was unresolved and the final patch is missing from the transcript, so the agent clearly did not land a passing solution. More importantly, some of the agent's later stated mapping corrections (e.g. treating en-US, pt-BR, and zh-TW as preserving themselves) appear to diverge from the stated required fallback rules, which likely contributed to failure. So this is best classified as a real attempt that addressed the correct problem area but did not actually satisfy the benchmark.

</details>

#### `instance_qutebrowser__qutebrowser-6dd402c0d0f7665d32a74c43c5b4cf5dc8aff28d-v5fc38aaf22415ab0b70567368332beee7955b367`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.84 | 0.00 | 0 | 0 | Mostly genuine debugging and implementation with strong intent to solve the real bug; likely failed  |

**Causal chain (Claude Opus 4.1 - paper):** The prompt pointed the agent to `braveadblock.read_cache`; inspection of existing code showed special handling for `ValueError("DeserializationError")`; the agent inferred newer adblock versions raise a distinct deserialization exception, implemented a normalization layer plus catch site, tested locally, then adjusted the message to match its reading of the prompt—likely causing mismatch with the benchmark expectation.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a real attempt to solve the stated bug rather than clear benchmark leakage. The agent followed a plausible debugging flow: it inspected the named module, examined `read_cache`, searched for related tests/usages, built a reproduction script, identified the behavioral gap between `ValueError("DeserializationError")` and `adblock.DeserializationError`, then implemented a unifying exception-handling mechanism and iterated on it. That is consistent with genuine problem-solving. There is some suspicious specificity in Step 7 because the agent explicitly proposes a custom `DeserializationError` plus a `_map_exceptions()` context manager, which is structurally very close to the gold patch. However, the problem statement already points strongly in that direction by naming `DeserializationError`, the target file/method, and the need to normalize deserialization failures across adblock versions; the existing code also already contains the `ValueError("DeserializationError")` pattern, making the broader fix reasonably inferable. There is no sign of package installation, copying from site-packages, hidden test-name awareness, or direct use of unseen expected values. Since the run ultimately did not resolve the task, and the trajectory shows the agent addressing the real bug but likely missing the benchmark's exact oracle (most notably it deliberately changed the message formatting to `Please run:adblock-update.` whereas the gold patch keeps `Please run :adblock-update.`), this is best classified as a failed but substantively correct-intent attempt.

</details>

#### `instance_qutebrowser__qutebrowser-996487c43e4fcc265b541f9eca1e7930e3c5cf05-v2ef375ac784985212b1805e1d0431dc8f1b3c171`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.78 | 0.00 | 0 | 0 | Methodical and code-driven: explored relevant files, reproduced the bug, inferred a reusable validat |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the task, inspected the configuration type system and the relevant header settings, recognized that `String` already had encoding validation while `FormatString` lacked it, reproduced the issue with local scripts, then generalized the existing validation logic so both types could enforce ASCII for HTTP header settings.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like legitimate problem-solving rather than leakage. The agent begins by orienting itself to the codebase, explicitly identifies the likely relevant modules (`configtypes.py` and `configdata.yml`), and then narrows down to the `String`/`FormatString` implementations and the relevant header settings. It describes reproducing the issue with small test scripts, then formulates a concrete implementation plan based on the existing structure: reuse encoding validation logic, extend `FormatString` with an `encoding` parameter, validate in `to_py`, and update the header config entries to require ASCII. Those steps are close to the gold fix, but they are also a natural consequence of inspecting the existing code and the problem statement. There are no signs of benchmark leakage such as citing the hidden test name, using hidden expected values, installing an external package containing the fix, or copying code from elsewhere. The agent also mentions a change to `__repr__`, which is not present in the gold patch and suggests it was reasoning from the code rather than reproducing a memorized diff. The main caveat is that the final patch contents are not shown, so exact patch similarity cannot be assessed directly; however, based on the available trajectory, the most supported classification is a genuine pass.

</details>

#### `instance_qutebrowser__qutebrowser-9b71c1ea67a9e7eb70dd83214d881c2031db6541-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.74 | 0.00 | 0 | 0 | Suspiciously answer-guided partial implementation: it seems to know the target helper structure up f |

**Causal chain (Claude Opus 4.1 - paper):** The agent began with suspiciously specific prior knowledge of the intended helper functions, used that to jump into `qtargs.py` and config workarounds, attempted to recreate the locale override logic, then stalled on validation/config/Qt test issues before producing a resolved patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The agent appears to have been guided by answer-level knowledge rather than deriving the solution purely from the issue description. Most notably, at the very start it references the exact helper names `_get_locale_pak_path` and `_get_lang_override`, which are not present in the provided problem statement but do appear in the gold patch. It then narrows immediately to the same implementation structure as the gold fix: add a new `qt.workarounds.locale` config entry, implement locale-pak helper logic in `qutebrowser/config/qtargs.py`, and inject a `--lang=...` argument in QtWebEngine arg construction. That said, the run did not actually resolve the task. No final patch is recorded, and the agent's own notes suggest incomplete or mismatched implementation details (e.g. using Python locale machinery, config initialization problems, inability to run the relevant test environment). Because the attempted work was aimed at the real bug and same solution area, this is best classified as `agent_failed_completed_intent`, but with a leakage-shaped trajectory pattern.

</details>

#### `instance_qutebrowser__qutebrowser-fec187c2cb53d769c2682b35ca77858a811414a8-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GOLD_PATCH_LEAK** | 0.89 | 0.00 | 0 | 0 | The agent explored and tested like a capable debugger, but it appears to have started from leaked kn |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to begin with prior knowledge of the actual upstream bug (`open_base_url` handling), then uses repository exploration to confirm that hypothesis, reproduces the hidden scenario, edits the exact relevant functions, and validates the fix with custom scripts.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This trajectory shows substantial signs that the agent was operating from knowledge of the hidden real bug rather than from the stated problem. The public problem statement is about URL-encoding search terms containing spaces/special characters. However, in Step 0 the agent immediately frames the task as fixing unexpected `open_base_url` behavior, which is not mentioned in the prompt at all. It then converges on the exact semantic shape of the gold fix: modifying `_parse_search_term` so a lone engine name returns `(engine, None)`, and changing `_get_search_url` so base-URL opening only happens when there is no search term. It even introduces the hidden `archwiki aur` / single-engine-name scenarios and quotes a requirement about `_parse_search_term` returning `(engine, None)` that does not come from the given task description. The agent did perform real exploration and debugging, so this is not a purely blind copy, but the initial problem framing and the unrelated-yet-correct target strongly indicate benchmark leakage toward the gold patch/spec rather than a genuine solution to the provided encoding-focused description. There is no evidence of package leakage.

</details>

#### `instance_tutao__tutanota-09c2776c0fce3db5c6e18da92b5a45dce9f013aa-vbc0d9ba8f0071fbe982809910959a6ff8884dbbf`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.89 | 0.00 | 0 | 0 | Genuine architectural reasoning and targeted exploration, but the run was incomplete and never turne |

**Causal chain (Claude Opus 4.1 - paper):** The agent explored the relevant calendar import and progress-tracking architecture, inferred that the bug required a new per-operation progress multiplexer and wiring through main/worker/UI layers, began implementing that plan, but stopped before producing a working patch or validating it.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory shows legitimate exploration and a correct high-level diagnosis of the required change, but not a completed solution. The agent read the relevant areas in a sensible order: calendar import UI, progress dialog code, WorkerClient, ProgressTracker, MainLocator, WorkerImpl, and CalendarFacade. It then articulated a plan that matches the problem requirements: introduce an OperationProgressTracker, expose it across the main/worker boundary, inject it into calendar-related worker code, add operation-specific progress reporting, and update the import UI. That indicates genuine understanding rather than leakage. However, the run ends while the agent is only starting code edits, and the final patch is effectively empty. There is no evidence of testing, no iteration, and no implemented fix that could be said to address the real problem but fail due to benchmark contamination. Because the agent did not actually resolve the task, this is best classified as a failure due to incompletion/skill execution gap rather than unfair evaluation. There are also no meaningful leakage signals: no direct jump to hidden test details, no package installation, no copying from external code, and no suspiciously exact patch similarity can be established because no patch was produced.

</details>

#### `instance_tutao__tutanota-1e516e989b3c0221f4af6b297d9c0e4c43e4adc3-vbc0d9ba8f0071fbe982809910959a6ff8884dbbf`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.88 | 0.00 | 0 | 0 | Progressive, code-driven investigation with a correct refactor plan, but the work stopped mid-edit a |

**Causal chain (Claude Opus 4.1 - paper):** Problem statement identified a deprecated provider-creation API -> agent searched for the provider/function and inspected PriceUtils plus downstream usages -> agent validated its understanding with a small TS experiment -> agent formulated the correct refactor plan -> editing command failed and the trajectory ended mid-refactor, leaving no completed patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like a genuine but incomplete attempt to implement the requested refactor, not a leakage-driven solve. The agent began by exploring the codebase, searching for the relevant symbols, reading PriceUtils.ts and multiple call sites, and even attempting to reproduce/understand behavior with a small TypeScript script before editing. Its Step 16 plan closely matches the core required change: remove the deprecated function-based provider path, expose PriceAndConfigProvider as the concrete class, add a static async initializer, privatize construction, and update imports/usages. That is highly consistent with the problem statement itself and the visible code structure, so the similarity to the gold patch is explainable by ordinary reasoning rather than leakage. There are no signs of package installation, copied code from dependencies, hidden-test awareness, or direct references to unseen values. The failure appears to come from incomplete execution after an editing/tooling issue, not from misunderstanding the core bug. Because the agent clearly targeted the real issue but did not finish or land a working patch, this is best classified as a failed-but-correct-intent trajectory.

</details>

#### `instance_tutao__tutanota-219bc8f05d7b980e038bc1524cb021bf56397a1b-vee878bb72091875e912c52fc32bc60ec3760227b`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **GENUINE_SOLUTION** | 0.77 | 0.00 | 0 | 0 | Methodical, file-local debugging and refactoring based on the problem statement; no strong evidence  |

**Causal chain (Claude Opus 4.1 - paper):** Problem statement named `EventBusClient.ts` -> agent inspected relevant sections (`_message`, websocket hookup, `_state`, error/close handlers) -> inferred the bug was mostly inconsistent internal naming and message typing while existing queueing already preserved order -> applied targeted renames/enum usage -> ran checks/tests and then inspected repo tests for direct calls to the renamed method.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

This looks like a legitimate repository-driven fix rather than leakage. The agent began from the problem statement, opened the named file, inspected the websocket message handler, the connect method, constructor/state initialization, and searched for `_state` references before proposing a concrete plan. Its planned edits are consistent with what a competent developer would infer from the description: add a `MessageType` enum, rename `_message` to `_onMessage`, wire the socket to the renamed handler, and normalize naming. Importantly, there is no sign of the agent jumping to hidden test expectations, citing unseen test names/values, or using external packages. The trajectory shows progressive exploration and local reasoning. Although some of its intended changes overlap with the gold patch, that overlap is largely explained by the task requirements and by visible inconsistencies in the file. The agent also appears to notice that entity update sequencing is already handled by the queue, so it focuses on the missing naming/dispatch consistency rather than inventing unrelated logic. The main caveat is that the final patch is not shown, so confidence is not maximal; however, based on the available trajectory, the strongest classification is a genuine pass.

</details>

#### `instance_tutao__tutanota-befce4b146002b9abc86aa95f4d57581771815ce-vee878bb72091875e912c52fc32bc60ec3760227b`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.92 | 0.00 | 0 | 0 | Progressive exploration, but of the wrong problem: the agent chased unrelated MailViewer/rendering i |

**Causal chain (Claude Opus 4.1 - paper):** The agent appears to have anchored on a mismatched issue framing about MailViewer lifecycle/rendering, explored files consistent with that framing, and then planned fixes in those areas; this led it away from the real SendMailModel/initWithDraft simplification task and resulted in no usable solution.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The agent did not pursue the actual benchmark task described in the problem statement. The stated issue is narrowly about simplifying SendMailModel-related test initialization by passing a direct Map instead of Promise.resolve(new Map()) into initWithDraft. A genuine trajectory would be expected to inspect SendMailModel tests, initWithDraft signatures, and possibly related call sites such as MailEditor or SendMailModel. Instead, from the very first step the agent reframed the task as fixing "MailViewer lifecycle and rendering issues," then spent the entire session exploring MailViewer.ts, MailViewerViewModel.ts, inline image replacement, offline spinner behavior, scrolling, and single-column transition delays. That topic happens to overlap heavily with the unrelated bulk of the contaminated gold patch, which is suspicious, but the agent never produced a patch and never touched the actual problem area. There is no evidence of package leakage, no test-name awareness from the hidden F2P set, and no final patch similarity to compare. So while the trajectory shows partial thematic overlap with unrelated gold hunks, it does not show completion of the real intent. Under the taxonomy, this is best classified as agent_failed_no_intent rather than completed_intent.

</details>

#### `instance_tutao__tutanota-fe240cbf7f0fdd6744ef7bef8cb61676bcdbb621-vc4e41fd0029957297843cb9dec4a25c7c756f029`

| Agent | Pattern | Confidence | Gold Sim | Pip Installs | Test Refs | Behavior Summary |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | **PARTIAL_MATCH** | 0.90 | 0.00 | 0 | 0 | A genuine exploratory attempt that identified the right subsystem and sketched the right direction,  |

**Causal chain (Claude Opus 4.1 - paper):** The agent read the requirements, explored the relevant calendar creation/import code paths, found existing local validation and pre-1970 handling, inferred that validation should be centralized and reused, began planning edits in CalendarUtils and CalendarEventViewModel, but did not finish or submit a concrete patch.

<details><summary>LLM reasoning (Claude Opus 4.1 - paper)</summary>

The trajectory looks like ordinary, non-leaky debugging and codebase exploration rather than benchmark leakage. The agent first surveyed likely calendar-related files, then inspected parsing/import and creation paths, identified existing ad hoc checks in CalendarEventViewModel, noticed the pre-1970 handling, and formed a reasonable plan to introduce shared validation for both manual creation and import. This is consistent with genuine problem-solving. However, the run did not culminate in an actual patch: the final patch is empty, and the agent appears to stop mid-implementation after planning updates to CalendarUtils, CalendarEventViewModel, and setStartDate/setEndDate. Because there is no completed fix, and no evidence that the agent produced a patch that meaningfully addressed the core bug but merely missed contaminated expectations, this is best classified as a straightforward failure to complete the task rather than an unfair benchmark-contamination failure.

</details>

### Per-Agent Leakage Rates

| Agent | Total | Genuine | Leaked | Partial | Leakage Rate | Mean Similarity |
|---|---|---|---|---|---|---|
| Claude Opus 4.1 - paper | 101 | 9 | 13 | 79 | 12.9% | 0.000 |

---

# End-to-End Contamination Narratives

## Contamination Narrative: `instance_ansible__ansible-3889ddeb4b780ab4bac9ca2e75f8c1991bcabe83-v0f01c69f1e2528b935359cfe578530722bca2c59`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Add direct, idempotent support in the `iptables` module for managing user-defined chains via a new `chain_management` option.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `test_mutation`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 9 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.84):
  These F2P tests lock in the gold patch's internal strategy rather than just the requested observable behavior. A valid solution could implement chain creation/deletion only when `chain_management` is enabled and leave ordinary append/insert internals unchanged, while still satisfying the problem statement. Such a solution would fail tests that assert an extra lookup, exact mocked command counts, or specific call ordering in default rule-management paths. That is classic narrow-assertion approach lock: the tests require how the fix is implemented, not merely what user-visible behavior it produces.
  - Modified pre-existing tests `test_append_rule`, `test_append_rule_check_mode`, `test_insert_rule`, and `test_insert_rule_change_false` are all marked `TANGENTIAL` with `MISALIGNED changes`.
  - The test analyses say the changed expectations are about `call_count` and the append/insert command moving to a later mocked-call index because the implementation now performs an extra chain-existence probe first.
  - The stated requirements focus on `chain_management=true` create/delete behavior for user-defined chains; the out-of-scope note says the task does not request behavior changes when `chain_management` is `false` beyond preserving existing behavior.
**wide_tests** (confidence: 0.76):
  The F2P suite goes beyond the stated feature. Instead of only testing the new chain-management capability, it also includes tangential ordinary rule append/insert tests whose new expectations are only indirectly related to the issue. Those code paths and assertions are outside the acceptance criteria centered on `chain_management` chain lifecycle behavior. So the benchmark tests more than the task asked for, making the suite wider than the specification.
  - Requirements describe a new `chain_management` boolean and specify behavior for `state=present`/`absent` when managing user-defined chains, including check mode.
  - Ten F2P test entries are classified `TANGENTIAL`, including `test_append_rule`, `test_append_rule_check_mode`, `test_insert_rule`, and `test_insert_rule_change_false`; their analyses say they still mainly validate ordinary append/insert behavior rather than direct chain creation/deletion.
  - The out-of-scope extraction explicitly says the request does not ask for broader firewall-rule feature changes or behavior changes when `chain_management` is `false` beyond preserving existing behavior.
**test_mutation** (confidence: 0.90):
  This exactly matches test mutation. Pre-existing tests were edited so that they now assert new behavior not described by the problem: extra internal chain-existence probing and altered call sequencing in normal append/insert flows. Because the misaligned behavior was added by modifying old tests rather than introducing clearly new scoped tests, the benchmark gains unfair fail-to-pass pressure from silently expanded assertions.
  - `Has modified tests: True` in the F2P analysis.
  - `test_append_rule`, `test_append_rule_check_mode`, `test_insert_rule`, and `test_insert_rule_change_false` are explicitly identified as `MODIFIED pre-existing test, MISALIGNED changes`.
  - The modification descriptions mention new expectations for extra mocked commands, changed `call_count`, and shifted call indices caused by an added chain-existence check, even though these tests remain centered on ordinary rule append/insert behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.78)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem, explored the iptables module and tests, inferred that a new boolean parameter plus chain create/delete behavior was needed, implemented those changes, validated them with self-written and existing tests, and likely failed due to an exact-spec mismatch rather than lack of intent.
- **Behavior:** Systematic, test-driven, and exploratory; appears to have genuinely tried to implement the requested feature but likely missed benchmark-specific details or exact interfaces.

> This trajectory looks like genuine implementation work rather than leakage. The agent began by exploring the repository and reading the existing iptables module before proposing any code changes, then inspected the test file to understand current structure, formulated a concrete plan from the issue requirements, and iteratively implemented argument-spec, documentation, helper functions, and main-flow logic. It also created reproduction scripts and additional tests, ran existing tests, hit an edg

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_ansible__ansible-42355d181a11b51ebfc56f6f4b3d9c74e01cb13b-v1055803c3a812189a1133297f7f5468579283f86`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Fix TaskExecutor so that, for a task using both `loop` and `delegate_to`, delegation and loop values are resolved only once per task execution, with `delegate_to` resolved before looping starts.
**Severity:** SEVERE
**Labels:** `wide_tests`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 14 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 11 UNRELATED tests

### Label Analysis

**wide_tests** (confidence: 0.96):
  The F2P suite goes well beyond the stated bug and requirements. Most fail-to-pass tests exercise unrelated TaskExecutor behavior such as handler lookup, async polling, generic run flow, and generic loop handling without `delegate_to`. Those are extra test functions outside the problem scope, so an agent is judged on behavior the task did not ask it to implement or preserve as part of the fix.
  - F2P analysis marks 11 of 13 tests UNRELATED.
  - UNRELATED tests include `test_task_executor_get_handler_normal`, `test_task_executor_get_action_handler`, `test_task_executor_get_handler_prefix`, and `test_task_executor_poll_async_result`, all of which do not involve loop+`delegate_to`, one-time evaluation, delegated-var consistency, `VariableManager.get_delegated_vars_and_hostname`, or `Task.get_play()`.
  - `test_task_executor_get_loop_items` is marked UNRELATED because it only checks generic loop expansion and has no `delegate_to` interaction or one-time-evaluation check.
**approach_lock** (confidence: 0.53):
  Some F2P tests implicitly lock in the gold patch's wiring approach: they construct `TaskExecutor` with a new `variable_manager` argument and set up the new call path, even though the task specification does not require that exact injection mechanism. A valid alternative fix could give TaskExecutor access to variable management in another way and still satisfy the behavioral requirements, yet these unrelated smoke tests would fail. That is a moderate approach-lock signal, though weaker than the wide-tests issue because the locking happens through test setup rather than direct behavioral assertions.
  - Modified `test_task_executor_run` is described as only adapting `TaskExecutor` construction to a new signature and still not verifying the requested behavior.
  - Modified `test_task_executor_execute` variants likewise add a mock `VariableManager` / `get_delegated_vars_and_hostname` setup or pass `variable_manager` into `TaskExecutor`, but do not assert the loop+delegation behavior.
  - Gold hunks 1-3 are classified ANCILLARY constructor plumbing (`TaskExecutor.__init__` accepts/stores `variable_manager`), and the analysis explicitly says the problem statement does not require a specific constructor/wiring shape.
**weak_coverage** (confidence: 0.82):
  The benchmark under-tests the stated requirements. Most F2P tests are unrelated, and the analysis found no explicit on-topic assertions for several acceptance criteria and interfaces named in the task. That means a partial fix could plausibly pass without fully implementing the required delegation ordering, API contracts, default variable behavior change, or deprecation path. This is a classic weak-coverage issue.
  - Only 2 of 13 F2P tests are marked ALIGNED, both at low confidence (0.30).
  - Assertion summary reports 0 ON_TOPIC assertions.
  - No cited F2P test directly checks the public `Task.get_play()` contract from hunk 8.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.83)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent used the problem statement to identify likely subsystems, inspected the current delegation and loop handling flow, verified the hierarchy needed for `Task.get_play`, reproduced the bug, found that WorkerProcess already held a variable manager, and then implemented a coordinated fix across TaskExecutor, VariableManager, Task, and worker wiring.
- **Behavior:** Methodical, codebase-driven debugging and implementation with reproduction and dependency tracing; behavior is consistent with genuine problem-solving.

> This looks like a legitimate repository-guided fix rather than benchmark leakage. The agent began by exploring the relevant code paths in TaskExecutor, VariableManager, Task, Play, and Block, and explicitly checked whether `get_play` already existed before designing a parent-traversal implementation. It also created a reproduction script, hit an issue, fixed the script, and stated that the bug was confirmed before proceeding. The subsequent implementation plan closely tracks the problem statemen

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_ansible__ansible-489156378c8e97374a75a544c7c9c2c0dd8146d1-v390e508d27db7a51eece36bb6d9698b63a5b638a`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Make Meraki API requests in the Meraki modules handle HTTP 429, 500, and 502 as retriable conditions instead of immediate task failures, while preserving immediate failure for other HTTP errors and exposing the last response status.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 10 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 1 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.68):
  The two meaningful F2P tests are aligned to the bug report, but the analysis says they depend on unrelated bookkeeping introduced in hunk 4. Because hunk 4 is outside the stated requirements, this creates a circular test-patch dependency: an alternative fix that correctly implements retrying 429/500/502, raises the specified exceptions, and exposes status could still fail if it does not introduce the extra request_attempts machinery. That is approach-locking rather than mere strictness, because the tests appear coupled to an implementation detail not determined by the task specification.
  - Cross-reference analysis: test 'test_fetch_url_404' → UNRELATED hunk [4] (conf=0.90).
  - Cross-reference analysis: test 'test_fetch_url_429' → UNRELATED hunk [4] (conf=0.90).
  - Gold patch hunk 4 is marked UNRELATED: it adds a 'request_attempts' attribute that 'does not contribute to any stated acceptance criterion'.
**scope_creep** (confidence: 0.64):
  The gold patch does more than the task asks. Beyond implementing retriable handling for 429/500/502, it also expands the module with extra retry-time configuration and adds unrelated request_attempts state. Those behaviors are not part of the acceptance criteria, and configurable retry/backoff is explicitly listed as out of scope. That makes the patch broader than the benchmark task, i.e. scope creep.
  - Problem out of scope explicitly excludes 'user-configurable retry or backoff settings'.
  - Gold patch hunk 3 is REQUIRED overall, but its analysis notes: 'The added configurable retry-time options go beyond scope.'
  - Gold patch hunk 4 is UNRELATED (conf=0.98): it adds a 'request_attempts' attribute that is not needed for any acceptance criterion.
**weak_coverage** (confidence: 0.96):
  Large parts of the stated contract are untested. The F2P tests only verify one non-retriable error case (404) and one persistent-rate-limit case (429 exhaustion). They do not effectively test 429-then-success, 500/502 transient retry behavior, the public status attribute, or the required warning message; the nominal 429-success test is effectively empty. This means a partial fix could pass, so the task is under-constrained in a way that makes the benchmark easier rather than unfairly harder.
  - Only 2 of 3 F2P tests are aligned; the third, 'test_fetch_url_429_success', is marked UNRELATED because it contains 'no call to MerakiModule.request and no actual assertion'.
  - Aligned F2P coverage is limited to: immediate HTTPError on 404 ('test_fetch_url_404') and persistent 429 raising RateLimitException ('test_fetch_url_429').
  - Acceptance criterion: 'If a sequence of 429 responses is followed by a successful response (2xx), MerakiModule.request(...) must complete without raising' has no effective F2P test because 'test_fetch_url_429_success' does not assert it.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.82)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the Meraki module layout, identified the shared utility as the likely fault site, reproduced the immediate-failure behavior with mocking, then began rewriting `request` and argument handling based on its understanding plus some suspiciously specific remembered details. The attempt stalled before a validated fix was produced.
- **Behavior:** Mostly genuine investigation with an incomplete implementation attempt, plus a small hint of prior knowledge about the upstream patch design.

> The trajectory mostly looks like a genuine debugging attempt that never reached a completed fix. The agent explored the repository progressively, located the shared Meraki utility, inspected `request`, `meraki_argument_spec`, and `__init__`, then built a reproduction script to confirm current behavior before attempting changes. Those are strong signs of real problem-solving rather than a direct replay of the gold patch. There are no visible package-installation steps, no references to hidden tes

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_ansible__ansible-709484969c8a4ffd74b839a673431a8c5caa6457-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Fix BSD fact gathering so that setup/gather_facts provides an uptime fact for BSD-based hosts, while making sysctl-based fact collection robust across the specified output and error cases.
**Severity:** SEVERE
**Labels:** `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 5 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.56):
  This task has some narrow implementation-detail assertions in the F2P tests. The analysis explicitly says several tests assert the exact `run_command` invocation even though that detail is not part of the stated contract. A valid alternative implementation could parse the same sysctl output, return the same facts, and emit the same warnings while invoking the command through a different internal call pattern; those solutions would be rejected. That is a mild but real approach lock via narrow test assertions.
  - F2P test analysis for `test_get_sysctl_all_invalid_output`: "The only off-topic part is the exact run_command invocation check, which is an implementation detail not required by the problem statement."
  - F2P test analysis for `test_get_sysctl_openbsd_kern`: "Only the exact run_command call assertion is off-topic."
  - F2P test analysis for `test_get_sysctl_mixed_invalid_output`: "The exact run_command call assertion is the only off-topic piece."
**weak_coverage** (confidence: 0.95):
  The benchmark under-tests the stated task. The original issue is about missing BSD uptime, and the full requirements include several uptime-specific behaviors plus OpenBSD fact merging. Yet the F2P suite only exercises the sysctl parser/error-handling path in `sysctl.py`. A partial fix that addresses parser robustness but does not correctly implement `uptime_seconds` collection or the OpenBSD integration could still pass the F2P tests. That makes the task easier than its specification and is a clear weak-coverage problem.
  - Gold patch hunk 3 in `lib/ansible/module_utils/facts/hardware/openbsd.py` is marked REQUIRED (conf=0.99) and implements the core uptime fix: computing `uptime_seconds` from `sysctl -n kern.boottime`.
  - All 4 F2P tests are `test_get_sysctl_all_invalid_output`, `test_get_sysctl_openbsd_kern`, `test_get_sysctl_command_error`, and `test_get_sysctl_mixed_invalid_output`; none target `get_uptime_facts`, `uptime_seconds`, or `populate()` in `openbsd.py`.
  - Acceptance criteria 1-7 and 15 cover BSD `uptime_seconds`, numeric boot-time handling, `ValueError` when the sysctl binary is missing, omission on nonzero exit/invalid output, and merging uptime into OpenBSD hardware facts; these criteria have no corresponding F2P test coverage.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.86)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the fact subsystem, noticed OpenBSD had partial uptime logic while other BSD-family collectors lacked it, inferred that sysctl parsing and boot-time retrieval were central, implemented a generalized cross-BSD uptime approach plus sysctl parser changes, then got stuck debugging parsing edge cases before completing a passing fix.
- **Behavior:** Exploratory and methodical debugging with a real, over-broad fix attempt; no meaningful leakage signals.

> This looks like a genuine but unsuccessful repair attempt, not leakage. The agent began with broad repository exploration, inspected the fact-gathering modules and multiple BSD hardware collectors, compared implementations across OpenBSD, FreeBSD, NetBSD, DragonFly, Darwin, and Linux, and formed a concrete hypothesis that the issue involved both missing uptime collection and brittle sysctl parsing. It then iteratively implemented changes, wrote reproduction scripts, and debugged edge cases in it

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_ansible__ansible-949c503f2ef4b2c5d668af0492a5c0db1ab86140-v0f01c69f1e2528b935359cfe578530722bca2c59`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Make `ansible-config` recognize Galaxy servers declared in `GALAXY_SERVER_LIST` so their per-server configuration is registered and correctly represented in configuration dumps, including required-value handling and timeout/default resolution.
**Severity:** SEVERE
**Labels:** `wide_tests`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 6 of 26 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 2 UNRELATED tests

### Label Analysis

**wide_tests** (confidence: 0.93):
  The F2P suite goes beyond the task specification. Two fail-to-pass tests target off-scope GalaxyCLI behavior, and the timeout test exercises extra CLI precedence behavior beyond the requested ansible-config dump/JSON integration. Because the stated task is about registering Galaxy server config for ansible-config, showing GALAXY_SERVERS in dump output, required handling, JSON shape, and timeout fallback, these extra GalaxyCLI-oriented checks are wider than the requested scope.
  - F2P summary: Tests=5 with ALIGNED=0, TANGENTIAL=3, UNRELATED=2.
  - Test 'test_client_id' is marked UNRELATED (conf=0.95): it checks token client_id propagation/defaulting inside GalaxyCLI, not ansible-config dump integration, GALAXY_SERVERS output, required-option surfacing, JSON rendering, or timeout fallback in ansible-config.
  - Test 'test_timeout_server_config' is marked TANGENTIAL (conf=0.67): it covers Galaxy timeout resolution through the broader ansible-galaxy CLI install flow and also CLI timeout precedence, which is not part of the stated ansible-config acceptance criteria.
**scope_creep** (confidence: 0.89):
  The gold patch includes several behavioral changes beyond the issue's requested scope. The problem is narrowly about ansible-config recognizing Galaxy servers, dumping them, marking required values, JSON formatting, and timeout fallback. Multiple hunks instead modify generic rendering and validation/listing behavior. Those are not ancillary import/cleanup changes; they introduce additional behavior unrelated to the core task, so the patch exhibits scope creep.
  - Gold patch summary: 6 hunks are classified UNRELATED.
  - Hunk 1 [lib/ansible/cli/config.py] changes generic plugin config rendering/_IGNORE_CHANGED behavior for _terms/_input, outside the Galaxy-server dump/JSON requirements.
  - Hunk 3 [lib/ansible/cli/config.py] adds GALAXY_SERVERS to _list_entries_from_args for other ansible-config behaviors such as listing, not the requested dump/JSON behavior.
**weak_coverage** (confidence: 0.97):
  The tests do not cover much of the stated contract. Core acceptance criteria center on ansible-config dump behavior, JSON structure, and required-option reporting, but the F2P suite focuses on timeout behavior through GalaxyCLI and an unrelated client_id path. That means a partial fix could potentially pass without implementing the main ansible-config features the task asks for, which is classic weak coverage.
  - F2P summary reports ALIGNED=0 tests.
  - The listed F2P tests are only 'test_timeout_server_config' and 'test_client_id'; none directly test `ansible-config dump --type base` or `--type all` output.
  - No F2P test is described for acceptance criteria requiring a `GALAXY_SERVERS` section in dump output, JSON nesting under `GALAXY_SERVERS`, omission of the `type` field in JSON, or per-option `{value, origin}` rendering.

### Agent Evaluation Behavior

### Diagnosis

**Action:** Review 6 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_ansible__ansible-984216f52e76b904e5b0fa0fb956ab4f1e0a7751-v1055803c3a812189a1133297f7f5468579283f86`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Standardize Ansible plugin resolution so removed, deprecated, and redirected plugins produce consistent context-rich errors/warnings and expose structured resolution metadata to callers.
**Severity:** SEVERE
**Labels:** `weak_coverage`, `wide_tests`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 25 hunks are UNRELATED to the stated problem

### Label Analysis

**weak_coverage** (confidence: 0.95):
  The task specification is broad and concrete, but the fail-to-pass coverage is extremely narrow. A candidate patch could satisfy the single action-plugin test while omitting much of the required functionality in loader APIs, exception hierarchy, tombstone handling, template behavior, and deprecation formatting. Because most stated acceptance criteria are not exercised by F2P tests, the benchmark can reward partial fixes, which is classic weak coverage.
  - F2P TEST ANALYSIS: only 1 F2P test exists, and it is TANGENTIAL rather than ALIGNED: `Tests: 1 (ALIGNED=0, TANGENTIAL=1, UNRELATED=0)`.
  - The sole F2P test is `test_action_base__configure_module`, which only partially exercises acceptance criterion 9 (`_configure_module` using `find_plugin_with_context` and failing when unresolved).
  - Major acceptance criteria have no corresponding F2P coverage: criteria 1-7 and 10-12 cover `AnsiblePluginError`, renamed plugin exceptions, `get_with_context`/`get_with_context_result`, tombstone handling in `_find_fq_plugin`, deprecated-plugin metadata behavior, template removed-plugin surfacing, and `Display.get_deprecation_message`/`Display.deprecated` behavior.
**wide_tests** (confidence: 0.58):
  The only F2P test mixes one relevant behavior with additional checks unrelated to the plugin redirection/deprecation/context-metadata bug. That means the benchmark's fail-to-pass surface extends beyond the stated acceptance criteria, fitting the 'extra assertions in an otherwise aligned test' form of wide tests. This is not severe because the extra checks appear to come from an existing test and are not described as blocking alternative valid fixes, but they still broaden the task beyond its specification.
  - `test_action_base__configure_module` is classified as TANGENTIAL with the note that 'most of the assertions are about existing module formatting behavior (style/shebang for Python and PowerShell), which is outside the reported bug.'
  - The same test analysis says 'Only the AnsibleError checks for an unresolved module are directly relevant' to the requirement that `_configure_module` use context-aware resolution and fail when unresolved.
**scope_creep** (confidence: 0.47):
  The gold patch is not perfectly scoped to the issue. In addition to the required loader/error/display work, it includes at least one unrelated code refactor in collection loader code that is outside the requested behavior. This is a mild form of scope creep rather than a fairness blocker, so confidence is lower than for weak coverage.
  - Hunk 19 in `lib/ansible/utils/collection_loader/_collection_finder.py` is marked UNRELATED: 'a small refactor introducing a local `collection_name` variable in collection finder code' outside the listed acceptance criteria.
  - Gold patch analysis reports `Has excess: True` with 3 UNRELATED hunks overall; while hunks 0 and 20 are comment-only, hunk 19 is an actual unrelated code refactor in a different subsystem.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.76)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement gave highly specific implementation targets, so the agent methodically inspected those components and planned edits matching the stated requirements. It appears to have started implementing the core refactor but stopped before producing or validating a complete working fix, leading to failure.
- **Behavior:** Genuine exploratory implementation attempt guided by the prompt's detailed requirements, but incomplete and unresolved; no meaningful evidence of benchmark leakage.

> The trajectory looks like a legitimate, problem-driven attempt rather than leakage. The agent began by exploring exactly the files and methods named in the problem statement: plugin loader, errors, display, task executor, action base, and template handling. It summarized the required changes in a way that closely follows the user-visible requirements, then described implementing them incrementally. There are no signs of package leakage, no pip installs, no references to hidden test names or expe

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_ansible__ansible-c616e54a6e23fa5616a1d56d243f69576164ef9b-v1055803c3a812189a1133297f7f5468579283f86`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** PIPELINE_ERROR: LLM request failed after 7 attempts. Last error: Request timed out.
**Severity:** SEVERE

### Contamination Signals


### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.91)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement pointed to module_common and import resolution bugs, leading the agent to inspect module_common.py, focus on recursive_finder, observe a possible '__init__' package-handling defect, reproduce that specific failure locally, and iterate on a small fix. It became stuck in that narrow debugging path and never expanded to the larger refactor the task actually required.
- **Behavior:** Genuine exploratory debugging of a plausible sub-bug, but too narrow and incomplete for the actual task; no evidence of leakage.

> The trajectory looks like genuine but unsuccessful debugging rather than leakage. The agent began by exploring the repository and the named target file, then inspected the recursive_finder path, ModuleInfo-related code, and adjacent helper classes before forming a concrete hypothesis. Its hypothesis was narrow: it concluded that package handling was incorrectly trying to resolve a literal '__init__' module name, and it iterated on that idea after reproducing an error and encountering secondary i

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_ansible__ansible-d33bedc48fdd933b5abd65a77c081876298e2f07-v0f01c69f1e2528b935359cfe578530722bca2c59`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Fix ensure_type and related configuration handling so config values returned through get_option preserve tags and the specifically reported coercion, warning, and list-based configuration cases behave correctly.
**Severity:** SEVERE
**Labels:** `wide_tests`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 20 hunks are UNRELATED to the stated problem

### Label Analysis

**wide_tests** (confidence: 0.80):
  The F2P suite exercises behavior outside the stated contract. The task specification explicitly excludes tmp/temppath/tmppath values from the tag-propagation requirement, but the tag-propagation test includes a tmp case that still expects tags. That is classic wide_tests contamination: the test scope extends beyond, and in fact conflicts with, the written acceptance criteria.
  - Acceptance criterion 1 says tag preservation applies "except when the original value type is temppath, tmppath, or tmp."
  - F2P test `test_ensure_type_tag_propagation` is marked TANGENTIAL (conf=0.90) because it "with the shown tmp parameterization, asserts tagging for a tmp result even though tmp/temppath/tmppath are explicitly exempted from the required tag-preservation behavior."
**approach_lock** (confidence: 0.66):
  Checking object identity is an implementation-detail assertion about how tag propagation is achieved, not just whether the observable behavior is correct. A valid solution could preserve the required tags on an equivalent converted value while returning a different object instance. Such a solution would satisfy the task specification but fail this identity-based test, so the test narrows the acceptable implementation approach.
  - The same F2P test `test_ensure_type_tag_propagation` is marked TANGENTIAL because it "also checks object identity."
  - Acceptance criterion 1 requires that converted values "retain the original tags/trust-or-origin metadata," but does not require the result to be the same object instance.
**weak_coverage** (confidence: 0.78):
  The task specification covers more than ensure_type coercion alone, but the fail-to-pass tests appear to validate only the ensure_type/tag-propagation portion. That means an agent could implement a partial fix centered on coercion and still pass the benchmark without addressing the warning/reporting path and list-default/ignored-extension behaviors explicitly required by the task. This is incomplete coverage rather than unfair strictness.
  - Acceptance criteria 9-12 require: deferred template_default error accumulation, warning emission through `_report_config_warnings`/`error_as_warning`, REJECT_EXTS list handling, ignored-extension filtering updates, and YAML-list defaults in `lib/ansible/config/base.yml`.
  - The F2P summary lists only `test_ensure_type` and `test_ensure_type_tag_propagation` cases; no F2P test is reported for template-default warning behavior, config warning reporting, plugin ignored-extension handling, REJECT_EXTS representation, or base.yml list-default normalization.
  - Required gold-patch hunks 11-19 implement warning/reporting, constants, loader, and display behavior, but the F2P suite summary remains focused on ensure_type coercion.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.90)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement pointed the agent to `ensure_type`; from there it traced the configuration retrieval path, investigated how tags are represented and copied, reproduced the tag-loss behavior, and then examined boolean conversion as another reported symptom. The run ended before implementation, so the failure stems from incomplete execution rather than from taking the wrong contaminated approach.
- **Behavior:** Genuine debugging-oriented exploration that identified part of the problem, but the agent failed to complete or implement a solution.

> The trajectory shows normal, grounded exploration of the codebase rather than answer-driven behavior. The agent started from the problem statement, navigated to the obvious relevant area (`config/manager.py` and `ensure_type`), then broadened its investigation to `get_option`, `get_config_value`, template handling, the data tag implementation, and `convert_bool.boolean`. It also appears to have created or updated a local repro script to understand how tags are applied and inspected, which is con

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_ansible__ansible-d58e69c82d7edd0583dd8e78d76b075c33c3151e-v173091e2e36d38c978002990795f66cfc0af30ad`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Add transparent, configurable handling of gzip-encoded HTTP responses so Ansible's `uri`, `get_url`, and shared URL request utilities return usable decompressed content by default and preserve compressed content only when explicitly requested.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `weak_coverage`

### Contamination Signals

- **WIDE_TESTS:** 2 of 4 assertions (50%) are OFF_TOPIC

### Label Analysis

**approach_lock** (confidence: 0.74):
  These assertions check an internal implementation detail rather than the externally required behavior. A solution could satisfy the task by returning the correct decoded bytes, preserving non-gzip behavior, and providing the required public `GzipDecodedReader` class, while using a different internal wrapper or decompression strategy inside `Request.open`. Such a valid alternative would fail these tests. That is classic narrow-assertion approach locking.
  - F2P test `test_Request_open_gzip` includes OFF_TOPIC assertion: `assert isinstance(r.fp, GzipDecodedReader)`.
  - F2P test `test_Request_open_decompress_false` includes OFF_TOPIC assertion: `assert not isinstance(r.fp, GzipDecodedReader)`.
  - The stated requirements/interface require that `GzipDecodedReader` exist as a public class, but do not require `Request.open` to expose that exact class as `r.fp`.
**wide_tests** (confidence: 0.61):
  The tests go beyond the described acceptance criteria by adding extra assertions about internal stream-wrapper identity. Those checks are not needed to verify the requested behavior and therefore widen the tested scope beyond the user-visible contract.
  - Both F2P tests are marked ALIGNED overall, but each contains one OFF_TOPIC assertion.
  - `test_Request_open_gzip`: OFF_TOPIC `assert isinstance(r.fp, GzipDecodedReader)`.
  - `test_Request_open_decompress_false`: OFF_TOPIC `assert not isinstance(r.fp, GzipDecodedReader)`.
**weak_coverage** (confidence: 0.96):
  The specification is broad, but the fail-to-pass coverage is narrow. A partial implementation focused on `Request.open` and basic gzip reading could pass the F2P suite while leaving many stated requirements unimplemented. This makes the task easier than its written specification and indicates substantial undercoverage.
  - There are only 2 F2P tests, and both exercise `Request.open` behavior only.
  - No F2P test covers the requirement that gzip responses remain compressed when `decompress=False`.
  - No F2P test covers propagation/exposure of `decompress` through `open_url`, `fetch_url`, `fetch_file`, `uri`, and `get_url`.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.79)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent used the problem statement to identify likely touchpoints, inspected the HTTP request stack and module call chain, reproduced the gzip-response behavior, concluded that transparent decompression was missing, and started plumbing a `decompress` feature plus a gzip reader through the relevant code paths before the attempt stopped unfinished.
- **Behavior:** Genuine exploratory debugging with a partially correct implementation plan, but the attempt ended before a complete working fix was produced.

> The trajectory looks like a genuine but incomplete debugging/implementation attempt, not benchmark leakage. The agent first explored the repository, read the relevant shared HTTP utility code in `lib/ansible/module_utils/urls.py`, then inspected `uri.py` and `get_url.py`, and even created a reproduction script to confirm that gzip-encoded responses were being returned as compressed bytes rather than transparently decoded. That is the expected causal path for a legitimate solver. It then began im

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Remove or quarantine 2 OFF_TOPIC assertions from the test patch.

---

## Contamination Narrative: `instance_ansible__ansible-e22e103cdf8edc56ff7d9b848a58f94f1471a263-v1055803c3a812189a1133297f7f5468579283f86`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Fix WinRM Kerberos authentication command handling so a custom kinit executable and optional extra arguments are supported via ansible_winrm_kinit_cmd and ansible_winrm_kinit_args, with consistent behavior across Kerberos invocation paths.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 4 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.74):
  The tests do not only check observable task behavior; they also pin internal implementation details. A valid fix could satisfy the stated requirements by constructing the right kinit command, invoking it once, setting `KRB5CCNAME`, and working on both subprocess and pexpect paths, yet still fail if it uses a different pexpect interaction pattern or preserves additional environment variables. That is a classic narrow-test-assertion / implementation-lock problem, so the task is approach-locking.
  - F2P test `test_kinit_success_pexpect` is marked TANGENTIAL (conf=0.94) because "most of the assertions validate pexpect interaction details such as echo=False, prompt matching, sendline, read, and wait sequencing."
  - The acceptance criteria require parity of kinit command content, single invocation, and KRB5CCNAME usage across subprocess/pexpect paths, but do not require a particular pexpect call sequence or exact `echo=False`/prompt-handling strategy.
  - F2P test `test_kinit_success_subprocess` is noted as stricter than the contract because it requires the env dict to contain only `KRB5CCNAME`, while the requirements only say the cache must be exposed through `KRB5CCNAME`.
**wide_tests** (confidence: 0.81):
  Some F2P assertions go beyond the task specification. The task asks for correct kinit command construction and consistent behavior across subprocess and pexpect paths, but the tests additionally verify low-level pexpect mechanics and an exclusivity property on the environment that the spec never states. These are extra assertions beyond scope, so `wide_tests` applies.
  - F2P test `test_kinit_success_pexpect` is classified TANGENTIAL because the bulk of its checks cover "pexpect interaction details such as echo=False, prompt matching, sendline, read, and wait sequencing," which are not part of the stated acceptance criteria.
  - F2P test `test_kinit_success_subprocess` includes an assertion that the environment contains only `KRB5CCNAME`; the requirements only specify that `KRB5CCNAME` must be used, not that no other environment variables may be present.
  - The requirements focus on `kinit_args` support, command construction order, delegation-flag precedence, unique credential cache handling, single invocation, and identical command content across both execution paths.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement identified WinRM/Kerberos, which led the agent to inspect the WinRM connection plugin, especially `_kerb_auth` and `_kinit_cmd` setup. From that code and the reported error, it inferred the command-construction bug, then used unit tests to refine the implementation, added `kinit_args` parsing and precedence logic, and validated both execution paths through iterative testing.
- **Behavior:** A methodical, code-driven debugging session with iterative testing and some over-and-above reasoning, consistent with a genuine fix rather than benchmark leakage.

> The trajectory looks like legitimate debugging rather than leakage. The agent began by exploring the repository and the WinRM connection plugin, then narrowed in on the Kerberos authentication path and the initialization of `_kinit_cmd`. It formed a concrete hypothesis from the observed code and the user-facing error: the command builder was treating a full command string as a single executable. Only after locating the relevant code did it inspect unit tests to understand expected behavior. It t

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_ansible__ansible-ecea15c508f0e081525be036cf76bbb56dbcdd9d-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5`

### Task Context

**Repository:** `ansible/ansible` (version )
**Core requirement:** Enhance the `ansible-galaxy` CLI so a requirements file containing both roles and collections is handled correctly in one workflow: bare `install` should install both when using default paths, while role-only or collection-only invocations should skip the other type with clear messaging.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `test_mutation`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 12 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 1 of 5 assertions (20%) are OFF_TOPIC
- **WIDE_TESTS:** 2 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.56):
  Some F2P coverage is tied to the gold patch's internal refactor, not just observable CLI behavior. A valid solution could implement the mixed install/skip behavior entirely inside execute_install and leave the helper return shape unchanged, yet still fail helper-level tests that assert the new internal parsing structure. That is a narrow-assertion form of approach locking: the tests partially check how the fix is implemented, not only what the CLI does.
  - Test 'test_require_one_of_collections_requirements_with_requirements' is marked TANGENTIAL because it verifies an internal helper's extraction behavior rather than the user-visible install workflow.
  - Test 'test_require_one_of_collections_requirements_with_collections' is marked UNRELATED and checks tuple parsing of collection names/versions in a non-install/helper-oriented path.
  - The task spec says 'No new interfaces are introduced,' but these tests depend on internal helper behavior introduced by hunk 5 ('collection-requirement parsing to return both roles and collections').
**wide_tests** (confidence: 0.89):
  The stated task is about ansible-galaxy install/role install/collection install handling mixed requirements files, skip behavior, and messages. Several F2P tests go beyond that scope into internal helper parsing, and one assertion checks extra default-path detail in a collection-only test. Those are classic wide tests: they verify behavior not required by the task specification.
  - Two entries for 'test_require_one_of_collections_requirements_with_collections' are marked UNRELATED; they exercise collection-requirement helper parsing for a non-install path rather than the mixed install behavior in the problem.
  - Test 'test_require_one_of_collections_requirements_with_requirements' is marked TANGENTIAL because it checks helper extraction from a requirements file instead of install/skip behavior and user messaging.
  - In 'test_install_collection_with_roles', the assertion 'mock_collection_install.call_args[0][1] == cli._get_default_collection_path()' is marked OFF_TOPIC.
**test_mutation** (confidence: 0.84):
  A pre-existing test was altered to assert new helper-level behavior that is not part of the problem's acceptance criteria. That is test mutation: the PR makes an old test look authoritative while silently broadening it to cover misaligned behavior.
  - Test 'test_require_one_of_collections_requirements_with_collections' is explicitly labeled '[MODIFIED pre-existing test, MISALIGNED changes]'.
  - The analysis says that modified test's assertion 'only checks tuple parsing of collection names/versions, not the mixed install workflow.'
  - A second entry for the same test is again marked UNRELATED and modified, reinforcing that the changed pre-existing coverage was expanded outside the task scope.
**weak_coverage** (confidence: 0.72):
  The test suite covers the main mixed-install flows, but several explicit requirements appear untested. Because important acceptance criteria lack direct F2P coverage, a partial implementation focused on the happy-path install cases could still pass. That makes the benchmark easier and under-measures the full requested behavior.
  - Acceptance criterion 9 (transitive role dependencies appended to the active requirements list and not reinstalled unless forced) is implemented by hunks 10-11, but no listed F2P test targets dependency-processing behavior.
  - Acceptance criterion 10 (reject non-.yml/.yaml role requirements files) is implemented inside hunk 9, but no F2P test is listed for invalid-extension rejection.
  - Acceptance criterion 11 ('Skipping install, no requirements found') is also implemented in hunk 9, but no listed F2P test targets the empty-input case.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.90)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem, reproduced the bug, identified the main control-flow points in the galaxy CLI, hypothesized that a unified install path was needed, attempted to modify parser/install logic, then discovered the implicit `role` insertion in `__init__` was defeating that approach and stalled before producing a working patch.
- **Behavior:** Legitimate exploratory debugging with partial understanding of the right area, but the agent failed to complete the fix; no meaningful evidence of leakage.

> This trajectory looks like genuine but incomplete debugging rather than leakage. The agent began by exploring the repository and the relevant CLI implementation in a sensible order: entry point, `lib/ansible/cli/galaxy.py`, `execute_install`, `_parse_requirements_file`, `_require_one_of_collections_requirements`, `add_install_options`, and `__init__`. It also created a reproduction script and compared observed behavior against the problem statement before proposing changes. Those are strong sign

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Remove or quarantine 1 OFF_TOPIC assertions from the test patch. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_element-hq__element-web-2760bfc8369f1bee640d6d7a7e910783143d4c5f-vnan`

### Task Context

**Repository:** `element-hq/element-web` (version )
**Core requirement:** Prevent duplicate admin actions in the user info panel by making member admin controls non-interactive immediately on first activation and keeping them blocked until the pending action finishes, fails, or is canceled.
**Severity:** SEVERE
**Labels:** `approach_lock`, `weak_coverage`

### Contamination Signals


### Label Analysis

**approach_lock** (confidence: 0.47):
  The task asks for user-visible locking behavior, not a particular internal state-plumbing API. A test centered on `<RoomAdminToolsContainer />` with `isUpdating=true` appears to encode the gold patch's chosen implementation boundary. A behaviorally correct alternative could keep the pending lock in different local/shared state without exposing the same prop interface, yet fail such a unit test. Confidence is only moderate because the full assertion body is not shown, but the test name plus the prop-plumbing hunks indicate some implementation coupling.
  - F2P includes `test/components/views/right_panel/UserInfo-test.tsx | <RoomAdminToolsContainer /> | should disable buttons when isUpdating=true`.
  - Gold patch hunk 0 adds `isUpdating` to a shared TypeScript props interface; hunks 13-16 thread `isUpdating` through `RoomAdminToolsContainer` into `RoomKickButton`, `BanToggleButton`, and `MuteToggleButton`.
  - The requirements describe observable behavior (member-scoped non-interactive admin controls while pending) but do not require an `isUpdating` prop or this specific internal component wiring.
**weak_coverage** (confidence: 0.87):
  The specification is substantially broader than what the visible F2P suite exercises. The tests appear to check mainly disabled rendering under an injected pending state, while leaving major acceptance criteria effectively unverified: deduplication under rapid activation, timing before confirmation, cancel behavior, failure handling, keyboard activation, and explicit accessibility/error guarantees. That means a partial fix could pass, so the benchmark under-measures the stated task.
  - Acceptance criteria require all of: at-most-once execution under rapid click/tap/keyboard activation; immediate pending state before confirmation; cancel re-enables with no operation sent; failure re-enables with a single clear error; and non-interactive state with both `disabled` and `aria-disabled="true"`.
  - The only clearly bug-focused listed F2P test is `test/components/views/right_panel/UserInfo-test.tsx | <RoomAdminToolsContainer /> | should disable buttons when isUpdating=true`.
  - Other listed F2P tests are `clicking »message« for a RoomMember should start a DM`, `clicking »message« for a User should start a DM`, and `returns mute toggle button if conditions met`, which do not directly exercise rapid repeated admin actions, confirmation cancel, failure recovery, keyboard activation, or single-error behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.81)
- **Gold patch similarity:** 0.0%
- **Causal chain:** Problem statement led the agent to search the right-panel/user-info components, inspect the kick/ban/mute button implementations and shared pending state, infer that a shared `isUpdating` lock should disable all admin actions for the member, and begin implementing that propagation—but the run ended before a patch was actually produced or tested.
- **Behavior:** Genuine exploratory debugging with a mostly correct high-level plan, but the run ended before a concrete fix was delivered.

> The trajectory shows a largely legitimate debugging process rather than leakage. The agent began by exploring the repository structure, searching for the user info panel, locating `UserInfo.tsx`, inspecting the admin action button components, tracing how `pendingUpdateCount` and update callbacks were wired, and only then looking at tests. That sequence is what you would expect from genuine problem-solving on this bug. There are no signs of package leakage, no evidence it cited hidden F2P test na

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_element-hq__element-web-582a1b093fc0b77538052f45cbb9c7295f991b51-vnan`

### Task Context

**Repository:** `element-hq/element-web` (version )
**Core requirement:** Change decryption failure tracking so that only user-visible events are eligible for reporting, using a single shared tracker to avoid duplicate monitoring and to surface unique visible failures promptly and consistently.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 13 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.75):
  The tests appear to depend on the specific grace-period reduction introduced by hunk [3], even though that exact value is not determined by the task specification. A solution could satisfy the stated requirements—singleton tracker, visible-only reporting, deduplication, errcode mapping, cleanup on successful decrypt—while keeping a different grace period, but the F2P suite would still fail if it is effectively calibrated to the gold patch's 4000ms choice. That matches approach_lock via circular test-patch dependency: tests require behavior from an out-of-scope hunk rather than only the described user-visible contract.
  - Cross-reference analysis reports 10 circular dependencies: every F2P test in test/DecryptionFailureTracker-test.js is linked to UNRELATED hunk [3].
  - Hunk [3] in src/DecryptionFailureTracker.ts is classified UNRELATED (conf=0.99): it changes the grace period from 60000 to 4000.
  - Requirements only say checkFailures should process visible failures that exceed 'the grace period'; they do not specify a 4-second threshold.
**scope_creep** (confidence: 0.84):
  The gold patch includes a behavioral change beyond the benchmark's stated acceptance criteria: it alters the grace-period duration itself. The required behavior is about limiting tracking to visible events, using a singleton, deduplicating reporting, cleanup, and consistent errcode mapping. Choosing a new 4-second delay is an extra policy change not required by the specification, so this is scope_creep rather than a purely ancillary refactor.
  - Gold patch analysis marks hunk [3] as UNRELATED (conf=0.99).
  - Hunk [3] changes the numeric grace period from 60000 to 4000 in src/DecryptionFailureTracker.ts.
  - Intent extraction says redefining the grace-period policy itself is out of scope; the acceptance criteria require processing only visible failures after the grace period, but do not require changing the duration.
**weak_coverage** (confidence: 0.72):
  The benchmark's tests focus on the DecryptionFailureTracker unit behavior but do not appear to verify some stated acceptance criteria about application wiring. An agent could implement the tracker logic well enough to satisfy the unit tests while failing to update MatrixChat and EventTile to actually use the singleton and mark rendered events visible in the real app. Because important required behavior lacks direct F2P coverage, the task has weak_coverage.
  - Acceptance criteria explicitly require EventTile to call DecryptionFailureTracker.instance.addVisibleEvent and MatrixChat to use DecryptionFailureTracker.instance.
  - These app-integration changes are implemented in required hunks [10] (src/components/structures/MatrixChat.tsx) and [12] (src/components/views/rooms/EventTile.tsx).
  - All listed F2P tests are in test/DecryptionFailureTracker-test.js; none target MatrixChat.tsx or EventTile.tsx behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the relevant code paths, formed the correct high-level fix from the PR requirements, implemented it, ran the available tests, saw those tests disagree with the new spec, and then weakened the implementation to satisfy the observed tests—leading to a final patch that no longer cleanly solves the real task.
- **Behavior:** Genuine, exploratory problem-solving with a mostly correct initial approach, later overfit to misleading local tests rather than leaked benchmark knowledge.

> This trajectory looks like a genuine attempt that was later derailed by mismatched local test pressure, not benchmark leakage. The agent did not jump straight to the final files/functions blindly: it explicitly explored the repository, read `src/DecryptionFailureTracker.ts`, inspected the test file, searched for usages, examined `MatrixChat.tsx`, and then found `EventTile.tsx` as the right visibility integration point. Its initial implementation plan matches the problem statement in a task-speci

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_element-hq__element-web-72a8f8f03b1a01bb70ef8a5bb61759416991b32c-vnan`

### Task Context

**Repository:** `element-hq/element-web` (version )
**Core requirement:** Add a public React hook for reading the current window width from UI state and keeping that value updated when the UIStore emits resize events.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 5 of 6 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.98):
  The task specification is narrow: add a new `useWindowWidth` hook that reads `UIStore.instance.windowWidth`, updates on `UI_EVENTS.Resize`, and unsubscribes on unmount. The gold patch expands scope by changing `TabbedView` behavior and adding a tooltip-focused E2E scenario. Those are behavioral changes unrelated to the requested hook, so this is clear scope_creep rather than ancillary refactoring.
  - Gold patch analysis marks 5 of 6 hunks as UNRELATED: hunk 0 in `playwright/e2e/settings/general-user-settings-tab.spec.ts` and hunks 1-4 in `src/components/structures/TabbedView.tsx`.
  - Hunk 0 adds an end-to-end test for narrow-screen tab tooltips in the General settings tab, which is outside the acceptance criteria for adding a `useWindowWidth` hook.
  - Hunks 1-4 import `useWindowWidth` into `TabbedView`, add tooltip-related props/behavior, and use the width to decide tooltip display; the task only asks for `src/hooks/useWindowWidth.ts` and its read/update/cleanup behavior.
**approach_lock** (confidence: 0.64):
  If the F2P tests depend on the unrelated `TabbedView` and tooltip hunks, then an agent could correctly implement the requested hook and still fail because it did not reproduce out-of-scope UI integration changes. That matches the circular test-patch dependency subtype of approach_lock. The test names themselves look aligned to the hook, so confidence is moderated, but the provided cross-reference analysis is strong enough to flag likely approach_lock.
  - Cross-reference analysis reports circular dependencies for both F2P tests: each test is linked to UNRELATED hunks `[0, 1, 2, 3, 4]` with confidence 0.95.
  - The cross-reference summary explicitly says: "This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for."
  - The linked hunks are the unrelated `TabbedView`/tooltip and E2E changes, not the required hook implementation in hunk 5.
**weak_coverage** (confidence: 0.57):
  The F2P tests cover the main read/update behavior, but the specification also requires cleanup on unmount. Since no listed test directly checks listener removal, a partial implementation could pass while leaking subscriptions. That is a classic weak_coverage issue: the benchmark does not fully test all stated acceptance criteria.
  - Acceptance criterion 5 requires that `useWindowWidth` "remove the `UI_EVENTS.Resize` listener from `UIStore` when the component using it is unmounted."
  - The only listed F2P tests are `should return the current width of window, according to UIStore` and `should update the value when UIStore's value changes`.
  - No listed F2P test explicitly targets unmount cleanup or listener removal.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.95)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to have recognized or recalled an upstream patch involving narrow-screen tab tooltips in `TabbedView`, started from that known destination, then worked backward to add the `useWindowWidth` hook required to support that change. The hook solved the evaluation tests, but the approach was driven by contaminated patch knowledge rather than solely by the problem statement.
- **Behavior:** Passed, but followed a suspiciously gold-patch-shaped path: targeted unrelated `TabbedView`/tooltip behavior early, then added the hook as part of that recalled solution.

> The trajectory strongly suggests benchmark leakage rather than a purely genuine solution. The stated task is narrowly about adding a new `useWindowWidth` hook that reads `UIStore.instance.windowWidth`, updates on `UI_EVENTS.Resize`, and cleans up its listener. A normal, task-driven trajectory would focus on `UIStore`, hooks, and perhaps tests around that hook. Instead, the agent immediately steered toward `TabbedView`, then investigated CSS breakpoints, tooltip behavior, and `UserSettingsDialog`

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 5 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_element-hq__element-web-b007ea81b2ccd001b00f332bee65070aa7fc00f9-vnan`

### Task Context

**Repository:** `element-hq/element-web` (version )
**Core requirement:** Add two new numeric-array utilities: a deterministic smoothing resampler to a target length and a linear min-max rescaler to a requested inclusive range.
**Severity:** SEVERE
**Labels:** `wide_tests`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 4 of 6 hunks are UNRELATED to the stated problem

### Label Analysis

**wide_tests** (confidence: 0.74):
  The task specification is framed around adding two new utilities and explicitly says broader redesign of existing resampling utilities is out of scope. However, the F2P suite also scores behavior of the pre-existing `arrayFastResample` API via three dedicated test functions. A solution could satisfy the stated contract for `arraySmoothingResample` and `arrayRescale` without changing the standalone `arrayFastResample` behavior, yet still fail the benchmark. That makes the test suite broader than the stated acceptance criteria.
  - INTERFACE lists only two new public interfaces: `arraySmoothingResample` and `arrayRescale` in `src/utils/arrays.ts`.
  - Intent extraction says out of scope: the request does not ask to 'replace or redesign existing resampling utilities beyond adding these two functions'.
  - F2P includes three standalone test functions for `test/utils/arrays-test.ts | arrayFastResample | should downsample`, `... | should upsample`, and `... | should maintain sample`.
**scope_creep** (confidence: 0.97):
  The gold patch expands beyond the requested feature. Four high-confidence UNRELATED hunks alter runtime behavior in `src/voice/Playback.ts`, including new waveform-generation logic and adoption of the new utilities in playback code. Those consumer-side behavioral changes are not part of the task's acceptance criteria, which are limited to adding the two array utilities, so the patch contains clear scope expansion.
  - Hunk 2 in `src/voice/Playback.ts` is marked UNRELATED (conf=0.95): import/integration change for Playback.
  - Hunk 3 in `src/voice/Playback.ts` is marked UNRELATED (conf=0.96): introduces `makePlaybackWaveform` helper.
  - Hunk 4 in `src/voice/Playback.ts` is marked UNRELATED (conf=0.95): changes `Playback` constructor behavior to use the new helper.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent started with repository exploration, identified `src/utils/arrays.ts` and `src/voice/Playback.ts` as relevant, inspected tests and helper utilities, formed a hypothesis about adding smoothing resampling and min-max rescaling, implemented those changes plus waveform integration, and iterated with targeted test scripts. The likely failure came from not matching the exact hidden deterministic algorithm rather than from misunderstanding the overall task.
- **Behavior:** Methodical and exploratory; appears to have genuinely understood and implemented the intended feature, but likely missed exact edge-case behavior required by hidden tests.

> This looks like a genuine, non-leaky attempt that likely addressed the real feature request but did not fully satisfy the hidden fail-to-pass checks. The agent did not jump straight to the gold locations and exact fix; instead it progressively explored the repository, inspected the relevant utility and playback files, examined tests, checked related helpers like `clamp`, and ran tests before and after implementation. Its stated plan matches the task requirements: add `arraySmoothingResample`, ad

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 4 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_element-hq__element-web-f14374a51c153f64f313243f2df6ea4971db4e15`

### Task Context

**Repository:** `element-hq/element-web` (version )
**Core requirement:** Improve the message composer and related messaging UI so tombstoned-room notices are semantically clear and accessible, while cancel interactions are standardized through a reusable accessible cancel button.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `unclear_spec`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 5 of 41 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.48)

### Label Analysis

**approach_lock** (confidence: 0.89):
  The sole F2P test is coupled to implementation changes that the task does not ask for: the send-button transition/animation path. That creates a circular test-patch dependency. An agent could implement the requested tombstoned-room notice semantics and inactive-room behavior without adopting the same send-button transition structure, yet still fail because the test traverses code tied to unrelated hunks. This is approach_lock via circular test-patch dependency, not merely strict testing.
  - Cross-reference analysis flags a circular dependency: test '/app/test/components/views/rooms/MessageComposer-test.tsx | MessageComposer | Does not render a SendMessageComposer or MessageComposerButtons when room is tombstoned' exercises UNRELATED hunks [10, 24, 26, 33] (conf=0.95).
  - Hunk 10 in res/css/views/rooms/_MessageComposer.scss is marked UNRELATED: it 'introduces a new animated wrapper and transition sizing for the send button.'
  - Hunk 33 in src/components/views/rooms/MessageComposer.tsx is marked UNRELATED: it wraps the send button in CSSTransition for animation/visibility behavior.
**scope_creep** (confidence: 0.86):
  The patch includes behavioral work outside the requested tombstone-notice, cancel-button, reply-preview, and profile-semantic changes. In particular, it introduces a separate send-button animation/transition feature and supporting plumbing. Those are not ancillary imports or formatting cleanups; they are extra behavior beyond the task scope, so scope_creep applies.
  - Gold patch analysis reports Has excess=True with 5 UNRELATED hunks.
  - Hunk 10 adds send-button animation CSS in res/css/views/rooms/_MessageComposer.scss and is explicitly marked UNRELATED.
  - Hunk 24 adds an import in src/components/views/rooms/MessageComposer.tsx solely for the new send-button transition behavior and is marked UNRELATED.
**unclear_spec** (confidence: 0.58):
  Even treating Requirements and Interface as part of the task spec, the overall specification mixes a narrow bug report with broad cross-component UI consistency goals. It is not very clear which components must change, how far 'across all interface components' extends, or whether the task is primarily a tombstone-notice fix or a broader messaging-UI refactor. That ambiguity can mislead solvers about the intended scope and solution surface.
  - The problem statement is narrowly framed around tombstoned-room notice semantics: 'display room replacement notices using semantic HTML markup (such as paragraph elements)'.
  - The Requirements broaden scope substantially to items like 'consistent cancel button functionality across all interface components,' 'Profile components support flexible rendering contexts,' and 'All messaging interface components follow consistent design patterns.'
  - Intent extraction reports Ambiguity score = 0.48.
**weak_coverage** (confidence: 0.95):
  The stated acceptance criteria cover multiple behaviors, but the fail-to-pass suite exercises only a small slice of them. A partial fix that merely suppresses composer controls in tombstoned rooms could plausibly pass without implementing the reusable CancelButton, the reply/profile semantic changes, or even the exact semantic notice markup/text. That makes the task easier than its written specification and fits weak_coverage.
  - F2P TEST ANALYSIS reports only 1 F2P test and 0 extracted assertions.
  - The only F2P test is '/app/test/components/views/rooms/MessageComposer-test.tsx | MessageComposer | Does not render a SendMessageComposer or MessageComposerButtons when room is tombstoned'.
  - No F2P coverage is reported for acceptance criteria about the reusable CancelButton at src/components/views/buttons/Cancel.tsx, its size/default/accessibility behavior, ReplyPreview naming/cancel behavior, or profile rendering via configurable semantic elements.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.87)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The prompt pushed the agent toward a broad UI refactor scope; the agent responded with methodical exploration of all referenced components, began implementing the reusable CancelButton and related styling, then appears to have stalled during integration before producing a substantive patch.
- **Behavior:** Genuine exploratory debugging and implementation attempt, but incomplete and unsuccessful; no meaningful evidence of leakage.

> The trajectory shows legitimate repository exploration rather than leakage. The agent read the problem statement, then systematically inspected the components and styles directly implicated by the prompt requirements: MessageComposer, ReplyPreview, ReplyTile, SenderProfile, DisambiguatedProfile, relevant SCSS, translations, icons, and related composer/button components. That is consistent with genuine task-oriented investigation, especially because the prompt itself explicitly mentioned a new Ca

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 5 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-05d7234fa582df632f70a7cd10194d61bd7043b9`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Propagate stable ETag-based version metadata through filesystem-backed snapshot loading so namespace version lookups return meaningful values for existing namespaces, error for missing namespaces, and file metadata exposes retrievable ETags.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 22 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.78):
  This task has at least one F2P test that checks implementation details rather than only required behavior. The spec asks for `FileInfo` to expose an ETag through `Etag()` and through `Stat()`, but `TestFileInfo` inspects the concrete `fi.etag` field. A solution that correctly exposes `Etag()` while storing or computing the value differently could satisfy the problem statement yet fail the benchmark. That is a textbook narrow-test-assertion form of approach lock.
  - F2P test 'TestFileInfo' is marked TANGENTIAL (conf=0.95) because 'The assertion is about the internal fi.etag field being set' even though the acceptance criteria only require a public `Etag()` accessor and exposure through `Stat()`.
  - Acceptance criteria 6-7 and Interface item 5 specify observable behavior: `Stat()` should return `FileInfo` exposing an ETag via `(*FileInfo).Etag`, not a particular internal field layout.
  - Cross-reference analysis also reports a circular dependency signal: `TestFSWithoutIndex` → UNRELATED hunks [0, 11] (conf=0.90), though this is weaker/noisier than the direct internal-field assertion evidence.
**scope_creep** (confidence: 0.61):
  The gold patch includes at least one behavioral code change beyond the task's stated scope. Hunk 11 removes an unrelated method in the object-store area that is not needed for any acceptance criterion. That makes the patch broader than the issue being benchmarked. I am not relying on hunk 0 (`go.work.sum`) for this label, since that checksum update is nonbehavioral; hunk 11 is sufficient on its own.
  - Gold patch analysis: `Has excess: True` with 2 UNRELATED hunks.
  - Hunk 11 (`internal/storage/fs/object/store.go`) is classified UNRELATED (conf=0.84): 'Removing this unused TODO method is not part of the required behavior.'
  - The requested changes are about ETag/version propagation and `GetVersion`; deleting an object-store-specific stub is outside that scope.
**weak_coverage** (confidence: 0.64):
  The requirements are broader than what the F2P tests appear to verify. Important parts of the stated contract—especially non-serialization of `Document.Etag` and the precise ETag fallback computation/format—do not appear in the enumerated F2P tests. That means a partial fix could plausibly pass the benchmark while missing some accepted requirements, which fits weak coverage.
  - Acceptance criteria 2-3 require the `Document` ETag to be excluded from JSON and YAML serialization (implemented in hunk 2), but none of the listed F2P tests target document serialization.
  - Acceptance criteria 10-11 and 13 require `WithEtag`, `WithFileInfoEtag`, and the exact fallback format based on `modTime` and `size` as hex values separated by a hyphen (implemented in hunks 14-15), but no listed F2P test explicitly asserts those APIs or that exact formatting.
  - The listed F2P tests focus mainly on `GetVersion`, constructor/plumbing, and `FileInfo` behavior: `TestGetVersion`, `TestNewFile`, `TestFileInfo`, and `TestFSWithoutIndex`. One `TestNewFile` case is noted as having 'no explicit assertion'.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.85)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent started with broad codebase exploration, narrowed to storage/versioning paths, found the TODO implementations and related file/document abstractions, inferred that ETag metadata must be propagated through snapshots and file info, and then began an implementation plan—but did not complete or validate it.
- **Behavior:** Genuine exploratory debugging with a reasonable diagnosis, but incomplete execution and no delivered fix.

> The trajectory shows legitimate repository exploration and a broadly correct diagnosis of the task: the agent inspected storage interfaces, located the unimplemented `GetVersion` methods in the filesystem store and snapshot, noticed the mock signature issue, and connected the problem to document/file metadata and ETag propagation. This is consistent with genuine reasoning rather than leakage. However, there is no evidence of a completed implementation or meaningful test/iteration cycle, and the 

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-21a935ad7886cc50c46852be21b37f363a926af0`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Add support for a dedicated gRPC logging level in application configuration so it can be loaded into runtime config and default to "ERROR" when unspecified.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 6 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.87):
  This task shows the circular test-patch dependency subtype of approach_lock. A solver could implement exactly what the issue asks for—add the config field, apply the default, and load log.grpc_level—yet still fail because multiple F2P tests depend on hunk 0, which was judged unrelated to the stated bug. That means the benchmark is not only checking whether the configuration bug was fixed; it also requires extra runtime wiring/validation behavior in cmd/flipt/main.go. Valid solutions matching the specification but omitting that unrelated startup behavior would be rejected.
  - Cross-reference analysis reports circular dependencies from F2P tests to UNRELATED hunk 0: TestLogEncoding  hunk [0] (conf 0.80), TestValidate  hunk [0] (conf 0.80), TestServeHTTP  hunk [0] (conf 0.80).
  - Hunk 0 in cmd/flipt/main.go is explicitly marked UNRELATED (conf 0.96): it wires gRPC's internal logger to zap using cfg.Log.GRPCLevel and adds runtime parsing/validation of the level string.
  - The acceptance criteria are fully covered by required hunks 1, 2, and 4: add LogConfig.GRPCLevel, default it to "ERROR" in Default(), and load log.grpc_level in Load(path).
**scope_creep** (confidence: 0.94):
  The gold patch contains behavioral changes beyond the problem scope. The issue is narrowly about configuration support: represent grpc_level in LogConfig, default it to "ERROR", and load it from log.grpc_level without changing existing log settings. Hunk 0 goes further by changing runtime startup behavior to consume that field and validate/parse it, which is a distinct feature/behavioral expansion rather than ancillary support code. That is classic scope_creep.
  - Gold patch analysis: Has excess = True.
  - Hunk 0 [cmd/flipt/main.go] is marked UNRELATED (conf 0.96).
  - The hunk description says it 'wires gRPC's internal logger to zap using cfg.Log.GRPCLevel and adds runtime parsing/validation of the level string.'

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.82)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent started from the issue description, explored config and logging code, inferred that config support alone might be insufficient without runtime gRPC logger wiring, researched available gRPC logging integration, and formed a sensible implementation plan. It then appears to have stalled or terminated before applying any patch.
- **Behavior:** Genuine exploratory debugging with a mostly correct hypothesis, but the agent did not complete implementation.

> The trajectory shows legitimate exploration and a plausible understanding of the bug, not leakage. The agent read the configuration-related code, checked defaults, searched for logging setup in main.go, inspected imports and dependencies, and researched how gRPC logging is handled. That is the opposite of a suspicious jump straight to the exact gold locations. It also never referenced hidden test names or unseen expected values, and there is no sign of package installation or copying code from e

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-84806a178447e766380cc66b14dee9c6eeb534f4`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Fix OCI storage backend configuration handling so `storage.type: oci` configurations are properly parsed and validated, especially for repository validation and OCI-specific fields.
**Severity:** SEVERE
**Labels:** `wide_tests`, `test_mutation`, `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 6 of 23 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 6 UNRELATED tests

### Label Analysis

**wide_tests** (confidence: 0.94):
  The benchmark's F2P suite goes beyond the stated OCI configuration task. Entire test functions are about unrelated store runtime behavior, not repository validation, schema parsing, credentials, poll interval, bundle directory propagation, or `DefaultBundleDir`. This is classic extra-test-function contamination: agents are scored on behavior the problem did not ask them to implement.
  - F2P analysis marks 6/10 tests as UNRELATED, including `TestStore_Fetch_InvalidMediaType`, `TestStore_Fetch`, `TestStore_Build`, `TestStore_List`, and `TestStore_Copy`.
  - Those tests are described as targeting OCI fetch/build/list/copy runtime behavior, while the task's out-of-scope section excludes 'OCI image fetching or runtime behavior beyond configuration propagation'.
  - For each of those tests, the analysis says the visible change is only a `NewStore` call-site update, not a new assertion about the stated config/validation requirements.
**test_mutation** (confidence: 0.95):
  Pre-existing tests were edited in this PR, but the edits are not aligned with the bug report's acceptance criteria. Instead, they pull unrelated OCI store behaviors into F2P simply because the constructor signature changed. That is exactly the test_mutation pattern: older tests were silently repurposed so the benchmark now demands passing assertions outside the described task.
  - `TestStore_Fetch_InvalidMediaType` is flagged as a MODIFIED pre-existing test with MISALIGNED changes.
  - `TestStore_Fetch`, `TestStore_Build`, `TestStore_List`, and `TestStore_Copy` are also flagged as MODIFIED pre-existing tests with MISALIGNED changes.
  - The analysis states these modifications are mechanical updates to the new `NewStore(logger, dir, ...)` signature inside tests whose actual purpose is unrelated fetch/build/list/copy behavior.
**approach_lock** (confidence: 0.72):
  The F2P suite is not only wider than the problem; it is coupled to unrelated implementation changes. An agent could correctly solve the specified OCI config issue—repository validation, parsing OCI fields, `NewStore` dir usage, and `DefaultBundleDir`—yet still fail because post-PR F2P tests exercise unrelated fetch/copy internals tied to hunk 21 and other off-topic paths. That is a circular test-patch dependency, a subtype of approach_lock.
  - Cross-reference analysis reports 10 circular dependencies and explicitly says: 'This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for.'
  - `TestStore_Fetch_InvalidMediaType`, `TestStore_Fetch`, `TestStore_Build`, `TestStore_List`, and `TestStore_Copy` all cross-reference UNRELATED hunk 21 in `internal/oci/file.go`.
  - Hunk 21 is classified UNRELATED (conf 0.99): changing manifest decoding in OCI copy logic, with 'no connection to the OCI configuration parsing, validation, poll_interval, credentials, or bundle directory requirements'.
**scope_creep** (confidence: 0.61):
  The patch itself extends beyond the reported configuration bug. The clearest example is the unrelated runtime change in OCI copy/manifest decoding, which is outside the task's scope. Even if some unrelated hunks are test-only, this production-code hunk shows the PR bundled an extra implementation change not required by the problem.
  - Gold patch analysis says `Has excess: True` with 6 UNRELATED hunks.
  - Hunk 21 in `internal/oci/file.go` is UNRELATED (conf 0.99): it changes manifest decoding from `io.ReadAll`+`json.Unmarshal` to streaming `json.Decoder` in OCI copy logic.
  - The hunk analysis states this change 'has no connection to the OCI configuration parsing, validation, poll_interval, credentials, or bundle directory requirements'.
**weak_coverage** (confidence: 0.67):
  Several stated requirements are not clearly covered by the F2P suite. In particular, the public-interface contract around `NewStore(..., dir, ...)` and `DefaultBundleDir()` appears implemented in required hunks, but the test analysis does not show corresponding on-topic assertions. That means a partial fix could plausibly pass the benchmark without fully satisfying the full stated specification.
  - The listed aligned F2P coverage is narrow: one `TestLoad` case for loaded OCI values, one `TestLoad` case for unsupported repository scheme, plus low-confidence aligned `TestJSONSchema` and `TestParseReference`.
  - No listed aligned test is described as asserting that `NewStore(logger, dir, ...)` actually uses `dir` as the bundles root; the modified store tests are explicitly UNRELATED and say 'no new on-topic assertion is evident.'
  - No listed aligned test is described as directly checking `DefaultBundleDir()` creating/returning the default OCI bundle path, despite acceptance criterion 8 requiring it.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.88)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement pointed the agent toward OCI config handling. It then explored the relevant files, discovered missing schema fields and absent runtime wiring, reproduced the runtime failure, and planned a multi-file fix. The effort stalled before a complete patch was produced, so the trajectory reflects partial understanding without successful completion.
- **Behavior:** Genuine exploratory debugging with a correct high-level diagnosis, but incomplete execution and no evidence of benchmark leakage.

> The trajectory shows a mostly legitimate debugging process rather than leakage. The agent began by exploring the repository structure, then inspected the schema files, storage config, OCI implementation, bundle command, and gRPC server. It formed a coherent hypothesis from what it found: the OCI schema was incomplete, the OCI storage type path was not wired into the gRPC server, defaults were inconsistent, and `NewStore` likely needed to accept a bundle directory directly. It also created a repr

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 6 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-86906cbfc3a5d3629a583f98e6301142f5f14bdb-v6bea0cc3a6fc532d7da914314f2944fc1cd04dee`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Add controlled, thread-safe reference deletion to the snapshot cache so fixed references are protected and non-fixed references are removable with correct garbage-collection behavior, and expose a public API to list remote branch/tag names from the default remote with defined timeout and error handling.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `test_mutation`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 38 of 38 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 5 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.98):
  This is the circular test-patch dependency subtype of approach_lock. A solver could correctly implement the stated task—controlled deletion in SnapshotCache and origin remote ref listing—and still fail because the F2P tests are wired to unrelated CSRF/configuration changes. The tests are therefore not merely broad; they require out-of-scope code paths to pass, rejecting valid solutions to the described problem.
  - Cross-reference analysis reports 18 circular dependencies where F2P tests depend on UNRELATED hunks; e.g. 'TestAnalyticsClickhouseConfiguration' → UNRELATED hunks [0, 1, 2, 3, 6, 9, 11, 15, 18, 19, 23, 26, 28, 30, 36] (conf=0.95).
  - The same circular dependency pattern is reported for many other tests, including 'TestAnalyticsPrometheusConfiguration', 'TestAuditEnabled', 'TestServeHTTP', 'TestStorageConfigInfo', and 'TestIsReadOnly'.
  - Those linked hunks include clearly unrelated behavioral changes such as hunk 30 (internal/cmd/http.go, CSRF middleware behavior) and hunks 31-32, 37 (internal/config authentication/CSRF settings), none of which are part of the snapshot-cache Delete or listRemoteRefs requirements.
**wide_tests** (confidence: 0.95):
  The problem specification is about snapshot-cache deletion semantics, garbage collection, concurrency safety, and listing branch/tag names from the origin remote. These F2P tests instead exercise configuration and CSRF-related behavior. That is beyond the described acceptance criteria, so the tests are wider than the task.
  - F2P analysis marks modified pre-existing test 'TestLoad' as UNRELATED three times, noting the post-patch changes concern configuration fields such as key/secure settings rather than SnapshotCache deletion or SnapshotStore.listRemoteRefs.
  - F2P analysis marks modified pre-existing test 'TestGetConfigFile' as UNRELATED, with reasoning that the modification is about configuration file handling and struct tags/camelCase equivalents, outside the task scope.
  - F2P analysis marks modified pre-existing test 'TestStructTags' as UNRELATED, explicitly stating it does not target any acceptance criterion for controlled snapshot-reference deletion or remote ref listing.
**test_mutation** (confidence: 0.97):
  This matches the definition of test_mutation exactly: pre-existing tests were edited to assert new behavior that is not in the problem statement or requirements. Because the modified assertions are about unrelated config/CSRF behavior, they silently expand the task under the guise of normal test maintenance.
  - Has modified tests: True.
  - Test 'TestLoad' is explicitly labeled '[MODIFIED pre-existing test, MISALIGNED changes]' and UNRELATED.
  - Test 'TestGetConfigFile' is explicitly labeled '[MODIFIED pre-existing test, MISALIGNED changes]' and UNRELATED.
**scope_creep** (confidence: 0.96):
  The patch does much more than the task asks—and in fact appears to solve a different feature entirely. The requested behavior concerns snapshot references and remote Git refs, while the patch introduces unrelated CSRF/configuration behavior. That is clear scope creep. This label is supported by the behavioral config/HTTP hunks, not by ancillary checksum or formatting churn.
  - Gold patch analysis says 'Has excess: True' with 38/38 hunks marked UNRELATED.
  - Behavioral unrelated hunks include hunk 30 in internal/cmd/http.go, which changes HTTP CSRF middleware behavior.
  - Behavioral unrelated hunks include hunks 31-32 in internal/config/authentication.go, which add/default a CSRF Secure field.
**weak_coverage** (confidence: 0.78):
  Beyond being misaligned, the F2P suite shown does not appear to cover the stated acceptance criteria at all. That means the benchmark is not actually verifying whether the described cache-deletion and remote-ref-listing behavior was implemented. A submission could miss key required behaviors yet still avoid being caught by task-relevant tests, so coverage of the stated spec is weak.
  - Acceptance criteria require testing Delete on fixed/non-fixed refs, lookup/list removal, shared-key garbage collection, idempotent deletion of missing refs, concurrency safety, and listRemoteRefs error handling.
  - The listed F2P tests are configuration/HTTP oriented ('TestLoad', 'TestGetConfigFile', 'TestStructTags', 'TestAnalyticsClickhouseConfiguration', 'TestServeHTTP', 'TestStorageConfigInfo', etc.), and none are identified as targeting internal/storage/fs/cache.go or internal/storage/fs/git/store.go.
  - F2P analysis explicitly states the unrelated modified tests do not exercise SnapshotCache deletion semantics, garbage collection, concurrency safety, or SnapshotStore.listRemoteRefs.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.98)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to have imported an unrelated remembered benchmark/task context at step 0, interpreted the repository through that lens, explored only CSRF/config-related files, implemented and validated that unrelated fix, and never inspected the actual snapshot-cache or git-store interfaces named in the prompt.
- **Behavior:** The agent showed coherent debugging behavior, but for the wrong problem: it pursued an unrelated Flipt CSRF/schema fix that aligns with the gold-patch contamination rather than the stated snapshot-cache task.

> The trajectory is a strong leakage/misattribution signal. From the very first step, the agent does not engage with the stated task about snapshot-cache reference deletion and remote ref listing. Instead, it confidently reframes the job as a completely different Flipt CSRF configuration bug: "fix the CSRF token key issue in the Flipt repository." It then explores authentication/config/server/schema code, forms a detailed hypothesis about `gorilla/csrf` secure cookies over HTTP, and plans changes 

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 38 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-af7a0be46d15f0b63f16a868d13f3b48a838e7ce`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Unify tracing configuration around top-level `tracing.enabled` and `tracing.backend` while keeping `tracing.jaeger.enabled` as a deprecated backward-compatible alias instead of allowing it to create an inconsistent tracing state.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `test_mutation`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 9 of 19 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 1 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.61):
  This fits the circular test-patch dependency subtype. The available analysis indicates at least one F2P test (`TestServeHTTP`) depends on unrelated patch work, especially the cache-config behavior in hunk 10. If so, an agent could correctly implement the tracing fix described by the task yet still fail because the suite also needs unrelated cache changes. Confidence is only moderate, not maximal, because two of the linked hunks ([0, 16]) are docs/formatting noise and the per-test alignment signal for `TestServeHTTP` was weak.
  - Cross-reference analysis: "Test 'TestServeHTTP' → UNRELATED hunks [0, 10, 16] (conf=0.95)" and "This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for."
  - Among the linked hunks, hunk 10 (`internal/config/cache.go`) is explicitly UNRELATED and behavioral: it maps deprecated cache-memory config to top-level cache backend selection.
  - The problem statement and requirements are limited to tracing configuration (`tracing.enabled`, `tracing.backend`, deprecated `tracing.jaeger.enabled`), not cache behavior.
**wide_tests** (confidence: 0.95):
  The F2P suite goes beyond the task scope by checking cache deprecation/default behavior that is not part of the tracing bug report or requirements. This is a straightforward scope-overreach contamination: the tests verify additional functionality unrelated to the asked tracing migration.
  - F2P analysis marks one modified `TestLoad` case as UNRELATED (conf=0.97): "This modified case is about deprecated cache-memory configuration defaults and cache deprecation warnings."
  - The problem statement is specifically about tracing configuration inconsistency caused by `tracing.jaeger.enabled`; the requirements mention only tracing fields and tracing schema/validation.
  - Heuristic pre-classification already flags `wide_tests` (conf=0.70): "1 UNRELATED tests found".
**test_mutation** (confidence: 0.97):
  This matches the taxonomy exactly: a pre-existing test was edited to assert new behavior not described in the problem. Because the added cache-related assertions are unrelated to the tracing task, the mutation makes the benchmark look more legitimate while silently expanding what must be implemented.
  - F2P analysis: `TestLoad` is a "MODIFIED pre-existing test" with "MISALIGNED changes".
  - That modified `TestLoad` case adds checks for deprecated cache-memory configuration defaults and cache deprecation warnings, which are outside the tracing acceptance criteria.
  - Heuristic pre-classification flags `test_mutation` (conf=0.80): "Test 'TestLoad' is pre-existing and modified with misaligned changes".
**scope_creep** (confidence: 0.94):
  The patch is not limited to the tracing migration. It also includes separate behavioral/configuration work for cache deprecations and UI schema deprecation. Those are not ancillary imports or formatting updates; they expand the PR's behavior beyond the described tracing issue, so the task includes genuine scope creep.
  - Gold patch analysis: "Has excess: True" with 9 UNRELATED hunks.
  - Hunk 10 (`internal/config/cache.go`) is UNRELATED and behavioral: it changes cache configuration mapping to a top-level backend selection.
  - Hunk 2 (`config/flipt.schema.cue`) changes cache-memory schema fields; hunk 7 (`config/flipt.schema.json`) deprecates `ui.enabled`; hunk 11 (`internal/config/cache.go`) renames cache deprecation message constants.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.89)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem, explored the relevant configuration and tracing code paths, then moved toward building a reproduction/test setup, but it never reached or recorded an implementation step, so the run ended as an incomplete attempt rather than a contaminated mismatch.
- **Behavior:** Legitimate exploratory debugging behavior with no leakage signs, but the agent stalled before producing a fix.

> The trajectory shows normal, problem-driven exploration rather than leakage. The agent starts by inspecting the repository structure, tracing configuration, main config integration, deprecation handling, telemetry/server usage, schema files, and tracing-related tests. That is exactly the kind of progressive search a genuine solver would do for this task, and it does not jump straight to the final files/functions in a suspicious way. There is also no sign of package installation, no mention of th

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 9 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-b22f5f02e40b225b6b93fff472914973422e97c6`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Add support for copying bundles between two local OCI references with tags, with strict tag validation, preserved bundle content, and returned metadata that proves the copied bundle exists at the destination.
**Severity:** SEVERE
**Labels:** `wide_tests`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 4 of 13 hunks are UNRELATED to the stated problem

### Label Analysis

**wide_tests** (confidence: 0.60):
  The benchmark includes at least one fail-to-pass test that goes beyond the requested behavior. The task specification only asks for File seek support and the specific unsupported-seek error, but TestFile also asserts additional File.Stat/file-info behavior not described in the problem, requirements, or out-of-scope exclusions. That is a classic wide_tests pattern: extra assertions in an otherwise related test broaden the evaluated surface beyond the stated acceptance criteria.
  - F2P Test 'TestFile' is classified TANGENTIAL (conf=0.95).
  - Test analysis states: 'a substantial portion of the test checks File.Stat-derived metadata and other file-info details that are outside scope.'
  - The stated scope for File only requires: support seeking when the wrapped stream is seekable, and return 'seeker cannot seek' when it is not.
**scope_creep** (confidence: 0.78):
  The gold patch expands behavior beyond the requested local tagged-copy feature. Although hunks 8 and 9 are marked REQUIRED overall because they also contain the needed `push` wiring, the same hunks introduce `pull` functionality tied to remote-related behavior that the task explicitly marks out of scope. This is behavioral expansion in product code, not merely ancillary imports or formatting, so scope_creep applies.
  - Out of scope explicitly says: 'The task does not ask for support for copying to or from remote registries...'
  - Hunk 8 [cmd/flipt/bundle.go]: REQUIRED, but analysis notes 'The added pull registration goes beyond scope.'
  - Hunk 9 [cmd/flipt/bundle.go]: REQUIRED, but analysis notes 'The `pull` implementation is extra remote-related functionality.'
**weak_coverage** (confidence: 0.90):
  Several stated acceptance criteria are not enforced by the F2P tests. In particular, the tests do not verify that the copied bundle shows up in later listings, that digest/file contents remain equal to the source, or that store initialization is reused rather than repeated. Because these omissions would allow an incomplete implementation to pass, the task has weak coverage.
  - Acceptance criterion: 'After a successful copy, the destination bundle appears in subsequent local bundle listings.'
  - Acceptance criterion: 'The application must not alter or lose content during the copy. The digest and file contents must remain consistent between source and destination.'
  - Acceptance criterion: 'The local store must be initialized once per operation and reused as needed. No redundant initialization of the local OCI store should occur.'

### Agent Evaluation Behavior

### Diagnosis

**Action:** Review 4 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-b433bd05ce405837804693bebd5f4b88d87133c8`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Support `otlp` as a valid tracing exporter in Flipt's configuration, using `exporter` as the primary field with the specified defaults and legacy Jaeger-setting compatibility.
**Severity:** SEVERE
**Labels:** `wide_tests`, `test_mutation`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 25 of 51 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 9 UNRELATED tests

### Label Analysis

**wide_tests** (confidence: 0.96):
  The benchmark tests go materially beyond the stated task scope. A solver could correctly implement OTLP tracing exporter support, the exporter rename/defaults, legacy Jaeger compatibility, and schema/serialization changes, yet still fail because F2P includes unrelated cache, database, auth, and version checks. This is wide_tests via extra test functions/cases, not merely stricter validation of the requested behavior.
  - F2P analysis: 9 tests are UNRELATED to the tracing-exporter/OTLP request.
  - Test 'TestCacheBackend': UNRELATED (modified pre-existing test, misaligned changes) targets cache backend behavior, not tracing.
  - Multiple modified 'TestLoad' cases are UNRELATED and cover cache/database/auth/version behavior: e.g. 'deprecated cache memory item defaults', 'cache no backend set', 'cache redis', 'version invalid', and HTTPS/database/authentication cases.
**test_mutation** (confidence: 0.94):
  This PR changed pre-existing tests to check behavior outside the problem statement. Because the modified assertions/cases target unrelated subsystems, they silently expand the benchmark scope while inheriting the legitimacy of old tests. That matches test_mutation exactly: misaligned modifications to existing tests, not legitimate updates to verify the requested tracing feature.
  - Test 'TestCacheBackend': UNRELATED [MODIFIED pre-existing test, MISALIGNED changes].
  - Several 'TestLoad' entries are UNRELATED [MODIFIED pre-existing test, MISALIGNED changes], including cache defaults/backend cases, database migration-path/UI cases, auth/session-domain normalization, and version handling.
  - These are not newly added isolated tests for the tracing feature; they are edits to existing tests that now assert unrelated behavior.
**scope_creep** (confidence: 0.73):
  The gold patch includes substantial non-tracing changes beyond the requested OTLP/exporter work. Some of these are behavioral or configuration-affecting, such as unrelated schema-default changes in database/logging/server sections and altered example runtime commands. These are not merely imports or formatting; they broaden the patch beyond the issue's tracing scope, so scope_creep applies.
  - Gold patch analysis: 25 hunks are UNRELATED.
  - Hunk 5 (config/flipt.schema.cue): unrelated change to database protocol defaults/order in a non-tracing schema section.
  - Hunk 6 (config/flipt.schema.cue): unrelated logging schema default/formatting change.
**weak_coverage** (confidence: 0.66):
  The specification is broader than what the F2P suite appears to verify. In particular, CUE-schema requirements and default-config example updates appear untested, and the runtime OTLP startup path is not clearly exercised by the visible tests. That means a partial implementation could still pass the benchmark, making the task easier and therefore weakly contaminated by undercoverage.
  - Acceptance criteria include CUE schema support for otlp and otlp.endpoint default (AC11), but the listed F2P tests only explicitly show TestTracingExporter, TestLoad cases, and TestJSONSchema.
  - Acceptance criteria include default configuration examples using 'exporter' under tracing (AC13), but no F2P test is listed for config/default.yml.
  - The only schema-focused F2P test identified is 'TestJSONSchema'; there is no corresponding explicit CUE-schema test in the F2P inventory.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.78)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem, explored config and tracing initialization code, identified that tracing config was centered in `internal/config/tracing.go` plus decode hooks and deprecations, implemented the core exporter/OTLP config changes, then ran into visible test mismatches caused by legacy expectations and shifted into test investigation instead of completing the remaining work.
- **Behavior:** Methodical and genuine exploration with a partially implemented real fix, derailed by outdated visible tests / incomplete follow-through rather than leakage.

> The trajectory looks like genuine task-oriented debugging, not leakage. The agent began with broad repository exploration, inspected the expected configuration path (`internal/config`, deprecations, decode hooks, runtime tracing setup in gRPC), checked tests and examples, and only then started editing the tracing config machinery. Its planned and partially executed changes align closely with the real requirements: rename `backend` to `exporter`, introduce a `TracingExporter` enum including OTLP,

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 25 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-b68b8960b8a08540d5198d78c665a7eb0bea4008`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Enforce `storage.read_only=true` for database-backed storage so that write operations are blocked consistently, matching the existing read-only behavior of the UI and other storage backends.
**Severity:** SEVERE
**Labels:** `approach_lock`, `weak_coverage`

### Contamination Signals


### Label Analysis

**approach_lock** (confidence: 0.58):
  This task appears mildly approach-locking through a narrow implementation-detail dependency: the test checks against a specific sentinel variable name (`errReadOnly`) rather than only observable behavior. A valid solution could satisfy the stated contract by using a different sentinel variable or exported error symbol, consistently returned and matchable via `errors.Is`, yet fail because the test expects the gold patch's package-private identifier. The overall wrapper approach is specified by the Requirements/Interface, so the lock is not about the wrapper itself; it is specifically about the exact sentinel symbol the test relies on.
  - F2P test `TestModificationMethods` is summarized as asserting `ErrorIs(err, errReadOnly)` for each mutating method.
  - The requirements only specify that each mutating method must return 'the same sentinel error' and that it 'must be comparable using `errors.Is`'; they do not specify the identifier name `errReadOnly`.
  - The Interface section lists `Store`, `NewStore`, and the mutating methods, but does not define any required public or package-level symbol named `errReadOnly`.
**weak_coverage** (confidence: 0.93):
  The tests under-cover the stated contract. They verify that mutating methods return a read-only error, but they do not verify several required behaviors: object-returning methods must also return nil/zero values, read/query methods must continue delegating normally, and the application must actually wrap the configured store in read-only mode at the server/integration level. As a result, a partial fix could pass F2P without fully implementing the specified behavior.
  - Acceptance criteria require: 'For mutating methods that also return an object, the method must return `nil` (or the type’s zero value) along with the sentinel error,' but the F2P analysis says `TestModificationMethods` only asserts `ErrorIs(err, errReadOnly)`.
  - Acceptance criteria require: 'Non-mutating methods (reads, queries, list operations) must remain functional and delegate normally to the underlying storage,' but the F2P suite contains only one aligned test covering mutating methods.
  - Gold patch hunk 1 (`internal/cmd/grpc.go`) is marked REQUIRED because it activates the wrapper when `cfg.Storage.IsReadOnly()` is true, yet the F2P test analysis describes only wrapper-method checks, not an integration check that the server actually uses the wrapper in read-only mode.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.76)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored storage interfaces and server initialization, found an existing read-only pattern in filesystem storage, generalized that into a wrapper-based solution, tried to wire it into gRPC startup, then attempted ad hoc validation but did not finish with a passing implementation.
- **Behavior:** A genuine, exploratory attempt that identified the right architectural fix pattern but likely failed due to incomplete execution or a subtle composition mismatch, not benchmark leakage.

> The trajectory looks like genuine problem-solving rather than leakage. The agent began by exploring the repository structure, then examined the storage interface, searched for existing read-only patterns, inspected configuration and gRPC server initialization, and explicitly derived the idea of a wrapper store from analogous filesystem storage behavior. That is a natural debugging path for this task. There are no signs that it knew the hidden test (`TestModificationMethods`), no suspicious refer

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_flipt-io__flipt-c8d71ad7ea98d97546f01cce4ccb451dbcf37d3b`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Enforce referential integrity consistently for Flipt configuration validation and snapshot/import loading so that rules referencing missing variants or segments are reported as errors instead of being ignored or inconsistently accepted.
**Severity:** SEVERE
**Labels:** `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 46 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.68):
  This task shows a circular test-patch dependency subtype of approach_lock. An F2P test (`FuzzValidate`) depends on patch hunks that were classified as UNRELATED to the requested behavior. Because those hunks are added fixture files rather than production logic, an agent could implement the described validation/import fix correctly yet still fail the benchmark if it does not also recreate those unrelated repository artifacts. That means the tests are not measuring only whether the requested behavior was solved; they also require extra, out-of-scope patch content. I am not assigning `scope_creep` because the unrelated hunks are test/support fixtures rather than behavioral code changes, and I am not assigning `wide_tests` because the main issue is dependency on unrelated patch material, not tests asserting extra product behavior.
  - Cross-reference analysis reports a circular dependency: Test 'FuzzValidate' → UNRELATED hunks [10, 12] (conf=0.90).
  - Hunk 10 adds fixture data at `internal/storage/fs/fixtures/invalid_boolean_flag_segment/features.yml` and is explicitly labeled UNRELATED.
  - Hunk 12 adds fixture data at `internal/storage/fs/fixtures/invalid_variant_flag_segment/features.yml` and is explicitly labeled UNRELATED.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.72)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the codebase, found the silent-ignore path for missing variants, reproduced the inconsistency, inspected import behavior for contrast, and then attempted to align validation with snapshot/import-time referential checks by modifying snapshot construction and related exported interfaces.
- **Behavior:** Systematic, bug-driven investigation with a real root-cause hypothesis and partial implementation of the correct approach, but incomplete execution rather than leakage.

> The trajectory looks like genuine debugging rather than leakage. The agent started with repository exploration, inspected the relevant command, CUE validation, storage filesystem code, and explicitly searched for the missing-variant behavior before identifying the silent `continue` in `internal/storage/fs/snapshot.go` as the core bug. It then created a reproduction file/script, confirmed the behavior, and compared the validate path with import logic to understand the inconsistency. That is a nor

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-cd18e54a0371fa222304742c6312e9ac37ea86c1`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Export the default configuration entry point and decode-hook set from `internal/config` so the canonical default config can be decoded and validated against the CUE schema.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 8 of 18 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 2 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.94):
  This is a circular test-patch dependency. An agent could satisfy the stated task by exporting DefaultConfig and DecodeHooks, wiring Load to use DecodeHooks, and preserving the relevant mapstructure tags, yet still fail because several F2P tests depend on unrelated schema and fixture changes. That means the tests are not only checking the described behavior; they require out-of-scope patch hunks to pass, which rejects otherwise valid solutions.
  - Cross-reference analysis reports 6 circular dependencies: TestJSONSchema, TestScheme, TestCacheBackend, TestTracingExporter, TestDatabaseProtocol, and Test_mustBindEnv each exercise UNRELATED hunks [4, 5, 16] with confidence 0.95.
  - Hunk 4 (config/flipt.schema.cue) is UNRELATED: it rewrites schema behavior for CORS, storage, and database sections beyond the export/decode-hook bug.
  - Hunk 5 (config/flipt.schema.cue) is UNRELATED: it adds shared schema-side #duration infrastructure not requested by the problem.
**wide_tests** (confidence: 0.82):
  The F2P suite extends beyond the stated acceptance criteria. The task asks for public config exports and successful decoding/validation of the default configuration, but the F2P set includes unrelated logging and HTTP-serving tests plus broad integration-style load tests for custom configurations. Those tests verify extra behavior outside the requested scope, so the test suite is wider than the problem.
  - F2P test analysis says Has excess: True, with 29 tests total and only 7 ALIGNED; 20 are TANGENTIAL and 2 are UNRELATED.
  - TestLogEncoding is marked UNRELATED (conf=0.90): it targets logging configuration/serialization rather than exported DefaultConfig/DecodeHooks or default-config CUE validation.
  - TestServeHTTP is marked UNRELATED (conf=0.93, modified pre-existing): it targets HTTP serving behavior, not the configuration export/decode-hook/schema-validation bug.
**scope_creep** (confidence: 0.90):
  The gold patch does more than fix the missing public exports and decode-hook wiring. It also expands and refactors the CUE schema in multiple unrelated ways, including new config surface and authentication/storage/schema behavior. Those are substantive behavioral changes beyond the described bug, so the patch itself exhibits scope creep.
  - Gold patch analysis: Has excess: True; 8 hunks are UNRELATED.
  - Hunk 0 (config/flipt.schema.cue) is UNRELATED: it adds new top-level experimental and storage schema entries.
  - Hunk 1 (config/flipt.schema.cue) is UNRELATED: it broadens authentication-related schema with new session lifetime/csrf rules.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.96)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem and performed broad repo exploration across config structs, schema files, tests, and testdata. That broad exploration seems to have led it into unrelated or peripheral config/CUE areas, after which it formed an incorrect intermediate hypothesis about the validation target and never converged on the concrete fix of exporting `DefaultConfig` and `DecodeHooks` and updating the load path.
- **Behavior:** Broad, exploratory debugging that remained inconclusive; no leakage signals, but no concrete fix or completed intent either.

> The trajectory shows normal exploratory behavior rather than leakage. The agent began by surveying the repository, configuration files, schema files, tests, and default-setting logic. It explicitly searched for `DefaultConfig`, searched for where defaults are constructed, inspected decode-hook usage, and looked through config-related test data. This is the opposite of a leak signature such as jumping immediately to the exact fix locations with no search. There is also no evidence of package inst

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 8 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-dbe263961b187e1c5d7fe34c65b000985a2da5a0`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Add lifecycle management for background polling in storage backends so that closing a `SnapshotStore` cleanly stops any active polling goroutine.
**Severity:** SEVERE
**Labels:** `wide_tests`, `test_mutation`, `weak_coverage`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 75 of 89 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 2 UNRELATED tests

### Label Analysis

**wide_tests** (confidence: 0.94):
  The fail-to-pass suite goes beyond the task's stated acceptance criteria by exercising unrelated Git TLS and CA-bundle behavior. Those test functions are not about the requested polling lifecycle fix, so they add extra scope to what the benchmark measures. This is wide_tests contamination because the F2P suite includes entire tests for behavior not described in the problem or requirements.
  - F2P test 'Test_Store_SelfSignedSkipTLS' is marked UNRELATED (conf=0.99); it targets Git TLS behavior via self-signed certificates / WithInsecureTLS rather than poller shutdown or SnapshotStore.Close lifecycle.
  - F2P test 'Test_Store_SelfSignedCABytes' is marked UNRELATED (conf=0.99); it targets CA bundle handling, not polling goroutine termination.
  - The stated task scope is polling lifecycle management: 'Polling goroutines should terminate cleanly when a SnapshotStore is closed' and the requirements are all about Poller/NewPoller/Poll/Close and SnapshotStore.Close.
**test_mutation** (confidence: 0.97):
  This exactly matches the test_mutation pattern: pre-existing tests were modified, and the modifications are explicitly classified as misaligned with the task. Because the changed assertions/execution path concern unrelated Git TLS/CA functionality rather than poller lifecycle management, the PR silently broadened what those old tests enforce.
  - F2P analysis says 'Has modified tests: True'.
  - Test 'Test_Store_SelfSignedSkipTLS': 'UNRELATED (conf=0.99) [MODIFIED pre-existing test, MISALIGNED changes]'.
  - Test 'Test_Store_SelfSignedCABytes': 'UNRELATED (conf=0.99) [MODIFIED pre-existing test, MISALIGNED changes]'.
**weak_coverage** (confidence: 0.95):
  The benchmark barely tests the requested fix. None of the F2P tests are fully aligned to the core acceptance criteria, and the only somewhat related test merely calls Close during cleanup without checking the required semantics. That means large parts of the specification—especially waiting for goroutine termination and no-op Close behavior—could be implemented incorrectly yet still pass, making this a clear weak_coverage issue.
  - F2P TEST ANALYSIS: 'Tests: 3 (ALIGNED=0, TANGENTIAL=1, UNRELATED=2)'.
  - Assertion summary: 'Assertions: 0 (ON_TOPIC=0, OFF_TOPIC=0)'.
  - Test 'Test_Store' is only TANGENTIAL: 'The added cleanup calls s.Close(), which is relevant ... However, the test does not explicitly assert any polling lifecycle behavior, goroutine termination, or no-op semantics.'
**scope_creep** (confidence: 0.83):
  The gold patch contains behavioral changes outside the reported bug: config path normalization and database URL formatting. Those code changes are unrelated to stopping polling goroutines and therefore expand the patch beyond the task's scope. I am basing this label on the behavioral config hunks, not the many go.work.sum metadata hunks, which are unrelated but non-behavioral.
  - Gold patch hunk 73 in 'internal/config/config.go' is UNRELATED (conf=0.99): it changes database path slash normalization, not polling lifecycle.
  - Gold patch hunk 74 in 'internal/config/database.go' is UNRELATED (conf=0.99): it changes default database URL path formatting, not Poller/SnapshotStore Close behavior.
  - The task scope is limited to 'internal/storage/fs' poller lifecycle management and SnapshotStore.Close behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.97)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to have explored the repo too broadly, latched onto an unrelated Windows database URL bug, then reinterpreted the task as a multi-issue PR. That mistaken diagnosis drove implementation effort away from the actual polling goroutine lifecycle problem.
- **Behavior:** Genuine but misdirected debugging: some relevant exploration, then strong commitment to an unrelated bug, resulting in failure to address the actual polling lifecycle task.

> The trajectory does not show benchmark leakage. Instead, it shows a confused and ultimately incorrect problem-solving attempt. The agent began with broad exploration, but quickly veered into an unrelated database URL / Windows path separator issue, explicitly diagnosing `filepath.Join()` producing backslashes in `file:` URLs. Although it later glanced at the polling mechanism and storage backends, its concrete hypothesis and implementation plan centered on the database bug, not the stated lifecy

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 75 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-ebb3f84c74d61eee4d8c6875140b990eee62e146`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Add support for token-authentication bootstrap settings in YAML so a configured static token and optional expiration are loaded into runtime configuration instead of being ignored.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 8 of 13 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.82):
  This fits the circular test-patch dependency subtype of approach_lock. The stated task only requires the config surface and loader behavior, so a valid solution could stop after implementing the config structs/fields and YAML parsing behavior. However, the analysis says an F2P test (`TestJSONSchema`) reaches unrelated behavioral hunks in command/bootstrap/storage code. If those unrelated hunks are needed for tests to pass, then the benchmark rejects a solution that correctly satisfies the written requirements but does not replicate the broader gold-patch approach.
  - Cross-reference analysis reports a circular dependency: test 'TestJSONSchema' depends on UNRELATED hunks [2, 6, 9, 10, 11, 12] with confidence 0.95.
  - The task specification is limited to configuration modeling/loading: add `AuthenticationMethodTokenConfig.Bootstrap`, introduce `AuthenticationMethodTokenBootstrapConfig`, and parse `authentication.methods.token.bootstrap` from YAML into `Token` and `Expiration`.
  - Hunk 2 (`internal/cmd/auth.go`) and hunks 6, 9, 10, 11, 12 are marked UNRELATED because they change bootstrap/storage behavior: passing configured values into `storageauth.Bootstrap`, adding `ClientToken`, and making memory/SQL stores honor supplied tokens.
**scope_creep** (confidence: 0.97):
  The patch goes well beyond the reported bug. The required fix is to expose and load `authentication.methods.token.bootstrap` into runtime configuration. Instead, the gold patch also extends the live bootstrap pipeline and storage layers so configured values actively control token creation semantics. Those are behavioral changes outside the requested scope, so the task has clear scope creep.
  - Gold patch analysis: `Has excess: True` with 8 UNRELATED hunks.
  - Hunk 2 (`internal/cmd/auth.go`) changes runtime bootstrap behavior by passing configured token/expiration into `storageauth.Bootstrap`.
  - Hunk 6 (`internal/storage/auth/auth.go`) adds `ClientToken` to `CreateAuthenticationRequest`.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.81)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem, explored the config and auth bootstrap flow, inferred that YAML parsing alone was insufficient because the bootstrap token also needed to propagate into authentication creation, implemented those runtime/config changes, then iterated through compile and validation issues; it likely failed due to incomplete coverage of schema or other benchmark-checked files.
- **Behavior:** A genuine, exploratory attempt that implemented much of the right runtime/config path and debugged through real issues, but likely missed some benchmark-checked supporting changes, leading to failure without evidence of leakage.

> This trajectory looks like genuine problem-solving rather than benchmark leakage. The agent did not jump straight to the final fix: it first explored the authentication config, storage layer, bootstrap logic, SQL and memory stores, command wiring, and example/default configuration. It then formed a coherent implementation plan and executed it incrementally: adding bootstrap config, extending authentication creation to accept explicit client tokens, adding bootstrap options, updating both storage

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 8 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_flipt-io__flipt-f1bc91a1b999656dbdb2495ccb57bf2105b84920`

### Task Context

**Repository:** `flipt-io/flipt` (version )
**Core requirement:** Introduce a standalone `Evaluator` abstraction and SQL-backed `EvaluatorStorage` so `Server.Evaluate` no longer depends on `RuleStore.Evaluate`, while preserving the specified flag-evaluation behavior and response semantics.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `test_mutation`

### Contamination Signals


### Label Analysis

**approach_lock** (confidence: 0.80):
  These tests lock the task to the gold patch's internal decomposition. A solution could satisfy the public contract—correct evaluation semantics, request ID handling, errors, rollout selection, and server delegation—while implementing the logic inline or with differently named/private helpers. Such a solution would still fail or not compile against tests that directly exercise specific internal helper functions. That is narrow implementation-detail checking, so this is approach_lock.
  - F2P contains helper-level tests named `Test_matchesString`, `Test_matchesNumber`, `Test_matchesBool`, `Test_evaluate`, and `Test_validate` rather than only black-box tests of `(*Server).Evaluate` / `(*EvaluatorStorage).Evaluate`.
  - `Test_validate` is explicitly described as focusing on "an internal validate helper".
  - The problem statement and Requirements specify evaluator behavior and the new `Evaluator`/`EvaluatorStorage` abstraction, but they do not require internal helpers named `validate`, `matchesString`, `matchesNumber`, `matchesBool`, or `evaluate`.
**wide_tests** (confidence: 0.62):
  At least one F2P test function goes beyond the stated task scope. The task asks for decoupling evaluation into a new `Evaluator`/`EvaluatorStorage` and preserving specified evaluation semantics. Testing an internal validation helper and malformed constraint-shape behavior as its own target exceeds that external contract. Because this is an extra test function outside the described acceptance criteria, wide_tests applies.
  - `Test_validate` is marked TANGENTIAL (conf=0.77) with reasoning: it "focuses on an internal validate helper and malformed constraint-shape checks, which are not part of the requested external evaluator contract."
  - The modified pre-existing `Test_validate` is also marked TANGENTIAL and notes "MISALIGNED changes".
  - Acceptance criteria define supported operators and evaluation behavior, but do not separately require a standalone validation-helper contract for malformed constraint shapes.
**test_mutation** (confidence: 0.93):
  This directly matches the taxonomy for test_mutation: a pre-existing test was changed to assert behavior not described by the problem. The modified `Test_validate` adds or retargets coverage toward tangential internal-validation behavior, making the task look more naturally covered by old tests while silently expanding what must be implemented.
  - F2P analysis reports `Has modified tests: True`.
  - `Test_validate` is a `[MODIFIED pre-existing test, MISALIGNED changes]`.
  - That same modified test is classified TANGENTIAL rather than aligned to the accepted feature.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.80)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the relevant files, inferred that evaluation logic currently lived in `RuleStore`, formed the correct high-level refactor plan from the task description, started creating `storage/evaluator.go` and removing `Evaluate` from `RuleStore`, then appears to have stalled during repository editing before finishing server wiring and validation.
- **Behavior:** Genuine exploratory refactor attempt with partial implementation and no clear leakage signals, but incomplete and unsuccessful.

> The trajectory shows a normal, non-suspicious attempt to implement the requested refactor, but not a completed or demonstrably working solution. The agent began by exploring the repository structure, reading the existing `server` and `storage` code, checking RPC types, and inspecting error helpers before planning changes. Its stated plan closely follows the problem statement: create `storage/evaluator.go`, add an `Evaluator` interface and storage implementation, remove `Evaluate` from `RuleStore

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_future-architect__vuls-1832b4ee3a20177ad313d806983127cb6e53f5cf`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Implement end-to-end macOS platform support in Vuls—including build targets, OS detection, scanning, package parsing, EOL/CPE handling, and Apple-specific metadata behavior—without introducing new public interfaces or regressing existing Windows/FreeBSD behavior beyond the shared ifconfig parsing change.
**Severity:** SEVERE
**Labels:** `unclear_spec`, `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 18 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.56)

### Label Analysis

**unclear_spec** (confidence: 0.97):
  The task statement is actively misleading: the headline and narrative describe an unrelated encapsulation/refactoring task, while the actual required work and gold patch are about macOS platform support in a different code area. This creates multiple incompatible interpretations of what the agent is supposed to do. Even though the SWE-bench Pro requirements rescue the task, the base problem statement itself is unclear enough to contaminate the benchmark.
  - Problem statement title/description says 'Improving Encapsulation in Client Functions' and discusses LastFM/ListenBrainz/Spotify clients being public.
  - Requirements and intent extraction instead specify end-to-end macOS support in Vuls: darwin build targets, Apple family constants, detectMacOS, scanner/macos.go, CPE generation, and Apple-specific metadata handling.
  - Intent extraction explicitly notes: 'The opening problem text about LastFM/ListenBrainz/Spotify client encapsulation appears unrelated to the concrete vuls requirements.'
**approach_lock** (confidence: 0.58):
  Some F2P tests appear to bind to internal helper decomposition rather than only observable behavior. A valid implementation could satisfy the stated requirements by parsing sw_vers inline inside detectMacOS, or by handling version parsing without exposing/retaining a specific 'majorDotMinor' helper, yet such a solution could fail these helper-targeted tests. That is a moderate approach-lock signal because the tests seem to constrain how the solution is structured, not just what it does.
  - F2P includes helper-specific tests 'Test_parseSWVers' and its subtests.
  - F2P includes helper-specific tests 'Test_majorDotMinor' and its subtests.
  - Acceptance criterion 4 requires macOS detection behavior ('run sw_vers, parse ProductName/ProductVersion, map to family, return release'), but does not require a separate helper named 'parseSWVers'.
**scope_creep** (confidence: 0.64):
  The gold patch includes behavioral changes beyond the requested macOS support scope. In particular, it broadens CPE behavior with extra Apple application CPE generation not asked for, and it adds Windows dispatch behavior that the requirements explicitly say should remain unchanged aside from the specified FreeBSD reuse of parseIfconfig. These are genuine scope expansions, not mere ancillary edits.
  - Hunk 9 [detector/detector.go] is marked REQUIRED overall but analysis notes it 'also adds extra Apple application CPEs beyond the stated acceptance criteria.'
  - Hunk 16 [scanner/scanner.go] is marked REQUIRED overall but analysis notes 'It also adds a Windows case, which is beyond the stated scope.'
**weak_coverage** (confidence: 0.95):
  A substantial fraction of the stated acceptance criteria is untested by the fail-to-pass suite. An agent could pass the visible F2P tests while omitting important required behaviors such as darwin release builds, Apple OS CPE generation, OVAL/GOST skipping, or detectOS registration/order. That makes the task easier than intended and weakens its value as a capability measure.
  - Listed F2P tests cover Apple EOL logic ('TestEOL_IsStandardSupportEnded'), shared ifconfig parsing ('TestParseIfconfig'), sw_vers parsing ('Test_parseSWVers'), and macOS package parsing/metadata ('Test_macos_parseInstalledPackages').
  - No F2P tests are identified for acceptance criterion 1 / hunks 0-4 (.goreleaser darwin build matrix changes).
  - No F2P tests are identified for acceptance criterion 9 / hunk 9 (Apple OS-level CPE generation).

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.87)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the codebase to infer existing OS-detection and scanning patterns, formed a plausible macOS-support plan, ran some local repro investigation that highlighted missing constants, then attempted implementation but got derailed by command/editing issues before producing a usable patch.
- **Behavior:** Legitimate exploratory debugging and planning for a broad macOS feature addition, but the attempt fizzled before any substantive patch landed.

> The trajectory shows mostly legitimate exploration and planning rather than leakage. The agent began by reading and mapping the repository structure, explicitly inspecting scanner, detector, OS detection, and platform-specific implementations before proposing changes. That is the opposite of a suspicious jump directly to the gold files/functions. There is no evidence of pip/go package installation, no copying from external sources, and no references to the fail-to-pass test names or hidden expec

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_future-architect__vuls-3c1489e588dacea455ccf4c352a3b1006902e2d4`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Make CVEs that have only a severity label, but no explicit CVSS2 or CVSS3 numeric score, behave like scored vulnerabilities by deriving a CVSS score from severity and using it consistently in filtering, grouping, sorting, max-score calculations, and report output.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `test_mutation`, `weak_coverage`

### Contamination Signals

- **WIDE_TESTS:** 2 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.64):
  The task specification requires deriving scores from severity and using them consistently, but it does not fully determine the exact point estimate within each severity range, nor does it require the `CalculatedBySeverity` flag. Tests that hard-code `8.9`/`6.9` and exact struct fields narrow the acceptable implementation to the gold patch's representation. An implementation that derives scores differently but still honors the stated ranges and observable filtering/grouping/reporting behavior could fail these tests, so the task shows approach-locking through narrow assertions.
  - The Requirements specify severity-to-CVSS *ranges* via `Cvss.SeverityToCvssScoreRange()` and only explicitly pin `Critical` to the `9.0-10.0` range; they do not specify exact numeric representatives like `HIGH -> 8.9` or `MEDIUM -> 6.9`.
  - F2P analysis for `TestCvss3Scores` says the expected output is a severity-only `Cvss3Severity=HIGH` case with a derived CVSS3 score of `8.9` and `CalculatedBySeverity` set.
  - F2P analysis for `TestMaxCvssScores` says expected values explicitly include derived scores `6.9` for `MEDIUM` and `8.9` for `HIGH`, again with `CalculatedBySeverity=true`.
**wide_tests** (confidence: 0.80):
  The F2P suite goes beyond the stated task by checking helper behavior and generic numeric sorting/counting/formatting cases that are not part of the severity-only CVSS regression. This is broader than the acceptance criteria, which focus on deriving scores for severity-only CVEs and using those derived scores in filtering, grouping, sorting, max-score logic, and reporting.
  - F2P analysis marks `TestCvss2Scores` as UNRELATED (conf 0.81) [MODIFIED pre-existing test, MISALIGNED changes], noting that it checks the `Cvss2Scores` helper and 'ordinary extraction of existing scores from multiple sources,' which the acceptance criteria do not mention.
  - F2P analysis marks a modified `TestToSortedSlice` case as TANGENTIAL/MISALIGNED (conf 0.91): 'Sorting by CVE ID when max scores tie is a generic tie-break rule. The problem only requires that sorting use severity-derived scores like numeric ones.'
  - F2P analysis marks modified `TestCountGroupBySeverity` cases as TANGENTIAL/MISALIGNED (conf 0.73/0.79), because they use explicit numeric CVSS fixtures and unknown entries rather than the severity-only derivation path described by the bug.
**test_mutation** (confidence: 0.92):
  This task contains classic test mutation contamination: existing tests were edited to add new obligations that are not described by the issue/requirements. Because these are mutated legacy tests rather than clearly separate new tests, they silently expand what the benchmark demands and can create false negatives for otherwise sufficient fixes.
  - `TestCountGroupBySeverity` is marked [MODIFIED pre-existing test, MISALIGNED changes] in two places; the analysis says the visible fixtures rely on explicit numeric scoring and an unknown entry rather than severity-only derivation.
  - `TestToSortedSlice` contains modified pre-existing misaligned cases, including the CVE-ID tie-break scenario called out as tangential to the problem.
  - `TestCvss2Scores` is marked [MODIFIED pre-existing test, MISALIGNED changes] and UNRELATED.
**weak_coverage** (confidence: 0.62):
  Several stated requirements appear only weakly or indirectly tested. The suite strongly exercises filtering, max-score fallback, and some sorting, but it does not directly cover important promised behavior such as TUI/Syslog/Slack rendering, severity-only grouping/report counts, or the new `SeverityToCvssScoreRange` interface. A partial fix could therefore pass without implementing all stated acceptance criteria.
  - Requirement 8 explicitly mentions rendering in `detailLines` (`report/tui.go`) and output logic in `syslog.go` and `slack.go`, but the listed F2P tests contain no test targeting TUI detail lines, Syslog output, or Slack output.
  - Gold patch hunk 10 (`report/tui.go`) is classified REQUIRED, yet no corresponding F2P test is listed for `detailLines` behavior.
  - Acceptance criterion 6 requires severity-only CVEs to be included in severity grouping/report counts, but the modified `TestCountGroupBySeverity` cases are marked TANGENTIAL/MISALIGNED and do not directly verify severity-only grouping.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.87)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent started with normal codebase exploration, inspected CVSS-related model/report logic, wrote ad hoc repro scripts, identified a likely root cause in `MaxCvss3Score()`, and outlined broader fixes. Tool/shell friction then appears to have interrupted progress, and the session ended before any concrete patch was applied.
- **Behavior:** Genuine exploratory debugging with a correct partial diagnosis, but incomplete execution and no final patch.

> The trajectory shows genuine repository exploration and problem-focused debugging, not leakage. The agent read relevant model and report code, attempted to reproduce the bug with custom scripts, and formed a plausible hypothesis that severity-only CVEs were mishandled because `MaxCvss3Score()` lacked the severity-derived fallback behavior present in `MaxCvss2Score()`. It also correctly inferred that additional changes would be needed in filtering and reporting. However, the agent never produced 

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_future-architect__vuls-436341a4a522dc83eb8bddd1164b764c8dd6bc45`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Synchronize the specified OS EOL metadata and modern Windows KB release mappings with current vendor timelines, and eliminate mixed struct-literal forms in the Windows release data so support status, KB applicability, and compilation are all correct.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 17 of 23 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.99):
  The patch goes well beyond the stated task. In addition to the required Fedora/SUSE Enterprise/macOS fixes and the three requested Windows branches, it performs a broader Windows KB data refresh across many unrelated branches and also changes unrelated SUSE/openSUSE entries. These are behavioral changes, not ancillary cleanup, so they fit scope_creep directly.
  - Gold patch analysis: Has excess=True with 17 UNRELATED hunks out of 23.
  - Hunk 0 [config/os.go] changes SUSE/openSUSE 15.3, 15.4, and 15.6 lifecycle data, while the requirements say to update only SUSE Enterprise version 13 and 14 and to leave other SUSE entries intact.
  - Hunks 4-10, 12, 14-21 [scanner/windows.go] add KB mappings for Windows branches other than the explicitly requested 10.0.19045.x, 10.0.22621/22631.x, and 10.0.20348.x branches.
**approach_lock** (confidence: 0.61):
  There is moderate evidence of a circular test-patch dependency: aligned F2P tests appear to require unrelated scanner/windows.go hunks to pass. That means an agent could implement the requested Fedora/macOS/SUSE Enterprise updates and the three requested Windows branches correctly, yet still fail because unrelated Windows-branch edits are also necessary for the tested build/test path. This matches the approach_lock subtype where tests require out-of-scope patch hunks. Confidence is not maximal because the dependency is inferred from cross-reference analysis rather than a direct failing assertion on the unrelated branches.
  - Cross-reference analysis reports 8 circular dependencies.
  - Example: Test 'Test_windows_detectKBsFromKernelVersion/10.0.19045.2129' → UNRELATED hunks [5, 12, 17, 21] (conf=0.95).
  - Example: Test 'Test_windows_detectKBsFromKernelVersion/10.0.22621.1105' → UNRELATED hunks [5, 12, 17, 21] (conf=0.95).
**weak_coverage** (confidence: 0.90):
  The task specification includes required behavior for macOS 11 and SUSE Enterprise 13/14, but the fail-to-pass tests shown only exercise Fedora and the targeted Windows KB detection paths. That means a partial fix could omit some stated requirements and still pass the benchmark tests, making the task easier and under-measured. This is classic weak_coverage.
  - Acceptance criterion 4 requires: 'macOS 11 is marked as ended, while macOS major versions 12, 13, 14, and 15 remain present...' but no F2P test listed targets macOS behavior.
  - Acceptance criterion 5 requires SUSE Enterprise Desktop/Server version 13 and 14 date updates, but no F2P test listed targets those SUSE dates.
  - F2P tests listed cover Fedora 37/38/40 and Windows kernel-version KB detection for 19045.x, 22621.x, and 20348.x only.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.93)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem, explored the relevant files and tests methodically, noticed that currently visible tests were passing, then tried to infer the needed updates from the PR description. That led to a narrowed and incomplete understanding of the required Windows/SUSE changes, and the run terminated before any concrete implementation was delivered.
- **Behavior:** Methodical repository exploration with partial understanding, but no completed implementation and no evidence of leakage.

> This trajectory looks like a genuine but incomplete debugging attempt rather than leakage. The agent began by identifying the likely relevant areas from the problem statement, then explored the repository step by step: locating `GetEOL`, `windowsReleases`, related tests, and constants. That progressive search behavior argues against benchmark leakage. There is no sign of package installation, copying from external sources, or jumping straight to the exact fix. However, the agent never produced a

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 17 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_future-architect__vuls-457a3a9627fb9a0800d0aecf1d4713fb634a9011`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Update the Windows scanner’s knowledge for the specifically affected Windows 10 22H2, Windows 11 22H2, and Windows Server 2022 tracks so recent monthly KBs/build revisions are recognized correctly in Applied/Unapplied results.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 21 of 24 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The patch clearly expands beyond the requested bug fix. Only three hunks are needed to satisfy the explicit acceptance criteria for the 19045, 22621, and 20348 cases. The remaining 21 hunks introduce additional behavioral mappings for other Windows tracks and duplicated table sections, which are not requested by the problem. Because these are substantive behavior changes rather than ancillary edits, this is strong scope_creep.
  - Gold patch analysis marks only hunks 9, 11, and 23 as REQUIRED; 21 of 24 hunks are UNRELATED behavioral changes.
  - UNRELATED hunks 0-8, 10, and 12-22 all modify scanner/windows.go to add KB/build mappings for other Windows branches or release tables not covered by the acceptance criteria.
  - Examples called out as out of scope include hunk 1 adding KBs 5023759/5025277/5026426/5027256 and hunk 4 adding KBs 5023713/5025234/5026382/5027230/5028622, none of which appear in the problem statement or requirements.
**approach_lock** (confidence: 0.64):
  This is not a narrow-assertion issue, but there is evidence of the circular-dependency subtype of approach_lock. The problem asks for specific KB/revision updates on three named tracks, yet cross-reference analysis indicates several F2P tests exercise UNRELATED hunks outside that scope. If a solver implemented only the required mappings (hunks 9, 11, 23), the benchmark may still fail because the tests depend on broader release-table edits the problem never asked for. That rejects a valid scoped solution, so approach_lock applies with moderate confidence.
  - Cross-reference analysis reports 5 circular dependencies with confidence 0.95.
  - Test 'Test_windows_detectKBsFromKernelVersion/10.0.19045.2129' is linked to UNRELATED hunks [2, 12, 20].
  - Test 'Test_windows_detectKBsFromKernelVersion/10.0.19045.2130' is linked to UNRELATED hunks [2, 12, 20].

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.67)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the codebase, identified the update-mapping table as the relevant logic, concluded that missing KB entries were the cause, then expanded the work into a broad multi-version KB refresh aligned with the contaminated task scope; this likely caused it to bog down and never finalize a patch.
- **Behavior:** Genuine debugging trajectory with correct subsystem identification, but derailed by over-broad scope and failed to complete the implementation.

> The trajectory shows real problem-oriented exploration rather than a direct jump to an exact hidden answer. The agent inspected the repository, focused on `scanner/windows.go`, found the `windowsReleases` map, and correctly inferred that the bug lives in stale KB/build-revision mapping data. That is the right conceptual fix. There are no signs of package leakage, no copying from installed artifacts, and no explicit references to hidden F2P test names or unseen expected values. However, the agent

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 21 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_future-architect__vuls-8d5ea98e50cf616847f4e5a2df300395d1f719e9`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Add an optional WordPress scanning setting/CLI flag, `-wp-ignore-inactive`, so inactive WordPress plugins and themes can be excluded from vulnerability scanning.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 8 of 15 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.78):
  This matches the circular test-patch-dependency subtype of approach_lock. The fail-to-pass test is reported to require unrelated patch hunks, so an agent could correctly implement the requested WordPress inactive-filtering behavior yet still fail unless it also reproduces unrelated dependency churn. That makes the benchmark reject otherwise valid solutions for reasons outside the stated task.
  - Cross-reference analysis reports a circular dependency: Test 'TestRemoveInactive' -> UNRELATED hunks [3, 4, 5, 6, 7, 8, 10] (conf=0.95).
  - Hunks 3, 4, 5, 6, 7, 8, and 10 are all classified as UNRELATED dependency/module changes in go.mod/go.sum rather than part of the requested flag/config/filter behavior.
  - The problem/requirements only ask for SetFlags registration, a WpIgnoreInactive config field, FillWordPress conditional filtering, and removeInactives filtering.
**scope_creep** (confidence: 0.56):
  The gold patch extends beyond the requested WordPress feature by including unrelated dependency-management changes. Those changes are outside the described product behavior and broaden the patch beyond the task's stated scope.
  - Gold patch analysis says Has excess=True with 8 UNRELATED hunks.
  - Hunk 3 [go.mod] updates dependency versions/adds indirect modules and is explicitly marked UNRELATED.
  - Hunks 4-10 [go.sum] are also marked UNRELATED and are corresponding dependency checksum changes, while the stated acceptance criteria are limited to SetFlags, config.WpIgnoreInactive, FillWordPress, and removeInactives.
**weak_coverage** (confidence: 0.91):
  The fail-to-pass coverage does not fully exercise the stated specification. A partial fix that only makes removeInactives filter inactive packages could plausibly satisfy the visible F2P coverage while leaving the CLI flag, config wiring, or FillWordPress integration incomplete. That makes the task easier and the measured score less representative of full task completion.
  - F2P test analysis shows only one aligned test: 'TestRemoveInactive'.
  - Acceptance criteria also require registering '-wp-ignore-inactive' in SetFlags, adding config field WpIgnoreInactive, integrating conditional filtering in FillWordPress, and preserving existing behavior when the option is false.
  - Required hunks 1, 2, 12, and 13 implement those behaviors, but no corresponding F2P tests are reported for them.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.87)
- **Gold patch similarity:** 0.0%
- **Causal chain:** Problem statement led the agent to inspect config/flag wiring and WordPress scanning code; from there it found the TODO in `FillWordPress` and the inactive status field in the model, forming the correct plan to add a config flag and filter inactive packages, but the run stopped before implementation.
- **Behavior:** Legitimate exploratory diagnosis with a plausible plan, but the task was left unfinished and no actual fix was applied.

> The trajectory shows a normal, grounded debugging process rather than leakage. The agent starts from the problem statement, explores configuration handling, command flag setup, WordPress-specific code, and then discovers an in-repo TODO in the relevant function explicitly mentioning the desired flag/config behavior. It also inspects the WordPress model and notices the existing inactive-status representation, which is the expected path for a legitimate solver. There are no signs of benchmark leak

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 8 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_future-architect__vuls-be7b9114cc9545e68fb0ee7bc63d7ec53d1a00ad`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Preserve Trivy-reported package URLs by adding and populating PURL data on Vuls library entries produced from Trivy scan results.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 5 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.94):
  The issue is narrowly about not dropping Trivy-reported PURLs during conversion into `models.Library` / `LibraryScanners`. Hunks 3 and 4 add new behavior in a separate scanner path that synthesizes PURLs, which is broader than preserving already-present Trivy metadata. Because these are behavioral changes, not ancillary edits, this is scope expansion in the patch itself.
  - Gold patch hunk 3 in `scanner/library.go` is classified UNRELATED (conf=0.82): it populates `PURL` by calling `newPURL(app.Type, types.Metadata{}, lib)` in a different scanner path, synthesizing a package URL rather than preserving Trivy's existing `Identifier.PURL`.
  - Gold patch hunk 4 in `scanner/library.go` is classified UNRELATED (conf=0.88): it adds a helper that generates a PURL via `trivy/pkg/purl.New` and logs failures.
  - The stated out-of-scope analysis says the request does not ask Vuls to generate or infer PURLs when Trivy does not provide them, or to refactor unrelated scan-conversion logic beyond preserving existing `Identifier.PURL` data.
**approach_lock** (confidence: 0.78):
  This matches the circular test-patch dependency subtype of approach_lock. A solver can satisfy the stated requirements by implementing the required changes in `contrib/trivy/pkg/converter.go` and `models/library.go` (hunks 0-2), yet still fail benchmark tests if those tests also depend on the unrelated PURL-generation logic added in hunks 3-4. That means the tests are not measuring only the requested behavior; they appear to require broader, out-of-scope code to pass, rejecting an otherwise valid minimal solution.
  - Cross-reference analysis reports circular dependencies: `TestLibraryScanners_Find` → UNRELATED hunks [3, 4] (conf=0.90), repeated across multiple entries.
  - Cross-reference analysis also reports `TestParse`, `TestParseError`, and `TestLibraryScanners_Find/{single_file,multi_file,miss}` → UNRELATED hunk [4] (conf=0.80).
  - Hunks 3 and 4 are explicitly classified UNRELATED because they generate/synthesize PURLs in `scanner/library.go`, while the problem only asks to preserve Trivy's existing `Identifier.PURL` during conversion.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.87)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, searched the codebase for the relevant model and conversion paths, inspected Trivy dependency types to verify where PURL lives, formed the hypothesis that `models.Library` lacked a propagated PURL field, then implemented propagation in the relevant conversion paths and validated via build/testing attempts.
- **Behavior:** Methodical, code-driven problem solving with repository exploration, dependency inspection, and iterative validation; behavior is consistent with a genuine solution.

> The trajectory looks like a legitimate debugging and implementation session rather than benchmark leakage. The agent did not jump straight to a specific gold-style edit; instead it explored the repository structure, searched for converter and Trivy-related code, inspected the `models` definition, examined `contrib/trivy/pkg/converter.go`, reviewed `scanner/library.go`, checked `go.mod` to understand the pinned Trivy version, and then dug into the vendored/module definitions for Trivy package typ

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_future-architect__vuls-ca3f6b1dbf2cd24d1537bfda43e788443ce03a0c`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Add repository-aware Amazon Linux 2 scanning so packages from the Extra Repository receive the correct advisories, and update Oracle Linux 6/7/8/9 EOL reporting to the specified extended support dates.
**Severity:** SEVERE
**Labels:** `wide_tests`, `test_mutation`, `scope_creep`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 27 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 2 UNRELATED tests

### Label Analysis

**wide_tests** (confidence: 0.94):
  The F2P suite checks lifecycle behavior outside the stated task scope. The task asks for Amazon Linux 2 repository-aware advisory handling plus Oracle Linux 6/7/8/9 EOL updates, but the tests also exercise Amazon Linux 2024 and Oracle Linux 10 lifecycle behavior. That is classic wide scope: extra test cases/assertions beyond the acceptance criteria.
  - F2P analysis marks `TestEOL_IsStandardSupportEnded` case `amazon linux 2024 not found` as UNRELATED (conf=0.98).
  - F2P analysis says the same modified pre-existing `TestEOL_IsStandardSupportEnded` adds an off-topic `Oracle Linux 10 not-found` case.
  - Requirements/out-of-scope limit lifecycle-date work to Oracle Linux 6/7/8/9 and explicitly exclude `changes to other operating systems' lifecycle dates besides Oracle Linux 6/7/8/9`.
**test_mutation** (confidence: 0.92):
  A pre-existing test was changed to assert behavior not described by the task. The mutation is not just updating expected values for the requested fix; it extends the test into off-topic lifecycle cases. That matches the definition of test_mutation.
  - F2P analysis explicitly reports `Has modified tests: True`.
  - `TestEOL_IsStandardSupportEnded` is identified as a `[MODIFIED pre-existing test, MISALIGNED changes]`.
  - The modified test adds off-scope cases such as `Oracle Linux 10 not-found`, and the same test family includes the unrelated `amazon linux 2024 not found` case.
**scope_creep** (confidence: 0.97):
  The gold patch includes a behavioral change outside the requested work: Amazon Linux lifecycle handling in `GetEOL`. This is not ancillary build churn or refactoring; it changes observable behavior in an area the task explicitly excludes, so it is scope creep.
  - Gold patch hunk 0 in `config/os.go` is labeled UNRELATED (conf=0.99).
  - Hunk 0 changes Amazon Linux lifecycle dates in `GetEOL`.
  - The task specification only requires Oracle Linux 6/7/8/9 EOL updates; intent extraction marks other OS lifecycle-date changes as out of scope.
**approach_lock** (confidence: 0.61):
  This looks like the circular test-patch-dependency subtype of approach_lock. Passing the F2P suite appears to require reproducing unrelated lifecycle behavior bundled into the gold patch, not just solving the described task. That means valid task-focused solutions can be rejected because the tests demand out-of-scope patch behavior.
  - The patch contains unrelated behavioral hunk 0 in `config/os.go` changing Amazon Linux lifecycle dates.
  - F2P includes unrelated `TestEOL_IsStandardSupportEnded` coverage for `amazon linux 2024 not found` and misaligned Oracle Linux 10 behavior.
  - The task does not ask for those lifecycle behaviors, so a solver could satisfy the stated Amazon Linux 2 repository-scanning and Oracle 6/7/8/9 requirements while still failing these EOL tests.
**weak_coverage** (confidence: 0.74):
  Some stated acceptance criteria are only indirectly tested or not directly exercised. In particular, the exact Oracle EOL dates are not clearly asserted, and `scanInstalledPackages` coverage is not evident from the F2P list. That means a partial fix could pass, making the task easier and less complete as a benchmark.
  - Acceptance criteria AC1-4 require exact extended-support end dates for Oracle Linux 6, 7, 8, and 9.
  - F2P analysis describes the EOL tests as only TANGENTIAL: Oracle Linux 6 is checked via support status at a 2021 date, and Oracle Linux 9 via a supported/not-supported style case, rather than exact June 2024 / July 2029 / July 2032 / June 2032 date assertions.
  - No listed F2P test explicitly targets Oracle Linux 7 or 8 exact-date behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.62)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The prompt pointed to specific files and functions, the agent explored those areas plus adjacent scanner/OVAL/model code to understand data flow, formed the correct hypothesis that Amazon Linux 2 needed repository-aware package parsing and OVAL matching, began implementing those changes, but stalled before producing a working patch or test-validated result.
- **Behavior:** Genuine exploratory debugging with correct problem localization and implementation intent, but incomplete / unresolved execution and no leakage signals.

> The trajectory looks like genuine, problem-directed work rather than leakage. The agent did not jump straight to a memorized fix; it systematically inspected the files named in the prompt, then broadened to related code paths such as constants, scanner logic, models, repoquery handling, and command execution flow. Its planned changes line up with the stated requirements: adding EOL data, extending the OVAL request with repository information, matching advisories by repository, adding repoquery p

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_future-architect__vuls-e1df74cbc1a1d1889428b3333a3b2405c4651993`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Fix Amazon Linux version parsing so that Amazon Linux 2023 release strings in `major.minor.patch` format are interpreted as their major version only.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 4 of 7 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The benchmark patch goes beyond the bug report. The problem asks for one parser behavior change in config/os.go: convert Amazon Linux strings like 2023.3.20240312 to the major version 2023, while preserving single-component inputs. That is fully addressed by hunk 0. The additional changes in oval/oval.go and oval/util.go alter downstream lookup and freshness behavior for OVAL data. Those are substantive behavioral modifications outside the stated acceptance criteria, so the task contains patch-level scope expansion.
  - Gold patch analysis marks excess=True and identifies 4 behavioral UNRELATED hunks: hunk 1 and hunk 2 in oval/oval.go, and hunk 3 and hunk 4 in oval/util.go.
  - Hunk 0 in config/os.go is the only REQUIRED change and already implements the stated contract for getAmazonLinuxVersion.
  - The task scope is explicitly limited to parsing Amazon Linux release strings in getAmazonLinuxVersion; the intent extraction says changes to 'vulnerability matching logic beyond providing the correct parsed version' are out of scope.
**approach_lock** (confidence: 0.58):
  There is evidence of the circular test-patch dependency subtype of approach_lock. If the F2P test truly depends on hunks 1-4, then an agent could implement the required parser fix correctly in getAmazonLinuxVersion and still fail because the tests also require unrelated downstream OVAL-normalization changes. That would reject a valid minimal solution. Confidence is moderate rather than high because the visible test intent is aligned to the parser bug, and the dependency signal comes from cross-reference analysis rather than explicit off-topic assertions.
  - Cross-reference analysis reports a circular dependency: Test 'Test_getAmazonLinuxVersion/2023.3.20240312' → UNRELATED hunks [1, 2, 3, 4] with confidence 0.95.
  - The same analysis explicitly calls this 'a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for.'
  - Hunk 0 alone is judged REQUIRED for the acceptance criteria, while hunks 1-4 are judged UNRELATED.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.80)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The issue description's references to vulnerability checks and warnings led the agent to inspect OVAL release normalization first; code search revealed existing Amazon normalization in some OVAL helpers, which motivated extending that logic to missing call sites; later, an EOL-related search surfaced `getAmazonLinuxVersion`, and the agent recognized that function also needed the same major-version extraction behavior.
- **Behavior:** Careful, code-driven debugging with some scope creep into related OVAL handling, but overall consistent with genuine problem-solving rather than benchmark leakage.

> The trajectory looks like legitimate debugging rather than leakage. The agent starts by exploring the repository and following the issue narrative into the OVAL path, because the problem statement mentions vulnerability-check mismatches and warnings. It inspects multiple files, compares behavior across codepaths, notices that Amazon Linux normalization already exists in some OVAL utility functions but not in others, and formulates a concrete hypothesis from that inconsistency. It then creates a 

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 4 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_future-architect__vuls-fd18df1dd4e4360f8932bc4b894bd8b40d654e7c`

### Task Context

**Repository:** `future-architect/vuls` (version )
**Core requirement:** Add support for carrying the OS version from Trivy scan results into the main scan metadata, and update Trivy-related package-CVE handling to use that explicit metadata instead of the `Optional` map.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `unclear_spec`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 6 of 11 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.43)

### Label Analysis

**approach_lock** (confidence: 0.89):
  This matches the circular test-patch dependency subtype of approach_lock. The benchmark's F2P test is not satisfied solely by implementing the requested behavior in `setScanResultMeta`, `isPkgCvesDetactable`, `DetectPkgCves`, and `reuseScannedCves`; it also depends on unrelated dependency-state changes. That means a valid alternative solution that fulfills the specification without those unrelated hunks could still fail the test suite.
  - Cross-reference analysis reports a circular dependency: F2P test `TestParse` exercises UNRELATED hunks [5, 9, 10] with conf=0.95.
  - Hunk 5 (`go.mod`) is classified UNRELATED because it upgrades dependencies unrelated to the requested Trivy metadata/detector behavior.
  - Hunks 9 and 10 (`go.sum`) are also classified UNRELATED dependency/checksum changes, yet `TestParse` depends on them.
**scope_creep** (confidence: 0.78):
  The gold patch goes beyond the stated task. The requested work is confined to carrying Trivy OS version metadata and adjusting Trivy-related CVE detection/reuse logic, but the patch also includes unrelated dependency upgrades in `go.mod`/`go.sum`. Those are outside the acceptance criteria and constitute patch-level scope expansion.
  - Gold patch analysis: 6 hunks are classified UNRELATED.
  - Hunk 5 modifies `go.mod` with version bumps for dependencies outside the feature request.
  - Hunks 6-10 modify `go.sum` for those dependency changes; the problem scope is parser/detector behavior, not dependency refreshes.
**unclear_spec** (confidence: 0.56):
  The specification is somewhat internally misleading. The high-level description suggests that adding OS version support should help downstream OVAL/GOST detection run correctly, but the detailed requirements simultaneously instruct the implementation to block OVAL/GOST when the result is marked as Trivy-scanned. That tension leaves room for incompatible interpretations of the intended detection flow.
  - Problem statement expected behavior: storing OS version 'enables downstream CVE detectors (such as OVAL or GOST) to function accurately based on full OS metadata when available.'
  - Requirements also say `isPkgCvesDetactable` must return `false` when results are 'scanned by Trivy', and `DetectPkgCves` should invoke OVAL/GOST only when that function returns `true`.
  - Intent extraction reports ambiguity score 0.43.
**weak_coverage** (confidence: 0.87):
  The tests under-cover the stated requirements. A large portion of the acceptance criteria concerns detector behavior and negative cases (`Family` missing, OS version missing, no packages, Trivy/`ScannedBy`, FreeBSD, Raspbian, pseudo types, error propagation, and reuse logic), but the F2P suite appears to exercise only the parsing path. Because partial implementations could pass, the benchmark score would overestimate task completion.
  - F2P analysis shows only 1 F2P test: `TestParse`.
  - Acceptance criteria span many additional behaviors beyond parsing, including `isPkgCvesDetactable` branches, `DetectPkgCves` gating/error handling, and `reuseScannedCves` using `ScannedBy` (criteria 6-15).
  - Hunk 3 analysis notes that the gold patch 'may not cover every enumerated case perfectly,' yet the F2P suite still contains only the single aligned test.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.63)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement pointed the agent to the parser and detector files; the agent then explored surrounding code and tests, confirmed the Trivy metadata layout, implemented the parser-side metadata extraction, and then got bogged down reconciling detector behavior for Trivy results versus reused scanned CVEs, leading to an unfinished or mismatched final state.
- **Behavior:** Methodical, exploratory, and genuine; partially implemented the right idea but appears to have stalled or misaligned on the full Trivy-handling details.

> This looks like a genuine but incomplete attempt rather than leakage. The agent did not jump straight to a memorized fix: it systematically inspected the parser, detector logic, models, constants, tests, JSON fixtures, and even the upstream Trivy type structure before coding. It explicitly reasoned from the observed report schema that `report.Metadata.OS.Name` should populate `Release`, and it recognized the `:latest` behavior for untagged container images. It also engaged with the detector-side

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 6 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-005dcb16bacc6a5d5890c4cd302ccfd4298e275d-vee9b09fb20c43af7e520f57e9239bbcf46b7113d`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Replace server-side SQL parsing of PostgreSQL wal2json replication output with client-side parsing that correctly turns public.kv change messages into Teleport backend events.
**Severity:** SEVERE
**Labels:** `scope_creep`, `weak_coverage`, `wide_tests`

### Contamination Signals

- **SCOPE_CREEP:** 10 of 14 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 1 UNRELATED tests

### Label Analysis

**scope_creep** (confidence: 0.96):
  The required fix is narrowly about moving wal2json parsing to client-side Go and deriving backend events from replication messages. That behavior is implemented by required hunks 2 and 13. In addition, the patch changes many ordinary SQL read/write code paths to normalize nil byte slices via nonNil. Those are behavioral changes in unrelated backend operations, not ancillary imports or refactors. Because they introduce extra behavior outside the stated wal2json parsing task, this is clear scope expansion.
  - Gold patch analysis marks 10 hunks as UNRELATED: hunks 3-11 in lib/backend/pgbk/pgbk.go change Create/Put/CompareAndSwap/Update/Get/GetRange/Delete/DeleteRange/KeepAlive to wrap parameters with nonNil.
  - Hunk 12 in lib/backend/pgbk/utils.go adds the nonNil helper solely to support those unrelated CRUD/query-path changes.
  - The task scope is wal2json change-feed parsing and event generation; the out-of-scope section explicitly excludes unrelated PostgreSQL backend changes.
**weak_coverage** (confidence: 0.78):
  The specification is fairly detailed, but the F2P tests do not appear to cover all of it. In particular, they seem to focus on wal2jsonMessage.Events behavior and leave the client-side pg_logical_slot_get_changes integration path untested. Several required action/error branches and typed-conversion branches are also not evidenced in the test summary. That means an agent could implement only part of the requested behavior and still pass, which is a classic weak-coverage issue.
  - F2P analysis shows only one ALIGNED test with substance: TestMessage. The other test, TestColumn, is marked UNRELATED and 'contains no assertions or calls into the wal2json column-parsing logic.'
  - Acceptance criterion 1 requires consuming raw wal2json JSON from pg_logical_slot_get_changes in client-side code; the core integration change is required hunk 2 in lib/backend/pgbk/background.go, but the test summary says TestMessage directly exercises wal2jsonMessage.Events rather than the polling/integration path.
  - The TestMessage coverage summary mentions insert/update/delete handling, missing-column errors, timestamptz type validation, NULL expires handling, identity fallback, changed-key updates, and delete-from-identity, but does not mention testing action 'T', skipping 'B'/'C'/'M', or the full bytea/uuid conversion and 'parsing [type]' failure branches described in the requirements.
**wide_tests** (confidence: 0.49):
  At least part of TestMessage exercises behavior for non-kv tables being ignored. The task specification is about public.kv handling and does not state what must happen for other tables. So that portion of the F2P test reaches beyond the stated acceptance criteria. This looks like a small extra-assertion form of wide_tests rather than the main substance of the task.
  - F2P analysis for TestMessage states: 'It also includes a small amount of extra checking for non-kv tables being ignored, which is not explicitly called out.'
  - The requirements and intent focus on interpreting messages for the public.kv table; the out-of-scope section says support for arbitrary tables or schemas beyond public.kv is not requested.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.78)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the pgbk backend code, identified background.go as the change-feed entry point, inferred that SQL-side wal2json extraction needed to become Go-side JSON parsing, implemented a parser/data model plus event conversion, updated DB byte handling utilities, then built and iterated based on self-testing.
- **Behavior:** Exploratory and implementation-driven; likely understood the real task and attempted a substantive fix, but missed enough hidden details to fail evaluation.

> The trajectory shows a mostly genuine debugging and implementation process rather than obvious benchmark leakage. The agent began by exploring the repository, locating the PostgreSQL backend, reading relevant files, identifying where change-feed logic lived, and reviewing backend item structures before proposing a fix. It then articulated the core task correctly: move wal2json parsing from SQL into Go and emit backend events from parsed messages. It also implemented supporting utility changes an

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 10 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-5dca072bb4301f4579a15364fcf37cc0c39f7f6c`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Make the Kubernetes proxy's mTLS handshake robust to deployments with many trusted clusters by avoiding oversized advertised client CA lists while preserving normal handshake behavior when the full CA list fits.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 4 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 1 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.84):
  This is a circular test-patch dependency. Multiple F2P tests are reported to exercise hunk 0, even though hunk 0 is explicitly out of scope for the bug being fixed. That means an agent could implement the requested behavior correctlyreturning a per-connection TLS config, advertising all CAs when they fit, reducing to local Host CAs when they do not, and preserving other TLS settingsyet still fail because the tests also depend on unrelated certificate SAN-generation changes. That matches the approach_lock subtype where tests require unrelated patch hunks rather than purely checking the requested observable behavior.
  - CROSS-REFERENCE: Test 'TestMTLSClientCAs/1_CA'  UNRELATED hunk [0] (conf=0.80).
  - CROSS-REFERENCE: Test 'TestMTLSClientCAs/100_CAs'  UNRELATED hunk [0] (conf=0.80).
  - CROSS-REFERENCE: Test 'TestMTLSClientCAs/1000_CAs'  UNRELATED hunk [0] (conf=0.80).
**scope_creep** (confidence: 0.90):
  The gold patch includes a behavioral change beyond the issue scope. The task asks for Kubernetes proxy mTLS robustness when many trusted-cluster CAs exist, specifically by selecting which client CA subjects are advertised per connection. Changing auth key-generation SAN contents for proxy/kube certificates is a separate behavior change and is not required by the stated acceptance criteria. Because this is behavioral and not merely ancillary cleanup, it is scope_creep.
  - GOLD PATCH Hunk 0 [lib/auth/auth.go] is classified UNRELATED (conf=0.87).
  - Hunk 0 changes server certificate DNS SAN generation for RoleProxy and RoleKube in auth key generation.
  - Problem statement and requirements only describe fixing oversized acceptable-CA advertisement in the Kubernetes proxy mTLS handshake via per-connection ClientCAs selection.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.92)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored kube proxy code, found similar TLS CA-size handling in auth middleware, inferred the kube proxy lacked the same protection, implemented that logic in the proxy path, validated the idea with local simulations/compilation, but likely failed evaluation because it did not also make the unrelated auth.go change required by a contaminated test.
- **Behavior:** A genuine debugger/implementer that found the right core cause and pursued a sensible fix, but likely failed due to benchmark scope creep rather than lack of intent or leakage.

> The trajectory looks like legitimate debugging and code adaptation, not leakage. The agent began by exploring the repository structure, looking for the kube proxy implementation and related tests, then inspected the auth package and discovered an existing analogous safeguard in auth middleware. From there it formed a concrete hypothesis: the kube proxy was constructing a client CA pool without the TLS-size guard already used elsewhere. It articulated the correct RFC-based reasoning about the 2-b

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-73cc189b0e9636d418c4470ecce0d9af5dae2f02-vee9b09fb20c43af7e520f57e9239bbcf46b7113d`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Add support for carrying GCP service account selection and allowed GCP service account lists in Teleport identities by encoding and decoding them through certificate subject ASN.1 extensions.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 8 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.93):
  The patch includes behavioral changes outside the requested feature. The task asks for carrying GCP service account data through Teleport identity subject encoding/decoding, with exact OIDs and round-trip preservation, plus non-regression of existing subject extensions. Updating event/audit metadata paths such as GetEventIdentity() and GetUserMetadata() is not part of that contract. Because these are behavioral UNRELATED hunks rather than ancillary edits, this is clear scope expansion in the gold patch.
  - Hunk 2 in lib/tlsca/ca.go is marked UNRELATED (conf=0.90): it updates GetEventIdentity() to copy the new GCP app field into audit/event structures.
  - Hunk 3 in lib/tlsca/ca.go is marked UNRELATED (conf=0.88): it propagates Identity.GCPServiceAccounts into the events.Identity returned by GetEventIdentity().
  - Hunk 7 in lib/tlsca/ca.go is marked UNRELATED (conf=0.89): it adds GCPServiceAccount to GetUserMetadata() event/audit metadata.
**approach_lock** (confidence: 0.75):
  This matches the circular test-patch dependency subtype of approach_lock. An agent could implement the requested feature correctly by adding the new fields and updating Subject()/FromSubject() so GCP values round-trip, while leaving unrelated event/audit metadata code untouched. If the F2P suite still depends on those unrelated hunks to satisfy the device_extensions test path, then the tests are effectively requiring extra implementation details outside the problem statement. That creates false negatives for otherwise valid solutions.
  - Cross-reference analysis reports a circular dependency: Test 'TestIdentity_ToFromSubject/device_extensions' requires UNRELATED hunks [3, 7] (conf=0.90).
  - Hunk 3 is classified UNRELATED because it changes event identity serialization rather than Subject()/FromSubject() GCP extension handling.
  - Hunk 7 is classified UNRELATED because it changes GetUserMetadata() event/audit metadata rather than the requested certificate subject ASN.1 round-trip behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** TEST_AWARE (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent used the problem statement to focus on Teleport's certificate identity code, explored analogous AWS/Azure implementations, discovered that event/protobuf definitions already had GCP-related fields, and then mirrored the existing encode/decode pattern into `tlsca`. Along the way, it showed awareness of the hidden test name `TestGCPExtensions`, suggesting benchmark contamination influenced the trajectory even though the implementation path itself was technically grounded.
- **Behavior:** Mostly competent, repository-grounded implementation work, but contaminated by awareness of a hidden test name.

> The trajectory shows substantial legitimate debugging and code comprehension: the agent identified `lib/tlsca/ca.go` as the likely implementation point from the feature request, searched for existing AWS/Azure patterns, inspected ASN.1 OID conventions, checked `Subject()`/`FromSubject()`, and traced related event/protobuf structs before outlining a concrete implementation plan. That is consistent with real task-specific reasoning rather than a direct jump to a memorized patch. However, there is 

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-8302d467d160f869b77184e262adbe2fbc95d9ba-vce94f93ad1030e3136852817f2423c1b3ac37bc4`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Enable a working macOS Touch ID WebAuthn registration and login flow when Touch ID is available, and expose a public diagnostics API that reports detailed Touch ID availability checks.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 9 of 19 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The gold patch expands well beyond the requested Touch ID WebAuthn registration/login behavior and public diagnostics API. It includes platform-compatibility changes, new behavior for credential-management APIs, and a CLI diagnostics surface that the task did not ask for. Because these are behavioral or externally visible changes rather than mere ancillary imports/build plumbing, this is clear scope creep.
  - Gold patch analysis marks 9 hunks as UNRELATED.
  - UNRELATED hunks 0 and 1 change build.assets macOS Info.plist minimum OS version from 11.0 to 10.12, which is outside the Register/Login/Diag requirements.
  - UNRELATED hunks 7 and 8 change ListCredentials and DeleteCredential behavior to return availability-related errors, but those management APIs are not mentioned in the problem statement or acceptance criteria.
**approach_lock** (confidence: 0.63):
  This matches the circular test-patch dependency subtype of approach_lock. If the benchmark's fail-to-pass test really requires unrelated hunks to pass, then an agent could implement the requested Touch ID registration/login and diagnostics behavior correctly yet still fail because it did not reproduce extra, out-of-scope changes from the gold patch. Confidence is moderate rather than maximal because the dependency is inferred by the cross-reference stage rather than shown by explicit test assertions.
  - Cross-reference analysis reports a circular dependency: TestRegisterAndLogin  UNRELATED hunks [0, 7, 8, 15, 16, 18] with confidence 0.95.
  - The linked hunks include out-of-scope behavior such as ListCredentials/DeleteCredential changes (hunks 7-8) and tsh CLI wiring (hunks 15-18), none of which are part of the stated Register/Login/Diag acceptance criteria.
  - F2P test analysis says the single F2P test is otherwise ALIGNED, so the contamination signal is specifically the test's dependence on unrelated patch hunks rather than explicit extra assertions.
**weak_coverage** (confidence: 0.56):
  Part of the stated task is the new public diagnostics API, but the fail-to-pass coverage described here appears focused only on the registration/login flow. That means a partial fix that gets Register/Login working while omitting or underimplementing the diagnostics contract could plausibly still pass the F2P portion of the benchmark. This makes the task easier to game and indicates incomplete coverage of the full specification.
  - Acceptance criteria 9 and 10 require a public DiagResult struct and a public Diag() function exposing detailed diagnostic fields.
  - F2P test analysis lists only one fail-to-pass test: TestRegisterAndLogin.
  - No F2P test is identified for the new Diag/DiagResult public API or for the individual diagnostic fields HasCompileSupport, HasSignature, HasEntitlements, PassedLAPolicyTest, PassedSecureEnclaveTest, and IsAvailable.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.76)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the repository, inspected Touch ID API and platform-specific files, checked tsh command handling, consulted an in-repo RFD/PR-related document for requirements, then began implementing a diagnostics-based availability redesign and CLI updates. Progress stopped before a completed, validated patch was produced, likely exacerbated by inability to reproduce on Linux.
- **Behavior:** Genuine exploratory debugging with a mostly correct implementation plan, partial alignment to the real fix, but incomplete execution and no strong leakage signals.

> The trajectory looks like legitimate, problem-directed exploration rather than benchmark leakage. The agent started by locating the Touch ID implementation, Darwin/non-Darwin variants, and tsh command integration, then formed a concrete hypothesis about availability checks, diagnostics, and CLI wiring. It did not jump straight to a single target file, did not install packages, did not reference hidden F2P test details, and did not copy code from elsewhere. Its planned changes substantially overl

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 9 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-89f0432ad5dc70f1f6a30ec3a8363d548371a718`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Add a new public utils.ReadAtMost helper that reads from an io.Reader with a byte limit and signals when the limit is reached, so callers can avoid unbounded body reads.
**Severity:** SEVERE
**Labels:** `scope_creep`, `wide_tests`

### Contamination Signals

- **SCOPE_CREEP:** 5 of 9 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.95):
  The gold patch expands beyond the requested task. The stated requirements only ask for a new public helper, ReadAtMost, with a defined contract. The patch additionally introduces concrete size-policy constants and changes multiple unrelated HTTP request/response handling paths to enforce those limits. Those call-site migrations are explicitly identified as out of scope in the task analysis, so this is classic patch-level scope expansion rather than necessary implementation detail.
  - Hunk 0 [constants.go] is marked UNRELATED: it adds concrete HTTP request/response body size constants even though the out-of-scope note says the specification 'does not define particular limit values for HTTP request or response bodies.'
  - Hunks 2, 3, 5, and 7 are marked UNRELATED: they retrofit specific internal HTTP call sites in lib/auth/github.go, lib/auth/oidc.go, lib/httplib/httplib.go, and lib/services/saml.go to use utils.ReadAtMost with concrete limits.
  - The acceptance criteria are limited to adding public utils.ReadAtMost in lib/utils/utils.go with the specified signature and error behavior; Hunk 8 is the only REQUIRED hunk.
**wide_tests** (confidence: 0.62):
  The test suite is mostly aligned, but it includes at least one extra/misaligned expectation for the exact-fit case. Under the written spec, if the full content fits within the limit, the function should return all bytes without error; a content length exactly equal to the limit fits within the limit. The F2P test instead expects ErrLimitReached for that case. That means the tests go beyond, and in this instance contradict, the stated acceptance criteria for an otherwise in-scope helper. This fits the 'extra assertions in otherwise-aligned tests' form of wide_tests.
  - F2P analysis for TestReadAtMost says: 'One expectation goes beyond the stated contract: for limit == len("hello"), it expects ErrLimitReached even though the acceptance criteria only require that error when content exceeds the limit and otherwise say full content should be returned without error.'
  - Requirement text: 'When the read reaches the limit before completing the content, ReadAtMost must return the bytes read up to that point and the error ErrLimitReached.'
  - Requirement text: 'When the limit allows reading all available content, ReadAtMost must return all bytes without error.'

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.82)
- **Gold patch similarity:** 0.0%
- **Causal chain:** Problem statement led the agent to search for unbounded HTTP body reads; it inspected utils and HTTP helper code, searched for `ioutil.ReadAll` in HTTP contexts, inferred the need for a bounded read helper plus constants/error, started updating multiple call sites, then hit cleanup/build issues before completing the task.
- **Behavior:** A genuine, exploratory agent that identified the right abstraction and call-site pattern, began implementing a real fix, and iterated on compilation issues, but did not finish successfully.

> The trajectory shows a legitimate debugging and implementation process rather than benchmark leakage. The agent began by restating the task, explored the repository structure, inspected `lib/utils/utils.go` and `lib/httplib/httplib.go`, searched for `ioutil.ReadAll` usages, and explicitly distinguished unrelated filesystem reads from relevant HTTP request/response body reads. It then formulated a concrete plan: add `utils.ReadAtMost`, introduce request/response size constants, add `ErrLimitReach

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 5 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-96019ce0be7a2c8e36363f359eb7c943b41dde70`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Fix Kubernetes proxy authentication/context-setup error handling so `authenticate` only classifies true authorization/access failures as `AccessDenied`, while preserving non-auth failures as non-access-denied errors.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 5 of 9 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.92):
  This task shows the circular test-patch dependency subtype of approach_lock. The problem asks for correct classification of `authenticate` errors (plus the two `httplib` wrapper APIs), but at least two F2P tests exercise unrelated forwarder/error-formatting hunks [4,5,7,8]. That means an agent could implement the stated bug fix correctly and still fail because the tests run through extra proxy-response machinery the problem does not require. The lock is not merely strictness of assertions; it is that passing the tests depends on behavioral patch code explicitly judged UNRELATED to the specification.
  - Cross-reference analysis reports circular dependencies: `TestAuthenticate/local_user_and_remote_cluster,_no_tunnel` → UNRELATED hunks [4, 5, 7, 8] (conf=0.95).
  - Cross-reference analysis reports circular dependencies: `TestAuthenticate/unknown_kubernetes_cluster_in_local_cluster` → UNRELATED hunks [4, 5, 7, 8] (conf=0.95).
  - Hunk 4 is UNRELATED: it rewires kube proxy handlers to use new error-writer-aware wrappers with a custom formatter, which the analysis says is not required by acceptance criteria 1-5.
**scope_creep** (confidence: 0.97):
  The gold patch clearly expands beyond the requested task. Only hunk 3 is the core authenticate fix, and hunks 0-1 implement the specified `httplib` APIs. In contrast, hunks 4-8 introduce additional proxy error-formatting and forwarding behavior not asked for in the problem statement or requirements. These are behavioral changes, not ancillary imports or refactors, so they are genuine scope creep.
  - Gold patch analysis: `Has excess: True` with 5 UNRELATED hunks.
  - Hunk 4 [lib/kube/proxy/forwarder.go] is UNRELATED: switches kube proxy handlers to use the new wrappers/custom formatter, not required by acceptance criteria 1-5.
  - Hunk 5 is UNRELATED: adds Kubernetes-specific response-error serialization helpers and emits HTTP 500 with embedded status codes, which the problem does not request.
**weak_coverage** (confidence: 0.76):
  The benchmark specification includes more than the authenticate bug: it also requires two `httplib` wrapper functions with specific error-writer behavior. But the fail-to-pass tests appear to cover only the authenticate/access-denied classification path. Because required behaviors in hunks 0 and 1 are not exercised by F2P tests, a partial solution that fixes `authenticate` while omitting or misimplementing the wrapper APIs could still pass the benchmark. That makes coverage incomplete relative to the stated acceptance criteria.
  - Acceptance criteria 4 and 5 explicitly require `httplib.MakeHandlerWithErrorWriter` and `httplib.MakeStdHandlerWithErrorWriter` behavior.
  - Hunks 0 and 1 are marked REQUIRED because they implement those wrapper APIs.
  - F2P test analysis lists 6 tests, all under `TestAuthenticate`; no F2P test is reported for `MakeHandlerWithErrorWriter` or `MakeStdHandlerWithErrorWriter`.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.82)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the proxy stack, noticed `trace.WriteError` produced plain JSON, inferred that Kubernetes error responses needed `Status` objects and custom error writers, and then started modifying `httplib`/forwarder plumbing instead of focusing on `authenticate`'s access-denied classification logic.
- **Behavior:** Genuine repo exploration followed by a strong but misplaced hypothesis that chased scope-crept proxy response-formatting changes rather than the benchmark's actual `authenticate` error-classification bug.

> The trajectory shows real exploration rather than a direct jump to the exact fix: the agent inspected Kubernetes proxy code, the forwarder, httplib, and trace error handling before forming a hypothesis. That argues against a clean gold-patch leak or test-aware behavior. However, the agent then latched onto a broader and largely different problem than the benchmark's core requirement. Instead of centering on `authenticate` and the distinction between `trace.IsAccessDenied(err)` and non-auth error

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 5 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-af5e2517de7d18406b614e413aca61c319312171-vee9b09fb20c43af7e520f57e9239bbcf46b7113d`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Add support for inbound SSH connections that start with a `Teleport-Proxy` metadata prefix so they are treated as valid SSH traffic and can carry a forwarded client address.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `test_mutation`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 7 of 10 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 25 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.88):
  This task shows the circular test-patch dependency subtype of approach_lock. The requested behavior is narrowly about recognizing Teleport-Proxy-prefixed SSH traffic and exposing ClientAddr via RemoteAddr(), which the patch analysis says is implemented by hunks 2-3. But the cross-reference analysis says the aligned F2P test also depends on unrelated hunks in service/server code. That means an agent could implement the specified behavior correctly, using a minimal or alternative solution focused on protocol detection and RemoteAddr handling, yet still fail because the test path touches extra, out-of-scope changes. That is not just broader scope; it rejects otherwise valid solutions unless they reproduce unrelated parts of the gold patch.
  - Cross-reference analysis reports a circular dependency: Test 'TestMux/SSHProxyHelloSignature'  UNRELATED hunks [0, 6, 8, 9] (conf=0.95), with the note: 'This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for.'
  - The only REQUIRED implementation hunks are hunk 2 and hunk 3 in lib/multiplexer/multiplexer.go, which add Teleport-Proxy recognition and classify it as ProtoSSH.
  - UNRELATED hunks exercised by the aligned test include hunk 6 [lib/service/service.go] (mux.Serve error logging) and hunk 9 [lib/sshutils/server.go] (suppress warning logs for EOF during SSH handshake), neither of which is part of acceptance criteria 1-5.
**wide_tests** (confidence: 0.94):
  The F2P suite goes far beyond the stated task. The issue is specifically about SSH multiplexer support for Teleport-Proxy-prefixed SSH connections and optional ClientAddr propagation. Yet most F2P coverage targets unrelated HTTP mux behavior, HTTP RemoteAddr behavior, and PROXY protocol cases. Those are extra behaviors not described in the problem statement, requirements, or interface, so this is a clear wide_tests contamination. Even if some of those checks live inside a broader TestMux function, they still expand the pass condition beyond the requested feature.
  - F2P TEST ANALYSIS: 27 tests total, with only 2 ALIGNED and 25 UNRELATED.
  - Multiple modified 'TestMux' entries are marked UNRELATED because they test HTTP behavior, e.g. 'The handler writes HTTP RemoteAddr' and 'HTTP server handler returning a fixed backend response'.
  - One modified 'TestMux' entry is marked UNRELATED because it uses 'bytes shown are for a PROXY protocol v2 header', while the intent extraction says support for 'other prefixed protocols' and 'non-SSH traffic handling' is out of scope.
**test_mutation** (confidence: 0.92):
  This is a textbook case of test_mutation. A pre-existing test function, TestMux, was modified, and the analysis repeatedly marks those modifications as both pre-existing and misaligned. The added/changed assertions do not merely check the requested Teleport-Proxy SSH feature; they assert unrelated HTTP and PROXY-protocol behavior. That silently broadens the benchmark using an existing test file/function, which makes the task look more legitimate than it is while actually testing behavior outside the issue.
  - F2P TEST ANALYSIS says 'Has modified tests: True'.
  - Many entries are explicitly labeled: Test 'TestMux': UNRELATED [MODIFIED pre-existing test, MISALIGNED changes].
  - The misaligned modified checks include HTTP RemoteAddr behavior and PROXY protocol v2 header handling, which are not part of acceptance criteria 1-5.
**scope_creep** (confidence: 0.78):
  The gold patch includes behavior beyond the issue's scope. The requested change is limited to Teleport-Proxy-prefixed SSH detection/routing and ClientAddr exposure. In addition, the patch alters service listener setup under Proxy Protocol and changes multiple logging/error-handling paths in service.go and server.go. Those are not ancillary compile fixes like imports or comments; they are extra operational behavior changes outside the stated feature. That makes the patch broader than the task specification, so scope_creep applies.
  - GOLD PATCH ANALYSIS: 'Has excess: True' with 7 UNRELATED hunks.
  - Hunk 4 [lib/service/service.go] changes listener setup so a dedicated SSH listener is wrapped in a multiplexer when Proxy Protocol is enabled; the analysis says this is not part of acceptance criteria 1-5.
  - Hunks 5-7 [lib/service/service.go] add mux.Serve error-logging behavior in multiple branches, and hunk 9 [lib/sshutils/server.go] suppresses warning logs for EOF during SSH handshake; all are marked UNRELATED.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.96)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent began by locating likely protocol-detection and listener setup code, traced the SSH proxy/server initialization path, but stopped before proposing or implementing any concrete changes.
- **Behavior:** Legitimate early-stage repository exploration with no leakage signals, but the agent failed to advance from code reading to an implemented solution.

> The trajectory shows ordinary initial codebase exploration, not leakage. The agent read the problem, then progressively inspected the multiplexer, searched for `ProxyHelloSignature`, located its definition, and moved on to proxy/service listener setup and the SSH server construction path. This is exactly the kind of exploratory behavior expected from a model trying to understand where protocol detection and connection wrapping happen. There are no signs that it jumped straight to the exact gold 

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 7 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-b5d8169fc0a5e43fee2616c905c6d32164654dc6`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Preserve OSS users' trusted-cluster connectivity during a root-cluster upgrade to Teleport 6.0 by keeping them on the `admin` role path instead of migrating them to a separate `ossuser` role.
**Severity:** SEVERE
**Labels:** `approach_lock`, `test_mutation`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 10 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.87):
  This matches the circular test-patch dependency subtype of approach_lock. The analysis says multiple F2P tests exercise hunk 7 even though hunk 7 is unrelated to the stated bug and even conflicts with the stated requirement for legacy user creation. That means an agent could implement the requested migration fix correctlymigrating the existing admin role in place, preserving admin mapping, and defaulting legacy users to adminyet still fail because the tests also depend on an out-of-scope CLI behavior change. That rejects otherwise valid solutions based on unrelated code, which is severe benchmark contamination.
  - Cross-reference analysis reports circular dependencies: 'TestMigrateOSS/EmptyCluster'  UNRELATED hunk [7] (conf=0.80).
  - Cross-reference analysis reports circular dependencies: 'TestMigrateOSS/User'  UNRELATED hunk [7] (conf=0.80).
  - Cross-reference analysis reports circular dependencies: 'TestMigrateOSS/TrustedCluster'  UNRELATED hunk [7] (conf=0.80).
**test_mutation** (confidence: 0.83):
  A pre-existing test was altered to cover behavior outside the task's acceptance criteria. The analysis explicitly identifies a modified pre-existing 'TestMigrateOSS' fragment whose changes are misaligned and tangential, adding GitHub connector-related coverage not described in the issue or requirements. That is the hallmark of test_mutation: the PR author changed an existing test in a way that silently expands what passing requires beyond the stated problem.
  - F2P analysis: Test 'TestMigrateOSS' is a '[MODIFIED pre-existing test]'.
  - One modified fragment of 'TestMigrateOSS' is marked TANGENTIAL (conf=0.71) with '[MISALIGNED changes]'.
  - The misaligned modification 'broadens coverage into GitHub connector setup within a migrateOSS test'.
**scope_creep** (confidence: 0.79):
  The gold patch includes at least one behavioral change beyond the requested scope. Hunk 7 introduces a new CLI behavior for omitted '--roles' that is not asked for by the task and, worse, contradicts the stated requirement that legacy user creation should default to the admin role. This is classic scope expansion in the patch itself. I am not counting hunk 6 because it is only a copyright update, but hunk 7 alone is enough to justify scope_creep.
  - Gold patch analysis marks hunk 7 [tool/tctl/common/user_command.go] as UNRELATED (conf=0.99).
  - Hunk 7 changes CLI behavior to reject user creation when '--roles' is omitted.
  - Requirement: 'For legacy user creation (when no roles specified), users must be assigned to teleport.AdminRoleName instead of teleport.OSSUserRoleName'.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.74)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the migration/regression description, mapped it to Teleport's role and auth subsystems, inspected the relevant files one by one, and then attempted to implement a fix centered on preserving the admin-role path for OSS users.
- **Behavior:** Methodical, task-aware exploration with a plausible fix strategy, but incomplete or unsuccessful execution; no meaningful evidence of benchmark leakage.

> The trajectory looks like genuine repository-driven debugging rather than leakage. The agent began from the problem statement, identified the likely subsystems involved (OSS migration logic, admin role handling, user creation, build type behavior), and then explicitly explored those areas in sequence: constants, migration code, the role-construction function, user creation paths, and role deletion logic. That is the expected search pattern for this bug. The planned implementation steps also trac

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-baeb2697c4e4870c9850ff0cd5c7a2d08e1401c9-vee9b09fb20c43af7e520f57e9239bbcf46b7113d`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Add a centralized HSM/KMS test-configuration entry point, centered on a public HSMTestConfig selector that detects an available backend from the environment instead of requiring each test file to duplicate its own setup logic.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 5 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.33)

### Label Analysis

**approach_lock** (confidence: 0.82):
  This task shows the circular test-patch dependency subtype of approach_lock. A solver can satisfy the stated task by implementing the requested centralized HSM/KMS test configuration API in testhelpers.go (hunks 2-4), yet still fail the benchmark because the F2P suite also requires unrelated production behavior from hunk 1. That means the tests are not just checking whether the described HSMTestConfig refactor was done; they effectively require an additional out-of-scope fix. So valid solutions to the stated problem are rejected unless they also reproduce unrelated gold-patch behavior.
  - Cross-reference analysis reports 33 circular dependencies: every listed F2P test (e.g. 'TestGCPKMSKeystore/key_pending_forever', 'TestAWSKMS_DeleteUnusedKeys', 'TestBackends', 'TestGCPKMSDeleteUnusedKeys') exercises UNRELATED hunk [1].
  - Hunk [1] in 'lib/auth/keystore/pkcs11.go' is classified UNRELATED (conf=0.95): it changes production PKCS#11 behavior in 'findUnusedID' / the label passed to 'FindKeyPair'.
  - The acceptance criteria and interface are confined to centralized test configuration in 'lib/auth/keystore/testhelpers.go' via 'HSMTestConfig' and backend-specific helpers; required implementation is in hunks [2], [3], and [4].
**scope_creep** (confidence: 0.90):
  The gold patch contains behavioral code beyond the requested test-infrastructure refactor. In particular, hunk 1 modifies production PKCS#11 keystore behavior, which is unrelated to centralizing test configuration. That is genuine scope expansion, not an ancillary import/comment change. Note that unrelated hunk 0 is documentation-only and is not the basis for this label; hunk 1 alone is sufficient to establish scope_creep.
  - Hunk [1] in 'lib/auth/keystore/pkcs11.go' is classified UNRELATED (conf=0.95) and changes production behavior by altering the label argument passed to 'FindKeyPair' in PKCS#11 key lookup logic.
  - The problem statement and requirements are about consolidating HSM/KMS test configuration logic and adding 'HSMTestConfig' plus backend helpers in 'lib/auth/keystore/testhelpers.go'.
  - Gold patch analysis states hunk [1] is not required for any acceptance criterion and that production keystore behavior changes are out of scope.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.71)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent began with normal codebase exploration around keystore test helpers and backend config structs, then appears to have been steered by hidden knowledge of the upstream patch/PR and expanded its work to the unrelated pkcs11 label-handling change that was not inferable from the stated task.
- **Behavior:** Mixed behavior: mostly normal repository exploration for the core task, but with a suspiciously specific detour into an unrelated gold-patch change, suggesting access to contaminated solution knowledge.

> The trajectory shows substantial surface-level exploration of the repository, which is a genuine-problem-solving signal. The agent looked through testhelpers.go, config structs, tests, and integration files before planning the central HSMTestConfig implementation. However, a strong leakage indicator appears later: it pivots to an unrelated pkcs11 `FindKeyPair` change and explicitly says 'the PR description mentions that the key lookup logic should call `FindKeyPair` without a label to ensure com

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-c782838c3a174fdff80cafd8cd3b1aa4dae8beb2`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Fix compatibility with pre-v7 remote clusters so that legacy `ClusterConfig` data is handled correctly without RBAC denials or cache reinitialization loops when older leaf/proxy peers connect to newer roots.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 4 of 21 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.74):
  This task shows circular test-patch dependency. The only F2P test (`TestState`) is reported to exercise unrelated hunk 11, which changes `ForDatabases` watch behavior. Since the problem and requirements narrowly scope the fix to pre-v7 handling and specific cache policies, an agent could implement a valid solution to the described bug without touching `ForDatabases`. If the benchmark test still requires that unrelated change, then the test rejects a valid alternative narrower fix. That matches the approach_lock subtype where tests require unrelated patch hunks.
  - Cross-reference analysis: "Test 'TestState'  UNRELATED hunks [11] (conf=0.80)" and "This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for."
  - Hunk 11 in lib/cache/cache.go is marked UNRELATED (conf=0.90): "This changes ForDatabases, which is not part of the required watch-policy changes in the acceptance criteria."
  - The stated watch-policy requirements name only `ForAuth`, `ForProxy`, `ForRemoteProxy`, `ForNode`, and `ForOldRemoteProxy`; they do not ask for `ForDatabases` changes.
**scope_creep** (confidence: 0.93):
  The gold patch includes several behavioral changes outside the task's stated scope. The problem is about pre-v7 remote-cluster compatibility for legacy `ClusterConfig` handling and specific watch-policy adjustments. Yet the patch also alters unrelated cache watch configurations (`ForKubernetes`, `ForApps`, `ForDatabases`) and expands `ForOldRemoteProxy` with `KindDatabaseServer`. These are not ancillary edits like imports or comments; they change runtime behavior beyond the requested fix, so the task has scope_creep.
  - Gold patch analysis: "Has excess: True" with 4 UNRELATED hunks.
  - Hunk 7 [lib/cache/cache.go] is UNRELATED: "Adding KindDatabaseServer to ForOldRemoteProxy is not mentioned in the problem or acceptance criteria."
  - Hunk 9 [lib/cache/cache.go] is UNRELATED: "Changing ForKubernetes goes beyond the described pre-v7 remote compatibility path."

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.82)
- **Gold patch similarity:** 0.0%
- **Causal chain:** A highly detailed problem statement guided the agent to the relevant subsystems; it then inspected those files, formed the correct high-level plan, began implementing required changes, and stalled before completing the critical cache/collections logic or producing a final patch.
- **Behavior:** Methodical explorer with correct high-level understanding, but incomplete execution and no concrete finished patch; no meaningful leakage signals.

> The trajectory looks like a genuine but incomplete attempt rather than leakage. The agent began by exploring the repository and the specific areas implicated by the problem statement: the ClusterConfig type, cache watch policies, reverse tunnel version checks, service helpers, and cache collections. That is the expected workflow for a legitimate solver on this task. It did not jump straight to an opaque final diff, did not install external packages, did not reference the hidden fail-to-pass test

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 4 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-dd3977957a67bedaf604ad6ca255ba8c7b6704e9`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Extend Teleport's additional-principal generation so proxy services include standard loopback identities and all configured public addresses for the proxy, SSH, tunnel, and kube roles are reflected in generated principals/DNS entries.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 13 of 14 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.94):
  This matches the circular test-patch dependency subtype of approach_lock. A solver could implement the problem's stated fix by changing getAdditionalPrincipals as in required hunk 11, yet still fail because at least one F2P test also depends on unrelated behavioral changes from other files. That means the test suite is not purely validating the requested behavior; it implicitly requires extra code paths introduced by the gold patch. This creates false negatives for otherwise valid minimal solutions.
  - Cross-reference analysis flags a circular dependency: Test 'TestGetAdditionalPrincipals/Proxy' -> UNRELATED hunks [0, 2, 3, 5, 7, 12] (conf=0.95).
  - Only hunk 11 in lib/service/service.go is marked REQUIRED for the stated fix; hunks [0, 2, 3, 5, 7, 12] are all classified UNRELATED.
  - The problem asks for additional principals to include `localhost`, `127.0.0.1`, and `::1`, plus configured public addresses, but the linked UNRELATED hunks concern kube-service permissions, heartbeat wiring, server-name generation, and component naming.
**scope_creep** (confidence: 0.98):
  The gold patch bundles substantial behavioral changes beyond the issue being benchmarked. Most of the patch changes kube-service permissions, heartbeats, announcement behavior, and operational wiring rather than the requested principal-generation logic. Because these are behavioral, not merely ancillary cleanup, they constitute genuine scope expansion. This makes the task less cleanly targeted and contributes to benchmark contamination.
  - Gold patch analysis: Has excess = True; 14 hunks total with 1 REQUIRED and 13 UNRELATED.
  - Hunks 0-1 in lib/auth/permissions.go broaden builtin auth permissions for KindKubeService from RO to RW, which is outside additional-principal/DNS generation.
  - Hunks 2-7 in lib/kube/proxy/server.go add heartbeat infrastructure, lifecycle cleanup, and kube server-name collision handling; these are explicitly marked unrelated to the principal-generation bug.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.88)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem description pointed toward proxy principals and Kubernetes/local access, which led the agent to inspect service, kube, and reversetunnel code. From there it expanded into adjacent infrastructure areas also touched by the upstream PR scope, but it never narrowed down to a concrete implementation in `getAdditionalPrincipals`, so the session ended without a fix.
- **Behavior:** Broad, exploratory, and ultimately non-convergent; the agent appears confused by surrounding Teleport/Kubernetes infrastructure and scope-creep rather than exhibiting answer leakage.

> The agent appears to have read the problem and begun a legitimate repository exploration, but it never converged on or implemented the core fix. Its trajectory starts broadly and then branches into multiple areas of the Teleport codebase: `lib/service`, `lib/srv`, kube-related code, reversetunnel, constants, roles, `TeleportProcess`, `NewTLSServer`, and `kubeClusters`. Some of those areas overlap with the gold patch's unrelated scope-creep changes, but there is no evidence of benchmark leakage i

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 13 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_gravitational__teleport-fb0ab2b9b771377a689fd0d0374777c251e58bbf`

### Task Context

**Repository:** `gravitational/teleport` (version )
**Core requirement:** Implement the missing watcher-observability support primitives and stats interfaces—especially a public thread-safe float64 circular buffer plus required sorting and histogram updates—so rolling watcher metrics can be computed and the code compiles.
**Severity:** SEVERE
**Labels:** `scope_creep`, `weak_coverage`, `approach_lock`, `wide_tests`

### Contamination Signals

- **SCOPE_CREEP:** 13 of 32 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The patch includes substantial behavioral work beyond the requested observability primitives and stats behavior. Most notably, it ships a new TUI/event-stats interface that the specification explicitly excludes, plus an unrelated metric rename. These are not ancillary imports or formatting changes; they are extra product behavior, so the task exhibits scope creep.
  - Hunks 12-19 in tool/tctl/common/top_command.go are all marked UNRELATED and add TUI behavior: key '4' handling, graph/table rendering helpers, an 'Event Stats' tab, and multiple layout changes.
  - The out-of-scope section says 'The task does not explicitly require implementing a dedicated monitoring or TUI tab'; hunks 12-19 implement exactly that UI surface.
  - Hunk 5 in lib/srv/authhandlers.go is marked UNRELATED because it renames a certificate-mismatch metric constant unrelated to watcher observability, circular buffers, sorting, or histogram sums.
**weak_coverage** (confidence: 0.87):
  The written task asks for much more than what the visible F2P suite directly checks. An implementation could satisfy the buffer constructor/data tests while omitting or partially implementing watcher stats wiring, deterministic sorting, histogram Sum/filter behavior, Event/AverageSize behavior, or concurrency guarantees. That means the benchmark can award credit for a partial solution, which is a weak_coverage issue.
  - The only explicitly described aligned F2P tests are TestNewCircularBuffer and TestCircularBuffer_Data, which target the constructor/Add/Data behavior of the new CircularBuffer.
  - Required hunks 20, 22, 24, 26, 27, 28, 30, and 31 implement WatcherStats, sorting, Histogram.Sum, filtered histogram extraction, watcher report wiring, and AverageSize-related behavior, but no F2P test is specifically identified for those acceptance criteria.
  - The requirement that CircularBuffer public operations be thread-safe has no explicit F2P coverage.
**approach_lock** (confidence: 0.48):
  There is a meaningful signal that some F2P tests only pass when unrelated top_command/TUI changes are also present. If so, an agent could implement the stated circular-buffer/statistics requirements correctly and still fail because the tests depend on code paths the problem does not ask for, which is the circular test-patch dependency subtype of approach_lock. Confidence is moderated because several linked hunks are comment-only, so the overlap signal may be somewhat noisy.
  - Cross-reference analysis reports circular dependencies: TestSlice and TestUtils each exercise UNRELATED hunks [6, 18, 21, 25] with confidence 0.95.
  - Among those linked hunks, hunk 18 is marked UNRELATED because it is TUI layout support in tool/tctl/common/top_command.go, and the task explicitly says a dedicated TUI tab is out of scope.
**wide_tests** (confidence: 0.42):
  At least one F2P assertion checks behavior beyond the stated constructor contract. A solution that correctly rejects invalid sizes with an error but returns a non-nil placeholder buffer would satisfy the written requirements yet fail this assertion. That makes the tests slightly wider than the spec, though only in a narrow, low-confidence way.
  - The TestNewCircularBuffer analysis notes that 'one assertion adds an extra expectation not explicitly stated in the problem (returning a nil buffer on error)'.
  - The requirements say NewCircularBuffer must return an error when size <= 0, but they do not require the returned *CircularBuffer to be nil in that case.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.83)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent used the problem statement to identify watcher metrics and rolling-buffer support as the main work, explored the relevant code paths across metrics, auth gRPC watcher emission, and the TUI/reporting layer, then started implementing a broad PR-style fix. The effort appears to have stalled before completion or validation.
- **Behavior:** Genuine but incomplete exploratory attempt; no leakage signals, but the agent did not finish or validate a working solution.

> The trajectory shows a broadly legitimate exploration process rather than leakage. The agent began by reading and searching through the repository for metrics, watcher, gRPC server, and top-command reporting code, progressively identifying likely integration points. This is the opposite of a suspicious direct jump: it inspected metrics.go, watcher-related files, grpcserver.go, NewGRPCServer, top_command.go, helper functions, and report structures before editing. It also planned changes that alig

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 13 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-0dc5b20fa186f9714f8a838178597e69f549d026-v2d9a6c849c60ed19fd0858ce9e40b7cc8e097e59`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Update MARC author parsing so that author records from fields 100, 700, and 720 include alternate-script names from linked 880 fields, while preserving the expected normalized author metadata.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 6 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.87):
  This matches the circular test-patch dependency subtype of approach_lock. The task asks for author-person parsing changes for 100/700/720 plus linked 880 alternate-script names, but the cross-reference analysis says the F2P test path also depends on unrelated behavioral hunks in `read_publisher` and 110/111 parsing. That means an agent could correctly implement the requested author fix and still fail because the tests also require out-of-scope code paths. The lock is not about output strictness; it is that passing the benchmark appears to require extra patch behavior the problem did not ask for.
  - CROSS-REFERENCE ANALYSIS: "Circular dependencies detected: 2".
  - Both F2P entries show: "Test 'test_binary'  UNRELATED hunks [0, 4] (conf=0.90)".
  - Hunk 0 is classified UNRELATED: it "changes publisher/place normalization in `read_publisher`, not author-person parsing."
**scope_creep** (confidence: 0.96):
  The gold patch includes behavioral changes beyond the task scope. Publisher/place normalization in `read_publisher` is unrelated to alternate-script author import, and the 110/111 normalization rewrite directly extends into areas the requirements say should remain unchanged. These are not ancillary edits like imports or typing; they alter behavior outside the requested fix, so scope_creep clearly applies.
  - GOLD PATCH ANALYSIS: "Has excess: True" with "UNRELATED=2".
  - Hunk 0 [openlibrary/catalog/marc/parse.py] is UNRELATED (conf=0.99): "changes publisher/place normalization in `read_publisher`, not author-person parsing."
  - Hunk 4 [openlibrary/catalog/marc/parse.py] is UNRELATED (conf=0.88): it rewrites 110/111 normalization to use `name_from_list`.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.78)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the relevant parser and tests, inspected MARC 880 linkage behavior with ad hoc scripts, implemented alternate-name support and tag-aware parsing, debugged its code, then drifted into an over-broad interpretation of 700/720 author handling and incorrect name normalization, which likely caused the unresolved outcome.
- **Behavior:** A genuine, exploratory debugging attempt that partially implemented the intended feature, but misinterpreted scope and normalization details, leading to a non-passing result without signs of leakage.

> The trajectory looks like a genuine debugging and implementation attempt rather than leakage. The agent started by exploring the repository, locating `openlibrary/catalog/marc/parse.py`, reading related functions (`read_author_person`, `read_authors`, `read_contributions`), then inspecting tests, MARC parsing internals, and binary test data to understand how 880 linkages work. It even wrote small inspection scripts to observe current behavior on alternate-script MARC records. That is consistent 

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-2fe532a33635aab7a9bfea5d977f6a72b280a30c-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Fix the Amazon import path so language information from Amazon metadata is retained instead of being dropped.
**Severity:** SEVERE
**Labels:** `wide_tests`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 6 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 1 of 1 assertions (100%) are OFF_TOPIC

### Label Analysis

**wide_tests** (confidence: 0.89):
  The task asks for a very specific bug fix around retaining Amazon language metadata, but the F2P tests exercise substantially more behavior than that. The clearest example is `test_serialize_sample_record`, which checks the entire serialized payload rather than just the new `languages` behavior. The three `clean_amazon_metadata_for_load_*` tests likewise bundle the new language expectation into tests dominated by unrelated metadata-cleaning assertions. This is a scope problem in the tests: they verify extra behavior not described in the acceptance criteria, so the task is contaminated by wide tests rather than by implementation-locking.
  - Requirements are narrow: retain Amazon language `display_value`s in `AmazonAPI.serialize`, deduplicate them, exclude entries with `type == "Original Language"`, and preserve `languages` in `clean_amazon_metadata_for_load`.
  - F2P summary reports 4 tests total with 0 ALIGNED and 4 TANGENTIAL.
  - `test_serialize_sample_record` is flagged with an OFF_TOPIC assertion: full-dict equality on the entire serialized record, including unrelated fields such as authors, contributors, cover, ISBNs, price, and publishers.
**scope_creep** (confidence: 0.96):
  The gold patch includes a behavioral change outside the reported issue: adding proxy configuration support in `scripts/affiliate_server.py`. That is not ancillary to retaining book language metadata; it is a separate behavior change in a different part of the codebase. Because the patch goes beyond the bug's stated scope with at least one unrelated behavioral hunk, the task has scope creep.
  - Gold patch analysis marks Hunk 5 in `scripts/affiliate_server.py` as UNRELATED with confidence 0.99.
  - Hunk 5 adds `proxy_url=config.get('http_proxy')` when constructing `AmazonAPI` and also renames a local variable.
  - Problem statement and requirements are limited to retaining `languages` during Amazon serialization and preserving that field in `clean_amazon_metadata_for_load`; they do not mention `affiliate_server.py` or proxy configuration.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.93)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the bug report, searched the codebase for Amazon import logic, inspected `vendors.py`, verified the missing language extraction and metadata cleaning behavior, implemented both required changes, tested with mocks and edge cases, adjusted the mock shape when serialization initially failed, and then reran relevant tests until the task passed.
- **Behavior:** Methodical and evidence-driven debugging with normal code exploration, implementation, and test iteration; no meaningful signs of leakage.

> The trajectory shows a normal, progressive debugging and implementation process rather than benchmark leakage. The agent began from the problem statement, searched for Amazon-related code, inspected the relevant adapter and cleaning function, looked through tests and related language-handling code, and then formed an explicit two-part hypothesis: serialization was not extracting languages, and cleaning was dropping them. It then implemented a fix, tested it, found an issue in its mock setup, cor

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Remove or quarantine 1 OFF_TOPIC assertions from the test patch. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-3f580a5f244c299d936d73d9e327ba873b6401d9-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Make autocomplete-related constant filter collections immutable and ensure handler entry points normalize iterable filter inputs to an immutable, stable sequence before forwarding them downstream.
**Severity:** SEVERE
**Labels:** `scope_creep`, `weak_coverage`, `wide_tests`

### Contamination Signals

- **SCOPE_CREEP:** 4 of 11 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The benchmark patch includes four behavioral hunks in unrelated modules that are not part of the stated autocomplete/filter-normalization bug. These are not ancillary import or formatting changes; they alter runtime constant containers in bookshelves and edits code. That is classic scope expansion beyond the task specification.
  - Gold patch hunks 0-1 in openlibrary/core/bookshelves.py are marked UNRELATED and change Bookshelves constants / primary-key containers to immutable forms.
  - Gold patch hunks 2-3 in openlibrary/core/edits.py are marked UNRELATED and change CommunityEditsQueue TYPE/STATUS/MODES mappings.
  - The intent extraction explicitly says broader immutable-constant cleanup outside autocomplete-related collections is out of scope: 'No broader change to unrelated handlers or all identifier groupings is concretely specified.'
**weak_coverage** (confidence: 0.96):
  Large parts of the stated contract are not actually enforced by the benchmark tests, and one important requirement (normalizing arbitrary iterables in direct_get before forwarding to Solr) is not implemented by a required runtime hunk at all. A patch that only changes some class defaults to tuples could still pass the visible F2P tests while failing several acceptance criteria. That makes the task easier and the score less representative.
  - The acceptance criteria include direct_get iterable normalization: 'Calling autocomplete.direct_get(fq=...) with any iterable of strings must result in the Solr call receiving an immutable sequence whose contents match the provided iterable in the same order.'
  - Hunk 6 is explicitly marked ANCILLARY because it only widens the type annotation on direct_get from list[str] to Iterable[str] and 'does not itself normalize or transform the runtime value forwarded downstream.'
  - F2P tests mention only two tests: test_autocomplete and test_works_autocomplete.
**wide_tests** (confidence: 0.61):
  The failing tests are not tightly scoped to the reported issue. They bundle the relevant immutability assertions together with checks for other autocomplete/worksearch behavior not described in the task spec. That means the F2P suite reaches beyond the documented acceptance criteria, even though the extra checks live inside pre-existing test functions.
  - F2P test 'test_autocomplete' is marked TANGENTIAL because, beyond the fq immutability check, it also validates unrelated query-string construction, q_op, and rows behavior.
  - F2P test 'test_works_autocomplete' is marked TANGENTIAL because, beyond the fq immutability check, it also validates query generation, response shaping, OLID lookup behavior, and DB fallback.
  - The problem statement and requirements are narrowly about immutable fq defaults, iterable normalization, ordered tuple forwarding, and non-mutation; they do not describe q_op/rows behavior, response shaping, or OLID/DB fallback.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to recognize or reconstruct the original upstream PR as a RUF012 mutable-class-attribute cleanup, uses that framing to target the same files/hunks as the gold patch, then applies the expected immutability conversions; the autocomplete portion is enough to pass the evaluation tests.
- **Behavior:** Behavior is consistent with prior knowledge of the upstream patch/PR: targeted, confirmation-oriented exploration of the exact gold-patch files rather than organic debugging from the stated autocomplete requirements.

> The trajectory does not look like a clean, requirement-driven solve from the benchmark statement alone. Before doing meaningful debugging, the agent framed the task as an upstream-style "RUF012 linter warning" cleanup and then explicitly said it would inspect the files "mentioned in the PR description." It proceeded to enumerate the exact unrelated scope-creep files and class attributes that appear in the gold patch: `openlibrary/core/bookshelves.py` (`PRIMARY_KEY`, `PRESET_BOOKSHELVES`, `PRESET

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 4 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-431442c92887a3aece3f8aa771dd029738a80eb1-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Add a new helper, `luqum_replace_child`, that can replace a direct child node within a Luqum parse-tree parent in place for supported parent node types.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 7 of 8 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 1 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.88):
  This matches the taxonomy's circular test-patch dependency subtype. The task specification asks only for a new helper and its behavior on Luqum parent nodes, but the benchmark includes fail-to-pass tests that rely on unrelated changes in `works.py`. That means a valid solution implementing the requested helper behavior could still fail because the tests require extra patch hunks outside the problem scope. This is stronger than mere overbreadth: the tests lock success to the broader gold-patch trajectory.
  - Cross-reference analysis reports 4 circular dependencies: each `test_luqum_remove_child` instance depends on UNRELATED hunks [0, 1, 2, 3, 4, 5, 6] with conf=0.95.
  - Problem scope is limited to adding `luqum_replace_child` in `openlibrary/solr/query_utils.py`, but hunks 0-6 are in `openlibrary/plugins/worksearch/schemes/works.py` and were all judged UNRELATED.
  - Hunk 6 uses the new helper to implement broader caller-side behavior in `convert_work_query_to_edition_query`; an agent could satisfy the helper contract in hunk 7 yet still fail tests that exercise these out-of-scope caller changes.
**wide_tests** (confidence: 0.82):
  The fail-to-pass suite goes beyond the stated requirements. At minimum, it includes an unrelated parser test function, and the cross-reference suggests additional F2P coverage reaches out-of-scope work-query conversion behavior. These tests verify functionality not requested by the issue/requirements, so the task exhibits wide test scope.
  - F2P test analysis marks `test_luqum_parser` as UNRELATED (conf=0.99): it targets parser/stringification behavior, while the issue is specifically about adding `luqum_replace_child`.
  - The acceptance criteria are narrowly about replacing a direct child, supported parent types, no-op when absent, and `ValueError` on unsupported parents; parsing behavior is explicitly out of scope.
  - Cross-reference analysis shows `test_luqum_remove_child` exercises unrelated `works.py` hunks [0-6], indicating F2P coverage extends into broader query-conversion behavior not described in the problem.
**scope_creep** (confidence: 0.97):
  The gold patch substantially exceeds the requested change. The issue asks for a new helper in `query_utils.py`; instead, most of the patch modifies `works.py` to support broader callable-based field conversion and new query behavior. Those are behavioral expansions, not ancillary cleanup, so this is clear scope creep.
  - Gold patch analysis: 7 of 8 hunks are UNRELATED; only hunk 7 in `openlibrary/solr/query_utils.py` is REQUIRED.
  - Hunk 3 changes `alternative_title` mapping in `openlibrary/plugins/worksearch/schemes/works.py` from a simple field mapping to a lambda that expands into an OR expression; this is new query-conversion behavior unrelated to the helper request.
  - Hunk 5 restructures `convert_work_query_to_edition_query` for callable-based field conversion, and hunk 6 uses `luqum_replace_child` to replace a `SearchField` with a synthesized grouped expression; both are explicitly beyond the requested helper API.
**weak_coverage** (confidence: 0.76):
  The tests do not fully cover the stated contract. They check successful replacement in some cases, but they appear not to verify several explicit acceptance criteria: unsupported-parent error behavior, no-op when the target child is absent, and preservation of the original child-sequence type. A partial implementation could therefore pass, making the benchmark easier and less diagnostic.
  - Only 2 on-topic assertions are identified, both in `test_luqum_replace_child`, and both assert the final serialized query string after replacement.
  - Acceptance criterion 5 requires unsupported parent types to raise `ValueError` with the exact message `"Not supported for generic class Item"`, but no F2P test is identified for that case.
  - Acceptance criteria 3 and 4 require preserving the original children sequence/container type and leaving children unchanged when `old_child` is absent, but no F2P test is identified for either behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.76)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to have started from a broader search-query bug context, explored the Solr/worksearch code to understand how Luqum trees are transformed, identified that a child-replacement helper would be needed, and then planned a set of changes aligned with that broader bug—but it stopped before producing a concrete patch or validating it.
- **Behavior:** Exploratory and partially informed, with some gold-patch-aligned planning, but ultimately incomplete and unresolved.

> The trajectory shows real exploration and understanding of the Luqum/query-conversion area rather than a direct jump to a finished patch: the agent inspected repository structure, searched search-related code, opened `query_utils.py` and `plugins/worksearch/schemes/works.py`, looked for `WORK_FIELD_TO_ED_FIELD`, and explicitly sought tests and a reproduction. That argues against strong leakage such as jumping straight to the exact helper implementation, package-copying, or test-aware behavior. H

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 7 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-5fb312632097be7e9ac6ab657964af115224d15d-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Add support for `WikidataEntity` to expose external author profiles as structured data, including language-aware Wikipedia resolution with English fallback, robust extraction of external identifiers, and inclusion of those profiles on the author infobox.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `weak_coverage`

### Contamination Signals

- **WIDE_TESTS:** 7 of 19 assertions (37%) are OFF_TOPIC

### Label Analysis

**approach_lock** (confidence: 0.84):
  The F2P suite narrows acceptable solutions beyond the stated contract. A correct implementation that returns only a URL or `None` from `_get_wikipedia_link()`—exactly what the requirements ask for—would fail because the tests demand extra tuple metadata. Likewise, a valid implementation that supplies an `icon_url` field with different asset paths would fail despite satisfying the spec. These are narrow assertions that reject valid alternative solutions, so the task is approach-locking.
  - Requirements state `_get_wikipedia_link()` should return the Wikipedia URL in the requested language, fall back to English, and return `None` otherwise.
  - `test_get_wikipedia_link` has OFF_TOPIC assertions requiring a tuple `(url, language_code)`, e.g. `assert entity._get_wikipedia_link('es') == ('https://es.wikipedia.org/wiki/Ejemplo', 'es')` and `assert entity._get_wikipedia_link('fr') == ('https://en.wikipedia.org/wiki/Example', 'en')`.
  - Requirements for `get_external_profiles()` only require each item to include the keys `url`, `icon_url`, and `label`, but `test_get_external_profiles` requires exact asset paths such as `'/static/images/identifier_icons/google_scholar.svg'`, `'/static/images/identifier_icons/wikipedia.svg'`, and `'/static/images/identifier_icons/wikidata.svg'`.
**wide_tests** (confidence: 0.91):
  The tests verify behavior outside the task specification. The requested feature is language-aware Wikipedia URL resolution, statement-value extraction, and structured external profile generation. The F2P suite additionally checks extra return-shape metadata and concrete icon asset values that were never part of the stated acceptance criteria. That is excess test scope, so `wide_tests` applies.
  - F2P analysis marks 2/4 tests as TANGENTIAL and 7/19 assertions as OFF_TOPIC.
  - OFF_TOPIC `_get_wikipedia_link` assertions add undescribed tuple metadata: requested-language and fallback cases assert `(url, 'es'/'en')` rather than just a URL.
  - OFF_TOPIC `test_get_external_profiles` assertions check exact icon asset paths for Google Scholar, Wikipedia, and Wikidata, while the specification only says each profile dict must contain an `icon_url` key.
**weak_coverage** (confidence: 0.73):
  The benchmark does not fully test the stated requirements. An implementation could pass the F2P suite by adding the Wikidata helper methods and profile-list generation while still failing to display those profiles on the actual author infobox. Because a required end-to-end integration outcome is untested, the task has weak coverage.
  - Acceptance criterion 15 says: `The generated external profile entries should be displayed on the author infobox.`
  - Required hunks 5 and 6 modify `openlibrary/templates/authors/infobox.html`, and required hunk 0 removes an unconditional `return None` from `openlibrary/core/models.py` so the infobox can actually reach `WikidataEntity`.
  - All four F2P tests only exercise `_get_wikipedia_link()`, `_get_statement_values()`, and `get_external_profiles()` in `openlibrary/core/wikidata.py`; none render the author infobox or exercise the `models.py` integration path.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.70)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem, explored the relevant Wikidata, model, and template files, noticed the disabled `wikidata()` path and missing helper methods, attempted to implement backend/profile support and then moved on to UI integration, but the run appears to have ended before a final patch was delivered.
- **Behavior:** Genuine exploratory debugging with a sensible implementation plan, but the recorded attempt appears incomplete and did not culminate in a delivered solution.

> The trajectory looks like genuine repository-driven problem solving rather than benchmark leakage. The agent explored the codebase progressively: it inspected the Wikidata model, templates, author model, searched for the `wikidata` method, examined tests only after locating the relevant implementation areas, and looked for existing icon assets and template structure before proposing changes. It formed a plausible hypothesis from code inspection (`Author.wikidata()` had an early `return None`, `W

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Remove or quarantine 7 OFF_TOPIC assertions from the test patch.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-60725705782832a2cb22e17c49697948a42a9d03-v298a7a812ceed28c4c18355a091f1b268fe56d86`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Add a public `User.get_safe_mode()` method that reliably returns the current `safe_mode` preference as a lowercase string and reflects the latest value saved.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 7 of 8 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.79):
  This matches the circular test-patch dependency subtype of approach_lock. The stated task is narrowly about adding User.get_safe_mode() and making it return the latest saved value as 'yes'/'no'/''. But the only F2P test is reported to exercise several hunks that were independently judged UNRELATED to that requirement. That means an agent could implement the required method correctly in models.py yet still fail because the test path depends on extra account/login/template changes. The problem is not just broader scope; it is that the test appears to require out-of-scope code, rejecting an otherwise valid solution.
  - Cross-reference analysis: Test 'test_user_settings' exercises UNRELATED hunks [0, 1, 2, 3, 6] with confidence 0.95.
  - Only hunk 5 in openlibrary/plugins/upstream/models.py is REQUIRED; it adds User.get_safe_mode().
  - Unrelated hunks touched login/account/template behavior, e.g. hunk 2 sets an 'sfw' cookie during login, hunk 3 propagates safe_mode into another login path, and hunk 6 changes account template text.
**scope_creep** (confidence: 0.98):
  The gold patch clearly expands beyond the benchmarked requirement. Only the models.py change adding User.get_safe_mode() is needed for the acceptance criteria. The remaining hunks introduce separate behavioral changes in login flows, cookie/session handling, privacy settings submission, telemetry, and templates/UI. These are not ancillary edits like imports or formatting; they are substantive out-of-scope behavior changes, so the task exhibits scope creep.
  - Gold patch analysis: 8 hunks total, with 1 REQUIRED and 7 UNRELATED.
  - Hunk 1 [openlibrary/plugins/upstream/account.py] parses email and remember fields in a POST handler for login/cookie behavior; not required by the safe_mode read-method task.
  - Hunks 2 and 3 [openlibrary/plugins/upstream/account.py] add login-session expiry and 'sfw' cookie propagation based on get_safe_mode().

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to have interpreted the task as a broad Safe Mode feature request, explored multiple UI/account/search/cookie code paths, got pulled into scope-creep investigation, and then started with an unrelated template change instead of implementing the required `User.get_safe_mode()` accessor.
- **Behavior:** Broad, exploratory, and scope-creep-prone; touched relevant model code but failed to execute the minimal required fix, with no strong evidence of leakage.

> This trajectory looks more like genuine but misdirected exploration than benchmark leakage. The agent did not jump straight to `openlibrary/plugins/upstream/models.py` and add the exact `get_safe_mode()` method; instead it performed a long exploratory sweep across accounts, templates, privacy pages, search-result rendering, cover handling, login cookie logic, and preference-related model code. That is consistent with trying to understand a broader Safe Mode feature rather than reproducing a memo

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 7 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-7edd1ef09d91fe0b435707633c5cc9af41dedddf-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Unify the existing autocomplete endpoints under shared logic that consistently builds queries, handles OLID extraction/conversion, and returns OLID-based results even when Solr has no hit by falling back to the primary data source.
**Severity:** SEVERE
**Labels:** `wide_tests`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **WIDE_TESTS:** 2 of 9 assertions (22%) are OFF_TOPIC

### Label Analysis

**wide_tests** (confidence: 0.84):
  The F2P suite tests behavior beyond the stated task scope. One extra assertion requires a specific Solr `q_op` setting that is never part of the acceptance criteria. Another extra assertion checks a specific title-only query string for `works_autocomplete`, even though the specification focuses on shared base behavior, endpoint filters/fields, and output shaping rather than that additional query detail. These are extra assertions in otherwise aligned tests, so this is wide_tests.
  - F2P analysis marks 2 assertions as OFF_TOPIC.
  - In `test_autocomplete`, the assertion `assert mock_solr_select.call_args.kwargs['q_op'] == 'AND'` is explicitly flagged OFF_TOPIC; neither the problem statement nor the Requirements specify any required `q_op` value.
  - In `test_works_autocomplete`, the assertion `assert mock_solr_select.call_args[0][0] == 'title:"foo"^2 OR title:(foo*)'` is explicitly flagged OFF_TOPIC.
**approach_lock** (confidence: 0.62):
  These assertions can reject valid alternative implementations that satisfy the described behavior. A solution could build an equivalent autocomplete feature without passing `q_op='AND'`, or could implement work searching with a different but valid query construction while still returning correct results. Because the tests lock onto exact mocked call arguments—how Solr is invoked, not just what the endpoint returns—they impose narrow implementation requirements not fixed by the specification.
  - The tests assert on internal mocked Solr call details rather than only endpoint outputs: `mock_solr_select.call_args.kwargs['q_op'] == 'AND'`.
  - The tests also assert an exact non-OLID query string for `works_autocomplete`: `mock_solr_select.call_args[0][0] == 'title:"foo"^2 OR title:(foo*)'`.
  - The stated contract is about search behavior, shared logic, filters, result limits, OLID fallback, and response formatting; it does not determine those exact internal call parameters.
**weak_coverage** (confidence: 0.76):
  Several stated acceptance criteria are untested by the fail-to-pass suite. An agent could plausibly pass the benchmark while omitting or partially implementing `authors_autocomplete`, `subjects_autocomplete`, or some utility edge cases such as unsupported OLID suffix handling. That makes the task easier than the full specification and indicates weak coverage.
  - F2P analysis lists only 2 tests: `test_autocomplete` and `test_works_autocomplete`.
  - Acceptance criteria 9-10 (`authors_autocomplete` behavior and `subjects_autocomplete` optional `type` filter / key+name-only response) have no corresponding F2P test coverage in the provided analysis.
  - Acceptance criteria 1-4 for standalone utility behavior (`find_olid_in_string` suffix filtering and uppercase return; `olid_to_key` mappings for A/W/M and `ValueError` on unsupported suffixes) are not directly covered by the listed F2P assertions.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.67)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the existing autocomplete and OLID-related code, checked tests and model helpers to infer expected behavior, formed a refactor plan around a shared autocomplete base plus unified OLID extraction/conversion, implemented that plan, and locally sanity-checked it. The likely cause of failure is mismatch on exact hidden-test expectations or implementation details, not leakage or aimless debugging.
- **Behavior:** Methodical, codebase-driven refactor attempt with genuine reasoning; likely a near-correct implementation that missed exact evaluation requirements rather than a leaked or test-aware solution.

> The trajectory looks like a genuine implementation attempt rather than leakage. The agent begins by exploring the repository, reading the existing autocomplete endpoints, utility functions, route registrations, tests, and model behavior before proposing a concrete plan. That plan tracks the issue requirements closely: add generalized OLID utilities, refactor autocomplete logic into a shared base, and adapt the specific endpoints. It then reports implementing those changes, running doctests, impo

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Remove or quarantine 2 OFF_TOPIC assertions from the test patch.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-7f6b722a10f822171501d027cad60afe53337732-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Fix the work-search query-processing regression so raw user queries with edge-case text are consistently normalized and escaped through the SearchScheme-based path before being sent to Solr.
**Severity:** SEVERE
**Labels:** `approach_lock`, `test_mutation`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 13 of 37 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.90):
  This matches the circular test-patch dependency subtype of approach_lock. The F2P tests for work-search query processing are reported to depend on unrelated subject/author-search hunks. That means an agent could implement a valid fix confined to WorkSearchScheme/process_user_query and the work-search routing path, yet still fail because the tests indirectly require unrelated refactor work. The tests therefore do not purely measure the requested behavior.
  - Cross-reference analysis reports 8 circular dependencies: test 'test_process_user_query' exercises UNRELATED hunks [16, 17, 18, 19] in openlibrary/plugins/worksearch/code.py (conf=0.98).
  - Hunk 16 removes legacy helpers tied to subject/author search migration; hunks 17-19 rewrite subject and author search paths and API behavior, all explicitly classified UNRELATED to the work-search regression.
  - The problem statement and extracted scope limit the task to work-search query processing; non-work-search behavior is stated to be out of scope.
**test_mutation** (confidence: 0.84):
  This is classic test_mutation: pre-existing tests were changed to assert behavior not described by the issue. Because the modified assertions target tangential legacy query-transformation behavior rather than the stated regression, they make the benchmark look more legitimate than a brand-new off-scope test while still expanding what must be satisfied.
  - F2P analysis says Has modified tests: True.
  - Four instances of 'test_process_user_query' are marked 'TANGENTIAL' and '[MODIFIED pre-existing test, MISALIGNED changes]'.
  - The reasoning for those modified tests says the visible assertions check plain passthrough and field-alias remapping rather than trailing hyphens, quotes, operator-like tokens, or ISBN-like regression cases from the problem statement.
**scope_creep** (confidence: 0.97):
  The patch goes well beyond fixing the work-search regression. It includes a broader migration/refactor for author and subject search plus related template and utility changes. Those are behavioral changes outside the requested scope, so the task's gold patch contains substantial scope expansion.
  - Gold patch analysis says Has excess: True with 13 UNRELATED hunks.
  - UNRELATED hunks 17-19 in openlibrary/plugins/worksearch/code.py migrate subject/author search to SubjectSearchScheme and AuthorSearchScheme and change response behavior.
  - UNRELATED hunks 22-23 add openlibrary/plugins/worksearch/schemes/authors.py and schemes/subjects.py, which are outside the required WorkSearchScheme work.
**weak_coverage** (confidence: 0.76):
  The benchmark under-tests part of its own stated contract. An agent could satisfy the tested process_user_query outputs yet fail to wire run_solr_query and the actual work-search entry points through the scheme-based path. Since that routing behavior is explicitly required but apparently not covered by F2P tests, the task is easier than its specification suggests.
  - All 8 F2P tests are variants of 'test_process_user_query'; there are no F2P tests targeting run_solr_query, do_search, or work_search.
  - Acceptance criterion 6 requires that 'run_solr_query should use the SearchScheme-based processing for search requests'.
  - Required hunks 7, 9, 11, 12, and 20 implement routing through SearchScheme/run_solr_query/work_search, but the F2P suite described here does not directly test those paths.

### Agent Evaluation Behavior

### Diagnosis

**Action:** Review 13 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-8a9d9d323dfcf2a5b4f38d70b1108b030b20ebf3-v13642507b4fc1f8d234172bf8129942da2c2ca26`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Add ISBNdb support to the import CLI so a locally staged ISBNdb JSONL dump can be recognized and converted into staged Open Library import records.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 8 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.58):
  The tests are partly locked to the gold patch's internal structure. A solution could satisfy the stated contract by producing the correct `json()` output and language/year normalization behavior without exposing private helpers named `_get_languages` and `_get_year`, or by implementing the logic inline. Because the F2P suite calls those internal methods directly, valid alternative implementations can fail despite meeting the problem's behavioral requirements. This is a narrow test-assertion form of approach lock.
  - F2P test 'test_isbndb_get_languages' directly asserts on the private helper `item._get_languages(...) == expected`.
  - F2P test 'test_isbndb_get_year' directly asserts on the private helper `item._get_year(isbndb_line) == expected`.
  - The Interface specifies behavior for `ISBNdb.json()` and the public function `get_language`, and only generally says the class 'contains helper methods to normalize ... language codes ... and publication years'; it does not require private methods with the exact names/signatures `_get_languages` or `_get_year`.
**scope_creep** (confidence: 0.93):
  The gold patch includes behavioral UI/template changes unrelated to the requested feature. Those hunks are not ancillary import or plumbing updates; they modify presentation behavior outside the scope of staged ISBNdb import support. That is classic scope expansion beyond the issue's requested functionality.
  - Hunk 0 [openlibrary/templates/history/comment.html] is marked UNRELATED (conf=0.99): it changes how ISBNdb imports are labeled/rendered in the history comment UI.
  - Hunk 1 [openlibrary/templates/history/sources.html] is marked UNRELATED (conf=0.99): it adds ISBNdb source-name/URL mapping for the history/sources template.
  - The acceptance criteria are confined to CLI ingestion and record transformation for staged ISBNdb JSONL data (AC1-AC11); they do not mention history/source template rendering.
**weak_coverage** (confidence: 0.90):
  The tests do not fully cover the stated acceptance criteria. An agent could pass by implementing parsing, non-book detection, and language/year helpers while omitting or breaking major promised behavior such as end-to-end CLI ingestion, `get_line_as_biblio`, or key `ISBNdb.json()` field transformations (`authors`, `isbn_13`, `source_records`, publishers/subjects normalization). This makes the task easier and the score less representative of full compliance.
  - F2P coverage is limited to `get_line`, `is_nonbook`, `_get_languages`, and `_get_year`; the listed tests are `test_isbndb_to_ol_item`, `test_is_nonbook`, `test_isbndb_get_languages`, and `test_isbndb_get_year`.
  - Acceptance criterion AC1 requires that the existing CLI import tooling can stage/import locally staged ISBNdb dumps, but no F2P test exercises `manage_imports.py` or an end-to-end CLI path.
  - Acceptance criteria AC2-AC3, AC5-AC6, and AC11 require `ISBNdb.json()` field shaping (authors, `isbn_13`, `source_records`, publishers, subjects) and `get_line_as_biblio(...)`, but no F2P test is identified for `json()` output structure or `get_line_as_biblio`.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.89)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement pushed the agent toward CLI/import-pipeline integration, so it explored `manage_imports.py`, import classes, partner batch import flow, and API staging format. It then found the existing ISBNdb provider and identified needed transformations, but it stalled before implementing changes.
- **Behavior:** Genuine exploratory debugging with a reasonable hypothesis, but the agent stalled before implementation and did not solve the task.

> The trajectory shows ordinary, non-leaky exploration rather than answer memorization. The agent started broadly, inspected the import pipeline, provider directory, existing `scripts/providers/isbndb.py`, partner batch import code, tests, and API views before forming a hypothesis. That is the opposite of a suspicious jump straight to the exact gold-edit region. It also did not install external packages, did not copy code from site-packages, and did not reveal hidden expected values before explora

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-92db3454aeaa02f89b4cdbc3103f7e95c9759f92-v2c55207218fb8a0138425cbf7d9675272e240b90`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Ensure the reading-log filtering cap exposed by the backend and Solr's boolean clause limit configuration stay consistent by defining an importable `FILTER_BOOK_LIMIT = 30000` in `openlibrary.core.bookshelves` and configuring Solr's `SOLR_OPTS` with a `-Dsolr.max.booleanClauses` value that is not lower than that cap.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 33 of 37 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.95):
  This task shows the circular test-patch dependency subtype of approach_lock. The specification asks only for keeping the Solr boolean clause limit aligned with an importable FILTER_BOOK_LIMIT constant, which is fully satisfied by hunks 0 and 2. However, the cross-reference analysis says the F2P test depends on several hunks explicitly judged UNRELATED to that problem. That means an agent could implement the described fix correctly yet still fail because the test path also requires unrelated reading-log, ratings, or Solr transport refactors from the gold patch. The test is therefore not measuring only whether the requested behavior was implemented.
  - Cross-reference analysis flags a circular dependency: test 'test_shared_constants' exercises UNRELATED hunks [4, 7, 9, 13, 16, 27] with confidence 0.95.
  - The required fix is narrowly defined by hunk 0 (docker-compose.yml Solr boolean clause flag) and hunk 2 (openlibrary/core/bookshelves.py defining FILTER_BOOK_LIMIT = 30_000).
  - UNRELATED hunk 4 rewrites reading-log retrieval/filtering behavior; hunk 7 adds LoggedBooksData and ratings loading; hunk 13 adds a q query parameter; hunk 27 changes Solr request transport.
**scope_creep** (confidence: 0.99):
  The patch massively exceeds the problem scope. The task only requires two behavioral changes: define FILTER_BOOK_LIMIT = 30000 in openlibrary.core.bookshelves and configure docker-compose.yml so SOLR_OPTS includes -Dsolr.max.booleanClauses at least that large. Instead, the gold patch bundles a broad reading-log search refactor, ratings plumbing, new data structures, template changes, endpoint changes, and Solr client transport changes. These are behavioral changes, not mere ancillary imports or formatting. This is clear scope creep.
  - Gold patch analysis: Has excess = True, with 37 hunks total; 33 are marked UNRELATED.
  - Hunk 4 is a large behavioral rewrite of reading-log retrieval, adding q filtering, Solr-backed filtering, LoggedBooksData, redirect handling, ratings plumbing, and runtime use of FILTER_BOOK_LIMIT.
  - Hunk 7 introduces a new public dataclass LoggedBooksData and rating-loading behavior, despite the interface section stating no new public interfaces are introduced.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.72)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent began with legitimate repository exploration, but appears to have anchored on the broader upstream reading-log filtering PR rather than the narrow benchmark requirement; that led it toward implementing the larger contaminated solution pattern, which still satisfied the evaluation.
- **Behavior:** Exploratory and competent on the surface, but it appears to have reconstructed the larger contaminated upstream PR pattern instead of reasoning only from the benchmark's minimal bug description.

> The trajectory shows substantial real exploration, so this is not a simple case of the agent instantly jumping to the target files or blatantly referencing hidden tests. However, the strongest signal is the agent's shift from the narrow benchmark requirement (align Solr boolean clause limit with a backend constant) to the much broader contaminated upstream approach reflected in the gold patch. After inspecting bookshelves, reading-log views, templates, Solr integration, models, ratings, and `myb

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 33 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-9bdfd29fac883e77dcbc4208cab28c06fd963ab2-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Fix the query parser so user queries are normalized correctly with the intended field alias mapping, greedy field binding, LCC normalization, and boolean-operator preservation.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 12 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.74):
  This fits the circular test-patch dependency subtype of approach_lock. The F2P tests are supposed to measure the requested parser fixes, but the analysis says they also depend on an unrelated behavioral hunk (DDC normalization). That means an agent could correctly implement the described alias, greedy binding, LCC, grouping, and OR-preservation behavior yet still fail unless it also reproduces extra code not asked for. That is unfairly restrictive and can create false negatives.
  - Cross-reference analysis reports all 5 parameterized instances of 'test_query_parser_fields' exercising UNRELATED hunk [2] in openlibrary/plugins/worksearch/code.py (conf=0.90).
  - Hunk 2 is explicitly marked UNRELATED: it changes DDC range normalization, while the problem statement/requirements only name alias mapping, greedy field binding, LCC normalization, multi-word grouping, and boolean-operator preservation.
  - The stated out-of-scope section excludes unrelated search behavior changes; DDC is never included in the acceptance criteria.
**scope_creep** (confidence: 0.83):
  The gold patch contains at least one substantive behavioral change beyond the issue scope: DDC range normalization. That is not ancillary plumbing or documentation; it expands search normalization behavior beyond what the problem asks for. While other unrelated hunks are docstring/doctest-only and do not matter for this label, hunk 2 is enough to classify the task as having scope creep.
  - Gold patch analysis marks Has excess: True and identifies hunk 2 as UNRELATED behavioral code.
  - Hunk 2 [openlibrary/plugins/worksearch/code.py]: 'This changes DDC range normalization, but the problem statement is specifically about alias mapping, greedy field binding, LCC normalization, and boolean-operator preservation.'
  - The requirements mention normalizing LCC classification codes only; they do not request DDC normalization.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, inspected the two relevant files, wrote a reproduction script, found a handful of concrete helper-function bugs, and started patching those issues; it appears to have anchored on local fixes and did not reach the larger parser-logic change required to solve the task.
- **Behavior:** Legitimate code inspection and partial bug fixing, but it missed the main parser-behavior change needed for the task.

> This looks like a genuine but incomplete debugging attempt, not leakage. The agent began with normal exploration, inspected the relevant modules, read the transformation and query-processing functions, and even created a small reproduction script to understand the parser behavior. From that investigation it identified several real code defects that do overlap with parts of the gold patch: incorrect `.value` handling for LCC/DDC ranges, a case-sensitivity bug in field alias remapping, and bugs in

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-b67138b316b1e9c11df8a4a8391fe5cc8e75ff9f-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Implement consistent structured MARC parsing and import behavior so metadata in 880 alternate-script fields is extracted and normalized correctly, including when the 880 field is the only source of the data.
**Severity:** SEVERE
**Labels:** `scope_creep`, `wide_tests`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 41 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.37)

### Label Analysis

**scope_creep** (confidence: 0.76):
  The gold patch includes at least one behavioral change outside the requested scope: deleting the old `parse_xml.py` module. That removal is not ancillary setup like imports or typing; it changes repository behavior/surface area beyond the issue's requested 880 extraction, normalization, and common MARC field interface work. This is a straightforward case of scope expansion in the patch itself.
  - Gold patch hunk 40 in `openlibrary/catalog/marc/parse_xml.py` is explicitly classified UNRELATED (conf=0.84).
  - Hunk 40 reasoning: 'Deleting the legacy parse_xml.py module is broader cleanup beyond the requested behavior.'
  - The task specification asks for `MarcXml` compatibility and structured MARC parsing, but does not ask to remove the legacy parser module.
**wide_tests** (confidence: 0.48):
  Several fail-to-pass tests are broader than the stated task: instead of targeting only the requested 880/interface/normalization behavior, they use full golden-output comparisons for entire imported editions. That likely pulls in unrelated metadata checks beyond the acceptance criteria, so a fix that correctly solves the reported problem but changes unrelated edition output could still fail. Confidence is moderate rather than high because the analysis does not enumerate exact off-topic assertions, and the Stage-5 summary did not mark the whole test set as excess.
  - F2P `test_xml` is marked TANGENTIAL (conf=0.69); analysis says it is an end-to-end MARCXML golden-file regression that 'validates the full imported edition payload rather than narrowly targeting the reported 880/interface issues.'
  - F2P `test_binary` appears in multiple parameterized cases and is marked TANGENTIAL (conf=0.72); analysis says it 'compares the full imported edition output' and 'likely checks many metadata details beyond the specific acceptance criteria.'
  - The acceptance criteria are specific to the MARC field interface, control/data field representation, author parsing, 880 linked/unlinked extraction, series de-duplication, and missing-data exceptions; they do not ask for wholesale full-record regression of unrelated edition metadata.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.72)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement explicitly pointed the agent toward MARC parsing abstractions and 880 alternate-script handling. The agent inspected the relevant code and tests, confirmed the current baseline, inferred that structured field interfaces and 880 linkage support were missing, then implemented those core changes plus targeted parser updates. The attempt likely failed because the task's required patch was broader than the subset it completed.
- **Behavior:** Genuine repository exploration and root-cause-oriented refactor attempt; targeted the correct problem but appears to have implemented only a subset of the full required changes.

> The trajectory shows a genuine debugging and implementation attempt rather than leakage. The agent began with broad repository exploration, then narrowed to the MARC modules named in the problem statement, read the relevant source files (`marc_base.py`, `marc_binary.py`, `marc_xml.py`, `parse.py`, `get_subjects.py`), inspected tests, and ran the existing suite before changing code. Its stated plan closely tracks the explicit requirements in the prompt: introduce `MarcFieldBase`, adapt binary/XML

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-bb152d23c004f3d68986877143bb0f83531fe401-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Implement a consistent zip-based cover archival workflow for Open Library that deterministically maps cover IDs to archive.org item/batch locations and updates database state to reflect completed remote archival.
**Severity:** SEVERE
**Labels:** `wide_tests`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 5 of 9 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 6 of 8 assertions (75%) are OFF_TOPIC

### Label Analysis

**wide_tests** (confidence: 0.96):
  The F2P suite exercises behavior outside, and in places contrary to, the stated contract for `Batch.get_relpath`. The task specification requires zip-based paths under `items/...` with zero-padded naming; the test instead checks legacy/underspecified relative paths and even `.tar` support. This is `wide_tests` via extra assertions in an otherwise related test.
  - `test_get_filename`: `assert archive.Batch.get_relpath('0008', '80') == 'covers_0008/covers_0008_80'` expects a path missing the required `items/` prefix and default `.zip` extension, contradicting the requirement `items/<size_prefix>covers_<item_id>/<size_prefix>covers_<item_id>_<batch_id>.zip`.
  - `test_get_filename`: `assert archive.Batch.get_relpath('0008', '80', ext='tar') == 'covers_0008/covers_0008_80.tar'` explicitly tests legacy tar output even though the task says to replace `TarManager` with `ZipManager` and deprecate legacy formats.
  - F2P analysis marks `test_get_filename` as TANGENTIAL with 6 OFF_TOPIC assertions; only 2 assertions in the whole suite are ON_TOPIC.
**scope_creep** (confidence: 0.89):
  The gold patch includes multiple behavioral changes in `openlibrary/coverstore/code.py` that are outside the requested archival implementation. The task asks for archive-path helpers, zip batching, upload verification, DB finalization, and schema changes; it explicitly excludes broader user-facing API/UI changes. Those unrelated web/redirect changes are behavioral scope expansion, so `scope_creep` applies.
  - Hunk 3 [openlibrary/coverstore/code.py] is UNRELATED: removes a URL helper in the web-serving path, not part of the requested archival classes/functions.
  - Hunk 4 [openlibrary/coverstore/code.py] is UNRELATED: refactors legacy zipview URL construction in `code.py`, outside the requested archive workflow.
  - Hunk 5 [openlibrary/coverstore/code.py] is UNRELATED: changes redirect behavior/comments for historical 8,000,000-8,819,999 / 8,820,000 cutoffs, which the out-of-scope note says need not be fully migrated.
**weak_coverage** (confidence: 0.93):
  The stated acceptance criteria are much broader than what the F2P suite meaningfully verifies. Most core requirements—database state updates, upload validation, zip-manager behavior, archive integration, and schema/index changes—have no aligned F2P coverage. That means a partial fix could satisfy the few checked helpers while leaving large portions of the requested functionality unverified, which is `weak_coverage`.
  - Only 3 F2P tests exist, and only 2 are ALIGNED (`test_get_batch_end_id`, `test_id_to_item_and_batch_id`).
  - Assertion analysis reports only 2 ON_TOPIC assertions total, despite a long acceptance list covering `Cover.get_cover_url`, `Batch.process_pending`, `Batch.finalize`, `ZipManager`, `Uploader.is_uploaded`, `CoverDB.update_completed_batch`, schema columns/indexes, `count_files_in_zip`, `get_zipfile`, `open_zipfile`, and `archive` integration.
  - No F2P test directly checks the required schema additions in `schema.sql` / `schema.py` (`failed`, `uploaded`, `cover_failed_idx`, `cover_uploaded_idx`).

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.72)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the coverstore codebase, inferred that tar-based archival needed to be replaced with zip-based batching plus deterministic ID/path helpers, implemented those components across the archive and DB layers, validated with self-authored and repository tests, then iterated on runtime and URL issues. It likely failed because its implementation surface did not exactly match the benchmark's expected locations/signatures.
- **Behavior:** Genuine, repo-driven implementation attempt with meaningful exploration and iteration, but likely incomplete or misaligned with the exact benchmark interface rather than leaked.

> The trajectory shows a largely genuine software-engineering process rather than leakage. The agent began by exploring the relevant repository areas (`archive.py`, schema, db layer, tests, coverlib, config), then formed an implementation plan from the problem statement, and iteratively added the requested pieces: schema changes, `Cover`, `Batch`, zip-based archival support, database updates, and URL handling. It also wrote and ran its own validation scripts, hit an implementation issue (`config.d

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Remove or quarantine 6 OFF_TOPIC assertions from the test patch. **Action:** Review 5 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-d109cc7e6e161170391f98f9a6fa1d02534c18e4-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Add support for optional public Markdown notes on individual list seeds that reference Things, while preserving existing behavior for unannotated seeds and subject string seeds.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `test_mutation`, `weak_coverage`

### Contamination Signals

- **WIDE_TESTS:** 1 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.62):
  The F2P tests check an implementation detail (`seed._list`) rather than the observable feature being requested (annotated per-seed notes, serialization, normalization, UI rendering, etc.). A valid solution could satisfy the public behavior without storing the list object in exactly that internal field, yet still fail these tests. That makes the tests partially approach-locking through narrow internal-state assertions.
  - F2P analysis says `test_seed_with_string` is UNRELATED because its only asserted behavior is that the `Seed` stores the passed `List` object in its internal `_list` field.
  - F2P analysis says `test_seed_with_nonstring` is TANGENTIAL and includes an assertion on `seed._list`, which is outside the stated contract.
  - Neither the problem statement nor the Requirements/Interface specify that `Seed.from_json` must preserve the input list in a particular internal attribute.
**wide_tests** (confidence: 0.80):
  The fail-to-pass tests go beyond the task specification by verifying off-topic internal behavior. The task asks for optional public notes on Thing-based seeds, compatibility for subject-string seeds, JSON/DB/list-operation support, and UI/rendering updates. Internal storage of the passed list object on `Seed._list` is not part of that scope, so these tests are wider than the stated requirements.
  - `test_seed_with_string` is marked UNRELATED; its asserted behavior is internal `_list` attachment, not any acceptance criterion about per-seed notes.
  - `test_seed_with_nonstring` is marked TANGENTIAL; beyond checking legacy JSON parsing, it also asserts internal `_list` attachment not described in the task.
  - F2P summary: ALIGNED=0, TANGENTIAL=1, UNRELATED=1.
**test_mutation** (confidence: 0.93):
  This is a textbook test-mutation case: a pre-existing test was changed, and the changed behavior is not aligned with the problem statement. The modification makes the benchmark look like it is validating the new feature, but the added check is actually about an internal detail unrelated to annotated seed notes.
  - F2P analysis explicitly reports `Has modified tests: True`.
  - `test_seed_with_string` is identified as a `MODIFIED pre-existing test` with `MISALIGNED changes`.
  - The reason given for `test_seed_with_string` is that the modification asserts only internal `_list` storage, which is unrelated to the requested feature.
**weak_coverage** (confidence: 0.98):
  The test suite barely covers the requested feature set. An implementation could miss most of the described functionality—especially the actual annotated-note behavior—and still pass, because the F2P tests focus on legacy parsing and internal state rather than the new acceptance criteria. This is a strong weak-coverage issue.
  - The acceptance criteria cover annotated Thing seeds, empty-note fallback, `to_json`, `to_db`, `normalize_input_seed`, list operations, edit/view UI, safe markdown rendering, and Solr/export workflows.
  - The F2P suite contains only 2 tests, with ALIGNED=0, TANGENTIAL=1, UNRELATED=1.
  - No F2P test is reported for core requested behaviors such as note persistence, annotated JSON parsing/serialization, DB conversion, UI editing/display, safe markdown rendering, or empty-notes compatibility.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.79)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the spec, explored the list-related implementation and templates, formed a correct high-level hypothesis about where annotated-seed support must be added, and began planning edits in those files, but it did not complete or validate the implementation.
- **Behavior:** Genuine repository exploration and task-specific reasoning, but the implementation effort appears unfinished and unsuccessful rather than leaked.

> The trajectory looks like a genuine but incomplete attempt rather than leakage. The agent began by exploring the repository, then inspected the main list model, list plugin code, edit/view templates, and existing tests. Its proposed changes closely follow the public problem statement: adding annotated seed types, extending `Seed`, updating `List` methods, adjusting input normalization, and exposing notes in templates. Those are exactly the areas a legitimate solver would identify from the specif

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_internetarchive__openlibrary-fdbc0d8f418333c7e575c40b661b582c301ef7ac-v13642507b4fc1f8d234172bf8129942da2c2ca26`

### Task Context

**Repository:** `internetarchive/openlibrary` (version )
**Core requirement:** Import record normalization should remove the fields `publishers`, `authors`, and `publish_date` when they are set to the exact placeholder values `['????']`, `[{"name":"????"}]`, and `'????'` respectively.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 6 of 9 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.84):
  This task shows the circular-dependency subtype of approach_lock. The requested behavior is narrowly about `normalize_import_record`, and the analysis identifies Hunk 1 as sufficient for the acceptance criteria. However, the F2P test is linked to unrelated hunks in `openlibrary/core/models.py`, especially the broader `from_isbn` rewrite in Hunk 7. That means an agent could implement the described normalization fix correctly, yet still fail because the test exercises extra gold-patch code outside the stated problem. The test is therefore not purely checking the requested observable behavior; it effectively ties success to the broader patch structure.
  - Cross-reference analysis: `test_dummy_data_to_satisfy_parse_data_is_removed` depends on UNRELATED hunks `[3, 5, 7]` with confidence `0.95`.
  - Hunk 1 in `openlibrary/catalog/add_book/__init__.py` is the only `REQUIRED` hunk and fully implements the stated fix: exact removal of placeholder `publishers`, `authors`, and `publish_date`.
  - Hunk 7 in `openlibrary/core/models.py` is explicitly marked `UNRELATED` and 'substantially rewrites parsing/loading/error behavior and return semantics' in `from_isbn`, which the problem statement never asks for.
**scope_creep** (confidence: 0.90):
  The gold patch expands beyond the bug as specified. While only Hunk 1 is needed to satisfy the normalization requirements, the patch also includes unrelated behavioral modifications in `openlibrary/core/models.py`, most notably the `from_isbn` rewrite. Those changes are not ancillary documentation or formatting; they alter behavior in a separate feature area not described by the task. That is classic scope creep: the benchmark patch bundles the requested fix with additional, out-of-scope behavior changes.
  - Gold patch analysis: `Has excess: True` with `6` UNRELATED hunks.
  - Hunk 7 (`openlibrary/core/models.py`) is UNRELATED and makes broader behavioral changes: it rewrites `from_isbn` parsing/loading/error behavior and return semantics.
  - Hunk 6 (`openlibrary/core/models.py`) is UNRELATED and removes a local error helper from `from_isbn`, part of the same out-of-scope refactor.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.77)
- **Gold patch similarity:** 0.0%
- **Causal chain:** Issue about placeholder values surviving normalization led the agent to inspect import-related code paths, find where records are parsed and loaded, discover that `load()` calls `normalize_import_record()`, infer that placeholder cleanup belongs there, and then plan to centralize the logic and remove duplicated cleanup from upstream callers.
- **Behavior:** Repository-guided debugging with a plausible, problem-specific centralization fix; likely addressed the real bug, but the recorded run did not finish as a confirmed pass.

> The trajectory looks mostly like genuine debugging rather than benchmark leakage. The agent did not jump straight to editing the exact target function; it explored the import flow, inspected related modules, searched for `parse_data`, `load`, and `normalize_import_record`, reproduced the issue, and then articulated a concrete hypothesis: cleanup should live in `normalize_import_record`, with duplicated cleanup removed from callers. That is a sensible causal path from the problem statement. There

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 6 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_navidrome__navidrome-29b7b740ce469201af0a0510f3024adc93ef4c8e`

### Task Context

**Repository:** `navidrome/navidrome` (version )
**Core requirement:** Add optional configuration to `SimpleCache` for maximum size and default entry TTL so it can evict old entries and stop returning expired ones.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 3 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.84):
  This task shows a circular test-patch dependency: the fail-to-pass test appears to require unrelated changes in cached_http_client.go, even though the problem only asks for new configurability and behavior in SimpleCache itself. If an agent implemented the requested SimpleCache API and semantics correctly but did not also migrate HTTP client internals, the cross-reference analysis indicates the test could still fail. That means the benchmark is not measuring only the requested behavior; it is coupling success to out-of-scope patch hunks, which is a form of approach_lock under the taxonomy's circular dependency subtype.
  - Cross-reference analysis: Test 'TestCache' → UNRELATED hunks [0, 1] with conf=0.90, explicitly flagged as a circular dependency.
  - Hunk 0 [utils/cache/cached_http_client.go] is UNRELATED (conf=0.94): it replaces direct ttlcache usage in HTTPClient with SimpleCache[string] plus a ttl field.
  - Hunk 1 [utils/cache/cached_http_client.go] is UNRELATED (conf=0.95): it refactors NewHTTPClient/Do to use SimpleCache Options and GetWithLoader, and removes a logging callback.
**scope_creep** (confidence: 0.92):
  The gold patch expands beyond the requested enhancement. The task asks for adding Options, size limiting, TTL expiration, and Keys filtering in SimpleCache, but the patch also performs behavioral refactoring in cached_http_client.go. Those changes are not ancillary cleanup; they alter production behavior in another component and were explicitly judged unrelated. This is classic scope creep: the patch bundles extra behavioral work that the issue did not ask for.
  - Gold patch analysis: Has excess=True with 3 hunks total; 2 are UNRELATED and 1 is REQUIRED.
  - Hunk 0 [utils/cache/cached_http_client.go] is UNRELATED (conf=0.94) because changing HTTPClient internals is not required by any acceptance criterion.
  - Hunk 1 [utils/cache/cached_http_client.go] is UNRELATED (conf=0.95) because migrating a consumer to the new SimpleCache API and changing loader/logging behavior is outside the problem scope.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.90)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent began with nominal repo exploration, but almost immediately focused on `HTTPClient`, inferred hidden/scope-creep requirements absent from the prompt, then implemented both the stated `SimpleCache` change and the unrelated `cached_http_client.go` refactor in a way that mirrors the gold patch, after which it ran tests and confirmed success.
- **Behavior:** Superficially methodical, but guided by suspiciously precise prior knowledge of the benchmark's gold-patch-specific extra changes rather than only the user-stated `SimpleCache` bug.

> The trajectory shows some real exploration and validation, but the core solution path is strongly contaminated by gold-patch-specific scope creep. The visible problem statement is narrowly about adding configurable `SizeLimit` and `DefaultTTL` to `SimpleCache`. Despite that, the agent immediately pivoted to `cached_http_client.go` and later asserted a highly specific requirement set involving replacing `ttlcache.Cache` with `SimpleCache[string]`, storing a `ttl` field on `HTTPClient`, and rewrit

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_navidrome__navidrome-5001518260732e36d9a42fb8d4c054b28afab310`

### Task Context

**Repository:** `navidrome/navidrome` (version )
**Core requirement:** Introduce normalized, user-scoped storage and access for user-specific properties by moving them out of the global prefixed-key `properties` table into a dedicated `user_props` table and updating the LastFM session-key use case to use that API.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 15 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.72):
  This matches the circular test-patch dependency subtype of approach_lock. The task specification asks for a new user_props table, a UserPropsRepository API, context-derived user scoping, and LastFM refactoring. Hunk 11 is explicitly judged outside that scope, yet the cross-reference analysis says all F2P suites exercise it. That means an agent could implement the requested behavior correctly while leaving model/properties.go unchanged and still fail the benchmark. The tests would therefore require an out-of-scope patch detail rather than only the observable behavior described by the problem.
  - Cross-reference analysis reports circular dependencies for all 4 F2P suites: TestCore → UNRELATED hunk [11], TestAgents → UNRELATED hunk [11], TestLastFM → UNRELATED hunk [11], TestPersistence → UNRELATED hunk [11] (each conf=0.80).
  - Cross-reference summary explicitly states: "This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for."
  - Hunk 11 [model/properties.go] is marked UNRELATED (conf=0.77): "Removing the old Property struct and adding a TODO in the global properties model is not required by any acceptance criterion."
**scope_creep** (confidence: 0.75):
  The gold patch includes at least one behavioral/code-structure change beyond the requested enhancement. The task is specifically about introducing normalized user-scoped storage and refactoring LastFM session-key handling, while non-user-specific global properties are listed as out of scope. Changing model/properties.go by removing the old Property struct and adding cleanup/TODO work is therefore extra patch scope rather than necessary implementation support. Because this is more than pure formatting or imports, it qualifies as scope_creep.
  - Gold patch analysis: Has excess = True.
  - Hunk 11 [model/properties.go] is marked UNRELATED (conf=0.77).
  - Hunk 11 rationale: "Removing the old Property struct and adding a TODO in the global properties model is not required by any acceptance criterion."

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.88)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the requirements, explored the existing property and LastFM codepaths, inferred the architectural changes needed, attempted to set up reproduction/tests, then switched to direct implementation planning when test setup looked cumbersome. The trajectory appears to end before code was actually produced or validated.
- **Behavior:** Methodical and requirement-driven exploration with a plausible implementation plan, but the run terminated before producing a real patch or validated solution.

> The trajectory shows a largely genuine debugging and implementation attempt rather than leakage. The agent began by exploring the relevant areas of the codebase in a sensible order: existing property models, datastore interfaces, persistence repositories, LastFM usage, session-key handling, migrations, and request/context utilities. It explicitly connected the observed `LastFMSessionKey_<userID>` pattern to the problem statement and then outlined a reasonable implementation plan that closely mat

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_navidrome__navidrome-66b74c81f115c78cb69910b0472eeb376750efc4`

### Task Context

**Repository:** `navidrome/navidrome` (version )
**Core requirement:** Add reversible encryption for user passwords so they are no longer stored in plain text, while still allowing the system to decrypt them for Subsonic authentication/token generation and case-insensitive user lookup.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 14 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.93):
  The patch includes a behavioral database migration for pre-existing plaintext passwords that goes beyond the requested feature. The task asks for encrypted-at-rest handling for create/update plus reversible decryption for authentication flows, not retroactive migration of old rows. Because this is a real behavioral change in an unrelated file and is explicitly outside the stated scope, the task has scope_creep.
  - Gold patch hunk 3 [db/migration/20210616150710_encrypt_all_passwords.go] is marked UNRELATED (conf=0.98): it 'encrypts all existing plaintext passwords already stored in the database.'
  - The intent extraction explicitly lists 'migration of existing plaintext records' as out of scope.
  - The stated acceptance criteria only require encrypting passwords on create/update and decrypting on lookup/authentication; they do not ask for a backfill migration.
**approach_lock** (confidence: 0.62):
  There is evidence that the F2P tests depend on an unrelated migration hunk. If that dependency is real, then an agent could implement the stated requirements correctly—public AES-GCM helpers, encrypted storage on create/update, and decrypted lookup/authentication—yet still fail because it did not also add the out-of-scope migration for existing records. That is a circular test-patch dependency and therefore an approach_lock signal. Confidence is moderate rather than high because the dependency is inferred from cross-reference analysis rather than explicit assertion-level test evidence.
  - Cross-reference analysis reports circular dependencies: Test 'TestPersistence' → UNRELATED hunk [3] (conf=0.80).
  - Cross-reference analysis reports circular dependencies: Test 'TestUtils' → UNRELATED hunk [3] (conf=0.80).
  - Hunk 3 is the out-of-scope migration of existing plaintext passwords, while the problem statement only requires encryption on create/update and decryption on retrieval/authentication.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.90)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent started from the problem statement, explored the relevant persistence/auth/config code paths, verified the bug empirically with custom scripts, implemented the AES-GCM utility layer, and then began broader integration work but stopped before producing a complete patch.
- **Behavior:** Methodical and genuine exploration with partial implementation, but it failed because it did not finish the task rather than because of benchmark leakage.

> This trajectory looks like genuine, incremental problem-solving rather than leakage. The agent did not jump straight to a finished patch or to obscure files; it explored the user model, repository implementation, configuration, migrations, property storage, and authentication code before making changes. It also created and ran repro scripts to confirm that passwords were currently stored in plaintext, which is exactly the kind of debugging step expected from a legitimate solver. The agent then i

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_navidrome__navidrome-69e0a266f48bae24a11312e9efbe495a337e4c84`

### Task Context

**Repository:** `navidrome/navidrome` (version )
**Core requirement:** Refactor public artwork image handling so JWTs encode only the artwork ID, while image size is passed separately in the request and generated image URLs.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 7 of 19 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.91):
  This task shows the circular test-patch dependency subtype of approach_lock. The stated task is to decouple artwork ID from size in public JWTs and URLs, but the F2P test is reported to require unrelated patch hunks in resizing code and an extra artist-response path. That means an agent could correctly implement the described requirements—id-only JWTs, separate size parameter, new route, updated URL generation, GetArtistInfo changes—and still fail because the test suite depends on out-of-scope behavior from hunks [2, 3, 4, 16]. Since the test effectively requires more than the problem asks for, valid solutions are rejected unless they also reproduce unrelated parts of the gold patch.
  - Cross-reference analysis: Test 'TestArtwork' exercises UNRELATED hunks [2, 3, 4, 16] with conf=0.95.
  - Hunk 2 is UNRELATED: changes image-resizing behavior/logging when resize fails or image is smaller than requested size.
  - Hunk 3 is UNRELATED: alters content-type detection for very small image inputs.
**scope_creep** (confidence: 0.95):
  The gold patch clearly expands beyond the issue scope. The problem asks for refactoring public artwork JWT contents, routing, request parsing, URL generation, and GetArtistInfo image URLs. In addition, the patch modifies image resizing behavior, content-type detection, no-upscaling logic, and multiple other artist/search response paths not requested by the problem. These are behavioral changes, not mere imports or cleanup, so they constitute scope creep.
  - Gold patch analysis: Has excess=True with 7 UNRELATED hunks.
  - Hunks 2, 3, 4, and 5 in core/artwork/reader_resized.go change resizing semantics/content-type handling, including 'don't upscale' behavior and related refactoring.
  - Hunk 15 in server/subsonic/helpers.go changes ArtistImageUrl generation in toArtist outside the named GetArtistInfo requirement.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.92)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement pointed the agent to the relevant subsystems; it explored those files and related tests to build understanding, then tried to reproduce behavior with a debug script, but never translated that investigation into code changes.
- **Behavior:** Genuine exploratory debugging behavior, but incomplete execution: the agent investigated the right areas and tried to reproduce the issue, then stalled without producing a patch.

> The trajectory shows normal, task-directed exploration rather than leakage. The agent started from the problem statement, inspected the named implementation areas (`core/artwork/artwork.go`, artwork ID model code, auth/JWT handling, public endpoints, helper usages, and tests), and then attempted to create a debug script to understand current behavior. This is the opposite of a suspicious jump-to-fix pattern. There is no evidence of package installation, no reference to hidden F2P test names or s

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 7 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_navidrome__navidrome-b3980532237e57ab15b2b93c49d5cd5b2d050013`

### Task Context

**Repository:** `navidrome/navidrome` (version )
**Core requirement:** Ensure `lastFMConstructor` always initializes the Last.FM agent with usable default values by using configured `apiKey`/language when present and falling back to a built-in shared API key and `"en"` when they are missing.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 7 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.61):
  This matches the circular test-patch dependency subtype of approach_lock. If the F2P test requires hunk 5, then a solver that correctly implements the requested Last.FM behavior (use configured API key or built-in shared key, and valid language defaults) could still fail unless it also reproduces an unrelated Spotify logging change. That means the test is not measuring only the asked-for behavior. Confidence is moderate rather than maximal because the dependency is inferred from cross-reference analysis rather than assertion-level evidence.
  - CROSS-REFERENCE ANALYSIS: circular dependency detected — Test 'TestAgents' → UNRELATED hunks [5] (conf=0.80).
  - Hunk 5 [core/agents/spotify.go] is explicitly UNRELATED (conf=0.99): it 'only removes a Spotify log line' and is 'outside the stated scope.'
  - The problem statement and requirements only ask for `lastFMConstructor` defaulting of `apiKey` and `lang`; Spotify logging is not part of the acceptance criteria.
**scope_creep** (confidence: 0.90):
  The gold patch contains a behavioral change outside the stated task scope. The requested fix is about Last.FM constructor defaults, but hunk 5 changes Spotify behavior instead. This is not merely ancillary plumbing like imports or config wiring; it is an unrelated code change in another component, so the patch exhibits scope creep.
  - GOLD PATCH ANALYSIS: Has excess: True.
  - Hunk 5 [core/agents/spotify.go] is UNRELATED (conf=0.99): it removes a Spotify log line and 'affects neither Last.FM nor constructor behavior.'
  - Intent extraction states the task is limited to `lastFMConstructor`, `apiKey`, and `lang`, and excludes unrelated integration/logging changes.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored relevant code, reproduced the failure mode around agent registration without an API key, concluded that constructor defaults alone were insufficient, and expanded the fix to include config/registration changes so Last.FM could operate out of the box.
- **Behavior:** Careful, exploratory debugger that identified the core issue and pursued a plausible full fix, but did not successfully complete the benchmark.

> The trajectory shows a genuine debugging process rather than benchmark leakage. The agent began with broad repository exploration, then inspected the configuration layer, the Last.FM agent, metadata flow, registration hooks, and the Last.FM client before forming a hypothesis. It created reproduction scripts to confirm the actual runtime behavior: with no API key, the Last.FM agent was not registered; with an API key, it was. From that evidence it inferred the need for a default/shared API key, p

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_navidrome__navidrome-d0dceae0943b8df16e579c2d9437e11760a0626a`

### Task Context

**Repository:** `navidrome/navidrome` (version )
**Core requirement:** Add the missing Subsonic share API support so clients can create music-content shares and retrieve existing shares, including public share URLs and Subsonic-compliant share responses.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 22 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.34)

### Label Analysis

**scope_creep** (confidence: 0.88):
  The task asks for missing Subsonic share endpoints, share validation, share retrieval, public share URLs, and Subsonic-compliant share responses. The patch also includes behavioral changes to public image URL generation in server/public/encode_id.go, and those hunks were explicitly classified as UNRELATED rather than ancillary plumbing. Because these are out-of-scope behavioral edits rather than whitespace/import-only support changes, this is scope creep.
  - Gold patch hunk 5 [server/public/encode_id.go] is marked UNRELATED (conf=0.98): it swaps filepath for path in public image URL code, and the analysis states this is about artwork image URL handling rather than Subsonic share creation/retrieval.
  - Gold patch hunk 6 [server/public/encode_id.go] is marked UNRELATED (conf=0.97): it changes ImageURL internals in public image URL generation, which the analysis explicitly says is outside the scope of adding Subsonic share endpoints.
**approach_lock** (confidence: 0.64):
  This fits the circular test-patch dependency subtype of approach_lock. The task specification is about share creation/retrieval and public share links, but the F2P tests are reported to exercise an unrelated image-URL hunk. That means an agent could implement the requested share functionality correctly while leaving public image URL internals untouched, yet still fail because the tests are entangled with out-of-scope code. The evidence is indirect (cross-reference linkage rather than explicit assertion text), so confidence is moderate rather than maximal.
  - Cross-reference analysis reports circular dependencies: Test 'TestSubsonicApi' → UNRELATED hunk [6] (conf=0.80).
  - Cross-reference analysis reports circular dependencies: Test 'TestSubsonicApiResponses' → UNRELATED hunk [6] (conf=0.80).
  - The cross-reference summary states: 'This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for.'

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.93)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent followed the PR description and repository structure to inspect the relevant Subsonic, sharing, persistence, response, and public URL codepaths, identified the missing endpoints, and appeared to prepare for testing, but it stopped before implementing any changes.
- **Behavior:** Methodical repository exploration with genuine task-oriented reasoning, but the agent stalled before implementation and did not solve the task.

> The trajectory shows normal exploratory behavior rather than leakage. The agent began by reading the Subsonic API structure, then progressively inspected the exact subsystems one would reasonably need for this feature: API routing, share model/core logic, persistence, response types, public URL helpers, and dependency wiring. It explicitly noticed that `getShares` and `createShare` were still marked as not implemented and then continued gathering context. That sequence reflects legitimate proble

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_navidrome__navidrome-d8e794317f788198227e10fb667e10496b3eb99a`

### Task Context

**Repository:** `navidrome/navidrome` (version )
**Core requirement:** Centralize artwork-unavailability handling in the `Artwork` API so strict fetches consistently report `ErrUnavailable`, fallback fetches return built-in placeholders, and artwork HTTP/Subsonic endpoints translate unavailability into not-found responses with logging.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 24 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.88):
  This matches the taxonomy's circular test-patch dependency form of approach_lock. Both F2P tests appear to depend on hunk 20 even though that hunk is not required by the task and conflicts with the stated Subsonic acceptance criterion. So an agent that correctly implements the written spec for Subsonic artwork unavailability could still fail unless it also reproduces this extra gold-patch behavior. The tests therefore partially lock success to unrelated implementation behavior rather than only the requested observable contract.
  - Cross-reference analysis: Test 'TestArtwork' exercises UNRELATED hunk [20] (conf=0.80).
  - Cross-reference analysis: Test 'TestSubsonicApi' exercises UNRELATED hunk [20] (conf=0.80).
  - Hunk 20 [server/subsonic/media_retrieval.go] is marked UNRELATED because it switches the Subsonic handler to `GetOrPlaceholder`, while the requirements say the Subsonic `GetCoverArt` handler must 'log a warning message when `ErrUnavailable` is returned for an artwork request and return a not-found response in the Subsonic XML format.'
**scope_creep** (confidence: 0.93):
  The gold patch includes behavioral changes beyond the issue's scope. The strongest example is hunk 20, which alters Subsonic behavior in a way the task did not ask for and that the hunk analysis marked UNRELATED. In addition, the playlist UI changes in hunks 22 and 23 are plainly outside the artwork-handling request. These are not mere ancillary refactors; they add extra behavior unrelated to the benchmarked task.
  - Gold patch analysis reports 3 UNRELATED hunks: [20], [22], [23].
  - Hunk 20 [server/subsonic/media_retrieval.go] changes Subsonic artwork behavior toward placeholder fallback via `GetOrPlaceholder`, instead of the requested `ErrUnavailable` -> warning + not-found response.
  - Hunks 22 and 23 [ui/src/playlist/PlaylistSongs.js] are unrelated frontend playlist changes, outside the artwork-unavailability API, cache, and handler scope described in the problem.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.80)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the requirements, surveyed the relevant artwork and handler code paths, formed a coherent fix plan around centralizing ErrUnavailable and placeholder behavior, but the recorded session stops before a concrete validated patch is produced.
- **Behavior:** Genuine exploratory debugging and planning, but incomplete execution; no meaningful evidence of leakage.

> The trajectory shows a normal, non-leaky investigation pattern: the agent explicitly started by exploring the repository, then inspected the artwork interface, model types/errors, empty-ID reader, source selection, cache warmer, constants, and both HTTP/Subsonic handlers before proposing changes. Its planned edits track the problem statement closely and reflect genuine task-specific understanding: add ErrUnavailable, centralize placeholder fallback in GetOrPlaceholder, remove per-reader placehol

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_NodeBB__NodeBB-18c45b44613aecd53e9f60457b9812049ab2998d-v0495b863a912fbff5749c67e860612b91825407c`

### Task Context

**Repository:** `NodeBB/NodeBB` (version )
**Core requirement:** Add authenticated HTTP API support for the full group invitation lifecycle—issuing, accepting, and rejecting/rescinding invites—so these actions are no longer limited to the existing socket-based web flow.
**Severity:** SEVERE
**Labels:** `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 12 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.34)

### Label Analysis

**approach_lock** (confidence: 0.72):
  This matches the taxonomy's circular test-patch dependency subtype. If the F2P tests really require hunks 2 and 3, then an agent could correctly implement the requested invite API, controllers, routes, and client behavior yet still fail because it did not also modify an unrelated pending-membership OpenAPI file. That means the benchmark would reject a valid solution for not reproducing unrelated patch content. Confidence is not maximal because the dependency signal comes from cross-reference overlap rather than explicit assertion text, but it is strong enough to label.
  - Cross-reference analysis reports 7 circular dependencies: every listed F2P test (`test/groups.js` rescind/error/accept/reject invite and `test/utils.js` POST/PUT/DELETE schema-doc tests) depends on UNRELATED hunks [2, 3].
  - Hunks 2 and 3 are in `public/openapi/write/groups/slug/pending/uid.yaml` and were judged UNRELATED because they only change example values for the existing `pending` route, not the required invite routes.
  - The requirements are narrowly about authenticated invite endpoints at `/groups/{slug}/invites/{uid}` plus client/controller/OpenAPI wiring; they do not ask for edits to `public/openapi/write/groups/slug/pending/uid.yaml`.
**weak_coverage** (confidence: 0.61):
  The task specification is broad and detailed, but the visible F2P coverage is narrow. The tests clearly check route documentation and some invite-flow behavior, yet they do not appear to exercise major required areas such as client rewiring, controller response behavior, or several error/logging requirements. That means a partial fix could plausibly pass, making the benchmark easier and less representative of the full stated task.
  - The F2P suite lists only 7 tests: 4 behavior tests in `test/groups.js` and 3 schema-doc existence tests in `test/utils.js`.
  - Acceptance criterion 13 requires client-side use of the new routes and UI/error updates, but no listed F2P test targets `public/src/client/groups/details.js`, even though hunks 4 and 5 were marked REQUIRED.
  - Acceptance criterion 12 requires controller methods returning JSON HTTP 200 responses, but no listed F2P test explicitly targets `src/controllers/write/groups.js` (hunk 8).

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.82)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the current socket-based invitation flow and related API infrastructure, inferred that REST endpoints/controllers/OpenAPI docs needed to be added, began planning those edits, but appears to have stopped before completing or validating the implementation.
- **Behavior:** Methodical and plausible repository exploration with a correct high-level diagnosis, but the attempt appears unfinished and does not show a completed solution or signs of leakage.

> The trajectory shows a largely legitimate, exploratory debugging process rather than leakage. The agent starts by surveying the repository, then inspects the existing invitation implementation across sockets, API files, controllers, routes, and OpenAPI docs. It explicitly reasons that the missing work is to add API endpoints, controller methods, API-layer functions, and schema entries. That is a sensible derivation from the problem statement and codebase structure, not a suspicious jump to the e

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_NodeBB__NodeBB-445b70deda20201b7d9a68f7224da751b3db728c-v4fbcfae8b15e4ce5d132c408bca69ebb9cf146ed`

### Task Context

**Repository:** `NodeBB/NodeBB` (version )
**Core requirement:** Make the specified chats and users API endpoints consistently reject missing or malformed required input with `[[error:invalid-data]]`, while preserving correct successful responses for valid requests, including exact status values and escaped recent-chat teaser content.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 4 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.72):
  This shows a circular test-patch dependency: multiple F2P tests appear to require behavior from hunk 1 even though hunk 1 modifies an endpoint the task does not ask the agent to change. An agent could implement the stated requirements for getRawMessage, recent chats, and getPrivateRoomId correctly yet still fail because the tests traverse or depend on the extra listMessages validation. That is approach_lock under the taxonomy's 'tests require unrelated patch hunks' subtype. Confidence is moderate rather than maximal because the dependency is inferred from cross-reference/identifier overlap rather than direct assertion traces.
  - Cross-reference analysis reports circular dependencies for 3 F2P tests to UNRELATED hunk [1] with conf=0.80.
  - Test 'test/messaging.js | Messaging Library rooms should return not allowed error if user is not in room'  UNRELATED hunk [1].
  - Test 'test/messaging.js | Messaging Library rooms should fail to load recent chats with invalid data'  UNRELATED hunk [1].
**wide_tests** (confidence: 0.56):
  At least one F2P test checks unauthorized-room behavior ('not allowed error if user is not in room'), but the task specification only requires correct behavior for the authorized case and does not ask for any new or changed unauthorized-error contract. That makes this test broader than the written acceptance criteria, i.e. an extra test function beyond scope. This is separate from approach_lock: even before considering the unrelated hunk dependency, the test appears to verify behavior the problem statement does not require.
  - F2P includes test 'test/messaging.js | Messaging Library rooms should return not allowed error if user is not in room'.
  - Acceptance criterion 2 only specifies the success case: 'when both `mid` and `roomId` are valid and the caller is authorized, the correct message content is returned.'
  - Intent extraction explicitly marks as out of scope: 'changes to authorization behavior beyond the stated authorized raw-message case'.
**scope_creep** (confidence: 0.91):
  The patch changes behavior beyond the requested task. The clearest example is hunk 1, which adds validation to chatsAPI.listMessages even though that endpoint is outside the described scope. In addition, hunk 2 bundles extra validation for getMessage beyond the explicitly requested getRawMessage fix. These are behavioral expansions, not ancillary cleanup, so the task exhibits scope_creep.
  - Gold patch analysis: Has excess = True.
  - Hunk 1 [src/api/chats.js] is marked UNRELATED (conf=0.95): 'changes `chatsAPI.listMessages`, but the problem statement does not mention that endpoint.'
  - Gold patch analysis on hunk 2 notes: 'The same hunk also adds equivalent validation to `getMessage`, which is beyond the stated scope.'
**weak_coverage** (confidence: 0.62):
  The written task specification is broader than what the visible patch/tests measure. Important stated behaviorsexact user-status retrieval and escaped teaser contentdo not appear in the listed F2P tests and are not reflected in the patch hunks. That means an agent could ignore parts of the stated acceptance criteria and still likely pass, which is weak_coverage. Confidence is moderate because some of these behaviors could be covered elsewhere (for example by pre-existing P2P tests), but based on the provided analysis the benchmark does not fully measure all stated requirements.
  - Requirements include: 'User status queries return the correct status value.'
  - Requirements include: 'Recent chats returned must contain properly escaped teaser content.'
  - The listed F2P tests are only: invalid-data for rooms/raw message, not-allowed if user not in room, invalid recent-chats data, and invalid private-chat lookup.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.76)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the codebase and tests, inferred the validation/defaulting inconsistencies in chats and users APIs, formed a fix plan matching the intended behavior, but did not convert that plan into an applied patch or completed test-verified solution.
- **Behavior:** Reasonable repository-driven diagnosis with a near-correct fix plan, but incomplete execution and no strong evidence of benchmark leakage.

> The trajectory shows a largely legitimate debugging flow: the agent started from the problem statement, explored the repository structure, identified the relevant API files (`src/api/chats.js` and `src/api/users.js`), searched for the named methods, and inspected tests to understand expected behavior. It then articulated a concrete fix plan that lines up closely with the real issue: adding invalid-data checks for missing identifiers and pagination inputs, and defaulting certain parameters from `

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_NodeBB__NodeBB-70b4a0e2aebebe8f2f559de6680093d96a697b2f-vnan`

### Task Context

**Repository:** `NodeBB/NodeBB` (version )
**Core requirement:** Enhance `sortedSetsCardSum` so it can return the summed count of elements across one or more sorted sets within optional inclusive `min`/`max` score bounds, including unbounded ranges.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 5 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The gold patch includes behavioral changes outside the requested database utility enhancement. Hunks 0 and 1 refactor an accounts helper to consume the new API and adjust downstream handling, but the task asks for `sortedSetsCardSum` to support optional inclusive min/max bounds and consistent backend behavior. Those controller changes are not ancillary cleanup like imports or formatting; they alter application behavior at a separate call site. That is classic scope expansion in the patch.
  - Hunk 0 in `src/controllers/accounts/helpers.js` is marked UNRELATED (conf=0.98): it changes a caller to use the enhanced `sortedSetsCardSum` API for `best` and `controversial` account statistics.
  - Hunk 1 in `src/controllers/accounts/helpers.js` is marked UNRELATED (conf=0.99): it removes post-processing reductions that were only needed because hunk 0 changed those values from arrays to scalar sums.
  - The stated scope is to enhance `sortedSetsCardSum` itself across Redis/Postgres/Mongo; intent extraction explicitly lists controller changes as out of scope.
**approach_lock** (confidence: 0.68):
  The reported circular dependency means the F2P test is not satisfied solely by implementing the requested `sortedSetsCardSum` behavior in the database backends; it also depends on unrelated controller refactoring. If that dependency is real, then an agent could produce a valid solution to the described problem—updating `sortedSetsCardSum` across Redis, Postgres, and Mongo—yet still fail because it did not modify `accounts/helpers.js`, which the problem does not require. That fits the circular test-patch dependency subtype of approach_lock. Confidence is moderate rather than maximal because the direct test-level analysis still called the test broadly aligned, so the strongest evidence here comes from cross-reference linkage rather than explicit assertion text.
  - Cross-reference analysis reports a circular dependency: test `sortedSetsCardSum() should work with min/max` → UNRELATED hunks [0, 1] (conf=0.90).
  - The cross-reference note explicitly states: "This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for."
  - Hunks 0 and 1 are both in `src/controllers/accounts/helpers.js` and were judged UNRELATED to the task, which is to implement `sortedSetsCardSum` behavior in backend files (hunks 2, 3, 4).

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.86)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement pointed the agent toward `sortedSetsCardSum`; the agent explored the existing database implementations, noticed that score-range logic already existed in `sortedSetCount`, generalized that logic into `sortedSetsCardSum` across all backends, then updated a higher-level caller (`getCounts`) to use the new aggregation capability and validated the behavior with self-constructed tests.
- **Behavior:** Methodical and evidence-driven: the agent explored the codebase, formed a concrete hypothesis from existing related functions, implemented backend-specific fixes plus the caller cleanup, and validated with iterative self-testing.

> The trajectory shows a credible, stepwise debugging and implementation process rather than shortcutting to a memorized answer. The agent begins by exploring repository structure and the existing implementation, then specifically inspects `sortedSetCount` and `sortedSetsCardSum` across the database backends to understand current behavior and how score filtering is already implemented elsewhere. It then inspects the higher-level caller (`getCounts`) and correctly identifies the inefficiency and mi

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_NodeBB__NodeBB-76c6e30282906ac664f2c9278fc90999b27b1f48-vd59a5728dfc977f44533186ace531248c2917516`

### Task Context

**Repository:** `NodeBB/NodeBB` (version )
**Core requirement:** Add validation for plugin identifiers during plugin activation so malformed plugin IDs are rejected instead of being processed.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 123 of 172 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.99):
  The issue is narrowly about validating plugin identifiers during activation in Plugins.toggleActive and rejecting invalid IDs with [[error:invalid-plugin-id]]. The patch, however, includes a large amount of unrelated behavioral work: a separate flag-limit feature, topic UI changes, dependency/version churn, and broad localization updates. Since these are behavioral changes outside the stated acceptance criteria, this is clear scope creep rather than mere ancillary support work.
  - Gold patch analysis: Has excess=True with 172 hunks total, but only hunk 169 is REQUIRED; 123 hunks are marked UNRELATED.
  - Hunk 167 in src/flags.js is UNRELATED and implements per-day flagging limits, a separate moderation feature.
  - Hunk 170 in src/views/admin/settings/reputation.tpl is UNRELATED and adds UI for daily flag limits.
**approach_lock** (confidence: 0.60):
  This looks like the circular test-patch dependency subtype of approach_lock. The benchmark's single F2P test is on-topic, but the analysis indicates it depends on a large set of unrelated hunks from the mixed PR. If true, an agent could correctly implement the requested validation behavior in Plugins.toggleActive yet still fail because it did not also reproduce unrelated changes bundled into the same upstream patch. That would make the task unfair by requiring more than the described fix. Confidence is moderate rather than maximal because the dependency signal is indirect, but the provided cross-reference evidence is strong enough to flag.
  - Cross-reference analysis reports a circular dependency: test 'test/plugins.js | Plugins install/activate/uninstall should error if plugin id is invalid' exercises 123 UNRELATED hunks (conf=0.95).
  - The same F2P test is linked not just to the REQUIRED fix hunk 169, but also to unrelated hunks such as hunk 0 (install/data/defaults.json), hunk 167 (src/flags.js), hunk 170 (src/views/admin/settings/reputation.tpl), and hunk 171 (src/views/partials/data/topic.tpl).
  - Only hunk 169 is classified REQUIRED for the described bug, so any dependency of the F2P test on the many unrelated hunks indicates test/patch entanglement.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.89)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to have latched onto contaminated benchmark metadata or gold-patch scope-creep about daily flag limits, explored that unrelated subsystem in depth, and never reoriented to the actual plugin activation validation bug, leading to a complete miss on the real task.
- **Behavior:** The agent performed coherent but entirely misdirected exploration, strongly anchored to the contaminated gold-patch topic rather than the real bug, resulting in a no-intent failure on the actual task.

> The agent did not work on the stated plugin-identifier validation bug at all. Instead, from Step 1 onward it explicitly reframed the task as implementing daily flag limits for posts/users, then explored only the flags subsystem, defaults, meta config, database counters, error translations, and API support for remaining flag counts. That thematic focus closely matches the unrelated dominant content in the provided gold patch contamination (post/user flag-per-day limits and related translations), 

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 123 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_NodeBB__NodeBB-b1f9ad5534bb3a44dab5364f659876a4b7fe34c1-vnan`

### Task Context

**Repository:** `NodeBB/NodeBB` (version )
**Core requirement:** Extend `sortedSetsCardSum` in all database adapters so it correctly counts elements across one or more sorted sets with optional inclusive score bounds `min` and `max`.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 7 of 10 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.72):
  This fits the taxonomy's circular test-patch dependency subtype. The task specification asks only for adapter-level `sortedSetsCardSum` support, so an implementation that correctly updates hunks 7-9 should be sufficient. However, the pipeline reports that the sole F2P test is coupled to seven UNRELATED hunks. If that dependency is real, then a valid solution confined to the required adapter files would still fail, meaning the benchmark is rejecting solutions for not reproducing unrelated patch content rather than for incorrect observable behavior on the stated problem.
  - Requirements restrict the task to extending `sortedSetsCardSum` in `src/database/mongo/sorted.js`, `src/database/postgres/sorted.js`, and `src/database/redis/sorted.js` with optional `min`/`max` range counting.
  - Cross-reference analysis reports a circular dependency: test `sortedSetsCardSum() should work with min/max` → UNRELATED hunks `[0, 1, 2, 3, 4, 5, 6]` with confidence `0.95`.
  - The linked UNRELATED hunks include non-adapter behavior such as topic vote visibility changes (hunks 0, 1, 2, 3, 6) and account-stats caller migration/cleanup (hunks 4, 5), none of which are part of the stated acceptance criteria.
**scope_creep** (confidence: 0.98):
  The gold patch clearly contains behavioral changes beyond the requested fix. The issue and requirements are narrowly about adding optional `min`/`max` support to `sortedSetsCardSum` in the Mongo, Postgres, and Redis adapters. In contrast, seven hunks modify unrelated API schema, client vote UI behavior, topic controller output, and account-statistics caller logic. These are not ancillary edits like imports or formatting; they introduce or alter behavior outside the problem scope, so the task exhibits scope creep.
  - Hunk 0 (`public/openapi/read/topic/topic_id.yaml`) adds `voteVisibility` to the OpenAPI schema and is marked UNRELATED.
  - Hunks 1-3 (`public/src/client/topic/votes.js`) add client-side vote-visibility gating and error-handling changes, all marked UNRELATED.
  - Hunks 4-5 (`src/controllers/accounts/helpers.js`) change a caller to use `db.sortedSetsCardSum(..., min, max)` and adjust downstream handling; both are marked UNRELATED because the task only requires implementing adapter behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.97)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to have recalled or accessed a broader contaminated patch/PR involving both vote-visibility UI changes and sorted-set count changes, then used superficial repository exploration to validate and apply that remembered solution rather than deriving the fix solely from the benchmark prompt.
- **Behavior:** The agent showed targeted, confirmatory exploration consistent with prior knowledge of the full contaminated patch, not genuine task-bounded debugging.

> The trajectory shows strong evidence that the agent was operating from knowledge of the broader gold patch rather than solving only the stated task. The benchmark problem is narrowly about extending `sortedSetsCardSum` in the three database adapters to support optional `min`/`max` bounds. However, from Step 0 the agent states it will fix both "vote visibility controls and database performance issues," introducing an unrelated feature area that is absent from the problem statement but present in 

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 7 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_NodeBB__NodeBB-b398321a5eb913666f903a794219833926881a8f-vd59a5728dfc977f44533186ace531248c2917516`

### Task Context

**Repository:** `NodeBB/NodeBB` (version )
**Core requirement:** Introduce and consistently enforce a new global `chat:privileged` permission so that only authorized users can initiate direct chats or chat-room invites involving privileged users, and expose that capability through the admin privileges UI and the user profile API.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 5 of 23 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.58):
  This matches the circular test-patch dependency subtype of approach_lock. The pipeline says multiple F2P tests depend on unrelated patch hunks, so an agent could implement the requested privileged-chat behavior correctly yet still fail unless it also reproduces unrelated rate-limit/header changes. Confidence is moderate rather than high because the dependency evidence is cross-reference based rather than assertion-level, but it is still strong enough to indicate the tests are not cleanly isolated to the requested behavior.
  - Cross-reference analysis reports 4 circular dependencies and explicitly says: "This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for."
  - Test 'test/middleware.js | Middlewares expose should expose privilege set' is linked to UNRELATED hunks [6, 19] (conf=0.90).
  - Test 'test/categories.js | Categories privileges should load global user privileges' is linked to UNRELATED hunks [2, 4, 6, 19] (conf=0.95).
**scope_creep** (confidence: 0.94):
  The problem is narrowly about adding and enforcing the new 'chat:privileged' permission, exposing it in i18n/admin privileges, updating profile API canChat, and extending privileges.global.can. The gold patch also includes several unrelated behavioral changes: a chat rate-limit refactor and a header-sanitization change. These are not ancillary import/cleanup edits; they change behavior outside the stated task, so scope_creep clearly applies.
  - Gold patch analysis: Has excess = True with 5 UNRELATED hunks.
  - Hunk 2 in src/api/chats.js: rate-limiter refactor ('rateLimitExceeded(caller, field)') is marked UNRELATED.
  - Hunk 3 in src/api/chats.js: generalizes chat rate-limit state from lastChatMessageTime to an arbitrary session field; marked UNRELATED.
**weak_coverage** (confidence: 0.92):
  The tests cover only a small slice of the requested behavior, mostly privilege exposure and i18n visibility. Core acceptance criteria—actual privileged-target chat enforcement, invite rejection, canChat API exposure, and the new privileges.global.can API contract—are not represented in the F2P suite provided here. That means a partial fix could likely pass the benchmark without implementing much of the intended functionality, which is classic weak_coverage.
  - F2P test analysis lists only 4 aligned tests: middleware privilege exposure, categories global user privileges, categories global group privileges, and i18n key structure.
  - No F2P test is identified for direct-chat rejection of unauthorized users with '[[error:no-privileges]]' (acceptance criterion 2).
  - No F2P test is identified for invite-flow per-UID checking via messaging.canMessageUser (acceptance criterion 4).

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.75)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the requirements, explored the relevant chat/privilege/profile code paths, tried to reproduce the bug, then formulated an implementation plan centered on `canMessageUser`, privilege checks, middleware, and profile API exposure.
- **Behavior:** Systematic repository exploration and feature-driven debugging, with no clear leakage indicators in the observed trajectory.

> The visible trajectory looks like legitimate problem-solving rather than benchmark leakage. The agent began by exploring the repository structure, then examined the messaging/chat implementation, privileges system, profile/user-data flow, middleware checks, and the existing privileged-user helper. It also attempted to reproduce the issue with scripts before falling back to source inspection when that failed, which is a natural debugging pattern. The agent's plan evolved from understanding the cu

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 5 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_NodeBB__NodeBB-cfc237c2b79d8c731bbfc6cadf977ed530bfd57a-v0495b863a912fbff5749c67e860612b91825407c`

### Task Context

**Repository:** `NodeBB/NodeBB` (version )
**Core requirement:** Expose avatar background color options through a publicly accessible `User.getIconBackgrounds` function so avatar background color customization can be supported.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 13 of 14 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.94):
  This is a circular test-patch dependency. The specification says the task is to expose a real callable `User.getIconBackgrounds` API on the exported `User` object, and the patch analysis says hunk 13 alone satisfies that contract. But the F2P tests exercise behavior tied to many UNRELATED hunks, especially broader icon-generation and saved-background handling. That means an agent could implement the specified API correctly and still fail because the tests demand additional out-of-scope code paths. The tests are therefore not just checking the required outcome; they require extra implementation/integration behavior beyond the stated problem.
  - Only hunk 13 is marked REQUIRED; hunks 0-12 are marked UNRELATED to the stated task.
  - Cross-reference analysis: both F2P tests are reported as exercising UNRELATED hunks [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] with conf=0.95.
  - Acceptance criteria are narrowly about exporting `User.getIconBackgrounds` from `src/user/data.js`, preserving it on `module.exports`, defaulting `uid` to `0`, and returning a Promise of color strings.
**wide_tests** (confidence: 0.87):
  The tests go beyond the specified acceptance criteria. The task specification is about making `User.getIconBackgrounds(uid=0)` publicly exported and callable, with a Promise-returning API. The F2P tests instead verify broader user-icon behavior and invalid-background fallback, which belong to persistence/integration/assignment logic that the problem explicitly marks out of scope. So the benchmark is testing more than what the task asks for.
  - Out-of-scope section explicitly excludes `persistence of a user's chosen color`, `how a selected color is stored`, and `changes to the existing username-based automatic assignment algorithm`.
  - Hunk 10 (`src/socket.io/user/picture.js`) stores and validates `'icon:bgColor'`, and hunk 12 (`src/user/data.js`) changes icon generation to read saved `'icon:bgColor'` and alter automatic assignment behavior; both are marked UNRELATED.
  - One F2P test is `User hash methods should return a valid background, even if an invalid background colour is set`, which targets invalid stored background handling rather than the exported API contract.
**scope_creep** (confidence: 0.98):
  The gold patch contains substantial behavioral work unrelated to the stated task. Instead of only exporting `User.getIconBackgrounds` correctly, it also adds UI strings, client-side settings UI, controller exposure, persistence/validation of a chosen color, and changes to icon-generation behavior. These are not ancillary edits like imports or formatting; they are new product behavior outside the requested scope.
  - Gold patch analysis: `Has excess: True | Hunks: 14 (REQUIRED=1, ANCILLARY=0, UNRELATED=13)`.
  - UNRELATED hunk 0 adds a UI translation string for avatar background colour.
  - UNRELATED hunk 1 updates OpenAPI/config schema for `iconBackgrounds`.
**weak_coverage** (confidence: 0.56):
  The stated API contract appears only partially covered by the tests. The listed F2P tests focus on hash/icon behavior, not on directly verifying that `User.getIconBackgrounds` is publicly exported, survives `module.exports`, defaults `uid` to `0`, and returns a Promise. That means parts of the formal acceptance criteria may be untested, so a solution could satisfy the tested behavior while still violating some of the stated API requirements. Confidence is moderate because assertion-level details are not provided.
  - Acceptance criteria require: exported `User.getIconBackgrounds`, no overwrite/shadowing on `module.exports`, default `uid` to `0`, Promise return, and resolution to an array of CSS color strings.
  - The only two F2P tests listed are about `User hash methods` returning valid backgrounds and invalid background-colour fallback.
  - No F2P test title directly mentions `User.getIconBackgrounds`, export accessibility, `uid=0`, or Promise-return semantics.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.93)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the feature request, inspected the user data and picture-related code, noticed existing avatar background logic, then expanded into adjacent frontend/socket/template areas as if trying to implement the broader product feature. That scope expansion prevented it from delivering the narrower server-side export fix that the fail-to-pass tests required.
- **Behavior:** Legitimate exploratory debugging with scope drift into broader feature areas, but no completed fix and no meaningful leakage indicators.

> The trajectory shows normal exploratory behavior rather than leakage. The agent began by reading relevant user/avatar files, identified that `src/user/data.js` already contained an `iconBackgrounds` array and the username-based background-color logic, and then broadened its search into socket handlers, client account-edit code, templates, and config plumbing. That exploration is consistent with a genuine attempt to understand the feature request. However, there is no evidence that the agent form

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 13 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_NodeBB__NodeBB-f2082d7de85eb62a70819f4f3396dd85626a0c0a-vd59a5728dfc977f44533186ace531248c2917516`

### Task Context

**Repository:** `NodeBB/NodeBB` (version )
**Core requirement:** Migrate raw post and post-summary retrieval from the legacy socket methods to Write API HTTP endpoints, while preserving the existing access behavior and updating client-facing callers to use the new routes.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 8 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.65):
  This matches the circular test-patch dependency subtype of approach_lock. The benchmark's own analysis says the F2P tests depend on hunk [3], even though that hunk is outside the stated task scope. If so, an agent could correctly implement the requested migration to `GET /api/v3/posts/:pid/raw` and `/summary`, preserve the required access rules, and still fail because it did not make the unrelated `postsAPI.get` change. That means the tests are not measuring only the requested behavior.
  - Cross-reference analysis reports circular dependencies for all 5 F2P tests, each linked to UNRELATED hunk [3] in `src/api/posts.js` (conf=0.80).
  - Hunk [3] is explicitly classified UNRELATED: it changes the existing `postsAPI.get` path for normal post retrieval to return `null` earlier when the post is missing or unreadable.
  - The problem/requirements ask for new Write API routes, controllers, `postsAPI.getSummary`, `postsAPI.getRaw`, client migrations, and raw socket-handler removal; they do not ask to alter the general `postsAPI.get` behavior.
**scope_creep** (confidence: 0.84):
  The gold patch includes at least one behavioral change beyond the requested migration. Modifying the general `postsAPI.get` path is not ancillary plumbing like imports or refactoring; it changes runtime behavior outside the feature described in the issue. That is classic scope creep.
  - Gold patch analysis: hunk [3] in `src/api/posts.js` is marked UNRELATED (conf=0.78).
  - The hunk changes behavior of the pre-existing general `postsAPI.get` method for ordinary post retrieval, making it return `null` earlier when a post is missing or unreadable.
  - The stated acceptance criteria are limited to adding `getSummary`/`getRaw`, new write-API routes/controllers, client caller migration, and removal of the obsolete raw socket handler.
**weak_coverage** (confidence: 0.78):
  The task specification is a migration to REST/Write API, but the visible F2P coverage is concentrated on legacy raw/summary access semantics. That leaves substantial required behavior unverified: route exposure, HTTP status/payload mapping, client-facing caller changes, and raw socket-handler removal. A partial fix could plausibly pass the tests without completing the full migration, which makes the task easier than its written requirements.
  - Acceptance criteria require route registration for `GET /api/v3/posts/:pid/raw` and `GET /api/v3/posts/:pid/summary`, controller translation of `null` to HTTP 404 `[[error:no-post]]`, client-path migration, and removal of the obsolete raw socket handler.
  - The listed F2P tests are only 5 pre-existing tests in `test/posts.js`, all named around "Post's socket methods ... raw post/summary"; none explicitly target the new write-API routes, controller HTTP responses, or client updates.
  - Several REQUIRED hunks implement behavior that appears untested by F2P tests: hunk [0] `public/src/client/topic.js`, hunk [1] `public/src/client/topic/postTools.js`, hunk [5] `src/controllers/write/posts.js`, hunk [6] `src/routes/write/posts.js`, and hunk [7] `src/socket.io/posts.js`.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.82)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the relevant API/controller/route/socket/client files, investigated privilege and response-handling behavior, searched for usages of the legacy socket methods, and then attempted to migrate those flows to new Write API endpoints; it likely failed on implementation details or coverage gaps rather than from lack of intent.
- **Behavior:** Genuine repo-guided implementation attempt that targeted the right migration, but likely missed details or failed to complete the exact expected fix.

> This trajectory looks like a genuine implementation attempt rather than leakage. The agent began by exploring the repository structure, then specifically inspected API routes, write controllers, the posts module, privileges, helpers, and call sites of the legacy socket methods. That is the expected workflow for solving this task from first principles. It also tried to understand behavior by creating a script, hit configuration issues, and fell back to reading analogous code paths and auth/respon

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-2dce79ea4451ad88d6bfe94da22e7f2f988efa60`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Add clear visual sender-verification indicators to the Proton Mail list interface so authenticated Proton senders can be quickly distinguished from external senders.
**Severity:** SEVERE
**Labels:** `scope_creep`, `weak_coverage`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 28 of 60 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The task asks for sender-verification indicators in the mail list interface and explicitly scopes the work around list rendering and supporting helper logic. The gold patch goes substantially beyond that by propagating badge behavior into message headers, recipient components, and the message details modal. Those are behavioral changes, not mere cleanup or typing support, so this is clear scope expansion in the patch itself.
  - Gold patch analysis marks 28 behavioral hunks as UNRELATED: hunks 22-49.
  - These UNRELATED hunks are in message-view files, not the list interface named by the task: HeaderCollapsed.tsx (22-26), HeaderExpanded.tsx (27-31), MessageDetailsModal.tsx (32-33), MailRecipientItemSingle.tsx (34-37), RecipientItem.tsx (38-41), RecipientItemLayout.tsx (42-45), RecipientItemSingle.tsx (46-49).
  - The stated interface and requirements focus on list-sender code only: ItemSenders, ProtonBadge, ProtonBadgeType, isProtonSender, and getElementSenders.
**weak_coverage** (confidence: 0.94):
  The tests cover only the helper-layer logic for sender extraction and Proton detection. They do not verify that the mail list actually renders badges, that ItemSenders is integrated into the list layouts, or that the new badge components behave as specified. As a result, an agent could implement only getElementSenders/isProtonSender (or otherwise satisfy those helper tests) and still pass without delivering the main UI behavior described by the task. That makes the benchmark easier and under-measures the stated acceptance criteria.
  - All 6 F2P tests are helper tests only: four in src/app/helpers/recipients.test.ts and two in src/app/helpers/elements.test.ts.
  - No F2P tests target the new UI components or list integration points required by the task: ItemSenders (hunk 18), ProtonBadge (hunk 19), ProtonBadgeType/PROTON_BADGE_TYPE (hunk 20), VerifiedBadge integration (hunk 21), or the Item/Item*Layout rendering changes (hunks 4, 5, 10, 11, 16, 17).
  - Acceptance criteria include visible mail-list badge rendering and component behavior: 'show a visible Proton verification badge', 'ItemSenders should render sender information', 'ProtonBadge should render a Proton badge', and 'ProtonBadgeType ... enum should include a VERIFIED value'.
**approach_lock** (confidence: 0.50):
  There is evidence of a circular test-patch dependency: helper tests appear to depend on unrelated message-view badge changes that the problem does not ask for. If that dependency is real, then an agent could implement the requested list-only behavior correctly yet still fail unless it also reproduces out-of-scope patch work. I assign this with only moderate confidence because the cross-reference is overlap-based rather than a direct test assertion trace, but it is still enough to flag a possible approach-locking contamination.
  - Cross-reference analysis reports 6 circular dependencies: every F2P test is linked to UNRELATED hunks, e.g. recipients.test cases link to unrelated hunks [22-49] and elements.test cases link to unrelated hunks [22, 25, 33, 47].
  - The cross-reference summary explicitly states: 'This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for.'
  - Those linked hunks are all outside the requested list-interface scope and were independently classified as UNRELATED in the gold patch analysis.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.90)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, explored the relevant mail UI and helper files, formed a plausible implementation plan based on the provided PR-style requirements, but stopped before producing and testing any substantive code.
- **Behavior:** Legitimate exploratory behavior with a sensible plan, but the agent did not follow through with an implemented or tested fix.

> The trajectory shows normal, progressive repository exploration rather than a leaked-answer pattern. The agent started by inspecting the mail app structure, then drilled into the exact areas implicated by the task: list components, row/column layouts, the existing VerifiedBadge, helper logic in elements.ts, message header components, shared Recipient interfaces, and the badge asset. That is the kind of search path a legitimate agent would take for this feature request. The later plan to create I

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 28 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-32ff10999a06455cb2147f6873d627456924ae13`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Update the Contact Group Details modal so its count label refers to email addresses rather than members, with correct localized singular/plural wording.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 35 of 36 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.91):
  This is a circular test-patch dependency. A valid minimal solution would only need the required wording/pluralization change in ContactGroupDetailsModal, but the sole F2P test is coupled to many unrelated hunks across modal plumbing, recipient rendering, and even other contact views. That means an agent could correctly satisfy the stated bug report and still fail unless it reproduces the gold patch's broader refactor. The tests are therefore locking onto the patch approach/surrounding implementation rather than purely the requested observable behavior.
  - Cross-reference analysis reports a circular dependency: test 'containers/contacts/group/ContactGroupDetailsModal.test.tsx | should display a contact group' exercises UNRELATED hunks [4, 5, 6, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35] (conf=0.95).
  - The problem only asks to rename the Contact Group Details modal count label from 'members' to localized singular/plural 'email address/email addresses' (AC1-AC5).
  - Many linked hunks are unrelated implementation changes, e.g. hunk 12 adds new modal props/interfaces (onCompose/onCloseContactDetailsModal), hunks 28-32 change RecipientDropdownItem behavior, and hunks 20-22 refactor ContactMergeDetailsModal.
**scope_creep** (confidence: 0.99):
  The patch massively exceeds the issue scope. Instead of a localized label-text fix inside the Contact Group Details modal, it bundles broad behavioral changes across unrelated files and features, including new modal interaction plumbing, recipient row UI changes, and merge-details refactors. These are not ancillary edits; they introduce or alter behavior outside the requested bug fix. This is a clear case of scope creep.
  - Gold patch analysis: Has excess = True; 36 hunks total, with only 1 REQUIRED hunk and 35 UNRELATED hunks.
  - The only REQUIRED hunk is hunk 13 in ContactGroupDetailsModal, which changes the localized count text from member/members to email address/email addresses.
  - UNRELATED behavioral changes include hunk 5 (DrawerContactView compose plumbing), hunks 6-9 (ModalHeader API/internals expanded to arbitrary actions), hunks 20-22 (ContactMergeDetailsModal changes), and hunks 28-32 (RecipientDropdownItem feature/UI changes).
**weak_coverage** (confidence: 0.46):
  Coverage appears thin relative to the specification. The task requires singular/plural correctness and consistency across all occurrences in the modal, but the recorded F2P coverage is just one generic render/display test. With no explicit singular-case test and no clear evidence that every required count location is checked, a partial fix could plausibly pass. Confidence is moderate rather than high because the exact assertions of the existing test are not visible.
  - Acceptance criteria require both singular ('email address') and plural ('email addresses') behavior, consistency wherever the count appears in the modal, and localization/pluralization via i18n.
  - F2P test analysis shows only one aligned test: 'containers/contacts/group/ContactGroupDetailsModal.test.tsx | should display a contact group'.
  - No assertion-level coverage is extracted for that F2P test, and there is no separate listed test for the singular-count case or for multiple display sites within the modal.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.95)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent did broad repository exploration, then appears to pivot from the stated issue to a hidden larger PR context. That hidden context drove it toward unrelated compose/header/recipient refactors that match the contaminated upstream patch, and the weak evaluation coverage allowed the resulting overbroad fix path to still pass.
- **Behavior:** Surface-level exploration followed by a highly specific, overbroad fix plan that tracks the contaminated gold patch rather than the stated bug, indicating likely benchmark leakage.

> This does not look like a clean, task-derived fix. The user-visible requirement was narrow: change the Contact Group Details modal label from “members” to localized singular/plural “email address(es).” A genuine solution would likely focus on ContactGroupDetailsModal and i18n/pluralization. Instead, after some nominal exploration, the agent began pursuing a much broader set of changes that align strikingly with the contaminated gold patch: updating useContactModals to support onCompose, moving a

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 35 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-369fd37de29c14c690cb3b1c09a949189734026f`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Implement support for discovering, adding, suggesting during setup, and managing public holidays calendars across Calendar Settings and related calendar UI, gated by the `HolidaysCalendars` feature flag.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 12 of 110 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.84):
  This matches the taxonomy's circular test-patch dependency subtype. The problem asks for public-holidays calendar support, but the F2P tests are reported as depending on unrelated generic component refactors and even mail-surface changes. That means an agent could implement the described holiday-calendar behavior correctly, without adopting those out-of-scope refactors, and still fail the benchmark. The lock is not that tests check observable outputs too strictly; it is that they appear to require unrelated patch hunks to pass.
  - Cross-reference analysis flags circular dependencies for every F2P test; e.g. `components/country/CountrySelect.helpers.test.ts | should return expected dropdown options` exercises UNRELATED hunks [30, 31, 32, 42, 43, 44, 45, 46, 47, 48, 49, 50] (conf=0.95).
  - Cross-reference analysis also links `containers/calendar/holidaysCalendarModal/tests/HolidaysCalendarModal.test.tsx | should pre-select the default holidays calendar based on time zone` to UNRELATED hunks [31, 32, 42, 43, 44, 45, 46, 47, 48, 49, 50] (conf=0.95).
  - Several of those unrelated hunks are broader generic-component changes, not public-holidays behavior: hunks 44-47 modify `SearchableSelect` API/behavior, hunks 42-43 modify generic `Option`, and hunks 49-50 modify generic `Spotlight`.
**scope_creep** (confidence: 0.90):
  The gold patch includes behavior-affecting changes beyond the requested feature. The task is about discovering, suggesting, and managing public holidays calendars in calendar settings/setup, but the patch also touches unrelated mail-event code and generic component APIs/behavior. Those are not merely imports or formatting; they broaden the patch beyond the task's scope, so scope_creep applies.
  - Gold patch analysis: `Has excess: True` with 12 UNRELATED hunks.
  - UNRELATED hunks 30-32 change mail extra-event files (`applications/mail/src/app/components/message/extras/ExtraEvents.tsx`, `.../ExtraEvent.tsx`), which are outside the named calendar settings/setup surfaces.
  - UNRELATED hunks 42-50 make broader generic UI changes in `packages/components/components/option/Option.tsx`, `selectTwo/SearchableSelect.tsx`, and `spotlight/Spotlight.tsx`; hunk 45 removes the `uniqueSearchResult` prop and hunk 47 changes filtered-option behavior.
**weak_coverage** (confidence: 0.87):
  The task specification is broad, but the F2P suite verifies only a subset of it. A solver could miss important required behavior—especially feature-flag gating, early loading, sidebar discoverability, setup-time creation, or the mandated helper flow—and still pass the visible F2P tests. That makes the benchmark easier and less representative, which is the hallmark of weak_coverage.
  - Acceptance criteria cover many areas: loading `useHolidaysDirectory` before render, prop threading through `CalendarSettingsRouter`/`CalendarContainerView`/`CalendarSidebar`/`CalendarSubpageHeaderSection`, feature-flag gating in `MainContainer`, setup creation/skip logic in `CalendarSetupContainer`, sidebar entry + spotlight, dedicated settings sections, and helper/data-flow requirements.
  - F2P tests are only 12 total and focus on three areas: `CountrySelect` helper dropdown behavior, `HolidaysCalendarModal` preselection/duplicate messaging, and one `CalendarsSettingsSection` sectioning test.
  - There are no listed F2P tests directly targeting criteria such as the `MainContainer` feature flag enablement (criterion 3), pre-render loading gate in `CalendarSettingsRouter` (criterion 1), sidebar menu/spotlight behavior (criteria 6-7), setup auto-creation/skip logic in `CalendarSetupContainer` (criteria 4-5), or the exact `setupHolidaysCalendarHelper` flow/interface (criteria 14-15).

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.97)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent parsed the requirements, explored the calendar app structure and existing holidays-calendar code paths to build context, recognized that multiple components would need changes, but then stopped before making any edits or validating a fix.
- **Behavior:** Legitimate exploratory analysis with no implementation follow-through; failed due to non-completion/skill gap rather than leakage.

> The trajectory shows a normal exploratory start but no actual problem resolution. The agent clearly read the task and then systematically inspected the relevant parts of the repository: main containers, setup flow, calendar UI, settings, feature flags, and existing holidays-related helpers/modal code. That exploration is consistent with genuine problem-solving rather than leakage. However, the agent never progressed to implementation: there is no code edit, no patch content, no test execution, a

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 12 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-428cd033fede5fd6ae9dbc7ab634e010b10e4209`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Fix the photo recovery flow so it recovers photo items from both regular and trashed sources in one operation, handles core recovery errors by failing consistently, and automatically resumes if recovery was previously in progress.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 12 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.76):
  This matches the circular test-patch dependency subtype of approach_lock. The recovery tests exercise code paths that depend on unrelated move-link payload/schema changes. That means an agent could implement the requested recovery behavior correctly yet still fail the F2P suite unless it also reproduces the unrelated payload rename. The tests are therefore not measuring only the stated task; they implicitly require out-of-scope patch content.
  - Cross-reference analysis reports circular dependencies for all 7 F2P tests, each linking to UNRELATED hunks [0, 9] with conf=0.90.
  - Hunk 0 and hunk 9 rename a move-link API payload field from `SignatureAddress` to `NameSignatureEmail`, while the problem/requirements are only about photo recovery across regular+trashed items, readiness gating, failure handling, counting, and auto-resume.
  - The cross-reference summary explicitly states: "This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for."
**scope_creep** (confidence: 0.93):
  The patch includes behavioral/API-contract changes beyond the issue's scope. The task is narrowly about photo recovery using regular and trashed items, readiness/decryption gating, progress/failure accounting, failure-state transitions, and resume-on-init. Renaming move-link payload fields and changing the shared move-link interface are separate behavior changes not requested by the problem.
  - Gold patch analysis marks 3 hunks as UNRELATED: hunk 0, hunk 9, and hunk 11.
  - Hunk 0 (`applications/drive/src/app/store/_links/useLinksActions.ts`) and hunk 9 (`packages/drive-store/store/_links/useLinksActions.ts`) rename a move-link payload field outside the recovery flow.
  - Hunk 11 (`packages/shared/lib/interfaces/drive/link.ts`) updates the shared `MoveLink` interface, which the analysis calls "outside the described recovery-specific acceptance criteria."
**weak_coverage** (confidence: 0.54):
  The tests appear to cover the recovery hook behavior, but not the full stated contract around preserving default enumeration behavior outside the explicit trashed-inclusive mode. A partial fix that makes recovery pass while globally changing listing defaults could plausibly satisfy these F2P tests. That makes the benchmark somewhat easier than the full requirements imply.
  - Acceptance criterion 2 requires an explicit trashed-inclusive enumeration mode while "keeping the default behavior unchanged when not explicitly requested."
  - That requirement is implemented in hunks 1-5 and 10 (`useLinksListing.tsx` and `packages/shared/lib/api/drive/folder.ts`), but all listed F2P tests are only in `src/app/store/_photos/usePhotosRecovery.test.ts`.
  - None of the 7 F2P test titles mention default/non-`showAll` listing behavior or directly target the listing/API modules where the default-preservation contract lives.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.76)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement led the agent to inspect the photo recovery hook, then the links-listing layer and folder API to understand how regular vs. trashed items are loaded. From that inspection it inferred a `ShowAll`-style plumbing change and related recovery updates, briefly examined move-link typing, then began implementing those changes but stopped before finishing the core recovery logic or validating against tests.
- **Behavior:** Methodical exploration with a plausible hypothesis and partial implementation plan, but the agent did not complete or validate a fix; weak hint of memorized scope-creep detail, not enough to call leakage.

> The trajectory shows mostly legitimate exploration rather than a direct jump to the answer. The agent started from the problem statement, navigated into the drive/photos store, inspected `usePhotosRecovery.ts`, then followed dependencies into `useLinksListing`, the folder query API, move-link actions/interfaces, and the trash-listing path. That is a plausible debugging path for this bug. It also formulated a coherent hypothesis: add a listing mode that includes trashed items, use trash cache sta

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-5f0745dd6993bb1430a951c62a49807c6635cd77`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Fix the Bitcoin payment flow so it is only offered in the allowed contexts, enforces Bitcoin amount limits, shows the correct loading/error/success UI, and validates chargeable tokens on the specified polling schedule.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 30 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.88):
  This fits the circular test-patch dependency subtype of approach_lock. The task specification is about Bitcoin payment behavior, but the F2P tests are reported to require unrelated patch hunks, especially test-infrastructure changes in hunks 28 and 29. That means an agent could implement the requested runtime behavior correctly yet still fail because the tests also depend on unrelated code. The problem is not that the tests are merely strict; it is that they require changes outside the stated task, creating false negatives.
  - Cross-reference analysis flags circular dependencies for all 3 F2P tests: 'containers/payments/Bitcoin.test.tsx | should render', 'should show loading during the initial fetching', and 'should check the token every 10 seconds' -> UNRELATED hunks [1, 28, 29] (conf=0.95).
  - Hunk 28 (`packages/testing/index.ts`) is UNRELATED because it is only 'test-package export plumbing'.
  - Hunk 29 (`packages/testing/lib/flush-promises.ts`) is UNRELATED because it adds a test helper and 'does not affect application behavior'.
**scope_creep** (confidence: 0.82):
  The gold patch contains at least one runtime behavioral change beyond the problem scope: hunk 1 alters payment-method eligibility in a way the specification does not ask for and in fact conflicts with the stated signup gating requirement. That is classic scope creep: extra behavioral patch content unrelated to the requested fix. Hunks 28 and 29 are also unrelated, but hunk 1 is the clearest behavioral evidence.
  - Hunk 1 in `packages/components/containers/paymentMethods/getPaymentMethodOptions.ts` is marked UNRELATED (conf=0.90).
  - Gold patch analysis for hunk 1: it 'changes the gate from excluding all signup flows (`!isSignup`) to excluding only regular signup (`!isRegularSignup`), which is not required by the stated contract.'
  - Requirements/AC1-AC2 require Bitcoin to appear only when the user is 'not in signup' and that signup gating cover both regular signup and pass signup.
**weak_coverage** (confidence: 0.93):
  The stated contract is much broader than what the F2P suite appears to verify. A solution that only fixes rendering/loading/polling inside `Bitcoin.tsx` could plausibly pass while missing payment-option gating, modal labels, QR/detail copy behavior, info-message content, or the constant export. This is weak_coverage rather than wide_tests: the tests do not exceed scope, they under-sample it, making the benchmark easier and less discriminative.
  - F2P test analysis lists only 3 tests, all in `containers/payments/Bitcoin.test.tsx`: 'should render', 'should show loading during the initial fetching', and 'should check the token every 10 seconds'.
  - The acceptance criteria also require behavior in many other areas with no corresponding F2P tests shown: `getPaymentMethodOptions` Bitcoin gating (AC1-AC2), over-max warning path (AC5), `BitcoinDetails` copy controls (AC14), `BitcoinQRCode` URI/container/copy action/state visuals (AC15-AC17), `BitcoinInfoMessage` KB link (AC18/AC24), modal/button labels in `CreditsModal`, `SubscriptionModal`, and `SubscriptionSubmitButton` (AC20-AC21), and export of `MAX_BITCOIN_AMOUNT` (AC22).
  - F2P test analysis reports zero assertion-level items and no F2P tests outside `Bitcoin.test.tsx` despite the requirements spanning multiple files and components.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.87)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent began with broad repository exploration, identified relevant Bitcoin/payment constants and types, and moved toward inspecting Bitcoin components, but stopped before making edits or running tests, so no real fix path materialized.
- **Behavior:** Legitimate early codebase exploration, but the run ended before any implementation or debugging; no leakage signs, just an incomplete attempt.

> The trajectory shows a normal, non-suspicious start: the agent read the task, then began exploring the repository structure, constants, payment method types, API helpers, and existing Bitcoin-related components. This is consistent with genuine problem setup rather than leakage. However, the run never progressed to implementation, testing, or iteration, and the final patch is empty. There is no evidence that the agent solved the core issue, nor even that it formed and executed a concrete fix stra

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-708ed4a299711f0fa79a907cc5847cfd39c0fc71`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Correct the `summer-2023` eligibility logic so users whose paid subscription ended less than one month ago are not treated as eligible.
**Severity:** SEVERE
**Labels:** `scope_creep`, `weak_coverage`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 5 of 7 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The patch clearly includes behavior beyond the stated bug fix. The task is about correcting the recent-cancellation timing rule in `isEligible` for the `summer-2023` offer. Only hunk 5 is REQUIRED for that. The UI guard, copy/branding edits, offer configuration change, and reordering of unrelated eligibility gates are all outside the acceptance criteria. Because several unrelated behavioral hunks are bundled into the gold patch, this task has scope creep.
  - Hunk 0 in `DealsWithCycleSelector.tsx` is marked UNRELATED: it adds a UI guard returning `null` when no deals match the selected cycle.
  - Hunks 1 and 2 in `summer2023/Layout.tsx` are marked UNRELATED: they add imports for branding/localization and replace placeholder UI text.
  - Hunk 3 in `summer2023/configuration.ts` is marked UNRELATED: it sets `canBeDisabled: true`.
**weak_coverage** (confidence: 0.71):
  The specification is richer than what the fail-to-pass tests appear to exercise. The tests cover app availability and the main "less than one month" regression, but the provided analysis shows no corresponding F2P coverage for the exact one-month boundary, missing/zero timestamps, UTC/timezone sensitivity, or preservation of unrelated eligibility gates. The presence of unrelated hunk 6 especially suggests the benchmark would still pass despite violating the explicit requirement that other gates remain unchanged. That makes the task under-constrained by tests.
  - F2P tests listed are only: `should be available in Proton Mail`, `should be available in Proton Calendar`, and `should not be available for users who have a subscription since less than one month`.
  - Requirement: "if `lastSubscriptionEnd` is exactly one calendar month prior ... the user is considered to have met the condition." No F2P test is identified for this exact-boundary case.
  - Requirement: "Time comparisons ... must use the current time in UTC to avoid timezone-dependent outcomes." No F2P test is identified for timezone/UTC behavior.
**approach_lock** (confidence: 0.50):
  There is evidence of the circular-dependency subtype of approach_lock: the tests appear to exercise unrelated hunks, so a minimal correct fix implementing only the required eligibility change in hunk 5 could still fail. That would make the benchmark reject valid solutions unless they also reproduce extra UI/config/gate-order changes from the gold patch. Confidence is only moderate because the linkage is inferred from cross-reference/identifier overlap rather than explicit assertion text, but the supplied pipeline analysis treats it as a strong signal.
  - Cross-reference analysis reports circular dependencies for all three F2P tests, each linked to UNRELATED hunks `[0, 1, 2, 3, 6]` with confidence `0.95`.
  - Reported link: `eligibility.test.ts | should be available in Proton Mail` → UNRELATED hunks `[0, 1, 2, 3, 6]`.
  - Reported link: `eligibility.test.ts | should be available in Proton Calendar` → UNRELATED hunks `[0, 1, 2, 3, 6]`.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.69)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the summer2023 offer code, then appears to have adopted a scope-expanded plan matching the contaminated PR/gold patch rather than the narrow prompt. It implemented a real eligibility change, but mis-handled the 'no previous subscription known' case (`lastSubscriptionEnd` absent/0), discovered that via tests, and did not complete the correction before ending.
- **Behavior:** Mostly exploratory and test-driven, but with suspicious gold-patch-like scope creep; it partially implemented the intended eligibility fix and then failed on an important edge case.

> The agent shows substantial legitimate workflow elements: it explored the repository, inspected the relevant summer2023 files, formed an eligibility hypothesis, edited code, and ran tests. It clearly engaged with the real bug and even diagnosed the reason its own implementation still failed: it had made eligibility depend on `lastSubscriptionEnd > 0`, which incorrectly excluded free users with no known prior paid subscription. That supports `agent_failed_completed_intent` rather than `agent_fail

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 5 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-b9387af4cdf79c2cb2a221dea33d665ef789512e`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Add a download-outcome metric that segments results by the actual download mechanism used, and emit it from standard download flows when a download finishes in a terminal state.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 4 of 16 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.98):
  The issue is narrowly about a Drive download mechanism success-rate metric and the data plumbing needed to emit it. The patch also introduces a separate mail performance histogram type, field, initialization, and schema. Those are substantive code and schema additions outside the requested Drive behavior, not mere ancillary imports or formatting. This is clear scope expansion in the gold patch.
  - Gold patch analysis: Has excess=True with 4 UNRELATED hunks.
  - Hunk 9 in packages/metrics/Metrics.ts imports a mail performance metric type and is marked UNRELATED.
  - Hunk 11 in packages/metrics/Metrics.ts adds mail_performance_email_content_render_time_histogram and is marked UNRELATED.
**approach_lock** (confidence: 0.82):
  This matches the circular test-patch dependency subtype of approach_lock. An agent could implement the requested Drive metric behavior from the problem and requirements, yet still fail the benchmark because the selected F2P tests also depend on unrelated mail-metric hunks. That means passing is coupled to reproducing extra patch content outside the task specification, so the tests are not measuring only the described solution.
  - Cross-reference analysis reports 5 circular dependencies where F2P tests exercise UNRELATED hunks [9, 11, 13, 15].
  - Test 'useDownloadMetrics should observe downloads and update metrics for successful downloads' → UNRELATED hunks [9, 11, 13, 15] (conf=0.95).
  - The same dependency is reported for the failed-download, retried-download, duplicate-processing, and multiple-LinkDownload tests.
**weak_coverage** (confidence: 0.56):
  The task specification includes several concrete requirements beyond generic hook emission: deterministic mechanism selection, explicit memory/sw/memory_fallback cases, and size propagation through preview/non-stateful flows. The observed F2P suite appears concentrated on existing useDownloadMetrics behaviors and does not obviously exercise those specific interfaces and paths. That suggests a partial fix could pass without fully satisfying all stated acceptance criteria, making the task easier than intended.
  - All 7 listed F2P tests are in src/app/store/_downloads/DownloadProvider/useDownloadMetrics.test.ts; no F2P test is listed for applications/drive/src/app/store/_downloads/fileSaver/fileSaver.ts, applications/drive/src/app/store/_downloads/useDownload.ts, or the new schema file.
  - Required hunk 5 adds the new public function selectMechanismForDownload(size?), but no F2P test is identified as targeting that interface directly.
  - Required hunk 7 implements preview/non-stateful size propagation (AC13), but no F2P test is identified for the preview/useDownload path.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.87)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The PR description led the agent to explore the Drive download and metrics codepaths, inspect existing metric schema conventions, infer how download mechanism selection currently works, and begin adding a new schema plus metric plumbing. The work stopped before the core end-to-end integration was completed or validated.
- **Behavior:** Genuine exploratory partial attempt that identified the right subsystem and began implementation, but did not finish the task; no meaningful leakage indicators.

> The trajectory shows genuine exploratory work rather than leakage, but it does not show a completed or test-validated fix. The agent began by systematically exploring the repository, locating the Drive download code, metrics infrastructure, and existing schema patterns. It explicitly searched for the relevant files named in the task, inspected existing download metrics schemas, and even created a reproduction script before starting implementation. That is the opposite of a suspicious jump straig

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 4 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-bf2e89c0c488ae1a87d503e5b09fe9dd2f2a635f`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Make calendar member/invitation permission controls respect restricted edit access by introducing and honoring a `canEdit` gate in `CalendarMemberAndInvitationList`, disabling permission changes while keeping current data visible and allowing access-reduction actions.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 12 of 28 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.36)

### Label Analysis

**approach_lock** (confidence: 0.87):
  This matches the circular test-patch-dependency subtype of approach_lock. A solution that correctly implements the requested member/invitation read-only behavior and share blocking could still fail because the F2P test reaches unrelated event-defaults/header/cleanup code paths. That means the test is not purely measuring the requested behavior; it implicitly requires extra patch content the task does not ask for.
  - Cross-reference analysis reports a circular dependency: the sole F2P test `containers/calendar/settings/CalendarMemberAndInvitationList.test.tsx | displays a members and invitations with available data` exercises UNRELATED hunks [0, 1, 2, 3, 4, 5, 6, 20, 21, 23, 24, 27] with conf=0.95.
  - Those unrelated hunks are outside the required fix surface: `CalendarEventDefaultsSection.tsx` hunks 0-6, `CalendarSubpage.tsx` hunks 20-21, `CalendarSubpageHeaderSection.tsx` hunks 23-24, and `packages/shared/lib/calendar/permissions.ts` hunk 27.
  - The stated requirements focus on `CalendarMemberAndInvitationList` gaining `canEdit`, disabling permission-change controls when `canEdit=false`, keeping removal/revocation enabled, and blocking new sharing via `canShare`.
**scope_creep** (confidence: 0.82):
  The patch expands beyond the requested bug fix. In addition to the required member-list and share-control gating, it changes other calendar settings behavior such as event defaults and header editing. Those are behavioral changes, not mere import or formatting cleanup, so they constitute scope creep.
  - Gold patch analysis says `Has excess: True` with 12 UNRELATED hunks.
  - Behavioral unrelated hunks 2-6 in `packages/components/containers/calendar/settings/CalendarEventDefaultsSection.tsx` disable event-duration, notification, and save controls, which the acceptance criteria do not require.
  - Behavioral unrelated hunk 24 in `packages/components/containers/calendar/settings/CalendarSubpageHeaderSection.tsx` disables the header edit pen, also outside the requested `CalendarMemberAndInvitationList`/sharing restriction fix.
**weak_coverage** (confidence: 0.66):
  The task's stated behavior is broader than what the visible F2P coverage appears to enforce. With only a single display-oriented member/invitation test, an incomplete fix that preserves display but mishandles disabled permission controls, removal availability, or share blocking could plausibly pass. That makes the benchmark easier and less discriminative than the specification suggests.
  - F2P test analysis lists only 1 aligned F2P test: `containers/calendar/settings/CalendarMemberAndInvitationList.test.tsx | displays a members and invitations with available data`.
  - The acceptance criteria include disabling permission selectors when `canEdit=false`, keeping `Remove this member` / `Revoke this invitation` enabled, and preventing new sharing, but no F2P tests are reported for those behaviors.
  - Gold hunks 17-19 and 25-26 implement `canShare` gating for share actions, yet the F2P side shows no corresponding share-control test coverage.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.90)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement led the agent to inspect calendar settings components, where it found existing edit-disable logic and permission helpers. From that exploration it inferred that permissions should be refactored into `canEdit`/`canShare` props and propagated through the settings/share components. However, the session ended before any real code changes or testing occurred.
- **Behavior:** Systematic exploration and plausible diagnosis, but the agent stalled before making or validating the fix.

> The trajectory looks like a genuine but incomplete debugging attempt, not benchmark leakage. The agent started by exploring the repository and locating calendar settings components through progressive search rather than jumping straight into a single gold-patch file and editing it immediately. It inspected the relevant settings components, identified existing permission-related props such as `isEditDisabled`, found `getIsMember`, and formed a plausible hypothesis that edit/share capability shoul

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 12 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-c6f65d205c401350a226bb005f42fac1754b0b5b`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Add stable, consistently scoped `data-testid` attributes to conversation and message view UI elements so automated tests can reliably target message views, attachments, banners, recipients, and recipient actions.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 51 of 89 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.86):
  This is best classified as the circular test-patch dependency subtype of approach_lock. The issue asks for a bounded set of `data-testid` additions/renames in conversation and message views, but the F2P tests are reported to depend on dozens of patch hunks that the patch analysis marked UNRELATED. That means a valid minimal solution implementing only the stated acceptance criteria could still fail because the benchmark is effectively locked to the gold patch's overbroad implementation footprint. Even though the tests were function-level classified as ALIGNED, the cross-reference evidence shows they are coupled to out-of-scope code changes, which makes the task unfairly restrictive.
  - Cross-reference analysis reports 21 circular dependencies where F2P tests exercise UNRELATED hunks; e.g. `src/app/components/message/tests/Message.modes.test.tsx | loading mode` is linked to 51 UNRELATED hunks `[0, 1, 3, 4, 5, 8, 9, 10, 12, 13, 17, 20, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 56, 71, 72, 73, 77, 79, 80, 81, 83, 84, 85, 86, 87, 88]` with confidence 0.95.
  - The same circular-dependency pattern is reported for attachment tests, banner tests, and many recipient tests such as `MailRecipientItemSingle.blockSender.test.tsx`, indicating the F2P suite broadly depends on out-of-scope changes rather than only the requested selectors.
  - Many of the linked UNRELATED hunks are clearly outside the stated requirements, such as hunk 9 (`components/list/ItemDate.tsx`), hunk 10 (`components/list/ItemLocation.tsx`), hunks 34-47 (`HeaderMoreDropdown.tsx` message-action selectors), and hunks 83-88 (`packages/components/.../LabelStack*`, `ContactImage.tsx`).
**scope_creep** (confidence: 0.97):
  The gold patch materially expands beyond the requested feature. The task asks for stable selectors for specific conversation/message-view areas: attachment header, message-view container, banners, recipient elements, recipient actions, and recipient detail dropdowns. Instead, the patch adds or renames test IDs across many unrelated controls, shared components, generic list components, and header action menus. These are behavioral UI changes, not merely ancillary imports or formatting. The large number of UNRELATED hunks and their distribution across unrelated files make scope_creep a strong contamination label.
  - Gold patch analysis: `Has excess: True | Hunks: 89 (REQUIRED=23, ANCILLARY=15, UNRELATED=51)`.
  - UNRELATED hunks include attachment item action selectors beyond the required attachment-list header rename: hunk 0 and hunk 1 (`AttachmentItem.tsx`), plus extra attachment-list selectors/actions in hunks 3, 4, and 5 (`AttachmentList.tsx`).
  - UNRELATED hunks include generic or external components outside the requested scope: hunk 9 (`ItemDate.tsx`), hunk 10 (`ItemLocation.tsx`), hunks 83-87 (`packages/components/components/labelStack/*`), and hunk 88 (`packages/components/containers/contacts/ContactImage.tsx`).

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.89)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement prompted the agent to inspect the mail UI component tree; after exploring likely attachment, message, header, banner, list, and recipient files, it formed a broad plan to add scoped data-testid attributes, but the session ended before any meaningful patch or validation was produced.
- **Behavior:** Genuine exploratory start with a reasonable implementation plan, but no actual patch landed; failure appears to be simple non-completion rather than benchmark leakage.

> The trajectory shows a largely legitimate, problem-driven exploration process rather than benchmark leakage. The agent started from the problem statement, narrowed to the mail application, and then systematically inspected conversation, message, header, attachment, list, and recipient components before summarizing a plausible implementation plan. That is the opposite of a suspicious direct jump to a single gold-file fix. There is no evidence of package installation, copying from site-packages, o

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 51 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-caf10ba9ab2677761c88522d1ba8ad025779c492`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Reorganize calendar-related code behind clearer domain-specific module boundaries and public exports so calendar consumers use the specified `calendar/*` and `date/timezone` entry points instead of scattered or unclear paths.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 4 of 97 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.88):
  This matches the circular test-patch dependency subtype of approach_lock. The task asks for calendar module reorganization and specific exports/import paths, but the F2P invite tests are reported to exercise unrelated patch hunks outside that scope. That means an agent could implement the stated requirements correctly yet still fail because the tests depend on out-of-scope changes in `AddAttendeeError.ts` and even payments-side import rewrites. When tests require unrelated hunks to pass, they reject otherwise valid solutions to the described task.
  - Cross-reference analysis reports 6 circular dependencies: every F2P test in `src/app/helpers/calendar/invite.test.ts` is linked to UNRELATED hunks [47, 48, 70, 71] with conf=0.95.
  - Hunks 70-71 in `packages/shared/lib/calendar/mailIntegration/AddAttendeeError.ts` change localization wiring and the participant-limit error message/pluralization, but the problem statement and requirements never ask for attendee-limit messaging changes.
  - Hunks 47-48 in `packages/components/containers/payments/subscription/{SubscriptionModal.tsx,UnsubscribeButton.tsx}` move payments imports to `calendar/plans`, a namespace not mentioned anywhere in the required module list.
**scope_creep** (confidence: 0.93):
  The patch goes beyond the requested separation-of-concerns refactor. In addition to the required calendar namespace moves and helper exports, it includes unrelated payments import migrations and a separate attendee-limit messaging change. Those are behavioral or out-of-scope modifications, not mere ancillary cleanup, so the task contains scope creep.
  - Gold patch analysis marks 4 hunks as UNRELATED: [47, 48, 70, 71].
  - Hunk 71 changes actual user-facing behavior in `packages/shared/lib/calendar/mailIntegration/AddAttendeeError.ts` by altering the participant-limit error message/pluralization.
  - Hunks 47-48 modify `packages/components/containers/payments/subscription/SubscriptionModal.tsx` and `UnsubscribeButton.tsx` to use `calendar/plans`, which is outside the requested `calendar/recurrence`, `calendar/alarms`, `calendar/mailIntegration`, `calendar/crypto`, `calendar/api`, `calendar/apiModels`, and `date/timezone` reorganization.
**weak_coverage** (confidence: 0.81):
  The stated acceptance criteria are much broader than what the fail-to-pass tests exercise. Visible F2P coverage is concentrated on invite logic, while many required helper behaviors and public exports appear untested. That makes the task easier than the specification suggests, because a partial solution could plausibly satisfy the tested paths without fully implementing the full required API surface.
  - The requirements specify many new or relocated behaviors/exports: `reformatApiErrorMessage`, `getHasSharedEventContent`, `getHasSharedKeyPacket`, `getSharedSessionKey`, `getBase64SharedSessionKey`, `getRecurrenceIdValueFromTimestamp`, `getPositiveSetpos`, `getNegativeSetpos`, and `convertTimestampToTimezone`.
  - All 6 F2P tests are in `src/app/helpers/calendar/invite.test.ts` and focus on invitation recurring-rule behavior (`accept/refuse ... recurring rules`, `should not import alarms for invites and keep recurrence id`).
  - Required behavioral hunks such as 55 (`calendar/api.ts`), 56 (`calendar/apiModels.ts`), 60 (`calendar/crypto/helpers.ts`), 76 (`calendar/recurrence/getRecurrenceIdValueFromTimestamp.ts`), 81 (`calendar/recurrence/rrule.ts`), and 94 (`date/timezone.ts`) have no corresponding F2P tests listed.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.86)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The broad refactor-oriented problem statement led the agent to spend its effort on repository exploration and planning the new calendar module boundaries; it then began sketching the intended reorganization, but the run appears to have ended before any meaningful code changes or validation occurred.
- **Behavior:** Genuine exploratory attempt focused on broad refactor planning, but it did not reach an implemented or validated solution.

> The trajectory shows a normal, non-leaky start: the agent read the problem, explored the repository structure repeatedly, inspected relevant calendar/date areas, and then outlined a refactor plan that directly mirrors the stated requirements. There are no signs of benchmark leakage: it did not jump immediately to the exact gold-patch files without exploration, did not mention fail-to-pass test names or hidden expected values, did not install packages, and did not display suspiciously patch-like 

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 4 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_protonmail__webclients-da91f084c0f532d9cc8ca385a701274d598057b8`

### Task Context

**Repository:** `protonmail/webclients` (version )
**Core requirement:** Update notifications so string messages containing HTML render as safe clickable content, and suppress duplicate non-success notifications using a defined stable key while still allowing repeated success notifications.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 2 of 6 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The gold patch contains behavioral changes beyond the requested fix. Both unrelated hunks change notification expiration behavior at specific call sites, which is separate from the HTML-rendering and deduplication bug described in the problem. These are not merely ancillary imports or type declarations, so this is genuine scope expansion.
  - Gold patch hunk 0 in `packages/components/containers/api/ApiProvider.js` is marked UNRELATED (conf=0.95): it starts passing an expiration value when creating API error notifications.
  - Gold patch hunk 5 in `packages/components/containers/payments/paymentTokenHelper.tsx` is marked UNRELATED (conf=0.97): it passes a longer `notificationExpiration` value on a payment-token API call.
  - The stated contract only covers rendering HTML notification text safely, forcing secure `<a>` attributes, and deduplicating non-success notifications; it says nothing about notification expiration/duration.
**approach_lock** (confidence: 0.56):
  If the cross-reference finding is accurate, the F2P tests depend on unrelated expiration-value changes. That would create a circular test-patch dependency: an agent could correctly implement the requested notification HTML rendering and deduplication behavior, yet still fail because the tests also require out-of-scope patch hunks. This matches the approach_lock subtype for circular test-patch dependency. Confidence is only moderate because the dependency is inferred from cross-reference analysis rather than explicit test assertions.
  - Cross-reference analysis reports a circular dependency: `containers/notifications/manager.test.tsx | should allow to create notifications with raw html text and deduplicate it` → UNRELATED hunks [0, 5] (conf=0.90).
  - Cross-reference analysis reports a circular dependency: `containers/notifications/manager.test.tsx | should deduplicate react elements using the provided key` → UNRELATED hunks [0, 5] (conf=0.90).
  - Hunks 0 and 5 are unrelated expiration-setting changes, not part of the problem's requested HTML rendering / secure link / deduplication behavior.
**weak_coverage** (confidence: 0.52):
  The available F2P coverage appears narrower than the full stated requirements. The named tests cover HTML-string rendering/deduplication and React-element deduplication with an explicit key, but they do not visibly exercise all specified fallback and exemption rules. That means a partial implementation could plausibly pass the fail-to-pass suite.
  - Only two F2P tests are listed: `should allow to create notifications with raw html text and deduplicate it` and `should deduplicate react elements using the provided key`.
  - Acceptance criterion 9 requires fallback to the notification identifier when `text` is not a string and no `key` is provided, but no listed F2P test explicitly targets that case.
  - Acceptance criterion 10 requires success-type notifications to be exempt from deduplication, but no listed F2P test explicitly covers repeated success notifications.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.88)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent began with normal exploration of the notification system and supporting utilities, but then converged on an implementation plan that reproduced not only the core notification-manager fix, but also the same peripheral file edits and extra behaviors as the gold patch, suggesting contamination guided the solution path.
- **Behavior:** Mostly polished and competent on the surface, but the solution path is suspiciously aligned with the contaminated gold patch, including unrelated file edits and exact extra behaviors not justified by the prompt.

> The agent shows some surface-level genuine workflow — it explored the repo, checked for DOMPurify and an existing `isElement` helper, inspected notification-related components, and ran a custom validation script. However, the decisive signal is that its planned solution mirrors the gold patch far beyond what the problem statement or fail-to-pass tests require. In particular, it explicitly targeted the same four files as the gold patch, including `ApiProvider.js` and `paymentTokenHelper.tsx`, whi

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 2 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-0833b5f6f140d04200ec91605f88704dd18e2970-v059c6fdc75567943479b23ebca7c07b5e9a7f34c`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** Update the WebKit backend's NetworkReply error handling so that constructing an error reply emits Qt's modern errorOccurred signal instead of the deprecated error signal.
**Severity:** SEVERE
**Labels:** `scope_creep`, `wide_tests`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 4 of 5 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.97):
  The task asks for one narrow behavioral change in the WebKit NetworkReply constructor. The gold patch includes four additional behavioral hunks in qtnetworkdownloads.py and misc/ipc.py that perform broader deprecated-signal migrations elsewhere in the project. Those are not ancillary edits; they change runtime behavior in unrelated subsystems. This is a clear case of patch scope expansion beyond the issue being benchmarked.
  - Gold patch hunk 2 in qutebrowser/browser/webkit/network/networkreply.py is the only REQUIRED hunk; it implements the requested switch from error to errorOccurred in the WebKit NetworkReply.
  - Hunk 0 in qutebrowser/browser/qtnetworkdownloads.py is UNRELATED (conf 0.95): it changes disconnect logic in the Qt network downloads code, outside the WebKit NetworkReply implementation named in the problem.
  - Hunk 1 in qutebrowser/browser/qtnetworkdownloads.py is UNRELATED (conf 0.96): it changes a download-subsystem consumer to connect to errorOccurred with fallback to error, described as a broader project-wide Qt signal migration.
**wide_tests** (confidence: 0.62):
  The benchmarked issue is narrowly about which signal is emitted when constructing an error reply. But the F2P test function also checks a broader bundle of ErrorNetworkReply behaviors that are not described in the problem statement or requirements. That makes the test wider than the stated task, even though the signal-related modification itself is on topic. Confidence is moderate rather than high because the extra checks appear to come from a pre-existing test function rather than a clearly newly added off-scope assertion block.
  - The only F2P test, test_error_network_reply, is classified as TANGENTIAL (conf 0.97).
  - F2P reasoning states that 'most of the test's remaining checks validate broader ErrorNetworkReply behavior such as request/url propagation, open mode, finished/running state, bytesAvailable, readData, stored error value, and error string.'
  - The acceptance criteria are limited to AC1-AC3: use errorOccurred for the initial error emission, carry the error code, and stop using the legacy error signal.
**weak_coverage** (confidence: 0.55):
  The test appears to verify that errorOccurred is emitted, and likely that the reply still reports the error code, but there is no clear test coverage for the 'instead of the legacy error signal' part of the requirement. A partial implementation that emits errorOccurred while still also emitting the deprecated error signal could plausibly pass. That means the benchmark may under-test the full stated acceptance criteria.
  - Acceptance criterion AC3 says: 'The initial error emission for that case should no longer use the legacy error signal.'
  - F2P analysis says the modified part of test_error_network_reply 'now waits for the modern errorOccurred signal instead of the deprecated error signal,' but it does not report any negative check that the legacy error signal is absent.
  - Assertion analysis lists 0 extracted assertions, leaving no explicit evidence of a check that emitting both signals would fail.

### Agent Evaluation Behavior

### Diagnosis

**Action:** Review 4 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-16de05407111ddd82fa12e54389d532362489da9-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** PIPELINE_ERROR: LLM request failed after 7 attempts. Last error: Request timed out.
**Severity:** SEVERE

### Contamination Signals


### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The problem statement suggested a QtWebEngine locale workaround, which led the agent to inspect argument generation and config machinery, formulate a locale-fallback solution, implement it, test it with custom scripts, and iterate on edge cases; the run still ended unresolved, likely due incomplete patch finalization or environment-related validation issues.
- **Behavior:** Methodical, codebase-driven debugging and partial implementation with genuine reasoning; failed to land a passing result but appears to have been addressing the real issue.

> The trajectory looks like a genuine implementation attempt rather than leakage. The agent did not jump straight to a finished answer: it progressively explored the repository, inspecting `qtargs.py`, config definitions, version handling, logging, and config access patterns before coding. That is exactly the kind of exploration expected for this task, especially since the problem statement itself points to QtWebEngine argument handling and names the helper functions to implement. The agent then d

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-21b426b6a20ec1cc5ecad770730641750699757b-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** Update `Values` so scoped configuration entries are managed consistently by pattern, avoiding duplicate scoped entries and making representation and iteration reflect a stable keyed ordering.
**Severity:** SEVERE
**Labels:** `approach_lock`, `wide_tests`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 10 hunks are UNRELATED to the stated problem
- **WIDE_TESTS:** 1 UNRELATED tests

### Label Analysis

**approach_lock** (confidence: 0.88):
  This task has the circular test-patch dependency subtype of approach_lock. An F2P test depends on an unrelated behavioral hunk (freezing ScopedValue) that is outside the problem's acceptance criteria. That means an agent could correctly implement the requested OrderedDict/_vmap, repr, iter, and duplicate-replacement behavior yet still fail because it did not also make the unrelated immutability change. The failure would come from the test suite's coupling to out-of-scope code, not from an incorrect solution to the stated problem.
  - Cross-reference analysis: Test 'test_add_url_benchmark'  UNRELATED hunk [1] (conf=0.90), flagged as a circular dependency and described as 'a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for.'
  - Hunk 1 in qutebrowser/config/configutils.py is UNRELATED (conf=0.89): 'Making ScopedValue frozen is not described by any acceptance criterion.'
  - F2P test 'test_add_url_benchmark' is UNRELATED (conf=0.99) and does not check the stated bugfix semantics; it instead exercises performance-oriented code paths.
**wide_tests** (confidence: 0.96):
  The F2P suite goes beyond the task specification by including an entire unrelated benchmark-style test. Performance over many URL patterns is not part of the described bug or the explicit requirements. This is the extra-test-function subtype of wide_tests: the benchmark verifies something outside scope, so the measured task is broader than the stated task.
  - F2P test 'test_add_url_benchmark' is classified UNRELATED (conf=0.99).
  - Test analysis states: 'Its purpose is performance measurement over many URL patterns, which is outside the stated acceptance criteria.'
  - The problem statement and requirements only ask for storage/reflection/iteration/replacement behavior in Values: _vmap initialization, __repr__, __iter__, and add replacement semantics.
**scope_creep** (confidence: 0.86):
  The gold patch contains at least one behavioral change beyond the problem scope. Freezing ScopedValue changes mutability semantics and is not required by the bug report or requirements. Because this is a real behavioral expansion rather than a pure import/whitespace/support change, it qualifies as scope_creep.
  - Gold patch analysis: Has excess=True.
  - Hunk 1 in qutebrowser/config/configutils.py is UNRELATED (conf=0.89): 'Making ScopedValue frozen is not described by any acceptance criterion.'
  - The stated scope is limited to changing how Values stores scoped entries and how __repr__, __iter__, and add behave.
**weak_coverage** (confidence: 0.84):
  The F2P coverage does not fully exercise the stated acceptance criteria. In particular, the key add-path requirementsstoring by pattern in _vmap and replacing duplicate-pattern entries rather than creating duplicateslack a direct aligned test. A partial fix focused only on repr and iteration could therefore score better than it should, making the task easier and less diagnostic.
  - Acceptance criteria include: 'Values.add should store each ScopedValue in _vmap using its pattern as the key' and 'When Values.add is given a ScopedValue whose pattern already exists, the new entry should replace the previous one instead of creating a duplicate.'
  - Aligned F2P tests only cover 'test_repr' and 'test_iter'.
  - Test analysis for 'test_add_url_benchmark' explicitly says it 'does not assert any of the bugfix semantics: no check of _vmap, no replacement-on-duplicate behavior, no repr/iteration behavior, and no ordering guarantees.'

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.80)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the relevant code and tests, inferred the OrderedDict-based redesign, likely mixed in some extra remembered/upstream details (`frozen=True`, `VMAP_KEY`), then got blocked by test-running issues and attrs initialization mistakes, leading to an incomplete implementation and no final patch.
- **Behavior:** Mostly genuine but unsuccessful debugging, with a small suspicious hint of prior patch knowledge that did not translate into a working fix.

> The trajectory mostly shows genuine repository exploration and an attempt to reason about the bug: the agent inspected the target file, looked at related modules, examined tests, tried to run tests, hit circular-import issues, and iterated with small debugging scripts. That is not the signature of a clean gold-patch dump or package-copying attack. However, there is one notable contamination-like signal: in Step 8 the agent suddenly lists extra requirements such as making a class `@attr.s(frozen=

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-394bfaed6544c952c6b3463751abab3176ad4997-vafb3e8e01b31319c66c4e666b8a3b1d8ba55db24`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** Replace qutebrowser's unreliable QtWebEngine version detection with a centralized mechanism that derives QtWebEngine and Chromium versions from multiple sources, exposes the source used, and updates dependent version-reporting logic to use that result.
**Severity:** SEVERE
**Labels:** `unclear_spec`, `approach_lock`

### Contamination Signals

- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.42)

### Label Analysis

**unclear_spec** (confidence: 0.78):
  The task bundle gives contradictory instructions for the core behavior: the problem description asks for ELF-first fallback ordering, while the Requirements, Interface, and extracted acceptance criteria require UA-first ordering. Because this is the central control flow of `qtwebengine_versions`, an agent can reasonably implement the description and still be wrong under the tests/gold patch. That makes the specification materially ambiguous rather than merely terse.
  - Problem statement Description says the lookup should "first try to read the version directly from the ELF binary `libQt5WebEngineCore.so.5` ... If that doesn't work, it should check `PYQT_WEBENGINE_VERSION`, and if that's not enough, it should fall back to parsing the user agent."
  - Requirements instead specify: "`qtwebengine_versions` must attempt to initialize a parsed user agent, then fallback to ELF parsing via `parse_webenginecore`, then fallback to `PYQT_WEBENGINE_VERSION_STR`."
  - Interface repeats the UA-first order: "it first attempts to use a pre-parsed user agent, then falls back to using the new ELF parser, and finally falls back to the PyQt version string."
**approach_lock** (confidence: 0.55):
  Some F2P coverage constrains the implementation method, not just the externally required behavior. In particular, `test_format_sizes` appears to pin internal struct-format calculations of the ELF parser. A solution could satisfy the public contract of `get_rodata`/`parse_webenginecore` with a different but valid parsing strategy and still fail these tests. That is a narrow implementation-detail check, i.e. approach locking. The evidence is moderate rather than overwhelming because the interface does prescribe an ELF parser module and public parser classes, but the format-size checks go beyond that public contract.
  - F2P test `test_format_sizes` is marked TANGENTIAL because it "checks struct format sizes used by the new ELF parser" rather than the stated acceptance criteria.
  - F2P test `test_hypothesis` is marked TANGENTIAL because it fuzzes "the internal ELF parser entrypoint with arbitrary bytes".
  - The stated requirements focus on observable ELF-parser behavior: locating `.rodata`, extracting `QtWebEngine/...` and `Chrome/...`, and raising documented errors/messages; they do not require a particular internal struct-format layout.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.82)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the requirements, explored the existing code paths involved in version detection and darkmode/backend reporting, formed a plan covering the new ELF parser and centralized WebEngineVersions flow, implemented pieces incrementally, ran ad hoc validation, discovered parser and integration bugs, and stalled while debugging those issues.
- **Behavior:** Genuine exploratory implementation attempt with iterative debugging, but incomplete and unsuccessful; no meaningful evidence of benchmark leakage.

> The trajectory looks like a genuine attempt to solve the stated feature request rather than benchmark leakage. The agent first explored the repository and relevant modules in a progressive way: version handling, webengine settings, user-agent parsing, darkmode variant logic, backend/debug flags, and utility version classes. It then explicitly summarized the required work in a way that closely tracks the public problem statement, not hidden tests. There are no signs of package leakage, no referen

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-473a15f7908f2bb6d670b0e908ab34a28d8cf7e2-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** PIPELINE_ERROR: LLM request failed after 7 attempts. Last error: Request timed out.
**Severity:** SEVERE

### Contamination Signals


### Agent Evaluation Behavior

### Diagnosis

Task flagged for manual review.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-66cfa15c372fa9e613ea5a82d3b03e4609399fb6-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** PIPELINE_ERROR: LLM request failed after 7 attempts. Last error: Error code: 504 - {'error': {'message': 'The server had an error while processing your request. Sorry about that!', 'type': 'server_error', 'param': None, 'code': None}}
**Severity:** SEVERE

### Contamination Signals


### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.74)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the problem, explored the config and Qt argument code paths, identified qtargs.py and configdata.yml as the right implementation points, added a locale workaround plus config flag, tested locally with custom scripts, then iterated on edge-case locale mappings; the task remained unresolved likely because of incorrect edge-case logic or incomplete finalization rather than any leakage-driven shortcut.
- **Behavior:** Genuine, methodical implementation attempt with debugging and iteration, but ultimately incomplete/incorrect on edge cases and not successfully resolved.

> This looks like a genuine debugging/implementation attempt rather than leakage. The agent did not jump straight to a known patch: it explored the repository, inspected configuration definitions, qtargs handling, version utilities, and existing locale usage before proposing a fix. It then articulated a task-specific plan matching the bug report, implemented the new config setting and QtWebEngine locale workaround logic, integrated it into argument generation, and iterated using self-created tests

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-6dd402c0d0f7665d32a74c43c5b4cf5dc8aff28d-v5fc38aaf22415ab0b70567368332beee7955b367`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** Make corrupted adblock cache deserialization failures in BraveAdBlocker.read_cache non-fatal by handling them gracefully, informing the user, and allowing qutebrowser to keep running.
**Severity:** SEVERE
**Labels:** `approach_lock`, `weak_coverage`

### Contamination Signals


### Label Analysis

**approach_lock** (confidence: 0.52):
  The test is narrower than the written specification on the user-facing message. A solution could correctly catch corrupted-cache deserialization failures, avoid crashing, and show a clear error telling the user to update filters, yet still fail if it uses different but equally valid wording. That means the F2P test rejects some valid implementations based on an exact string choice not determined by the task spec, which fits approach_lock via a narrow assertion.
  - F2P test 'test_corrupt_cache_handling' has a single explicit assertion: `assert msg.text == 'Reading adblock filter data failed (corrupted data?). Please run :adblock-update.'`.
  - Requirements specify only the semantic content of the message: it must be error-level, say the filter data could not be loaded, and advise updating adblock filters; they do not prescribe this exact wording.
**weak_coverage** (confidence: 0.76):
  The benchmark does not fully test several stated acceptance criteria. A partial fix could pass by catching the failure and emitting the expected text, without implementing the public `DeserializationError` interface or without demonstrating the broader post-failure state guarantees described in the requirements. This makes the task easier than its stated specification and is a weak_coverage issue.
  - There is only 1 F2P test and 1 explicit assertion, both centered on the emitted message text in `test_corrupt_cache_handling`.
  - Acceptance criterion 7 requires 'A public DeserializationError exception should exist in qutebrowser/components/braveadblock.py', but no F2P assertion checks the existence/importability of that class.
  - Acceptance criteria 5 and 6 require continued normal operation and adblock remaining disabled until resolved, but the F2P test only calls `read_cache()` in isolation and checks message text.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.84)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The prompt pointed the agent to `braveadblock.read_cache`; inspection of existing code showed special handling for `ValueError("DeserializationError")`; the agent inferred newer adblock versions raise a distinct deserialization exception, implemented a normalization layer plus catch site, tested locally, then adjusted the message to match its reading of the prompt—likely causing mismatch with the benchmark expectation.
- **Behavior:** Mostly genuine debugging and implementation with strong intent to solve the real bug; likely failed on exact benchmark expectations rather than lack of understanding.

> The trajectory looks like a real attempt to solve the stated bug rather than clear benchmark leakage. The agent followed a plausible debugging flow: it inspected the named module, examined `read_cache`, searched for related tests/usages, built a reproduction script, identified the behavioral gap between `ValueError("DeserializationError")` and `adblock.DeserializationError`, then implemented a unifying exception-handling mechanism and iterated on it. That is consistent with genuine problem-solvi

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-996487c43e4fcc265b541f9eca1e7930e3c5cf05-v2ef375ac784985212b1805e1d0431dc8f1b3c171`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** Add optional encoding-based input validation to the FormatString configuration type so it can reject invalid non-encodable values, especially for ASCII-constrained HTTP header settings such as user_agent.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 9 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.82):
  This matches the circular test-patch dependency subtype of approach_lock. A solver could implement the requested fix for `FormatString`—for example by making the constructor accept `encoding` and validating in `FormatString.to_py`—and still fail the F2P test because the test also exercises unrelated behavior from hunk 0. Since hunk 0 is outside the stated problem scope, the benchmark rejects at least one otherwise valid solution to the described task.
  - Cross-reference analysis reports a circular dependency: test 'test_invalid_encoding' depends on UNRELATED hunk [0] (conf 0.80).
  - Hunk 0 in qutebrowser/config/configdata.yml is marked UNRELATED (conf 0.90): it changes `content.headers.accept_language`, a `String` setting rather than the `FormatString` behavior requested.
  - The problem acceptance criteria are narrowly about `FormatString`: adding an optional `encoding` parameter and validating in `FormatString.to_py`, while preserving behavior when no encoding is set.
**scope_creep** (confidence: 0.90):
  The gold patch includes behavioral changes beyond the requested fix. The task asks for optional encoding validation support in `FormatString`, especially for `user_agent`. Updating `accept_language` introduces extra behavior on a separate `String`-backed setting that is not required to satisfy the stated acceptance criteria. That is classic scope expansion in the patch itself.
  - Gold patch analysis marks hunk 0 as UNRELATED (conf 0.90).
  - Hunk 0 changes `qutebrowser/config/configdata.yml` for `content.headers.accept_language`, which is a `String` setting, not the `FormatString`/`user_agent` path described in the issue.
  - The intent extraction explicitly says out of scope: 'The request does not ask for ... changes to the existing String type' and focuses on `FormatString` encoding validation.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.78)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the task, inspected the configuration type system and the relevant header settings, recognized that `String` already had encoding validation while `FormatString` lacked it, reproduced the issue with local scripts, then generalized the existing validation logic so both types could enforce ASCII for HTTP header settings.
- **Behavior:** Methodical and code-driven: explored relevant files, reproduced the bug, inferred a reusable validation approach, and implemented the fix without obvious leakage signals.

> The trajectory looks like legitimate problem-solving rather than leakage. The agent begins by orienting itself to the codebase, explicitly identifies the likely relevant modules (`configtypes.py` and `configdata.yml`), and then narrows down to the `String`/`FormatString` implementations and the relevant header settings. It describes reproducing the issue with small test scripts, then formulates a concrete implementation plan based on the existing structure: reuse encoding validation logic, exten

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-9b71c1ea67a9e7eb70dd83214d881c2031db6541-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** PIPELINE_ERROR: LLM request failed after 7 attempts. Last error: Request timed out.
**Severity:** SEVERE

### Contamination Signals


### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.74)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent began with suspiciously specific prior knowledge of the intended helper functions, used that to jump into `qtargs.py` and config workarounds, attempted to recreate the locale override logic, then stalled on validation/config/Qt test issues before producing a resolved patch.
- **Behavior:** Suspiciously answer-guided partial implementation: it seems to know the target helper structure up front, heads straight to the right files, but fails to complete and validate the fix.

> The agent appears to have been guided by answer-level knowledge rather than deriving the solution purely from the issue description. Most notably, at the very start it references the exact helper names `_get_locale_pak_path` and `_get_lang_override`, which are not present in the provided problem statement but do appear in the gold patch. It then narrows immediately to the same implementation structure as the gold fix: add a new `qt.workarounds.locale` config entry, implement locale-pak helper lo

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-ef5ba1a0360b39f9eff027fbdc57f363597c3c3b-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** PIPELINE_ERROR: LLM request failed after 7 attempts. Last error: Error code: 500 - {'statusCode': 500, 'message': 'Internal server error', 'activityId': '4dd444c2-b56c-4443-b436-e3005f906d6c'}
**Severity:** SEVERE

### Contamination Signals


### Agent Evaluation Behavior

### Diagnosis

Task flagged for manual review.

---

## Contamination Narrative: `instance_qutebrowser__qutebrowser-fec187c2cb53d769c2682b35ca77858a811414a8-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`

### Task Context

**Repository:** `qutebrowser/qutebrowser` (version )
**Core requirement:** Ensure search URL construction correctly URL-encodes search terms in query parameters, especially when terms contain spaces or special characters.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `unclear_spec`

### Contamination Signals

- **SCOPE_CREEP:** 3 of 3 hunks are UNRELATED to the stated problem
- **VAGUE_SPEC:** Problem statement has significant ambiguity (0.34)

### Label Analysis

**approach_lock** (confidence: 0.96):
  This is a circular test-patch dependency. The only F2P test is coupled to behavioral changes the analysis marks as unrelated to the stated bug, so an agent could correctly implement the described encoding fix and still fail unless it also reproduces the engine-base-URL behavior from hunks 1-2. That means the test suite is not purely checking the requested observable behavior; it effectively locks the task to the unrelated gold-patch path.
  - Cross-reference analysis: `test_get_search_url` exercises UNRELATED hunks `[0, 1, 2]` in `qutebrowser/utils/urlutils.py` (conf 0.98).
  - Hunk 1 changes `_parse_search_term` for exact-engine inputs with `open_base_url`, returning `(engine, None)`; this is not part of the stated encoding requirements.
  - Hunk 2 adds a `term is None` branch in `_get_search_url` to open the search engine base URL directly and strip path/fragment/query; the actual encoding line `urllib.parse.quote(term, safe='')` is unchanged.
**scope_creep** (confidence: 0.97):
  The patch expands behavior beyond the problem scope. Instead of implementing the requested search-term encoding fix, it introduces separate behavior for exact engine-name inputs and base-URL opening. Because these are behavioral changes unrelated to the stated acceptance criteria, the task contains clear scope creep.
  - Gold patch analysis: 3 hunks total, `REQUIRED=0`, `UNRELATED=3`.
  - Hunk 0 only widens the return type annotation of `_parse_search_term` so the term may be `None`.
  - Hunk 1 changes parsing semantics for exact search-engine-name inputs when `open_base_url` is enabled.
**unclear_spec** (confidence: 0.71):
  The task specification is actively misleading relative to what the patch/test path actually depends on. An agent reading the problem would reasonably search for broken quoting or query-parameter encoding, but the gold patch changes engine-selection and base-URL behavior instead. That mismatch makes the intended solution hard to infer from the problem statement alone.
  - Problem statement: 'Search URL construction needs proper parameter encoding' and 'Search terms should be properly URL-encoded when constructing search URLs.'
  - Requirements repeatedly focus on encoding spaces/special characters in query parameters.
  - Hunk 2 explicitly leaves the real search-term encoding logic unchanged: `urllib.parse.quote(term, safe='')` remains the same, while adding only `term is None` / base-URL behavior.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GOLD_PATCH_LEAK (confidence: 0.89)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to begin with prior knowledge of the actual upstream bug (`open_base_url` handling), then uses repository exploration to confirm that hypothesis, reproduces the hidden scenario, edits the exact relevant functions, and validates the fix with custom scripts.
- **Behavior:** The agent explored and tested like a capable debugger, but it appears to have started from leaked knowledge of the real hidden bug and then worked backward to justify and implement the gold-style fix.

> This trajectory shows substantial signs that the agent was operating from knowledge of the hidden real bug rather than from the stated problem. The public problem statement is about URL-encoding search terms containing spaces/special characters. However, in Step 0 the agent immediately frames the task as fixing unexpected `open_base_url` behavior, which is not mentioned in the prompt at all. It then converges on the exact semantic shape of the gold fix: modifying `_parse_search_term` so a lone e

### Diagnosis

**Agent impact:** 1/1 analyzed agents showed leakage patterns on this task. **Action:** Review 3 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_tutao__tutanota-09c2776c0fce3db5c6e18da92b5a45dce9f013aa-vbc0d9ba8f0071fbe982809910959a6ff8884dbbf`

### Task Context

**Repository:** `tutao/tutanota` (version )
**Core requirement:** Add operation-specific progress tracking for calendar imports so each import reports continuous 0–100% progress independently, can be consumed by the UI, and is marked complete when finished.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`, `weak_coverage`

### Contamination Signals

- **SCOPE_CREEP:** 1 of 22 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.84):
  This matches the circular test-patch dependency form of approach_lock. The F2P suite appears to depend on hunk [7], even though that hunk is outside the task's stated scope. An agent could implement the requested calendar-import progress behavior correctly while leaving `connectivityListener` untouched, yet still fail the benchmark if the test suite depends on that unrelated cleanup. That means the tests are not measuring only the requested behavior; they are also enforcing an out-of-scope patch detail.
  - Cross-reference analysis: `test/tests/api/worker/facades/CalendarFacadeTest.js | test suite` exercises UNRELATED hunk [7] (conf=0.80).
  - Hunk [7] in `src/api/worker/WorkerImpl.ts` was classified UNRELATED: removing the `connectivityListener` lazy field 'does not implement any stated acceptance criterion about calendar import progress, operation IDs, callback signatures, or UI cleanup.'
  - The stated requirements focus on operation-specific import progress (`OperationProgressTracker`, `saveImportedCalendarEvents(operationId)`, `_saveCalendarEvents(..., onProgress)`, and UI cleanup), and do not ask for changes to `connectivityListener`.
**scope_creep** (confidence: 0.73):
  The patch includes at least one behavioral/code-structure change unrelated to the requested feature. Removing `connectivityListener` is not part of the acceptance criteria for operation-specific calendar import progress and is not a pure ancillary import/whitespace change. That is classic scope creep: an opportunistic cleanup bundled into the fix.
  - Gold patch analysis: `Has excess: True` with 1 UNRELATED hunk.
  - Hunk [7] in `src/api/worker/WorkerImpl.ts` is explicitly marked UNRELATED (conf=0.72).
  - The hunk removes a `connectivityListener` lazy field, while the problem statement and requirements are about per-operation calendar import progress, callback wiring, and UI dialog cleanup.
**weak_coverage** (confidence: 0.57):
  The stated spec is broad: it requires not just callback-based progress reporting in `CalendarFacade`, but also a public tracker abstraction, main/worker forwarding, and UI cleanup on success and error. Yet the provided F2P coverage shows only a single suite in `CalendarFacadeTest.js`. From the available analysis, several explicit acceptance criteria appear untested, so a partial implementation concentrated in the worker facade could plausibly pass. That makes the task easier and indicates incomplete benchmark coverage.
  - F2P test analysis reports only 1 aligned F2P test target: `test/tests/api/worker/facades/CalendarFacadeTest.js | test suite`.
  - The requirements span multiple areas beyond `CalendarFacade`, including the public `OperationProgressTracker` API (AC10-AC13) and UI dialog display/cleanup in `CalendarImporterDialog` (AC6-AC8).
  - Required hunks implementing those areas include hunk [3] (`src/api/main/OperationProgressTracker.ts`) and hunks [20]-[21] (`src/calendar/export/CalendarImporterDialog.ts`), but the provided F2P list contains no dedicated tests in those files or areas.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.89)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent explored the relevant calendar import and progress-tracking architecture, inferred that the bug required a new per-operation progress multiplexer and wiring through main/worker/UI layers, began implementing that plan, but stopped before producing a working patch or validating it.
- **Behavior:** Genuine architectural reasoning and targeted exploration, but the run was incomplete and never turned into a working implementation.

> The trajectory shows legitimate exploration and a correct high-level diagnosis of the required change, but not a completed solution. The agent read the relevant areas in a sensible order: calendar import UI, progress dialog code, WorkerClient, ProgressTracker, MainLocator, WorkerImpl, and CalendarFacade. It then articulated a plan that matches the problem requirements: introduce an OperationProgressTracker, expose it across the main/worker boundary, inject it into calendar-related worker code, a

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 1 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_tutao__tutanota-1e516e989b3c0221f4af6b297d9c0e4c43e4adc3-vbc0d9ba8f0071fbe982809910959a6ff8884dbbf`

### Task Context

**Repository:** `tutao/tutanota` (version )
**Core requirement:** Update subscription pricing utility/provider creation to use the class-based PriceAndConfigProvider.getInitializedInstance API instead of the deprecated getPricesAndConfigProvider function, while preserving existing behavior.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 14 of 16 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.95):
  This task exhibits the circular test-patch dependency subtype of approach_lock. A solver can satisfy the stated acceptance criteria by making only the required API transition in PriceUtils.ts (hunks 0-1), preserving behavior and argument compatibility. However, the benchmark's F2P test set still exercises numerous unrelated production call-site migrations in other modules. That means a valid solution to the described problem can fail unless it also reproduces unrelated patch breadth from the gold commit. The tests therefore lock the task to code changes outside the asked-for scope, creating unfair false negatives.
  - Cross-reference analysis: 'Circular dependencies detected: 107' and explicitly states 'This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for.'
  - Minimal required fix is confined to hunks 0-1 in src/subscription/PriceUtils.ts; hunk 0 exports PriceAndConfigProvider as a concrete class and hunk 1 adds/implements PriceAndConfigProvider.getInitializedInstance.
  - Many F2P suites depend on UNRELATED hunks, e.g. test/tests/subscription/PriceUtilsTest.js -> UNRELATED hunks [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], and test/tests/api/worker/facades/LoginFacadeTest.js -> UNRELATED hunks [2, 3, 4, 5, 7, 9, 10, 12, 15].
**scope_creep** (confidence: 0.98):
  The gold patch goes well beyond the requested change. The problem asks for adopting PriceAndConfigProvider.getInitializedInstance in the pricing utility/test context while preserving existing behavior. But the patch also updates many unrelated application flows and gift-card/subscription UI call sites. Those are not ancillary import-only cleanups; they are behavioral adoption changes in unrelated modules. This is classic scope expansion in the patch itself, so scope_creep clearly applies.
  - Gold patch analysis: 'Has excess: True' with 16 hunks total, only 2 REQUIRED and 14 UNRELATED.
  - UNRELATED hunks 2-15 are behavioral/runtime call-site migrations in src/subscription/SubscriptionViewer.ts, src/subscription/SwitchSubscriptionDialog.ts, src/subscription/UpgradeSubscriptionWizard.ts, src/subscription/giftcards/PurchaseGiftCardDialog.ts, and src/subscription/giftcards/RedeemGiftCardWizard.ts.
  - The problem statement and requirements are narrowly about replacing deprecated provider creation in pricing utilities/tests and preserving identical behavior/type/arguments.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.88)
- **Gold patch similarity:** 0.0%
- **Causal chain:** Problem statement identified a deprecated provider-creation API -> agent searched for the provider/function and inspected PriceUtils plus downstream usages -> agent validated its understanding with a small TS experiment -> agent formulated the correct refactor plan -> editing command failed and the trajectory ended mid-refactor, leaving no completed patch.
- **Behavior:** Progressive, code-driven investigation with a correct refactor plan, but the work stopped mid-edit after tooling friction; genuine intent, incomplete delivery.

> The trajectory looks like a genuine but incomplete attempt to implement the requested refactor, not a leakage-driven solve. The agent began by exploring the codebase, searching for the relevant symbols, reading PriceUtils.ts and multiple call sites, and even attempting to reproduce/understand behavior with a small TypeScript script before editing. Its Step 16 plan closely matches the core required change: remove the deprecated function-based provider path, expose PriceAndConfigProvider as the co

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 14 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_tutao__tutanota-219bc8f05d7b980e038bc1524cb021bf56397a1b-vee878bb72091875e912c52fc32bc60ec3760227b`

### Task Context

**Repository:** `tutao/tutanota` (version )
**Core requirement:** Make `EventBusClient` handle incoming WebSocket messages consistently by using a predictable internal message handler and ensuring ordered processing of entity updates plus reliable delivery of unread counter updates.
**Severity:** SEVERE
**Labels:** `approach_lock`, `scope_creep`

### Contamination Signals

- **SCOPE_CREEP:** 9 of 13 hunks are UNRELATED to the stated problem

### Label Analysis

**approach_lock** (confidence: 0.88):
  This task shows the circular-test-patch-dependency subtype of approach_lock. The stated task is narrowly about websocket message routing and sequencing in EventBusClient, but dependency analysis says the F2P tests require a separate internal refactor (`_state` -> `state`) and associated logging/reconnect edits that the problem does not ask for. That means an agent could implement all stated acceptance criteria correctly and still fail because the benchmark expects unrelated patch hunks to be present. This is not merely wider behavioral coverage; it is the tests effectively binding success to out-of-scope implementation changes.
  - Cross-reference analysis reports 78 circular dependencies, explicitly noting: "This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for."
  - Test 'test/tests/api/worker/EventBusClientTest.js | test suite' is linked to UNRELATED hunks [2, 3, 4, 6, 7, 9, 10, 11, 12] with conf=0.95.
  - Test 'test/tests/api/worker/facades/LoginFacadeTest.js | test suite' is also linked to the same UNRELATED hunks [2, 3, 4, 6, 7, 9, 10, 11, 12] with conf=0.95, despite the problem being only about EventBusClient message handling.
**scope_creep** (confidence: 0.77):
  The gold patch bundles a substantial refactor beyond the requested websocket-message fix. The acceptance criteria focus on introducing MessageType, `_onMessage`, parsing and routing messages, sequential entity-update processing, and unread-counter forwarding. In contrast, most of the patch is a broader internal `state` naming refactor plus related log/reconnect edits. Because 9 of 13 hunks are classified as unrelated to the stated problem, the patch clearly expands beyond task scope.
  - Gold patch analysis: "Has excess: True" with 13 hunks total, of which 9 are marked UNRELATED.
  - Only hunks 0, 5, and 8 are REQUIRED for the acceptance criteria; hunk 1 is ANCILLARY.
  - Hunk 2: constructor rename from `this._state` to `this.state` is marked UNRELATED.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** GENUINE_SOLUTION (confidence: 0.77)
- **Gold patch similarity:** 0.0%
- **Causal chain:** Problem statement named `EventBusClient.ts` -> agent inspected relevant sections (`_message`, websocket hookup, `_state`, error/close handlers) -> inferred the bug was mostly inconsistent internal naming and message typing while existing queueing already preserved order -> applied targeted renames/enum usage -> ran checks/tests and then inspected repo tests for direct calls to the renamed method.
- **Behavior:** Methodical, file-local debugging and refactoring based on the problem statement; no strong evidence of benchmark leakage.

> This looks like a legitimate repository-driven fix rather than leakage. The agent began from the problem statement, opened the named file, inspected the websocket message handler, the connect method, constructor/state initialization, and searched for `_state` references before proposing a concrete plan. Its planned edits are consistent with what a competent developer would infer from the description: add a `MessageType` enum, rename `_message` to `_onMessage`, wire the socket to the renamed hand

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 9 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_tutao__tutanota-befce4b146002b9abc86aa95f4d57581771815ce-vee878bb72091875e912c52fc32bc60ec3760227b`

### Task Context

**Repository:** `tutao/tutanota` (version )
**Core requirement:** Simplify SendMailModel test initialization by passing a Map directly as the fourth argument to initWithDraft instead of wrapping that Map in Promise.resolve() when asynchronous behavior is not needed.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`, `wide_tests`

### Contamination Signals

- **SCOPE_CREEP:** 57 of 61 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.98):
  The benchmark task describes a very small test-focused cleanup, but the gold patch bundles a large unrelated refactor across mail viewer, UI, search, and other components. Because the overwhelming majority of behavioral hunks are marked UNRELATED to the acceptance criteria, this is a clear case of scope expansion in the patch itself, not just ancillary compilation support.
  - Gold patch analysis reports Has excess=True with 61 hunks total: only hunk 7 is REQUIRED, while 57 hunks are UNRELATED.
  - The stated scope is narrow: simplify SendMailModel test calls to pass `new Map()` directly to `initWithDraft`, especially in REPLY and FORWARD cases.
  - Representative UNRELATED behavioral hunks include hunk 16 (`MailViewer` constructor/state refactor), hunk 25 (`MailViewer` inline-image/dropdown behavior), hunk 50 (`MailViewerViewModel.forward()` rewrite), and hunk 57 (`assignMail` / `initAsResponse` flow rewrite).
**approach_lock** (confidence: 0.90):
  This is the circular test-patch dependency subtype of approach_lock. The failing-to-passing set appears to require numerous unrelated code changes from the bundled commit, so an agent can solve the described issue correctly and still fail benchmark tests. The lock is not about a specific internal implementation detail of the direct-Map fix; it is that the benchmark effectively demands unrelated patch content to satisfy the F2P set.
  - Cross-reference analysis reports: "Circular dependencies detected: 78" and explicitly calls this "a strong APPROACH_LOCK signal."
  - `test/tests/mail/SendMailModelTest.js | test suite` is linked to UNRELATED hunks [2, 3, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60].
  - Many completely unrelated F2P suites (e.g. `LoginFacadeTest.js`, `CalendarModelTest.js`, `WizardDialogNTest.js`) also depend on large sets of UNRELATED hunks.
**wide_tests** (confidence: 0.70):
  The benchmark's F2P coverage extends far beyond the described acceptance criteria. Instead of focusing on the SendMailModel test simplification, it includes many extra test suites for unrelated product areas. That makes the test scope materially wider than the task specification.
  - Requirements are narrowly limited to `SendMailModel` / `initWithDraft` parameter simplification and preserving the REPLY and FORWARD initialization tests.
  - The F2P set contains 78 test suites spanning unrelated areas such as `LoginFacadeTest.js`, `LoggerTest.js`, `CalendarModelTest.js`, `ExporterTest.js`, and `WizardDialogNTest.js`, not just `SendMailModelTest.js`.
  - Cross-reference links those suites to unrelated mail-viewer/UI/API hunks rather than only to the `initWithDraft` change.

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.92)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent appears to have anchored on a mismatched issue framing about MailViewer lifecycle/rendering, explored files consistent with that framing, and then planned fixes in those areas; this led it away from the real SendMailModel/initWithDraft simplification task and resulted in no usable solution.
- **Behavior:** Progressive exploration, but of the wrong problem: the agent chased unrelated MailViewer/rendering issues that partially align with contaminated gold-patch scope and never formed intent around the actual SendMailModel Map-vs-Promise simplification.

> The agent did not pursue the actual benchmark task described in the problem statement. The stated issue is narrowly about simplifying SendMailModel-related test initialization by passing a direct Map instead of Promise.resolve(new Map()) into initWithDraft. A genuine trajectory would be expected to inspect SendMailModel tests, initWithDraft signatures, and possibly related call sites such as MailEditor or SendMailModel. Instead, from the very first step the agent reframed the task as fixing "Mai

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 57 UNRELATED patch hunks — the gold patch may need to be scoped down.

---

## Contamination Narrative: `instance_tutao__tutanota-fe240cbf7f0fdd6744ef7bef8cb61676bcdbb621-vc4e41fd0029957297843cb9dec4a25c7c756f029`

### Task Context

**Repository:** `tutao/tutanota` (version )
**Core requirement:** Add consistent calendar event date validation so events with invalid date values, pre-1970 start dates, or start times that are not strictly before end times are identified and rejected consistently in both creation and import flows.
**Severity:** SEVERE
**Labels:** `scope_creep`, `approach_lock`

### Contamination Signals

- **SCOPE_CREEP:** 5 of 19 hunks are UNRELATED to the stated problem

### Label Analysis

**scope_creep** (confidence: 0.91):
  The requested task is narrowly about validating event dates and returning/using the specified CalendarEventValidity outcomes consistently in creation and import flows. The gold patch goes beyond that by adding a new partial-import confirmation/warning UX in CalendarImporterDialog, plus supporting translation entries. Those user-facing messaging changes are explicitly out of scope in the provided task spec, so the patch contains behavioral scope expansion beyond what the benchmark problem asks for.
  - Problem decomposition/out-of-scope explicitly says the task 'does not specify UI text or warning message changes.'
  - Hunk 14 in src/calendar/export/CalendarImporterDialog.ts is classified UNRELATED: 'adds/refactors confirmation dialogs and warning messaging for partially skipped imports.'
  - Hunks 16, 17, and 18 in src/translations/de.ts, src/translations/de_sie.ts, and src/translations/en.ts add new UI strings for those importer messages, which are outside the requested validation behavior.
**approach_lock** (confidence: 0.58):
  There is moderate evidence of a circular test-patch dependency: some fail-to-pass tests appear to depend on unrelated importer-dialog and translation changes, not just on the requested event-validity behavior. If so, an agent could correctly implement checkEventValidity and consistently reject invalid events, yet still fail because it did not reproduce the gold patch's extra warning-dialog/translation approach. That fits the approach_lock subtype where tests require unrelated patch hunks. Confidence is not maximal because the per-test alignment report did not independently flag excess, so the cross-reference signal may overapproximate.
  - Cross-reference analysis reports circular dependencies for 107 F2P tests and explicitly says: 'This is a strong APPROACH_LOCK signal: tests require code the problem doesn't ask for.'
  - Example cross-reference: 'test/tests/calendar/CalendarImporterTest.js | test suite' → UNRELATED hunks [2, 14, 17] (conf=0.95).
  - Example cross-reference: 'test/tests/calendar/CalendarUtilsTest.js | test suite' → UNRELATED hunks [2, 14, 17] (conf=0.95).

### Agent Evaluation Behavior

#### Agent: Claude Opus 4.1 - paper

- **Classification:** PARTIAL_MATCH (confidence: 0.90)
- **Gold patch similarity:** 0.0%
- **Causal chain:** The agent read the requirements, explored the relevant calendar creation/import code paths, found existing local validation and pre-1970 handling, inferred that validation should be centralized and reused, began planning edits in CalendarUtils and CalendarEventViewModel, but did not finish or submit a concrete patch.
- **Behavior:** A genuine exploratory attempt that identified the right subsystem and sketched the right direction, but failed to carry the implementation through to a working patch.

> The trajectory looks like ordinary, non-leaky debugging and codebase exploration rather than benchmark leakage. The agent first surveyed likely calendar-related files, then inspected parsing/import and creation paths, identified existing ad hoc checks in CalendarEventViewModel, noticed the pre-1970 handling, and formed a reasonable plan to introduce shared validation for both manual creation and import. This is consistent with genuine problem-solving. However, the run did not culminate in an act

### Diagnosis

**Agent impact:** 0/1 analyzed agents showed leakage patterns on this task. **Action:** Review 5 UNRELATED patch hunks — the gold patch may need to be scoped down.

---
