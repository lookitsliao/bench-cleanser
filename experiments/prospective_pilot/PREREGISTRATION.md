# Independent-evidence routing pilot protocol

**Status:** draft after two post-draft, pre-freeze feasibility executions; not
externally registered and not confirmatory.

This protocol advances the next empirical milestone without pretending the
existing hosted outcomes are unknown. Developers have already seen those
outcomes and container-free outcomes for `sympy__sympy-15976` and
`sphinx-doc__sphinx-8475`. Both tasks were executed after a draft existed but
before the draft was committed, registered, or otherwise immutably frozen. They
are therefore **post-draft,
pre-freeze feasibility evidence**, not prospective evidence. The complete
24-task/72-candidate cohort remains a descriptive
development frame; both clusters are excluded from every prospective, OPE, and
confirmatory estimand, leaving at most 22 future task clusters and 66 candidates
with no replacement.

The machine-readable authority is
[`preregistration.json`](preregistration.json), now protocol `0.3`. The
append-only [`prehistory.json`](prehistory.json) binds both feasibility events,
their raw-evidence identities, and the unfrozen repository state. Before any
further protocol-governed evidence action, a release must bind the exact
protocol, prose, prehistory, resource,
collection-policy, scheduler-contract, execution, adjudication, and analysis
bytes to a clean commit/tree receipt. Any material change creates a new protocol
version and an append-only deviation record.

`validate_protocol.py` verifies both source-locked feasibility records, old-draft
digests, the Sphinx bundle/index/environment/runner identities, prehistory hash
chain, protocol binding, claim limits, sampler identity, and declared activation
blockers. It can exclusively generate or check an
external clean-tree receipt, binding the exact Git commit, tree, blob IDs, bytes,
and SHA-256 values. Its `--require-activation-ready` mode exits nonzero while
this draft, a required identity, or that receipt remains absent.

## Question and estimand

For every task in the 24-task descriptive frame, a policy receives the same
three opaque candidate patches and may acquire evidence before selecting one
candidate or abstaining. Protocol-governed prospective/OPE analyses use only
the 22 task clusters without pre-freeze independent evidence. The primary
descriptive quantity is accepted-set false-accept risk:

