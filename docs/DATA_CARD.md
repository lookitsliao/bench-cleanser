# Verification-gap corpus data card

## Status

**Artifact status:** schema and collection contract only. There is no released
or populated verification-gap dataset in this repository.

Corpus schema `0.5.0`, its validator, and synthetic fixtures describe how a
future paired dataset must be represented. The hosted-outcome, matched-rollout,
real-agent, and seed studies are development studies; none satisfies the corpus
card below and none may be advertised as the released dataset.

## Intended unit and purpose

One record represents one exact task/candidate pair joined to a reference-free
deployable manifest, an acquisition trajectory, measured evidence events, and
curator-only truth. The same task may have multiple candidate records. Task is
the split and analysis cluster.

The intended uses are:

- learning and calibrating which verification evidence to acquire next;
- auditing SFT admission, RL rewards, and Best-of-N rollout selection;
- measuring task, candidate, and verifier uncertainty without collapsing them;
- evaluating risk, coverage, abstention, cost, and environment failures; and
- reproducing oracle-hardening and disagreement analyses.

It is not intended to certify patches automatically, replace maintainers or
reviewers, infer developer quality, rank individual contributors, or serve as a
new benchmark score without the raw target-population result.

## Required data surfaces

The deployable surface contains only information available to a live policy:

- dataset/repository/base-commit and candidate-patch identities;
- lifecycle context and reference-free risk features;
- complete pre-action catalogs and history-conditioned propensities;
- acquired observations, source/version, status, local measured cost, and
  calibration declarations; and
- write-ahead policy, sampler, action-spec, and chain identities.

The curator-only surface contains:

- `TaskAdjudication`: valid, invalid, or indeterminate task truth;
- `CandidateAdjudication`: correctness conditional on task validity;
- `EvidenceValidityAdjudication`: validity, source, protocol, blinding,
  reviewer count, agreement, and notes for every evidence event; and
- split, candidate type, human-review, and artifact provenance.

Invalid tasks require candidate correctness `not_applicable`; indeterminate
tasks require indeterminate candidate correctness. Determinate evidence labels
are paired-ready only when blinded, reviewed by at least two annotators, and at
or above 0.80 agreement. Indeterminate labels are retained and excluded from
verifier calibration rather than converted to failure or success.

## Collection and sampling requirements

A publishable dataset must include real agent patches as the majority and use
synthetic gold/no-op/under-fix/wrong-file/test-overfit candidates only as named
stress strata. It must span interpreted and compiled languages, build systems,
native dependencies, migrations, security/authentication, concurrency, and
broken environments.

Collection must acquire every evidence modality for a fully observed subset
and randomize additional acquisitions with non-zero history-conditioned
propensities. Candidate-level random splits are prohibited. Development,
calibration, and test partitions must be repository- and time-disjoint, with
task identity shared across every candidate assigned to the same partition.

Every unavailable artifact, setup failure, timeout, abstention, invalid task,
and adjudication disagreement remains in the frame and published denominators.

## Provenance and reproducibility

Every release must preserve:

- source dataset and revision, repository, full base/environment commits;
- exact patch, test patch, problem/task, image, dependency, prompt, model,
  scaffold, policy, and code digests where applicable;
- action-spec preimages and immutable raw evidence bytes;
- cold build/pull, warm execution, cache, queue, token, storage, dollar, and
  human-time costs;
- adjudication instructions, reviewer blinding, agreement, and deviations;
- record, corpus, acquisition-trajectory, and evaluation digests; and
- environment lock, SBOM, license inventory, and redistribution decision.

Checksums prove byte identity, not authenticity. A public release must also
authenticate ingestion or sign the evidence bundle.

## Privacy, licensing, and security

Public repositories and agent traces can contain personal names, email
addresses, issue discussions, generated secrets, copied code, or license terms
that differ by repository and file. Public availability is not redistribution
permission. Before release, a named curator must perform privacy and license
review, remove credentials, document redactions, preserve required notices,
and record whether raw traces or patches can be redistributed.

The current repository contains schemas and source-locked hashes, but no human
privacy/license attestation for a populated corpus.

The package release attestation covers the Python distribution's dependency
SBOM and license inventory only. It does not authorize redistribution of
repository code, patches, issue text, trajectories, execution logs, or reviewer
annotations. A populated corpus requires a separate, named privacy and
redistribution attestation bound to the exact research-artifact manifest.

## Known limitations and current evidence

- No populated paired corpus exists.
- No blinded adjudication set or inter-rater result exists.
- No repository/time-disjoint calibration or test population exists.
- Current hosted studies are Python-only and repository-imbalanced.
- Hosted `resolved` is a prior execution measurement, not candidate truth.
- One SymPy task has post-draft/pre-freeze container-free targeted execution
  over three candidates and controls. It is not a corpus record, full-harness
  execution, blinded adjudication, or prospective policy evidence; the task is
  excluded from prospective/OPE estimands in protocol `0.3`.
- Current semantic producer fields and token/USD costs are producer-declared,
  not independently authenticated.
- No learned task-validity, candidate-correctness, oracle-validity, or
  action-observation model has been released.

The pre-execution protocol for the first independent-evidence development pilot
is in
[`experiments/prospective_pilot/PREREGISTRATION.md`](../experiments/prospective_pilot/PREREGISTRATION.md).

## Release gate

This card may change from “contract only” to “released dataset” only when the
dataset bytes, manifest, corpus report, splits, adjudication report, environment
lock, privacy/license review, and signed release dossier are preserved together
under a clean tagged commit or durable DOI.
