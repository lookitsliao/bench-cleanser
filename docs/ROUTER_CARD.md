# Conservative router card

## Status and identity

**Policy:** `ConservativeRouter` / `RoutingPolicy(version="conservative-v1")`

**Artifact type:** deterministic engineering baseline; no model weights

**Calibration status:** uncalibrated

**Release status:** research-alpha control, not a validated verifier

The router exists to make evidence acquisition and failure handling inspectable
while paired data are collected. Its numeric candidate risk, verifier risk,
information-gain, and relative-cost outputs are heuristic scores. They are not
probabilities, calibrated value estimates, or statistical guarantees.

## Intended use

The policy may be used to:

- exercise and audit the manifest, acquisition, policy-log, corpus, and
  evaluation contracts;
- provide a deterministic baseline for learned or randomized policies;
- collect paired counterfactual evidence under an explicit behavior policy;
- force abstention when required evidence is unavailable or contradictory; and
- reproduce negative controls and failure cases.

It must not be used as an unattended gate for production patches, training-data
admission, RL rewards, public model scores, or safety/security decisions.

## Inputs and outputs

Inputs are a reference-free `ValidityManifest`: immutable candidate provenance,
lifecycle stage, patch/runtime-oracle risk features, evidence history, and
declared evidence availability. The deployed router does not receive gold
patches, hidden tests, curator adjudications, or eventual execution labels.

Outputs are one next action—static, semantic, targeted execution, full
execution, oracle hardening, accept, reject, or abstain—plus candidate/verifier
risk scores, heuristic information gain, relative cost, reasons, policy
version, and calibration status.

Task validity is represented only in the curator corpus and offline evaluator.
The current manifest/router has no task-validity prediction or task-aware
acquisition head.

## Default policy behavior

The default thresholds and declared relative costs are implementation constants
for a baseline, not fitted parameters:

| field | default |
|---|---:|
| maximum declared false-accept risk | 0.02 |
| minimum trusted verifier validity | 0.95 |
| high candidate-risk threshold | 0.55 |
| high verifier-risk threshold | 0.40 |
| static / semantic / targeted relative cost | 0.01 / 0.05 / 0.20 |
| full / hardening relative cost | 0.70 / 1.00 |
| minimum full-execution replicates | 2 |
| maximum full-execution attempts | 3 |

The 0.02 field is a policy target used only when a separately trusted,
calibrated observation supplies a compatible bound. The router itself does not
establish that bound. Serialized `authoritative=true` and calibration IDs are
ignored unless source, version, calibration, and unique acquisition identities
match explicit policy bindings.

## Training and evaluation data

There is no trained router and therefore no training dataset. No held-out
calibration set exists. Corpus `0.6.0` and evaluation `0.5.0` are infrastructure
for the future task/candidate/oracle model; they are not evidence that the
baseline is calibrated.

## Empirical performance

No positive performance claim is supported.

- In the complete 500-row retrospective hosted-outcome study, patch size beats
  router risk at every matched nonterminal budget. Router-risk hosted-failure
  ROC AUC is `0.53249` overall.
- In the fresh 24-task matched-v2 development study, the fixed hybrid starts at
  15/24 hosted-resolved selections while the confounded Claude-first diagnostic
  reaches the 18/24 hosted Best-of-3 ceiling. The hybrid catches up only after
  additional hosted-label reveals.
- These studies use preserved hosted execution labels, not independent
  candidate truth or a prospective held-out policy.
- A later one-task SymPy targeted replay independently reproduced the same
  three-candidate pass/fail pattern across three repeats, but it was selected
  post-draft/pre-freeze and did not exercise or evaluate the router.

The correct interpretation is that `conservative-v1` validates plumbing and is
a baseline to beat.

## Known failure modes

- Coarse score ties and weak discrimination.
- Patch-size and repository difficulty confounding.
- No task-validity estimate.
- Hand-set costs do not represent wall-clock, queue, cold-build, token, dollar,
  storage, or human costs.
- Semantic confidence may be miscalibrated or unauthenticated.
- Repeated execution can be consistently wrong when tests are weak.
- Environment errors, flakes, and generated tests can make runtime evidence
  invalid or inconclusive.
- Risk features underrepresent uncommon build systems, native code, security,
  migrations, concurrency, and alternative-correct patches.
- Allowlist bindings are policy checks, not cryptographic producer identity.

## Fairness, security, and misuse

Router decisions can disproportionately quarantine unfamiliar languages,
repositories, dependency systems, or patch styles. Report coverage and errors
by predeclared subgroup, but do not tune on protected test groups or drop hard
environment failures. Never treat contributor identity, organization, or model
label as correctness evidence.

Run untrusted repository code only in an operator-provisioned, attested
environment. The local argv runner is explicitly non-isolated. The Docker
builder constructs a conservative request but does not attest the daemon,
image, workspace, or completed execution.

## Required evidence before promotion

Promotion beyond a deterministic baseline requires:

1. a populated paired verification-gap corpus;
2. repository/time-disjoint calibration and evaluation;
3. explicit task-validity, candidate-correctness, oracle-validity, and
   action-observation heads;
4. prospective write-ahead propensity logs and overlap diagnostics;
5. independent repeated execution and blinded multi-reviewer adjudication;
6. equal-budget Best-of-N comparisons against simple and contemporary
   baselines; and
7. controlled downstream SFT/RL experiments before any training-benefit claim.

The first development protocol is
[`experiments/prospective_pilot/PREREGISTRATION.md`](../experiments/prospective_pilot/PREREGISTRATION.md).
