# Independent-evidence development pilot

This directory contains a post-feasibility development protocol for the next
empirical milestone. It uses the frozen matched 24-task/72-candidate cohort
while stating that developers already know its hosted labels and two tasks'
container-free outcomes. The `sympy__sympy-15976` and
`sphinx-doc__sphinx-8475` clusters are retained for descriptive reporting but
excluded from prospective/OPE estimands, leaving a governed 22-task/66-candidate
frame; no replacement is allowed.

- [`PREREGISTRATION.md`](PREREGISTRATION.md) explains the estimand and limits.
- [`preregistration.json`](preregistration.json) is the machine-readable
  contract checked by the offline suite.
- [`prehistory.json`](prehistory.json) records the post-draft, pre-freeze SymPy
  and Sphinx feasibility executions, including the Sphinx raw bundle, index,
  environment, and runner identities, and why neither is prospective evidence.
- [`resource_ceiling.json`](resource_ceiling.json),
  [`collection_policy.json`](collection_policy.json),
  [`scheduler_contract.json`](scheduler_contract.json),
  [`frame_manifest.json`](frame_manifest.json),
  [`execution_freeze.json`](execution_freeze.json),
  [`adjudication_plan.json`](adjudication_plan.json), and
  [`analysis_plan.json`](analysis_plan.json) are the exact activation contracts.
  Numeric limits and decision rules are fixed. [`scheduler.py`](scheduler.py)
  implements the source-bound task-round scheduler core against the exact
  22-task/66-candidate mapping. Its nine-entry disclosed catalog is exactly
  joinable to the package policy log while deterministic static bootstrap and
  curator-only hardening remain outside randomization; no more than seven
  actions can be behavior-eligible. Every scheduler action embeds the exact
  `LoggedPolicyDecision`, and nonterminal acquisition IDs are allocated before
  dispatch. [`review_packets.py`](review_packets.py) now
  implements the frame-bound structurally blinded packet projection;
  [`target_policies.py`](target_policies.py),
  [`target_policy_manifest.json`](target_policy_manifest.json), and
  [`analysis.py`](analysis.py) implement fixed truth-free target likelihoods and
  support/ESS-gated descriptive importance-sampling diagnostics. They implement
  no learned policy, doubly robust estimator, confidence interval, calibration,
  or performance result. [`ledger.py`](ledger.py) and
  [`dispatcher.py`](dispatcher.py) add a tested single-host durable core:
  complete-round/spec commit, exact stored-preimage joins, permanent
  claim-before-launch, strict result ingestion, acknowledgement-loss recovery,
  explicit worker-exit-gated halt, and full-repeat equivalence. Durable dispatch
  and typed persistence remain explicit activation blockers because the real
  action registry, validated activation context, authenticated provisioner
  receipts, and externally immutable artifact store are absent. Docker,
  semantic-model, opaque-map custodian, and reviewer identities also remain
  blockers; the scheduler is not operationally activated.
  [`release_bundle.py`](release_bundle.py) is the first fail-closed publication
  bridge. It requires a separately pinned canonical anchor, reopens and audits
  ledger, action-spec, artifact, and completed-output bytes, and derives policy
  actions, propensities, terminal decisions, task selections, partial/halt
  state, execution counts, and dimension-qualified cost declarations. Its
  output profile is deliberately `STRUCTURAL`: a pinned checksum is external
  integrity anchoring rather than a signature, and the compiler cannot enable
  logged-policy, paired-sensor, or scientific profiles until typed signed
  bootstrap, curator, adjudication, resource-settlement, candidate-registry,
  and calibrated-score inputs exist.
- [`validate_protocol.py`](validate_protocol.py) verifies the hash chain and
  claim boundary; `--require-activation-ready` intentionally fails while any
  declared external or implementation identity is absent.

No protocol-governed semantic call, blinded adjudication, or result is included
yet. A clean commit binding protocol `0.3` and its prehistory must precede the
next evidence action. The separate feasibility runs do not activate or validate
this protocol.

Validate chronology, source digests, the append-only prehistory chain, claim
limits, and the declared draft blockers:

```bash
python experiments/prospective_pilot/validate_protocol.py
```

An execution wrapper must use the stricter gate and stop on its nonzero exit
until every binding exists and an external clean-tree receipt is supplied:

```bash
python experiments/prospective_pilot/validate_protocol.py \
  --check-freeze-receipt /durable/evidence/prospective-pilot-freeze.json \
  --require-activation-ready
```

Once the governed files are committed and the entire worktree is clean, create
the receipt at a new path outside this repository. Creation is exclusive and
will not overwrite an existing receipt:

```bash
python experiments/prospective_pilot/validate_protocol.py \
  --write-freeze-receipt /durable/evidence/prospective-pilot-freeze.json
```

No receipt is created or checked in by this change. Generation fails whenever
the governed repository has any tracked or untracked worktree drift.