\[
R_{FA}=\frac{\#\{\text{unsafe non-abstaining selections}\}}
{\#\{\text{non-abstaining selections}\}}.
\]

A selection is unsafe when the task is invalid or indeterminate, or when the
candidate is incorrect or indeterminate conditional on a valid task. Coverage,
full-execution count, warm worker time, cold build/pull cost, and the complete
risk–coverage–cost frontier are mandatory co-primary context. The pilot's 10%
target is diagnostic. Under the optimistic full-coverage,
independent-Bernoulli reference calculation, even zero false accepts among the
22 future task clusters gives a one-sided 95% upper bound of 12.73% (11.73% for
all 24 descriptive selections), so neither frame can certify the target. Those
figures are not cluster-valid inference under adaptive acceptance; the actual
analysis must preserve task/repository dependence and the realized accepted-set
denominator.

## Frozen cohort and knowledge boundary

The cohort is all 72 candidates in acquisition manifest
`f79578fb9860ef0eb4bf02a62691e98c4002a5de96b8dda9ab2d3616f082b574`.
No task, candidate, infrastructure failure, or inconvenient adjudication may be
dropped or replaced from the descriptive frame. The pre-freeze SymPy and Sphinx
clusters are retained and reported as descriptive strata but excluded from
prospective/OPE estimands; neither is replaced. Submission and model labels are
replaced with opaque patch-digest identities before future execution ordering,
policy fitting, and human review.

Future evidence on the 22 untouched task clusters can be prospective only after
the required clean-commit freeze. The full study remains a development-mechanics
study and cannot support a held-out performance claim, model comparison,
low-risk deployment guarantee, downstream training claim, or new SWE-bench
score. More precisely, it is **prospective measurement collection on an
outcome-exposed development cohort, not prospective policy validation**. It
cannot supply evidence for H1-H6.

## Evidence and randomized collection

Static patch/repository evidence is collected deterministically and bound by a
separate bootstrap receipt. It is a risk-feature input, not a randomized policy
event, and receives no invented propensity. Every later decision discloses a
nine-action catalog covering the complete package route enum. Two entries are
permanently unavailable to the behavior policy: the already-completed static
bootstrap and curator-only oracle hardening. The at-most-seven behavior-eligible
entries are semantic judging, targeted FAIL_TO_PASS execution, full execution,
repeated full execution, accept, reject, and abstain. Accept and reject appear
only when the frozen admissibility rule makes them eligible, but they remain
logged actions. The behavior policy gives half its mass to the frozen preferred
action and half uniformly to the available behavior catalog. With at most seven
available actions, every available action has propensity at least `1/14`
(approximately 0.07143); the two disclosed non-policy entries have probability
zero by construction and are outside the support claim.

Every decision is committed before acting with the full nine-action catalog,
history-conditioned probabilities, sampler draw, action-spec digest, and an
exact embedded package `LoggedPolicyDecision`. The scheduler candidate head is
the package policy-log trajectory head, and each nonterminal decision
preallocates the acquisition ID that its successor observation must reuse. A
separate curator stream later executes every candidate and never enters the
policy history. This avoids learning only from candidates selected for
execution by the current router.

If no semantic producer, prompt, schema, model, endpoint class, and cost policy
are frozen at the protocol commit, semantic evidence is unavailable. The current
[`collection_policy.json`](collection_policy.json) records every such field as
unavailable and blocking because frozen target policies use the semantic action.
Removing that action instead requires a new protocol version; it cannot be
enabled or disabled selectively after seeing another action's result.

The same file fixes three domain-separated 256-bit seeds, the `1/14` propensity
floor, preferred-action fallback, concrete-offer tie rule, and terminal
admissibility. [`scheduler_contract.json`](scheduler_contract.json) fixes the
logical three-candidate round order and task-level joint-propensity calculation.
[`scheduler.py`](scheduler.py) now implements that contract: domain-separated
task/candidate order, reserved non-reused action-draw counters, one complete
preferred-plus-uniform decision for each active candidate in a round, summed-log
task-trajectory propensity, strict hash chains, and a separate deterministic
task-selection record. Its reason-free router projection and strict schemas have
no hosted-outcome or curator-label field. The source is still uncommitted; this
implementation does not activate the study.

[`release_bundle.py`](release_bundle.py) now supplies a structural publication
boundary for that ledger. A consumer must provide the SHA-256 of a canonical
trust anchor through an independent channel; the loader never infers its own
trusted digest. The compiler then reopens the export, repository bindings,
every behavior-available typed action spec, and every retained acquisition and
completed-output artifact. Terminal-at-step-zero decisions and the separate
task selection are part of the derived trajectory digest, and partial or halted
frames remain visible. Observation costs retain per-dimension provenance:
currently wall time and storage bytes are measured, while semantic token/USD
values may be producer-declared and CPU zeros are not measurements. This is an
externally anchored `STRUCTURAL` bundle, not authenticated adjudication or a
scientific corpus. The signed non-policy ledgers and incompatible oracle/truth
schema remain activation blockers.

## Independent execution and substrate comparison

Future primary full-execution evidence uses a digest-pinned official SWE-bench
container environment. Two fresh-worktree, network-disabled runs are required
per candidate; disagreement triggers a third. Setup, patch application, test
failure, timeout, and infrastructure error remain distinct outcomes.

The existing SymPy and Sphinx feasibility runs are not this primary evidence.
SymPy replayed a targeted test file; Sphinx replayed the exact scored node list
in split public-link and localhost phases. Both used reconstructed macOS arm64
container-free environments without an attested official container or full
harness, and neither was blinded or governed by a clean committed freeze.

Container-free execution is a secondary paired substrate factor, not an
execution-free verifier. Within each of the four repositories, the two tasks
with the lowest domain-separated task hashes are run under both substrates
using identical repository commits, patches, test patches, test IDs, argv,
timeouts, and cache declarations. The comparison reports agreement, environment
failures, and cold/warm cost separately.

[`execution_freeze.json`](execution_freeze.json) pins the canonical dataset,
harness commit/tree, Linux target, timeouts, isolation/resource limits,
replication, and cache accounting. Docker daemon/provisioner attestation and the
exact architecture plus per-task image, dependency-lock, and execution-spec
manifests are deliberately `unavailable` and block activation.

## Truth and adjudication

Three model- and submission-blinded reviewers independently label task
validity, candidate correctness conditional on valid tasks, and each evidence
event's validity. Disagreement and indeterminate labels are preserved. A
determinate evidence label is paired-ready only with at least two blinded
reviewers and agreement of at least 0.80.

[`adjudication_plan.json`](adjudication_plan.json) fixes the review-packet
allowlist and prohibited fields, breach handling, label vocabularies, conditional
candidate labels, agreement denominator, and no-tie-break disagreement rule.
The source-bound packet generator now emits manifest schema `0.2`, binds the
exact frozen frame and generator bytes, removes directional evidence status,
and verifies every projected packet. The opaque-map custodian and all three
reviewer identities and independence/conflict attestations remain unavailable
and blocking; the generator does not replace their content-level blinding and
conflict review.

Execution is evidence, not adjudication. Curator-only hardening includes base
and no-op sanity, gold sanity, negative/mutation sanity, alternative-correct
preservation, and repeated-run flake checks after policy decisions are frozen.

## Analysis, stopping, and honest claims

The task is the randomization and analysis cluster. Report exact accepted-set
binomial bounds and paired task-level intervals; repository-stratified task
bootstrap is sensitivity analysis only. Four repositories cannot support
credible cluster asymptotics or repository subgroup claims.

The descriptive frame is fixed at 24 tasks and 72 candidates; the
protocol-governed future frame is fixed at the remaining 22 task clusters and
66 candidates with
no replacement. There is no outcome-dependent stopping. Operational halts are
limited to digest mismatch, blinding breach, or the predeclared hard resource
ceiling. Always-execute winning is a valid negative result.

[`resource_ceiling.json`](resource_ceiling.json) fixes task/candidate, decision,
process, worker-time, CPU, memory, storage, token, dollar, human-time, concurrency,
and calendar caps. Hitting any cap halts without replacement and cannot trigger an
outcome-dependent extension. [`analysis_plan.json`](analysis_plan.json) fixes the
six target policies, task-cluster weight, support rule, no-trimming primary OPE
diagnostic, effective-sample-size suppression rule, fixed-repository bootstrap
sensitivity, and mandatory raw outputs. Four repositories support no repository-
generalization or cluster-asymptotic claim.

[`target_policies.py`](target_policies.py) implements the six frozen target
likelihoods from validated pre-action state only, and
[`target_policy_manifest.json`](target_policy_manifest.json) binds their exact
rules and truth-free input boundary. [`analysis.py`](analysis.py) implements
only self-normalized sequential importance-sampling point diagnostics. It
suppresses a policy on any support violation, effective sample size below ten,
or an empty weighted accepted set. Doubly robust estimation, nuisance models,
cross-fitting, OPE confidence intervals, and learned/calibrated policies remain
unimplemented and unclaimed.

This development pilot can validate execution, logging, cost, disagreement,
and oracle-validity mechanics. It cannot validate a prospective policy effect.
A future low-risk claim requires at least 149 accepted candidates for an
idealized zero-error 95% upper bound below 2%, or 299 below 1%, before
repository clustering and adjudication uncertainty.

## Missing implementation before protocol-governed execution

The core repository already supplies candidate manifests, action catalogs,
write-ahead propensities, bounded acquisitions, paired corpus truth, and exact
evaluation joins. The experiment still needs:

- real repository/image provisioning and execution;
- a matched-artifact-to-manifest/corpus/analysis adapter;
- authenticated blinded-adjudication import; and
- typed queue, memory, cache, image, and human-time cost fields.

The numeric resource ceiling, policy/order RNG seeds, task-level scheduler
contract, terminal-admissibility rule, infrastructure requirements, blinded
label-aggregation rule, and cluster-respecting analysis plan now exist as strict
machine-readable files, and the scheduler now has a source-bound core that
enforces the exact frame, recomputes the frozen router from a safe state
preimage, and validates full task chains. The source-bound single-host ledger
and dispatcher additionally commit complete rounds and canonical executable
specs before a permanent claim, derive the routed manifest, request, plan, and
reservation from that stored preimage, launch only the winning claim, recover
an exact committed result across acknowledgement loss, and require an explicit
worker-exit receipt before halting an abandoned claim. Adversarial tests cover
claim contention, pre-claim tampering, recovery races, repeated-execution
equivalence, and symlinked artifacts.
`activation_readiness.ready` nevertheless remains false: Docker attestation;
per-task image/dependency/execution manifests; semantic producer;
opaque-map custodian; and reviewer identities/attestations remain absent. The
durable-dispatch and typed-persistence requirements also remain blocking because
the real 22-task action registry and validated activation context are not
populated, provisioner/clean-start receipts are declarative rather than
authenticated, and no externally immutable artifact store is bound.
An external clean-commit/tree receipt is also required. Validation fails closed
on every one of those facts.

Until those pieces, a clean committed freeze, and the required release objects
exist, this document is a development protocol candidate. The separate SymPy
and Sphinx feasibility runs establish only that two reconstructed execution
paths ran; they do not activate or validate this protocol.
