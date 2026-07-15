# Route Evidence, Not Models

## Oracle-aware active verification for SWE training, rollout, and evaluation

**Status:** research specification, not an empirical result.  Bench Cleanser does
not yet claim that its router is calibrated, that it saves a particular fraction
of executions, or that filtering improves a trained model.  Those are the claims
this program is designed to test.

## Thesis

Many SWE benchmark, reward-learning, and rollout-selection pipelines contain
multi-stage internals but collapse a harness outcome into one terminal label.
That label is then easy to consume as if it were candidate truth.  The collapse,
not the existence of tests, is unsafe: tests can be weak, toxic, flaky,
over-specific, contaminated, or run in a broken environment.  An incorrect patch
may pass; a valid alternative patch may fail; an environment error may be
recorded as model failure.

The research program therefore separates three truth uncertainties:

1. **task/specification uncertainty** — is candidate correctness even
   well-defined for this issue?
2. **candidate uncertainty** — conditional on a valid task, is this patch or
   trajectory correct?
3. **verifier uncertainty** — would the available evidence/test/environment
   produce an informative, valid label for this candidate?

The engineering-alpha manifest/router currently exposes candidate and verifier
risk only. Corpus `0.6.0` now separates deterministic label evidence from the
randomized live behavior trajectory, and evaluation `0.5.0` joins target-policy
outcomes to the exact terminal behavior log while reporting the logger identity
separately. Task-validity, conditional-candidate-correctness, and per-event
evidence-validity adjudications remain outside live policy state. A learned research policy
must add a deployable task-validity estimate rather than bury ambiguity inside
candidate error; that routing surface is not implemented today.

Task validity must not be collapsed with **agent-relative actionability**. A
well-defined task can still have an incomplete, poorly structured, or
model-mismatched issue report. Recent controlled bug-report studies report that
removing requirements, localization cues, or report structure can change agent
solve rates, while the effect of a particular information type varies by model
([What Makes a Good Bug Report for an AI Agent? v1](https://arxiv.org/abs/2607.07593v1),
[`bug-report-ablation-actionability`]). A separate study likewise finds that
operational cues such as localization and suggested fixes can matter even when
human-oriented report components are individually redundant
([Writing Bug Reports for Software Repair Agents v1](https://arxiv.org/abs/2607.09553v1),
[`agent-ready-operational-cues`]). Actionability is therefore a deployable,
lifecycle- and model-relative state, not curator truth and not part of the
unsafe-accept definition. Filtering low-actionability but valid tasks would
silently change difficulty and the target population.

An **evidence intervention** is the deliberate choice of the next measurement
procedure while the candidate and underlying task truth remain fixed: for
example, specification clarification/refinement, a semantic judge, static
checker, compiler, targeted reproduction, full harness, oracle-hardening
procedure, or blinded human review. Repeating an unchanged test is a repeated
measurement; adding adversarial or sanity checks changes the measurement
procedure and is therefore an intervention. Specification refinement must be
logged separately because it changes the information available about the task,
not the fixed underlying task or candidate.

These execution regimes must not be conflated:

| Regime | What actually runs | Representative work | Role in this program |
|---|---|---|---|
| Containerized execution | Repository tests in a per-task container | [DockSmith v2](https://arxiv.org/abs/2602.00592v2), [SWE-Hub v1](https://arxiv.org/abs/2603.00575v1) | One possible execution substrate |
| Container-free execution | Tests still run, isolated without a per-task container | [SWE-MiniSandbox v5](https://arxiv.org/abs/2602.11210v5) | A potentially cheaper substrate, not execution-free verification |
| Learned execution surrogate | A model predicts environment or test feedback | [SWE-World v1](https://arxiv.org/abs/2602.03419v1) | A curator-context upper bound where reported inputs are unavailable live |
| Execution-free verifier | A semantic or repository judge scores a patch without running it | [SWE-RM v1](https://arxiv.org/abs/2512.21919v1), [Dockerless v1](https://arxiv.org/abs/2606.28436v1) | Evidence actions and serious baselines, not presumed truth |
| Selective acquisition | A policy chooses specification, semantic, static, targeted, full, hardening, human, or abstention evidence per candidate | Proposed program | The unvalidated target contribution |

[Kimi-Dev v3](https://arxiv.org/abs/2509.23045v3) is a mixed training recipe,
not an end-to-end Docker-free verifier. Its synthetic file-view/search skill
prior is execution-free, while Agentless RL and BugFixer/TestWriter verification
use final execution outcomes and thousands of Docker environments. Likewise,
SWE-ZERO→HERO uses a global execution-free-to-execution-backed curriculum.
These are downstream training baselines. Containerized versus container-free
physical execution is a substrate factor beneath an evidence action, not a
synonym for execution-free verification.

The proposed system acquires the next piece of evidence only when its expected
reduction in verification loss justifies its cost.  Depending on the instance and
the evidence already collected, it can:

- accept or reject using calibrated static/semantic evidence;
- acquire repository-supported specification clarification while preserving the
  original report and target-population identity;
- run a compiler, type checker, or targeted reproduction test;
- run a complete isolated test environment;
- harden a suspect oracle with gold-sanity and adversarial tests;
- abstain and quarantine the example rather than manufacture a label.

The same exactly joined contracts—not one truth-bearing live manifest—must span
all three places. Training and rollout operate on the deployable manifest,
evidence, and policy log. Privileged task/candidate/oracle adjudications remain
in the curator corpus and are joined only for offline learning, calibration, or
evaluation:

| Stack position | Deployable decision surface | Privileged/offline join |
|---|---|---|
| Training data / SFT | admit, weight, acquire more evidence, or quarantine from reference-free state | train/calibrate on blinded corpus truth; never expose adjudicated labels as admission features |
| RL and rollout selection | score cheaply, acquire execution selectively, harden, or abstain | construct and audit rewards from exact candidate/evidence joins rather than terminal self-report alone |
| Evaluation | log pre-action state, acquire evidence, and preserve abstentions | join truth-free outcomes to the exact corpus for task-validity, conditional-correctness, verifier-validity, and denominator reporting |

The broader verifier problem is itself dynamic. [The Verification Horizon
v2](https://arxiv.org/abs/2606.26300v2) argues that a policy can outpace and
exploit a fixed verifier, motivating co-evolution and evaluating signals along
scalability, faithfulness, and robustness
(`verification-horizon-coevolving-verifier`). That is direct motivation, not
the proposed novelty: verifier co-evolution does not by itself specify a
deployable per-candidate sequence of evidence actions, identify latent oracle
validity, or control accepted-set false-accept risk.

The public hook is **“Route evidence, not models. Execution is a measurement,
not ground truth.”** The operating premise is: **every SWE verifier is a noisy
sensor; learn which sensor to query next for this candidate under a false-accept
budget.** This differs from asking whether an agent should use execution while
generating a patch: the target is post-generation, multi-modal, oracle-aware
evidence acquisition. The proposed outcome is
execution-minimal, risk-controlled verification—not Docker obsolescence or
execution-free verification by default.

## Proposed contribution and novelty boundary

“Hybrid execution-based plus execution-free verification” is already occupied,
as are generic adaptive compute, selective expert/model calls, and calibrated
risk gates. If the prospective experiment supports it, the proposed empirical
contribution is narrower: **candidate-level sequential acquisition among
verification evidence modalities, under a false-accept budget, while jointly
modeling candidate correctness, task validity, and the validity and
informativeness of each acquired oracle**. This remains a hypothesis, not an
established novelty or performance claim. It is not a fixed cascade, generic
uncertainty router, or another LLM audit taxonomy.

[Bayesian Control for Coding Agents v1](https://arxiv.org/abs/2606.24453v1)
makes the novelty boundary stricter. It already formulates coding-agent
orchestration as cost-sensitive sequential hypothesis testing over candidate
correctness, treats critics as noisy observations, and chooses among more
evidence, refinement, expensive verification, and stopping
(`bayesian-control-sequential-orchestration`). Neither Bayesian belief-state
routing nor sequential cost-aware verification is therefore novel here. The
defensible contribution must be the combination the reported controller does
not study: task truth separated from candidate truth, a verifier that can itself
be invalid rather than a deterministic oracle, a paired intervention corpus,
and a prospectively frozen accepted-set false-accept constraint.

The constraint is not novel by itself either. [LEC
v3](https://arxiv.org/abs/2512.01556v3), [SCoRE
v1](https://arxiv.org/abs/2603.24704v1), [Conformal Selective Acting
v1](https://arxiv.org/abs/2605.20270v1), and the [joint selective certificate
v1](https://arxiv.org/abs/2606.08517v1) already address
selection-conditioned risk, general selected-set risk, anytime pathwise risk,
and joint risk–acceptance–utility certification. The claim must therefore be
the SWE-specific empirical combination: **which fallible evidence intervention
to buy next, when both the task and verifier can be wrong, and whether that
policy improves an equal-budget candidate-selection frontier on a paired
prospective corpus**. A risk gate without acquisition and an acquisition
controller without oracle fallibility are both required baselines.

The closest systems differ on the deployability and decision axes that matter:

| Work | Deployable without gold/reference | Per-candidate next-evidence choice | Oracle fallibility modeled | Prospective false-accept budget |
|---|---|---|---|---|
| [R2E-Gym v1](https://arxiv.org/abs/2504.07164v1) | Yes | No—fixed top-N then tests | No | No |
| [SWE-RM v1](https://arxiv.org/abs/2512.21919v1) | Yes | No—fixed semantic or hybrid feedback | No | No |
| [SWE-World v1](https://arxiv.org/abs/2602.03419v1) | No in the reported curator-context setup | No—learned execution surrogate | Learns Docker targets, not latent oracle validity | No |
| [Dockerless v1](https://arxiv.org/abs/2606.28436v1) | No in the evaluated reference-context setup | No—fixed execution-free verifier | No | No |
| [SWE-MiniSandbox v5](https://arxiv.org/abs/2602.11210v5) | Yes as infrastructure | No—execution substrate, not an evidence policy | No | No |
| [To Run or Not to Run v1](https://arxiv.org/abs/2606.26978v1) | Empirical trajectory study | No—study, not a routing policy | Documents execution and environment outcomes; no latent oracle model | No |
| [Bayesian Control for Coding Agents v1](https://arxiv.org/abs/2606.24453v1) | Yes for the reported critic/verifier interface | Yes—critique, refine, verify, or stop | No—the SWE harness is defined as a deterministic correctness oracle | No—optimizes expected utility, not accepted-set risk |
| [SCATE v1](https://arxiv.org/abs/2607.08983v1) | Yes for its reported test-generation setting | Adjacent—per-class next test-generation action, not candidate-verification evidence | No—coverage and complexity feedback are treated as objectives | No |
| [Rubric-Supervised Critic v1](https://arxiv.org/abs/2603.03800v1) | Yes | No—fixed critic/reranker | No | No |
| [LLM-as-a-Verifier v2](https://arxiv.org/abs/2607.05391v2) | Yes | No—scaled semantic verifier | No | No |
| [Calibrating Conservatism (CCO) v1](https://arxiv.org/abs/2605.28807v1) | Yes | No—risk gate without evidence acquisition | No | Analogous online violation-rate gate under an eventually-safe action family; not the same candidate false-accept estimand |
| [LEC v3](https://arxiv.org/abs/2512.01556v3), [SCoRE v1](https://arxiv.org/abs/2603.24704v1), [CSA v1](https://arxiv.org/abs/2605.20270v1), and [joint certificate v1](https://arxiv.org/abs/2606.08517v1) | Yes under their declared calibration/online assumptions | No—select, route, or abstain after scoring rather than acquire a new evidence modality | No | Analogous risk guarantees conditional on a valid declared loss/oracle; not direct SWE candidate false-accept control with fallible labels or verifiers |
| [Test-Time Harness Evolution v1](https://arxiv.org/abs/2607.08124v1) | Yes on the reported unlabeled test traces | No—adapts a harness across test inputs rather than querying evidence for one candidate | Names execution-proxy reliability as a challenge; does not model latent oracle validity | No |
| Proposed program | Target: yes | Target: sequential multi-action choice | Target: explicit task/candidate/oracle model | Target: frozen prospective bound |

| Prior work | What the paper reports | Boundary this project must cross |
|---|---|---|
| [SWE-bench v3](https://arxiv.org/abs/2310.06770v3) and [SWE-bench Goes Live v2](https://arxiv.org/abs/2505.23419v2) | Establish executable issue-resolution evaluation and a continuously refreshed variant | A benchmark harness supplies observations; it does not make task, candidate, or oracle validity interchangeable |
| [SWE-smith v2](https://arxiv.org/abs/2504.21798v2), original [SWE-rebench v2](https://arxiv.org/abs/2505.20411v2), and successor [SWE-rebench V2 v2](https://arxiv.org/abs/2602.23866v2) | Scale task synthesis, training, and refreshed evaluation environments | They are candidate/task sources and test beds; their generated tasks and oracles still require the paired validity audit |
| [Agentless v2](https://arxiv.org/abs/2407.01489v2) | Static localization and patch sampling followed by generated reproduction/regression tests | Generated tests are themselves noisy; routing their acquisition and validating their oracle remain open |
| [SWE-Gym v2](https://arxiv.org/abs/2412.21139v2) | Executable training gym and execution-trained outcome verifier | Environment construction is costly and the verifier leaves a substantial Best@K gap |
| [SWE-RL v2](https://arxiv.org/abs/2502.18449v2), [Agent-RLVR v2](https://arxiv.org/abs/2506.11425v2), [long-context multi-turn SWE RL v2](https://arxiv.org/abs/2508.03501v2), and [SWE-Master v2](https://arxiv.org/abs/2602.03411v2) | Report execution-grounded reinforcement-learning recipes for multi-turn SWE agents | Better training with executable rewards does not establish which evidence to acquire for each rollout or whether the reward oracle is valid |
| [R2E-Gym v1](https://arxiv.org/abs/2504.07164v1) | Fixed composition of an execution-free ranker and execution-based generated tests (`r2e-fixed-topn-hybrid`, `r2e-generated-test-toxicity`) | It executes the retained set rather than learning whether execution has positive value for each case |
| [SWE-RM v1](https://arxiv.org/abs/2512.21919v1) | Reward-model ranking, AUC, and calibration all matter; the best reported RL reward combines execution and semantic feedback (`swe-rm-hybrid-rl-reward`) | Its best RL arm uses a fixed combination; it does not selectively acquire execution or model oracle validity |
| [SCATE v1](https://arxiv.org/abs/2607.08983v1) | Uses LinUCB to choose `DEFAULT`, `ANALYSIS`, or `STOP` test-generation actions from static class features and runtime coverage/complexity feedback, with a reward that trades test gains against token-dollar cost (`scate-contextual-bandit-test-routing`); the reported study is Defects4J/Java and trains and evaluates on classes drawn from the same projects (`scate-java-generation-scope`) | This is the closest direct contextual-bandit/action-cost baseline, but it optimizes unit-test-generation coverage and cost; it does not choose correctness-evidence modalities for a fixed candidate, model oracle validity, or control accepted-set false-accept risk |
| [Bayesian Control for Coding Agents v1](https://arxiv.org/abs/2606.24453v1) | Maintains a posterior over candidate correctness and dynamically chooses critics, refinement, a costly verifier, or stopping (`bayesian-control-sequential-orchestration`); it reports that Bayesian control is most useful when verification is costly and critics are informative but imperfect, while simple gates or always-verify win in other regimes (`bayesian-control-regime-map`) | It defines the terminal verifier as deterministic correctness—including a Podman SWE-bench harness—and has no distinct public-test critic for SWE-bench (`bayesian-control-deterministic-oracle-boundary`); this project must model task and oracle fallibility, preserve abstention, and test accepted-set risk rather than relabel harness success as truth |
| [SWE-Reasoner v2](https://arxiv.org/abs/2503.23803v2), [SWE-PRM v2](https://arxiv.org/abs/2509.02360v2), [EGSS v1](https://arxiv.org/abs/2602.05242v1), and [SWE-Protégé v1](https://arxiv.org/abs/2602.22124v1) | Test-time search, trajectory intervention, entropy-guided scaling, and selective expert calls already allocate agent compute adaptively (`egss-tool-entropy-allocation`) | Adaptive agent compute is not the claim; the acquisition policy must choose among verification modalities and account for whether their observations are trustworthy |
| [TwinRouterBench v2](https://arxiv.org/abs/2605.18859v2) and [Not All Errors Are Equal v1](https://arxiv.org/abs/2606.04402v1) | Cheapest-sufficient step-level model routing and consequence × marginal-utility compute allocation provide direct SWE baselines (`twinrouter-cheapest-sufficient-model`, `twinrouter-execution-verified-tiers`, `consequence-marginal-utility-allocation`) | Generic cost-aware routing is not novel; this project routes evidence interventions under candidate-, task-, and oracle-validity uncertainty |
| [SWE-ZERO to SWE-HERO v2](https://arxiv.org/abs/2604.01496v2) and [Kimi-Dev v3](https://arxiv.org/abs/2509.23045v3) | Use mixed global curricula: execution-free synthetic skill/trajectory data followed by execution-backed stages, RL, or verification (`swe-hero-two-stage-curriculum`) | Their allocation is global rather than repository-, task-, patch-, or uncertainty-adaptive; Kimi-Dev is not Docker-free end to end |
| [From Patches to Trajectories v1](https://arxiv.org/abs/2605.21996v1), [Open-SWE-Traces v1](https://arxiv.org/abs/2606.16038v1), and [SWE-Replay v2](https://arxiv.org/abs/2601.22129v2) | Expand trajectory supervision through privileged reconstruction, open traces, or replay | They are training-data sources and upper bounds; their labels still require provenance, leakage, and verifier-validity audits before causal training claims |
| [SWE-ABS v1](https://arxiv.org/abs/2603.00520v1) and [STING v1](https://arxiv.org/abs/2604.01518v1) | Coverage-, mutation-, and adversarial-test augmentation expose weak regression suites and can materially change accepted patches and rankings | Oracle hardening itself is not novel; the open decision is when its extra execution is needed and whether the hardened oracle is valid |
| [Rethinking the Value of Agent-Generated Tests v2](https://arxiv.org/abs/2602.07900v2) | Directly studies agent-generated tests as SWE-agent feedback rather than assuming that more generated tests imply better verification | Generated-test outcomes are one fallible evidence action; transfer to a risk-controlled acquisition policy must be measured |
| [All Smoke, No Alarm v1](https://arxiv.org/abs/2606.18168v1) | Applies an eight-category syntactic taxonomy to 86,156 agent-authored test-file patches and reports that 80.2% have weak or no explicit oracle signals; reliability is checked against a 384-patch human-labeled sample (`all-smoke-oracle-signal-prevalence`) | Test-file presence and syntactic assertion strength are cheap features, not proof that a test is semantically valid, discriminative for a candidate, or safe to use as a reward |
| [ReProAgent v1](https://arxiv.org/abs/2607.09123v1) | Uses localization, root-cause analysis, planning, repository context, and runtime interaction to generate reproduction tests from issue reports (`reproagent-runtime-test-action`, `reproagent-reproduction-rate-cost`) | Reproduction-test generation is a serious targeted-execution action and cost baseline; a generated test and its reported success still require evidence-validity adjudication |
| [DockSmith v2](https://arxiv.org/abs/2602.00592v2) and [SWE-Hub v1](https://arxiv.org/abs/2603.00575v1) | Scale environment/image construction and executable SWE infrastructure | They reduce acquisition friction but do not decide which candidate needs which evidence or validate the resulting oracle |
| [SWE-MiniSandbox v5](https://arxiv.org/abs/2602.11210v5) | Runs SWE workloads without per-task containers through a lighter isolation substrate | This is container-free execution, not execution-free verification and not an evidence-routing policy |
| [SWE-World v1](https://arxiv.org/abs/2602.03419v1) | Learned transition/reward models can replace much Docker feedback during rollout, post-training, and test-time scaling (`swe-world-transition-reward-surrogate`, `swe-world-curator-context`) | The surrogate is trained on Docker targets and receives curator-only gold patch/test context; final benchmark truth remains Docker-based |
| [Dockerless v1](https://arxiv.org/abs/2606.28436v1) | A read-only, environment-free verifier can approach execution-reward RL (`dockerless-reference-context`, `dockerless-execution-derived-training-labels`) | It receives the reference patch at inference and learns from execution-derived labels; it replaces rather than selectively acquires execution |
| [The SWE-Bench Illusion v4](https://arxiv.org/abs/2506.12286v4) and [Automated Benchmark Auditing v2](https://arxiv.org/abs/2605.26079v2) | Expose consequential task/test defects through manual, static, and trajectory audits | An audit taxonomy or sampled precision result alone is not a calibrated evidence-acquisition policy or a full-population guarantee |
| [Repairing Qiskit Programs using Bugs4Q v1](https://arxiv.org/abs/2607.09007v1) | Re-executes benchmark entries across pinned library versions and reports version-conditioned label inversion, invalid entries, and environment/API failures (`bugs4q-version-conditioned-validity`) | Benchmark identity must include the environment version; a passing or failing harness observation cannot by itself certify task or candidate truth |
| [To Run or Not to Run v1](https://arxiv.org/abs/2606.26978v1) | Holds a scaffold fixed, studies execution inside repair trajectories, and reports concentrated benefit alongside material cost and environment errors (`to-run-fixed-scaffold`, `to-run-environment-error-rate`) | Its proposed adaptive allocation motivates a direct baseline; this project must add post-generation multi-modal choice, explicit oracle validity, and a prospective accepted-set risk bound |
| [Scaffolding Evolution v1](https://arxiv.org/abs/2607.03691v1) | Holds the LLM fixed across 35 Qwen Code releases on 50 stratified SWE-bench Verified tasks and reports no statistically significant resolve-rate improvement while later releases consume more resources (`scaffolding-evolution-fixed-model`) | Scaffold revision is part of treatment identity and cost, but the result is one scaffold/model and a 50-task subset; it is not a population claim about all scaffolds or an evidence-routing policy |
| [How Far Are We from Detecting Flaky Tests? v1](https://arxiv.org/abs/2607.09345v1) | Finds shortcut-sensitive code-only flakiness results and reports that many CI cases require evidence beyond test code, including repeated execution (`flakiness-static-evidence-limit`) | This is direct evidence against treating a static surrogate as universally sufficient; the router must learn when runtime history or new execution is necessary rather than infer a global Docker rule |
| [Auditing Reward Hackability v1](https://arxiv.org/abs/2606.16062v1) | Docker-verified incorrect patches can pass; gold-sanity rejects many generated-test augmentations | Shows why verifier-validity uncertainty and hardening must be first-class routing targets |
| [The Verification Horizon v2](https://arxiv.org/abs/2606.26300v2) | Frames verifier quality through scalability, faithfulness, and robustness and argues for policy-verifier co-evolution as fixed rewards saturate or become exploitable (`verification-horizon-coevolving-verifier`) | This establishes the dynamic-verifier problem, not candidate-level sequential evidence acquisition, a deployable oracle-validity model, or a prospective false-accept bound |
| [Calibrating Conservatism for Scalable Oversight v1](https://arxiv.org/abs/2605.28807v1) and [Self-Evolving Agents with Anytime-Valid Certificates v1](https://arxiv.org/abs/2607.00871v1) | Conditional risk control and anytime-valid gates have been demonstrated in SWE-agent settings | Statistical gating itself is not novel, and its bounded-loss/safe-family assumptions must be explicit; this project must acquire among verification modalities and model oracle validity |
| [LEC v3](https://arxiv.org/abs/2512.01556v3), [SCoRE v1](https://arxiv.org/abs/2603.24704v1), [Conformal Selective Acting v1](https://arxiv.org/abs/2605.20270v1), and [joint selective certificate v1](https://arxiv.org/abs/2606.08517v1) | Provide finite-sample or anytime control of selection-conditioned/general selected risk, and in the joint certificate also acceptance and utility (`lec-selection-conditioned-risk-control`, `score-general-selected-risk-control`, `csa-anytime-pathwise-selective-risk`, `joint-certificate-risk-coverage-utility`) | Accepted-set risk, abstention, coverage, and utility certification are not novel; these methods must be evaluated as gates over the same calibrated scores, while this project must additionally choose evidence interventions and model invalid tasks/oracles |
| [A Rubric-Supervised Critic from Sparse Real-World Outcomes v1](https://arxiv.org/abs/2603.03800v1) | Distills sparse real-world outcomes into a rubric-supervised critic for candidate assessment and reranking | A fixed critic is a strong rollout-selection baseline; it does not choose the next evidence action or model test validity |
| [LLM-as-a-Verifier v2](https://arxiv.org/abs/2607.05391v2) | Score granularity, repeated judging, and criteria decomposition improve an execution-free verifier and Best-of-N ranking | Scaling one semantic verifier is a baseline action, not a substitute for deciding whether to acquire static, runtime, or oracle-hardening evidence |
| [From Confident Closing to Silent Failure v1](https://arxiv.org/abs/2606.09863v1) | Across the paper's tau2-bench setup no tested LLM-judge configuration exceeds 0.65 AUROC, and GPT-4o peaks at 0.537 on AppWorld API-call traces (`false-success-llm-judge-ceiling`) | This is evidence against treating self-report or an LLM judge as terminal truth, but tau2-bench and AppWorld are not SWE patch-verification populations; transfer must be tested rather than assumed |
| [SWE-Doctor v1](https://arxiv.org/abs/2607.00990v1) | Multi-faceted runtime diagnoses outperform treating generated reproduction tests as direct pass/fail targets; narrow or failing tests can mislead patch generation | Runtime diagnosis is a high-value targeted-execution action; deciding which candidates need it, and validating its generated tests, remain open |
| [What Makes a Good Bug Report for an AI Agent? v1](https://arxiv.org/abs/2607.07593v1), [TrajSpec v1](https://arxiv.org/abs/2607.07882v1), and [Writing Bug Reports for Software Repair Agents v1](https://arxiv.org/abs/2607.09553v1) | Study model-relative effects of issue content/structure and trajectory-guided repository-supported report refinement (`bug-report-ablation-actionability`, `trajspec-task-spec-refinement`, `agent-ready-operational-cues`) | They intervene on the specification used to generate a patch; this project must keep actionability distinct from validity and test post-generation specification evidence as one fallible, costed action rather than relabel hard tasks invalid |
| [PatchFusion v1](https://arxiv.org/abs/2607.01597v1) | Cross-candidate edit agreement can select or construct strong patches in milliseconds without test outcomes | Static candidate consensus is a serious baseline and evidence of likely correctness—not evidence that agents leaked the gold patch |
| [TraceProbe v1](https://arxiv.org/abs/2607.06184v1) | Canonical, deterministic trajectory structure exposes search loops, verification skips, and cross-run divergence beyond resolve rate | Trajectory diagnostics are not novel by themselves; router features must declare which are oracle-free and which use gold anchors |
| [Failure as a Process v1](https://arxiv.org/abs/2607.09510v1) | Studies onset, evolution, and recovery across CLI coding-agent trajectories and argues for earlier validation rather than terminal-outcome-only evaluation (`failure-process-early-intervention`) | Temporal intervention motivates rollout-time evidence routing, but post-hoc failure annotations and future trajectory events cannot enter a deployable pre-action state |
| [DeepSWE v1](https://arxiv.org/abs/2607.07946v1) | Original, multi-language patch tasks reduce memorization and inherited-test artifacts | It is a stronger fresh-repository test bed; it does not learn an evidence-acquisition policy |
| [TestEvo-Bench v1](https://arxiv.org/abs/2607.02469v1) | Live Java test-generation and test-update tasks provide purpose-built verifier targets | It is chiefly an oracle-hardening/test-generation test bed, not a general patch-verification benchmark |
| [Test-Time Harness Evolution v1](https://arxiv.org/abs/2607.08124v1) | Evolves an executable harness during evaluation from unlabeled traces and execution-derived proxy signals | Harness adaptation across test inputs is a distinct policy axis; the adaptation state must be frozen/logged for comparison, and proxy observations remain fallible evidence rather than truth |

The table records author-reported methods and results, not independent
replication. This matters especially for the rapidly changing 2026 preprints.
The novelty boundary should rest on inspectable inputs, interventions, and
estimands—not on treating a paper's headline benchmark rate as settled fact.

### Algorithmic foundations this project does not claim to invent

The routing problem is also an instance of older active-information-acquisition
and sequential-decision problems. A credible paper must say so directly rather
than presenting value of information, costly features, off-policy evaluation,
or conformal risk control as new algorithms.

| Foundation | What is already prior art | What remains SWE-specific here |
|---|---|---|
| [Adaptive submodularity v5](https://arxiv.org/abs/1003.3967v5) | Sequentially select observations for information gain under structural assumptions | SWE evidence actions need not be submodular or conditionally independent; those assumptions must be tested, not borrowed |
| [Costly-feature RL v2](https://arxiv.org/abs/1711.07364v2) and [EDDI v4](https://arxiv.org/abs/1809.11142v4) | Learn which costly feature to acquire next and when to classify | A compiler, generated test, full harness, or hardened oracle is an intervention with candidate-dependent failure and validity, not a passive feature lookup |
| [Doubly robust OPE v3](https://arxiv.org/abs/1511.03722v3) and [Double Reinforcement Learning v3](https://arxiv.org/abs/1908.08526v3) | Evaluate sequential policies from logged behavior data under overlap and nuisance-model assumptions | The artifact must log exact action-level propensities and validate them prospectively; citing OPE does not repair missing support or post-outcome logging |
| [Learn then Test v5](https://arxiv.org/abs/2110.01052v5) and [Conformal Risk Control v4](https://arxiv.org/abs/2208.02814v4) | Calibrate a finite family of predictive rules to control declared risks under exchangeability-style assumptions | The acquisition policy changes what labels are observed, repositories shift, and verifier validity is latent; any SWE false-accept bound must state the calibration population and failure modes |
| [LEC v3](https://arxiv.org/abs/2512.01556v3), [SCoRE v1](https://arxiv.org/abs/2603.24704v1), [CSA v1](https://arxiv.org/abs/2605.20270v1), and [joint certificate v1](https://arxiv.org/abs/2606.08517v1) | Control risk conditional on selection under finite-sample or online assumptions, with CSA adding anytime pathwise validity and the joint certificate adding acceptance and utility | Their calibrated score/gate can wrap a frozen SWE policy; it does not identify whether static, semantic, targeted, full, or hardened evidence should be acquired or whether the evidence oracle is valid |

Accordingly, the durable contribution is not a generic routing theorem. It is
the combination of (i) a deployable SWE action/state contract, (ii) a paired
candidate × evidence-intervention corpus with blinded task/candidate/oracle
labels, (iii) an action-observation model that treats execution as fallible, and
(iv) a frozen prospective result under an auditable false-accept budget.

Three restrictions are essential to a credible claim:

1. **Deployable router inputs.**  A live router may not see the gold patch, hidden
   tests, future commits, or an eventual Docker label.  Curator-only inputs can be
   used to construct training labels, never as inference features.
2. **No accuracy-only result.**  The result must expose the full risk–coverage–cost
   frontier, calibration, abstention, and false-accept behavior. Harm-weighted
   or “severe” errors require a separately declared harm annotation.
3. **History-conditioned acquisition propensities.**  A learned router changes
   which labels it observes.  Every action must record its probability given the
   complete decision history and its cost.  Collection must preserve positivity
   and overlap; sequential inverse-propensity or doubly robust estimates must
   handle time-varying confounding and be checked prospectively.

## Artifacts: deployable state and curator-only truth

Every task/candidate pair should be represented by two digest-joined surfaces.
The deployable validity manifest and policy log contain:

- immutable provenance: dataset revision, repository, full base commit, patch
  digest, scaffold version, prompt/model identity, image digest, dependency lock;
- pre-execution features: language/build system, scope, risky files, native
  dependencies, patch structure, and oracle-free trajectory diagnostics;
- deployable candidate/verifier state plus acquired environment observations:
  construction result, repeated-run stability, flake rate, setup/runtime error
  class, and historical repository failure rate;
- evidence events: source, status, cost, confidence, calibration identity, and
  whether the evidence is independent or derived from another signal;
- route history plus a separate write-ahead policy log: policy/code/config
  identity, complete concrete action catalog, chosen action and structured
  reason, history-conditioned behavior distribution, sampler draw, and terminal
  accept/reject/abstain state.

The curator-only corpus record contains blinded task validity—specification
completeness, ambiguity, leakage, and whether correctness is well-defined—plus
candidate correctness conditional on a valid task and provenance-bearing
evidence-validity adjudications with source, protocol, blinding, reviewer count,
agreement, and indeterminate status. The current manifest has no
task-validity prediction. A future learned policy may add a deployable estimate,
never the adjudicated label.

Training and rollout code consume the deployable surface for acquisition,
weighting, and quarantine. Offline policy learning may use the exact corpus join
as labels. Evaluation consumes truth-free outcomes plus that exact join to form
task-validity, conditional-correctness, verifier-validity, quarantine, cost, and
auditable-denominator estimates.

## Decision objective

For decision history \(h\), lifecycle context \(s\), and evidence-acquisition
action \(a\), the learned router should minimize a predeclared loss such as

\[
  \mathbb{E}[L_T(T,\hat T_{a,o})
  + \mathbf{1}\{T=\mathrm{valid}\}L_C(y,\hat y_{a,o})
  + \lambda_v \mathbf{1}\{V_a\ne\mathrm{valid}\} \mid h,s,a]
  + \lambda_c C(a),
\]

where \(T\) is task/specification validity, \(V_a\) is the validity of the
action-specific oracle/observation, and \(o\) is the observation returned by
action \(a\). Candidate loss is undefined and therefore excluded unless the
task is valid. The task, candidate, and invalid-observation losses must be
defined so the same failure is not counted twice; an integrated loss is also
valid if it states that decomposition explicitly. Subject to a declared
false-accept bound, acquire execution when its estimated value of information
exceeds its cost and acquire oracle hardening when test validity is the dominant
uncertainty.  False accepts should normally cost more than false rejects for
training rewards and public benchmark claims. If no action can meet the bound,
abstention is the correct output.

The primary controlled risk must use the accepted set as its explicit
denominator:

\[
R_{FA}=P\bigl(T\ne\mathrm{valid}\;\lor\;
(T=\mathrm{valid}\land y\ne\mathrm{correct})\mid D=\mathrm{accept}\bigr).
\]

Coverage, abstention/quarantine, and cost are reported separately so a policy
cannot satisfy the bound by silently accepting almost nothing. Indeterminate
task or candidate truth is not counted as a safe acceptance.

The repository's initial deterministic router is only an inspectable baseline.
Any future learned policy must be calibrated on repository- and time-disjoint
data and compared with conformal/selective prediction where risk guarantees are
claimed.

## Proposed method: task–candidate–oracle evidence acquisition

The method should not be a single risk score with a Docker threshold. At
history \(h\), learn at least five separately testable quantities:

- \(p_T(h)=P(\text{task/specification valid}\mid h)\);
- \(p_A(h,s)=P(\text{current specification actionable}\mid h,s)\), where
  lifecycle/model context \(s\) is explicit and actionability is not truth;
- \(p_y(h)=P(\text{candidate correct}\mid T=\text{valid},h)\);
- \(p_{V,a}(h)=P(V_a=\text{valid}\mid h,a)\), an explicit action-specific oracle-
  validity model;
- \(q_a(o\mid y,T,V_a,h)=P(o\mid y,T,V_a,h,a)\), an action-observation/confusion
  model that captures sensitivity, specificity, inconclusiveness, and failure
  conditional on oracle validity.

Oracle validity is therefore not hidden inside a generic outcome model. It is
necessary but not sufficient for value of information: two equally valid tests
can have very different ability to distinguish correct from incorrect
candidates.

For every lifecycle-available action—specification clarification, semantic
re-judging, static checking, targeted diagnosis, full execution, oracle
hardening, human review, or abstention—estimate the post-acquisition
verification loss and measured cost.
Gold-sanity and blinded human review are curator/evaluation actions, not assumed
available during live rollout; action availability must be encoded in state.
Choose the cheapest action whose conservative loss bound satisfies the
predeclared false-accept
budget; otherwise acquire the action with positive estimated value of
information, or abstain.  A weak or flaky full test can therefore route to
hardening instead of being treated as more authoritative merely because it ran.

The first learned baseline should be deliberately modest:

1. fit task-validity, candidate-correctness, evidence-validity, and action-
   observation heads on the paired corpus, plus a separately evaluated
   lifecycle-relative actionability diagnostic;
2. calibrate them only on repository- and time-disjoint calibration data;
3. estimate action value from counterfactual paired outcomes and measured cost;
4. compare a greedy value-of-information rule with a contextual-bandit policy;
5. freeze the policy before the final, temporally fresh evaluation.

Task validity is shared across all N candidates for a task. It governs
acceptance, quarantine, and whether task/oracle hardening is worthwhile, but
normally cannot rank candidates within that task; candidate and oracle state do
that work. Actionability is also shared at the initial task state but can change
after clarification and can interact with the generator; neither low
actionability nor high repair cost makes a valid task invalid.

Conformal risk control, conformal decision theory, or anytime-valid confidence
sequences are comparison methods, not decorative guarantees.  Their assumptions,
calibration population, subgroup behavior, and failure conditions must be stated
alongside any bound.

## Hypotheses and falsification criteria

### H1 — selective execution

On a frozen, time-, repository-, and language-disjoint stream, a calibrated
router avoids a material share of full-container executions while satisfying
two separately preregistered criteria against independent multi-adjudicator
task/candidate labels: (1) the one-sided upper confidence bound on accepted-set
false-accept risk \(R_{FA}\) is at most an absolute ceiling \(\epsilon\); and
(2) the one-sided upper confidence bound on the paired risk difference
\(R_{FA}^{router}-R_{FA}^{always}\) is at most a non-inferiority margin
\(\Delta\). An unsafe acceptance is an invalid/indeterminate task or an
incorrect/indeterminate candidate. Semantic judgment is an acquired evidence
modality, not the truth label.

**Falsified if:** always-execute dominates the router on the cost–risk frontier,
the absolute bound exceeds \(\epsilon\), the paired difference bound exceeds
\(\Delta\), or the result fails on compiled-language or risky-file subgroups.

### H2 — oracle validity

Explicit task/oracle validity and action-observation models reduce false accepts
and false rejects beyond a candidate-correctness-only router at matched evidence
cost.

**Falsified if:** the paired confidence interval includes no frontier improvement,
or hardening cost does not buy measurable risk reduction.

### H3 — action-set value

Targeted static/compiler/reproduction actions and oracle hardening improve the
cost–risk frontier beyond a binary execute/skip router.

**Falsified if:** removing those intermediate actions does not worsen the paired
frontier within uncertainty.

### H4 — downstream causal value

At equal model, unique task pool, optimizer tokens, rollout count, wall-clock
envelope, and seeds, validity-weighted or selectively verified SFT/RL data improve
fresh-task Pass@1 and reward-hacking robustness over raw, semantic-only, and
test-only filtering.

**Falsified if:** gains vanish after difficulty/effective-sample controls, fail on
fresh repository-disjoint evaluation, or come only from using fewer/easier
samples.

### H5 — evaluation validity

Validity-aware decisions move model scores and rankings closer to independent,
blinded multi-adjudicator task/candidate labels with explicit disagreement and
indeterminate outcomes, supported by hardened evidence, while exposing both raw
target-population estimates and validity-adjusted estimates or bounds.
Repeatability is secondary evidence, not the ground truth.

**Falsified if:** agreement with blinded adjudication does not improve, validity
adjustment merely drops hard tasks, or the audit systematically favors particular
model families.  A stable but wrong ranking does not satisfy this hypothesis.

### H6 — offline-policy validity

History-aware logged-policy estimates predict the risk, cost, and coverage of a
prospective randomized deployment within a preregistered tolerance.

**Falsified if:** inverse-propensity/doubly robust estimates miss prospective
outcomes, overlap collapses in material subgroups, or router drift makes the
logged estimand irrecoverable.

## Flagship empirical unit

The paper should have one center of gravity: **equal-budget Best-of-N rollout
selection on a fresh stream**, not three disconnected claims about SFT, RL, and
leaderboards. For every task, the generator and its N candidate patches are
frozen before verification; every method sees the same N candidates and receives
the same verification budget and wall-clock envelope. The primary outcomes are
selected-candidate correctness against blinded multi-adjudicator labels and the
false-accept–cost frontier of the frozen acquisition policy.

The preregistration must name one false-accept target, one primary cost measure,
one target population, and one unit of analysis. Events from the same candidate
are dependent; candidates from the same repository are clustered. Confidence
intervals and bootstraps must respect that hierarchy rather than treating every
test invocation as an independent row.

Scale should follow the risk claim, not a round-number dataset target. For a
false-accept target \(\epsilon\) and tail probability \(\delta\), with zero
observed false accepts, even the idealized one-sided binomial requirement is

\[
n \ge \left\lceil\frac{\log(\delta)}{\log(1-\epsilon)}\right\rceil,
\]

which is 299 accepted candidates for a 95% upper bound below 1%, or 149 for a
bound below 2%. Non-zero errors, repository clustering, subgroup claims, policy
selection, and adjudication uncertainty require more. A small pilot can debug
the protocol; it cannot support a low-risk headline.

The flagship figure should plot the one-sided false-accept bound against both
full-execution rate and measured total cost. It should show always-execute,
never-execute, fixed cascades, semantic verifiers, the learned acquisition
policy, and oracle upper bounds on the same candidates. A second panel should
decompose environment errors, weak-oracle false accepts, alternative-correct
false rejects, and abstentions. If always-execute appears at zero risk merely by
definition, the experiment has failed to measure oracle validity.

The minimum convincing release bundle is:

1. a fully paired development subset used to learn action-observation models;
2. a randomized, propensity-logged collection stream with positivity audits;
3. a repository-, language-, and time-disjoint frozen-policy evaluation;
4. raw per-candidate decisions, artifacts, costs, adjudications, and failure
   cases, including every abstention and environment error;
5. one controlled equal-budget Best-of-N rollout-selection demonstration before
   broader SFT/RL claims;
6. later SFT and RL experiments that reuse the same decisions while holding
   model, unique candidate pool, tokens, rollouts, wall-clock envelope, and
   seeds fixed.

This ordering binds the method to the complete SWE stack without making the
first paper depend on training several frontier-scale models. Rollout selection
is the direct online use of the policy; SFT weighting/quarantine and RL reward
auditing are downstream causal tests; validity-adjusted evaluation is a separate
estimand that must always be reported beside the raw benchmark score.

## Adoption surface: make the result reusable

A paper result alone will not make this a common SWE-stack dependency. The
release should make one evidence contract reusable at three integration points:

- a dataset transform that emits admission weights, quarantine decisions, and
  immutable evidence joins for SFT/RL corpora;
- a rollout hook that consumes a frozen candidate set and returns one selected
  patch or abstention under an explicit evidence budget; and
- an evaluator that reports the raw target-population score beside
  validity-aware bounds, abstentions, environment failures, and ranking shifts.

Reference adapters should target at least the SWE-bench harness, one widely used
agent scaffold, and plain JSONL/Parquet training pipelines. They must consume the
same manifest, action log, and curator join rather than three bespoke exports.
The portable public result should be a four-coordinate record—accepted-set
false-accept upper bound, coverage, measured total cost, and full-execution
rate—not a new scalar leaderboard score that hides abstention.

The adoption artifact should be the named **Verification Gap** corpus plus a
small challenge protocol on temporally fresh tasks. Participants may submit
semantic verifiers, fixed cascades, learned acquisition policies, or substrate
implementations, but all must operate on the same frozen candidates and return
the same audit record. Raw negative results, failed environments, weak-oracle
counterexamples, and policies beaten by patch size are part of the release; the
project becomes credible and useful by making failure analysis cheap, not by
manufacturing a winning headline.

The working paper title is **“Verification Gap: A Prospective Evaluation of
Oracle-Aware Evidence Routing for SWE Candidate Selection.”** “Route evidence,
not models” remains the public hook; the corpus and equal-budget challenge are
the result people should be able to use without adopting this implementation.

## Paired evidence dataset

The decisive dataset is not another pile of unexecuted PRs.  It is a paired
**verification-gap** corpus in which the same task/candidate has all relevant
signals:

1. blind deterministic/static evidence;
2. reference-free semantic/reward-model score and calibration metadata;
3. targeted compiler/type/reproduction-test outcomes;
4. complete isolated execution, repeated to detect flakes;
5. adversarial/oracle-hardening outcomes, including gold, base, and negative
   sanity; alternative-correct preservation; independence; and non-vacuity;
6. independent blinded multi-adjudicator labels for task validity, candidate
   correctness, and evidence-event validity, including source/protocol/agreement,
   disagreements, indeterminate cases, and alternative-valid patches;
7. disaggregated cold-image construction, warm marginal execution, cache
   amortization, parallel queueing, storage, tokens, human time, and dollar cost.

Candidate types must include gold, no-op, under-fix, wrong-file, test-overfit,
regression-inducing, equivalent-but-textually-different, alternative-correct, and
real agent patches.  Real patches must dominate the final evaluation; synthetic
no-op and under-fix candidates are stratified stressors, not a convenient
majority.  Sample across Python, JavaScript/TypeScript, Java, Rust, and C/C++;
interpreted-only evidence would not support the routing thesis.

Use older public tasks for development and reserve temporally fresh repositories
for the final test.  Candidate-level random splits leak repository and harness
structure and are not acceptable.

## Experiments

### Estimation without selective-label bias

The collection policy must initially acquire all modalities for a stratified
subset and randomize additional acquisitions with known non-zero,
history-conditioned propensities.  Predeclare overlap diagnostics and minimum
action probabilities. Report direct paired estimates on the fully observed
subset, sequential inverse-propensity weighted estimates on logged data, and a
doubly robust sensitivity analysis that addresses time-varying confounding.
Validate those estimates against a prospective randomized deployment. Never
train only on cases the current router chose to execute and then call the result
an unbiased execution-benefit model. For RL, preserve a random execution audit
stream throughout training so policy drift or router-gaming remains observable.

### Baselines

- changed-file count, patch size, and cheap metadata logistic/GBDT models; the
  hosted development study makes this non-negotiable;
- always full execution;
- never execute / semantic only;
- random execution at the same budget;
- random execution-backed training subsets at the same sample and token budget;
- best single evidence modality at matched cost;
- candidate-confidence thresholding and fixed execution quotas at matched cost;
- fixed-scaffold prohibited, quota-limited, and unrestricted execution arms
  matching To Run or Not to Run;
- fixed language/risky-file heuristics;
- report-completeness/actionability heuristics and trajectory-guided
  specification refinement, while preserving the original-report result and
  treating re-generation as a distinct generation intervention;
- static → execute-all, semantic → targeted → full, and static → semantic →
  full cascades;
- R2E-Gym-style top-N semantic filter followed by tests;
- fixed semantic+execution reward as in SWE-RM;
- repeated, criteria-decomposed LLM-as-a-Verifier judging;
- Rubric-Supervised Critic reranking;
- PatchFusion static candidate consensus;
- EGSS-style entropy gating and SWE-Reasoner-style search allocation;
- conformal/CCO acceptance gate with no adaptive evidence acquisition;
- LEC, SCoRE, Conformal Selective Acting, and joint
  risk–acceptance–utility certificate gates under their actual calibration,
  exchangeability, filtration, bounded-loss, and threshold-family assumptions;
- consequence × marginal-utility compute allocation;
- TwinRouter-style cheapest-sufficient routing;
- inherited full execution versus repeated execution versus hardened execution;
- oracle hardening with gold-sanity but no validity/observation head;
- All Smoke-style syntactic oracle-signal features as cheap inputs, never as
  candidate-correctness or oracle-validity labels;
- candidate-only, task+candidate, candidate+verifier, and full
  task+candidate+verifier ablations;
- SCATE-style LinUCB routing among `DEFAULT`, `ANALYSIS`, and `STOP` unit-test-
  generation actions with its reported context and cost-aware reward;
- a nonadaptive cost-sensitive multiclass action policy before contextual
  bandits;
- identical-test Docker versus container-free execution with cache state fixed,
  reported as a substrate factorial rather than a verification method;
- Dockerless and SWE-World only as curator-input upper bounds where their gold
  context is unavailable to a deployable router;
- greedy value of information, a contextual bandit, and Bayesian Control's
  belief-state greedy/finite-horizon policies at matched action and verifier
  cost, including its simple-gate and always-verify regime baselines;
- oracle router using withheld paired outcomes (upper bound only).

For downstream training, SWE-RL, Agent-RLVR, and SWE-Master are execution-
grounded RL comparators; SWE-ZERO→HERO and Kimi-Dev supply global mixed
execution-free/execution-backed curriculum baselines. From Patches to
Trajectories is a privileged-trajectory SFT upper bound, not a deployable
verifier. SWE-MiniSandbox is an execution-cost substrate, not a routing baseline;
substrate and cache state must be fixed or matched across policies. Open-SWE-
Traces and SWE-Replay are candidate/trajectory sources whose provenance and
verifier labels still require the same audit. CCO and anytime-valid certificate
baselines must be implemented under their actual online safe-family/gating
assumptions, not relabeled as candidate false-accept guarantees.

### Training and RL

Hold base model, optimizer, tokens, unique candidate pool, rollout budget,
wall-clock envelope, and seeds fixed:

1. raw trajectories;
2. semantic-only accepted trajectories;
3. Docker-only accepted trajectories;
4. deterministic risk-router accepted/weighted trajectories;
5. learned calibrated-router accepted/weighted trajectories.

For RL, treat dense semantic reward plus selective execution as one experimental
arm, not the default method before its reward robustness is established. Preserve
a random execution-audit stream in every arm, track reward-model drift, and
replay known reward-hacking cases throughout training. Log the exact verifier
revision and treat every verifier upgrade as a new intervention: co-evolution
cannot justify pooling rewards across an unrecorded moving oracle. Likewise,
test-file presence or a syntactic strong-oracle category is at most a cheap
feature. The All Smoke classifier's population estimate is grounded by 384
human-labeled patches, not by human semantic adjudication of all 86,156 patches.

### Rollout selection

Generate and freeze the same N candidates for every method. Compare Best-of-N
selection at equal verification budget and equal wall-clock. The primary outcome
is whether the selected candidate is correct, reported together with the
false-accept–cost frontier. Execute uncertain near-ties and high-risk candidates,
not merely the highest semantic scores. Report the gap to Pass@N so verifier
quality cannot be hidden behind generation quality.

Agent completion claims and LLM-judge scores remain evidence, not outcome
labels. The false-success judge ceiling is a required stress case for rollout
monitoring, but because it is measured on tau2-bench and AppWorld rather than
SWE patch correctness, it cannot be imported as a SWE error-rate estimate.

### Evaluation

Choose the number of model/scaffold seeds from a preregistered variance/power
criterion rather than an arbitrary fixed range. Freeze and publish scaffold,
prompt, parser, image, and dependency versions. Report the raw target-population
score, validity-adjusted estimate or bound, agreement with independent blinded
multi-adjudicator labels, abstentions, invalid-task count, bootstrap confidence
intervals, and Kendall/Spearman ranking stability before and after task auditing. State the
estimand explicitly: removing invalid/ambiguous tasks changes the population and
cannot silently replace the raw benchmark result. Never compare scaffold
releases as though only the model changed. The fixed-model 35-release Qwen Code
study makes scaffold revision an empirical confounder and cost dimension, while
its single-scaffold, 50-task SWE-bench Verified subset prevents a broader causal
generalization.

## Metrics

Primary metrics:

- selected-candidate correctness in equal-budget Best-of-N;
- false-accept and false-reject rate with explicit numerators/denominators;
- harm-weighted errors only when a separate, blinded harm tier is available;
- selective risk–coverage and risk–execution curves;
- area under the cost–risk frontier;
- Brier score, ECE, ROC-AUC, and precision–recall AUC;
- executions avoided at a predeclared error bound;
- cost per correctly accepted label, separating cold build, warm marginal run,
  cache amortization, queueing, storage, human time, tokens, and dollars;
- abstention/quarantine rate and disagreement-resolution yield;
- environment build success, setup-error rate, and repeated-run flakiness;
- downstream Pass@1 with confidence intervals and Best@K–Pass@K gap;
- leaderboard rank correlation and score sensitivity under validity correction.

Aggregate accuracy and nominal benchmark resolve rate are insufficient.
Subgroup results must be reported by language, build system, repository, patch
scope, risky-file class, and environment reliability.

## Reward-hacking and oracle stress suite

The release should include adversarial fixtures for:

- optimistic trajectory narration paired with a wrong patch;
- gold-patch/string-similarity traps with valid alternative implementations;
- tests that pass an under-fix or fail the gold solution;
- generated tests that error, are vacuous, or depend on the patch implementation;
- test-file leakage and package substitution;
- config, dependency, native-code, schema, security, concurrency, and migration
  changes that static similarity tends to miss;
- environment setup failures mislabeled as candidate failures;
- duplicate test names in different files and modified-test reconstruction.

Gold-sanity is necessary but not sufficient. Before an augmentation can change a
reward or evaluation label it must also pass base/negative sanity,
alternative-correct preservation, independence and non-vacuity checks, plus human
review whenever task semantics remain disputed.

## Release ladder

1. **Engineering alpha:** portable provider support, safe path/provenance handling,
   corrected deterministic analyses, buildable wheel, and regression tests.
2. **Research alpha:** manifest schema, inspectable deterministic router, paired
   collection protocol, cost logging, and adversarial fixture suite.
3. **Empirical beta:** blinded human audit set, calibrated learned policy,
   repository/time-disjoint results, and complete ablations.
4. **Research release:** paired verification-gap dataset, model/router weights,
   manifests, environment digests, scripts, raw per-seed outputs, paper, and a
   model card/data card stating known failure modes.

Until steps 2–3 are complete, the project should describe itself as an
**experimental benchmark-auditing and verification-routing toolkit**, not
production/stable software and not a validated substitute for execution.

The flagship empirical scope should be **candidate/rollout verification**.  SFT,
RL, and leaderboard correction should be downstream demonstrations using the
same manifest and policy, not three loosely validated products.  The paired
candidate × evidence-action corpus and prospective frozen-policy result are the
durable contributions.

The repository's [synthetic seed study](../experiments/seed_study/RESULTS.md)
is an execution-path integration check only. Its eight hand-authored JavaScript
candidates demonstrate that repeated inherited-suite execution can be stable yet
wrong, and that the acquisition/artifact path reproduces inside a pinned
network-disabled container. It supplies no evidence for H1–H6 because it has no
agent-sampled candidates, blinded adjudication, randomized policy, held-out
repositories, learned router, confidence interval, or downstream model.

The [real-agent contrastive pilot](../experiments/real_agent_pilot/RESULTS.md)
adds four source-locked public OpenHands/Qwen3-Coder candidates. Every terminal
trajectory claims successful completion, while the hosted SWE-bench reports
resolve two. That is direct evidence that optimistic agent narration is not a
verifier, but the contrastive one-repository sample is non-random, not
independently re-executed, and comes from a submission marked `checked: false`.
It therefore supplies no estimate for H1–H6.

The [500-row hosted-outcome development study](../experiments/hosted_outcome_study/RESULTS.md)
adds a complete finite prefix frame from one such public submission. Its strict
patch-only phase freezes four base and 48 sensitivity permutations before any
official or per-instance outcome decode. The later policy comparison is a
retrospective hosted-label-reveal proxy: it performs no new test execution and
has one candidate per task. Patch size beats the hand-built router at all
matched budgets, while post-hoc AUC shows the router score is coarse and barely
discriminative overall. Its pinned canonical SWE-bench Verified parquet exactly
matches all 500 hosted task IDs, repositories, and full base/environment commits.
This is a useful negative control and collection-stack validation, not
calibration, causal policy evaluation, or H1–H6 evidence.

The [matched three-rollout v2 study](../experiments/matched_rollout_study/RESULTS.md)
source-locks three checked OpenHands-family submissions over a 499-task common
frame and separates patch-static evidence from post-rollout tool/history
structure. Its source-locked post-outcome union establishes aggregate candidate
diversity, not a deployable selector. A fresh source-identical 24-task v2
development run adds an honest negative result: Claude-first reaches the 18-task
hosted Best-of-3 ceiling, while the fixed hybrid starts at 15 and only catches up
after more hosted-label reveals. All task-level patch sets are byte-distinct, so
candidate diversity alone does not imply useful selection headroom on a chosen
slice. Model/date remain confounded, exact scaffold/budget equality is
unavailable; that matched-selector result itself had no independent execution
and provides no H1–H6 evidence.

The [SymPy targeted feasibility execution](../experiments/independent_execution_smoke/RESULTS.md)
adds independently captured runtime evidence for one matched task. Across three
repeats each, base failed 1/39 tests, GPT-5 passed 39/39, Kimi failed 1/39,
Claude passed 39/39, and gold passed 39/39, matching the already-visible hosted
candidate pattern. This is a post-draft/pre-freeze, manually selected,
non-blinded macOS-arm64 targeted-file replay. It is not official-container or
full-harness Linux execution, task/candidate adjudication, a Docker comparison,
or evidence for H1–H6.

Protocol `0.2` records both the SymPy and Sphinx chronologies in an append-only
hash-chained prehistory, excludes both task clusters from prospective/OPE
estimands, and calls the governed 22-task/66-candidate remainder prospective
measurement collection on an outcome-exposed development cohort—not
prospective policy validation. Numeric ceilings, domain-separated seeds, the
task-level scheduler and joint-propensity contract, terminal admissibility,
review-packet projection, six truth-free target policies, and guarded
self-normalized importance-sampling diagnostics are now fixed and source-bound.
Its validator still reports `activation_ready: false` until a clean-commit
receipt, attested execution infrastructure and per-task manifests, semantic
producer identity, and custody/reviewer attestations exist. A tested
single-host claim-before-launch dispatcher and strict typed-result core now
exist, but their activation requirements remain blocking until the real action
registry, validated activation context, authenticated provisioning receipts,
and externally immutable artifact store are bound. An externally anchored
structural StudyBundle compiler now derives behavior actions, propensities,
terminal decisions, task selections, result identities, partial/halt state, and
dimension-qualified cost declarations from that ledger while reopening retained
bytes. It intentionally refuses scientific-profile eligibility: checksum
pinning is not signature verification, and the typed candidate registry,
bootstrap/curator streams, raw adjudication votes, aggregate resource
settlements, and calibrated score receipts do not yet exist.

## Contemporary references

- Jimenez et al., [SWE-bench v3](https://arxiv.org/abs/2310.06770v3), ICLR 2024.
- Xia et al., [Agentless v2](https://arxiv.org/abs/2407.01489v2), 2024.
- Pan et al., [SWE-Gym v2](https://arxiv.org/abs/2412.21139v2), ICML 2025.
- Shypula et al., [SWE-RL v2](https://arxiv.org/abs/2502.18449v2), 2025.
- Ma et al., [Thinking Longer, Not Larger / SWE-Reasoner v2](https://arxiv.org/abs/2503.23803v2), 2025.
- Jain et al., [R2E-Gym v1](https://arxiv.org/abs/2504.07164v1), COLM 2025.
- Yang et al., [SWE-smith v2](https://arxiv.org/abs/2504.21798v2), NeurIPS 2025.
- Badertdinov et al., [SWE-rebench v2](https://arxiv.org/abs/2505.20411v2), 2025.
- Zhang et al., [SWE-bench Goes Live v2](https://arxiv.org/abs/2505.23419v2), 2025.
- [Agent-RLVR v2](https://arxiv.org/abs/2506.11425v2), 2025.
- Zhang et al., [The SWE-Bench Illusion v4](https://arxiv.org/abs/2506.12286v4), 2025.
- [Training Long-Context, Multi-Turn Software Engineering Agents with Reinforcement Learning v2](https://arxiv.org/abs/2508.03501v2), 2025.
- Gandhi et al., [When Agents Go Astray / SWE-PRM v2](https://arxiv.org/abs/2509.02360v2), 2025.
- Yang et al., [Kimi-Dev v3](https://arxiv.org/abs/2509.23045v3), 2025.
- Shum et al., [SWE-RM v1](https://arxiv.org/abs/2512.21919v1), 2025.
- [SWE-Replay v2](https://arxiv.org/abs/2601.22129v2), 2026.
- [DockSmith v2](https://arxiv.org/abs/2602.00592v2), 2026.
- [SWE-Master v2](https://arxiv.org/abs/2602.03411v2), 2026.
- [SWE-World v1](https://arxiv.org/abs/2602.03419v1), 2026.
- Mao et al., [EGSS v1](https://arxiv.org/abs/2602.05242v1), 2026.
- [Rethinking the Value of Agent-Generated Tests v2](https://arxiv.org/abs/2602.07900v2), 2026.
- [SWE-MiniSandbox v5](https://arxiv.org/abs/2602.11210v5), 2026.
- Kon et al., [SWE-Protégé v1](https://arxiv.org/abs/2602.22124v1), 2026.
- Badertdinov et al., [SWE-rebench V2 v2](https://arxiv.org/abs/2602.23866v2), 2026.
- [SWE-ABS v1](https://arxiv.org/abs/2603.00520v1), 2026.
- [SWE-Hub v1](https://arxiv.org/abs/2603.00575v1), 2026.
- [A Rubric-Supervised Critic from Sparse Real-World Outcomes v1](https://arxiv.org/abs/2603.03800v1), 2026.
- Ludwig et al., [SWE-ZERO to SWE-HERO v2](https://arxiv.org/abs/2604.01496v2), 2026.
- [STING v1](https://arxiv.org/abs/2604.01518v1), 2026.
- Yang et al., [TwinRouterBench v2](https://arxiv.org/abs/2605.18859v2), 2026.
- [From Patches to Trajectories v1](https://arxiv.org/abs/2605.21996v1), 2026.
- Tu et al., [Automated Benchmark Auditing v2](https://arxiv.org/abs/2605.26079v2), 2026.
- Overman and Bayati, [Calibrating Conservatism for Scalable Oversight v1](https://arxiv.org/abs/2605.28807v1), 2026.
- Wen et al., [Not All Errors Are Equal v1](https://arxiv.org/abs/2606.04402v1), 2026.
- Advani, [From Confident Closing to Silent Failure v1](https://arxiv.org/abs/2606.09863v1), 2026.
- [Open-SWE-Traces v1](https://arxiv.org/abs/2606.16038v1), 2026.
- Rajan, [Auditing Reward Hackability v1](https://arxiv.org/abs/2606.16062v1), 2026.
- Banik et al., [All Smoke, No Alarm v1](https://arxiv.org/abs/2606.18168v1), 2026.
- Papamarkou et al., [Bayesian Control for Coding Agents v1](https://arxiv.org/abs/2606.24453v1), 2026.
- Wang et al., [The Verification Horizon v2](https://arxiv.org/abs/2606.26300v2), 2026.
- [To Run or Not to Run v1](https://arxiv.org/abs/2606.26978v1), 2026.
- [Dockerless v1](https://arxiv.org/abs/2606.28436v1), 2026.
- Sengupta, [Self-Evolving Agents with Anytime-Valid Certificates v1](https://arxiv.org/abs/2607.00871v1), 2026.
- Guo et al., [SWE-Doctor v1](https://arxiv.org/abs/2607.00990v1), 2026.
- Yang et al., [PatchFusion v1](https://arxiv.org/abs/2607.01597v1), 2026.
- Wang et al., [TestEvo-Bench v1](https://arxiv.org/abs/2607.02469v1), 2026.
- Ben Sghaier et al., [Scaffolding Evolution v1](https://arxiv.org/abs/2607.03691v1), 2026.
- Kwok et al., [LLM-as-a-Verifier v2](https://arxiv.org/abs/2607.05391v2), 2026.
- Shu et al., [TraceProbe v1](https://arxiv.org/abs/2607.06184v1), 2026.
- Huang et al., [DeepSWE v1](https://arxiv.org/abs/2607.07946v1), 2026.
- Nie et al., [Test-Time Harness Evolution v1](https://arxiv.org/abs/2607.08124v1), 2026.
- Gu et al., [SCATE v1](https://arxiv.org/abs/2607.08983v1), 2026.
- Brahmbhatt et al., [Repairing Qiskit Programs using Bugs4Q v1](https://arxiv.org/abs/2607.09007v1), 2026.
- Zhang et al., [ReProAgent v1](https://arxiv.org/abs/2607.09123v1), 2026.
- Gültekin et al., [How Far Are We from Detecting Flaky Tests? v1](https://arxiv.org/abs/2607.09345v1), 2026.
- Zhao et al., [Failure as a Process v1](https://arxiv.org/abs/2607.09510v1), 2026.
- Khatib et al., [What Makes a Good Bug Report for an AI Agent? v1](https://arxiv.org/abs/2607.07593v1), 2026.
- Fahim et al., [Bug Report Specification Refinement with Trajectory Guidance for Automated Program Repair v1](https://arxiv.org/abs/2607.07882v1), 2026.
- Bruno et al., [Writing Bug Reports for Software Repair Agents: What Information Matters Most? v1](https://arxiv.org/abs/2607.09553v1), 2026.

Methodological foundations:

- Golovin and Krause, [Adaptive Submodularity v5](https://arxiv.org/abs/1003.3967v5), 2010/2017.
- Jiang and Li, [Doubly Robust Off-policy Value Evaluation v3](https://arxiv.org/abs/1511.03722v3), 2015/2016.
- Janisch et al., [Classification with Costly Features v2](https://arxiv.org/abs/1711.07364v2), 2017/2018.
- Ma et al., [EDDI v4](https://arxiv.org/abs/1809.11142v4), 2018/2019.
- Kallus and Uehara, [Double Reinforcement Learning v3](https://arxiv.org/abs/1908.08526v3), 2019/2020.
- Angelopoulos et al., [Learn then Test v5](https://arxiv.org/abs/2110.01052v5), 2021/2022.
- Angelopoulos et al., [Conformal Risk Control v4](https://arxiv.org/abs/2208.02814v4), 2022/2025.
- Wang et al., [LEC v3](https://arxiv.org/abs/2512.01556v3), 2025/2026.
- Bai and Jin, [SCoRE v1](https://arxiv.org/abs/2603.24704v1), 2026.
- Khosravi and Huo, [Conformal Selective Acting v1](https://arxiv.org/abs/2605.20270v1), 2026.
- Yu and Liu, [joint selective certificate v1](https://arxiv.org/abs/2606.08517v1), 2026.

All 59 SWE/agent arXiv identities, canonical titles, cited version suffixes, and
arXiv submission/update timestamps in this boundary were rechecked through the
primary arXiv API on 2026-07-14 (Asia/Shanghai; the lock records exact UTC
retrieval time). The eleven methodological references above were checked through
the same primary API. These timestamps do not establish peer-reviewed
publication status.
The separate [`literature.claims.json`](literature.claims.json) ledger maps 35
central claims from 26 exact primary PDFs—R2E-Gym, LEC, SWE-RM, SWE-World, EGSS,
SWE-ZERO→HERO, TwinRouterBench, Not All Errors Are Equal, To Run or Not to Run,
Dockerless, Bayesian Control for Coding Agents, SCoRE, Conformal Selective
Acting, the joint selective certificate, two controlled bug-report studies,
TrajSpec, Bugs4Q version
validation, SCATE adaptive test generation, generated-test oracle signals,
verifier co-evolution, false-success judging, scaffold evolution, ReProAgent,
code-only flakiness detection, and temporal CLI-agent failure analysis—to pages
and sections. The claim IDs appear inline above. These
mappings are machine-assisted and all remain `human_confirmed: false`; ordinary
metadata-only validation rehashes none of the external PDF files. Several
records that an earlier draft called v1 now resolve to v2 or later—including
SWE-Reasoner v2, SWE-PRM v2, TwinRouterBench v2, and LLM-as-a-Verifier v2—so an
eventual paper and artifact lock must pin every exact version/date again. It
must also distinguish benchmark-wide rates from rates measured only on one
agent's passing subset.

[`literature.lock.json`](literature.lock.json) schema `0.1.0` records all 70
exact cited versions, canonical titles, authors, primary categories,
submission/update timestamps, retrieval time, query identity, and the SHA-256
of the primary arXiv Atom response. It is regenerated with
`python scripts/lock_literature.py`; offline tests require exact
body/bibliography/lock parity and reject unversioned, missing, duplicate, or
version-drifting records. This proves citation-metadata provenance, not paper
claims or independent replication. The partial claim ledger binds recorded PDF
digests and sizes, but a paper release must preserve or independently retrieve
and rehash every exact PDF, obtain named human confirmation, and retain
corrections append-only.
