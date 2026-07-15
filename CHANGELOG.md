# Changelog

All notable changes to `bench-cleanser` are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — 0.1.0 engineering-alpha candidate

This source tree is an experimental benchmark-auditing and verification-routing
toolkit. It is not a stable release, a calibrated verifier, or an empirical
research result. No public artifact should be described as such until the gates
in [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md) are met.

### Added

- Corpus `0.6.0` and evaluation `0.5.0` separate deterministic
  bootstrap/counterfactual/human label evidence from the randomized live-policy
  behavior trajectory. Exact behavior source manifests, deterministic bootstrap
  history, terminal completion, logger identities, and behavior digests are
  independently bound; target-policy identity is not rewritten as behavior
  propensity. The bootstrap source is a sanitized policy projection, while
  nonempty live-result metadata must match the exact typed acquisition producer
  envelope and route constants. Opaque audit strings remain excluded from policy
  state rather than being classified by a brittle content blacklist. Corpus
  reports expose disjoint label, bootstrap, live-behavior, and inclusive costs
  with timezone-aware ranges and no invented bootstrap timestamps.
  Scientific-ledger/export/resource-settlement `0.2.0` adds an independently
  digest-pinned semantic export replay
  and durably records resource overruns before halting new work.

- A versioned, reference-free `ValidityManifest` for SWE training, rollout, and
  evaluation candidates, with immutable provenance, separate candidate/verifier
  risk features, measured evidence costs, and auditable route history.
- An inspectable `ConservativeRouter` baseline that can request static,
  semantic, targeted, full-execution, or oracle-hardening evidence and can end
  in accept, reject, or abstain.
- A bounded `bench-cleanser-acquire` adapter for argv-only local semantic,
  static, targeted, full, and oracle-hardening commands. Semantic producers
  emit a strict versioned stdout schema whose exit code denotes transport only;
  retained raw bytes and parsed fields are digest-bound and revalidated by the
  one-step coordinator, while token/USD and producer-input claims remain
  explicitly declared rather than measured or authenticated. The runner
  confines the initial working directory, excludes ambient credential
  variables, kills the process group at a real wall deadline, bounds both
  output streams, atomically stores the artifact, and emits a unique
  non-authoritative observation; it explicitly does not claim OS-level
  sandboxing.
- A fail-closed pinned-container request builder that requires an immutable
  image digest and explicit local Docker endpoint and fixes network, mount,
  root-filesystem, user, capability, privilege, resource, log, and entrypoint
  controls. It constructs but does not execute or attest a container.
- A strict one-step `RouteAcquisitionPlan`/`execute_route_acquisition` bridge
  that preallocates the acquisition identity, persists intent before launch,
  binds the request to the routed manifest/candidate/base/workspace marker,
  revalidates the raw artifact, and fails closed on concurrent or interrupted
  steps. It is a programmatic non-isolated primitive, not an end-to-end verifier.
- A strict live `RouterStateView`/`ActionOffer`/`LoggedPolicyDecision` contract
  with typed deployable inputs, concrete action-spec identities, full behavior
  distributions including terminal actions, canonical sampling, and chained
  decision digests. Corpus `0.6.0` preserves live decisions in a separate
  behavior trajectory without conflating them with deterministic label evidence
  or collapsing multiple offers per modality. The corpus layer computes no OPE estimate; the
  separate prospective analysis is limited to support/ESS-gated
  self-normalized importance-sampling point diagnostics.
- A strict verification-gap corpus schema and `bench-cleanser-corpus` CLI with
  candidate/artifact binding, collection timestamps, all-modality pairing,
  repeated conclusive execution, separate blinded task validity and conditional
  candidate correctness, provenance-bearing `EvidenceValidityAdjudication`
  records, and split checks. Each evidence adjudication names its source,
  protocol, blinding state, reviewer count, agreement, and indeterminate status.
  Legacy Boolean truth cannot be silently migrated. Its report explicitly does
  not claim scientific adequacy.
- A lossless `bridge_logged_policy_observation` path plus corpus-wide checks for
  temporal contradictions, cross-record/cross-namespace ID collisions,
  trajectory reuse, policy implementation drift, and stable-action redefinition.
- Strict paired-outcome metrics and CLI reporting for calibration, selective
  risk, auditable false accepts/rejects, execution rate, cost, risk–coverage
  curves, and subgroup slices. Evaluation `0.5.0` accepts truth-free target-policy
  outcomes only when they join exactly to corpus `0.6.0` and its terminal
  behavior trajectory; task validity,
  conditional candidate correctness, verifier validity, and quarantine are
  reported separately. Verifier reports preserve adjudication source/protocol
  counts and explicitly exclude indeterminate or inadequately adjudicated labels
  from calibration.
- Public `tree-sitter-language-pack` structural analysis behind the
  `[structural]` extra, with a conservative Python-`ast`/text fallback.
- Path-confinement, resume-integrity, installed-wheel, routing, manifest,
  metrics, timeout, concurrency, and cache-semantics regression tests.
- Commit-and-run-attempt-scoped, 90-day CI retention of the complete
  wheel/sdist/SBOM/license/artifact evidence directory through the official
  upload action pinned to an immutable commit; missing evidence fails the job
  and mutable action tags are regression tested.
- Automatic canonical test, coverage, lint, and type evidence capture with a
  fail-closed 70% line-coverage floor in both
  Python 3.11/3.12 matrix jobs, a pip-report-bound Linux environment lock in the
  package job, and a final `bench-cleanser-linux-ci-evidence-0.2.0` record that
  inventories both matrix receipts, embeds GitHub context, and binds the exact
  release artifacts. These are digest-bound declared records, not independently
  authenticated GitHub attestations.
- CI strict-mypy coverage for both release scripts and all four study runners,
  in addition to the package-wide type check.
- The “Route Evidence, Not Models” research specification: novelty boundary,
  falsifiable hypotheses, selection-bias controls, task–candidate–oracle method,
  paired verification-gap dataset, lifecycle-wide experiments, and a
  literature boundary rechecked through July 2026.
- A strict 70-entry primary-arXiv literature lock with exact cited versions,
  canonical metadata, retrieval identity, raw Atom-response SHA-256, an offline
  regeneration/check path, duplicate-key rejection, bounded redirect-safe Atom
  fetching, and tests that reject citation/version/metadata drift and preserve
  existing outputs across network or atomic-publication failures.
- A source-locked real-agent contrastive pilot over four public SWE-bench
  submission patches, reports, and trajectories. It reproduces the gap between
  four optimistic terminal self-reports and two hosted resolved outcomes while
  explicitly recording contrastive selection and the submission's unchecked
  status; it is not presented as a population estimate.
- A complete 500-row hosted-outcome development study with a sanitized
  patch-only feature builder, four base plus 48 sensitivity full-order freezes,
  post-freeze-only outcome decoding, hash-checked order consumption, exact
  failure/resolved/unknown repository-stratified randomization, and explicitly
  post-hoc discrimination diagnostics. Its budgets reveal preserved hosted
  labels as execution-cost proxies; the study performs no repository or test
  execution and makes no calibration or population claim. Patch size beats the
  hand-built router at every matched nonterminal budget, and the post-hoc router
  ROC AUC is 0.53249.
- A matched three-rollout v2 development study over three checked OpenHands
  submissions and a 499-task common frame. It binds canonical task commits,
  code identity, unknown outcomes, and outcome-sanitized feature freezes. Its
  fresh source-identical 24-task run is an honest negative result: Claude-first
  reaches the 18-task hosted oracle ceiling, while the fixed hybrid starts at 15
  and catches up only after spending more hosted-label reveals. This is
  retrospective development evidence, not independent execution or H1–H6.
- A versioned independent-evidence development protocol with an explicit
  accepted-set false-accept estimand, full action-level propensity logging,
  repeated execution, blinded adjudication, substrate factorial, fixed stopping,
  and power limits. Protocol `0.3` records that the SymPy and Sphinx feasibility
  tasks were executed post-draft but pre-freeze and excludes both clusters from
  prospective/OPE estimands. It fixes a 22-task/66-candidate frame, the
  nine-action disclosed catalog with at most seven behavior-eligible actions,
  the `1/14` propensity floor, numeric ceilings, domain-separated seeds, an
  exact scheduler/package-policy-log crosswalk, terminal admissibility, blinded
  packet projection, six truth-free target policies, and guarded descriptive
  analysis.
  Deterministic static bootstrap is now an immutable candidate-bound prefix,
  separate from randomized policy history and propensity accounting. The
  experiment-local proposal policy skips unavailable modalities through a
  frozen fallback and exposes accept or reject only after concordant,
  independent primary/repeat full executions; infrastructure errors,
  inconclusive evidence, and disagreement cannot propose rejection.
  Completed route-acquisition outputs can now be reloaded only against retained
  manifest, decision, and plan preimages; recovery revalidates the prepared
  envelope, raw artifact, route provenance, and exact manifest successor without
  rerunning the command. A single-host prospective ledger/dispatcher now commits
  exact executable specs and whole rounds before a permanent claim, launches
  only the winning claim, derives recovery inputs from the stored preimage,
  returns an exact result after acknowledgement loss, requires an explicit
  worker-exit receipt before halt, and checks full-repeat equivalence and fresh
  provisioning identities.
  A structural StudyBundle compiler requires an independently supplied anchor,
  reopens the ledger/spec/artifact bytes, derives actions, propensities,
  terminal/task selections, execution counts, qualified cost declarations, and
  partial-frame status, and publishes a content-addressed artifact. It does not
  authenticate producers or manufacture scientific truth.
  A separate experimental single-host scientific-ledger module defines
  domain-bound signed bootstrap, curator, resource-reservation, and
  resource-settlement envelopes. It is empty, unjoined, and deliberately supplies no
  reviewer-vote/adjudication record, frozen production roles, behavior-ledger
  chronology join, external checkpoint, immutable artifact store, activation
  claim, or empirical result.
  Activation remains blocked on external execution/custody/review identities,
  the populated action registry and activation context, authenticated
  provisioning, externally immutable artifact storage, and a clean-commit
  receipt for the current candidate; the receipt for baseline commit `6b26448`
  does not bind this working tree, and the durable-dispatch and typed-persistence
  gates remain blocking.
- Contract-only data and router cards that deny a populated dataset, learned
  policy, calibration, task-validity prediction, or supported performance claim.
- A partial claim-level literature ledger and fail-closed verifier covering 35
  page/section mappings from 26 exact PDFs among 70 metadata-locked papers,
  including a direct novelty red-team against Bayesian cost-sensitive
  sequential verification control.
  All mappings remain machine-assisted and `human_confirmed: false`.
- A fail-closed release-dossier generator that binds a clean Git tree, signed
  annotated tag, wheel/sdist bytes, exact gate commands and logs, Linux evidence,
  dependency environment, SBOM/license reports, literature lock/claim ledger,
  study code, and a digest-bound human attestation. It verifies evidence; it
  does not upload or convert automation into legal/scientific approval.
- An evidence-availability inventory that distinguishes checked-in summaries,
  local temporary bundles, upstream source URLs, and durable release/DOI assets.
- A source-locked SymPy feasibility-execution record with 15 digest-bound raw
  acquisitions (base, three candidates, and gold; three repeats each), strict
  external-bundle validation, and explicit post-draft/pre-freeze exclusions.
  The targeted macOS-arm64 replay matched hosted candidate outcomes but is not
  full-harness/container evidence, adjudicated truth, or H1–H6 support.
- A paired Linux/arm64 SymPy feasibility record with 15 independently parsed
  container runs over the same prepared roles and targeted 39-test file. Its
  repeated role pattern matches the container-free arm, but the locally built
  non-official image, reused source trees, tagged base reference, targeted
  harness, and absent runner timeout preclude substrate-equivalence, routing,
  population, or correctness claims.
- A second-repository Sphinx feasibility record with 15 container-free
  observations, 255/255 passing P2P checks, and repeated base-fails/gold-passes
  F2P behavior. All candidates share the gold functional change, and the
  network-sensitive checks required split proxy policies, so it provides
  environment bring-up evidence but no candidate discrimination, official
  harness equivalence, prospective inference, routing result, or H1–H6 support.

### Changed

- Replaced Microsoft-internal CloudGPT/Azure authentication with the standard
  OpenAI-compatible `AsyncOpenAI` client. Authentication uses
  `OPENAI_API_KEY`; `OPENAI_BASE_URL` selects a compatible endpoint.
- Added real per-request and total retry deadlines, an API-attempt semaphore,
  and a narrow transient-error retry policy. Authentication and malformed
  requests are not retried.
- Cache identity now covers provider, base URL, model, call mode, token and
  reasoning settings, prompts, and structured-output schema semantics.
- Packaged configuration defaults to `gpt-4.1`, a 32,768-token ceiling, unset
  reasoning effort, a 180-second request timeout, and a 600-second total retry
  deadline. `--config` is optional outside the source checkout.
- Cross-agent patch convergence is review evidence, not proof of leakage:
  non-trivial converged clusters are marked unknown for review rather than
  automatically upgraded to a gold-patch leak.
- Project maturity metadata and public documentation now say engineering alpha.
- Router authority is fail-closed: source/version/calibration claims must match
  explicit policy bindings, authoritative observations need unique acquisition
  IDs, full execution needs repeated consistent trusted observations, and a
  false-accept bound can accept but never reject.

### Fixed

- Ordinary newly added tests no longer imply `APPROACH_LOCK` by themselves.
- F2P matching uses file identity and abstains on ambiguous name-only matches;
  unmatched tests are not silently treated as aligned; modified tests are
  reconstructed from full context when available.
- Contradictory trajectory outcome/`resolved` combinations can no longer become
  `FAIR_PASS`.
- Repository identifiers, full commit hashes, patch paths, source reads,
  instance IDs, report paths, and symlink resolution are confined and tested.
- Resume rejects malformed, stale, incomplete, and pipeline-error reports;
  all-new-work-failed runs exit nonzero and expose failure details.
- `code_visitation.enabled` is honored.
- Live trajectory rehydration searches the Live dataset and tool observations
  are included in semantic trajectory evidence.
- Structural analysis no longer depends on the unavailable `astred-core`
  package or its temporary checkout workflow.
- Verification JSON rejects duplicate keys and non-finite values; artifact
  writes flush the temporary file and, where supported, the containing
  directory before reporting success.
- Prospective analysis derives each repository stratum from the frozen task ID
  instead of trusting a caller label, preventing silent repository splitting or
  merging in descriptive and future bootstrap inputs.
- CI strict type checking now covers the prospective scheduler, target-policy,
  and analysis implementations plus their tests, and uses explicit package
  bases for the protocol validator.
- Paired evaluation preserves policy/run/seed/calibration/corpus identity,
  reports undefined rates as `null` with auditable counts, uses confidence in
  the action actually taken, and extends risk integration through explicit
  abstentions to full coverage.
- The artifact secret gate distinguishes exact schema-bound public commit and
  SHA-256 provenance from credentials by path, field, value shape, source line,
  and scanner identity; classifications remain visible and all other findings
  fail closed.

### Removed

- Microsoft-internal provider source and Azure/MSAL dependencies.
- The unavailable `astred-core` extra.
- The `[trajectory]` dependency extra. Docent ingestion remains a lazy,
  user-managed integration, while the release SBOM covers the default and
  public structural dependency profiles without Docent's conflicting,
  fast-moving provider/telemetry closure.
- Duplicate prompt force-inclusion configuration; prompts and the default YAML
  ship as ordinary package resources.
- Unsupported claims of production stability, benchmark-wide validity, fixed
  wall-clock performance, and an obsolete exact test count.

### Still open before an empirical research release

- Real multi-repository environment provisioning/attestation and a paired
  reference-free semantic/targeted/full/hardened-oracle/human corpus.
- Repository- and time-disjoint calibration with selective-risk guarantees.
- Controlled SFT/RL/rollout experiments and multi-seed evaluation stability.
- A deployable task-validity estimate/task-aware router and a prospectively
  frozen matched selector run on held-out tasks with independent execution.
- Regenerated representative artifacts with full model, prompt, dataset,
  scaffold, environment, and cost provenance.
- A populated, human-reviewed corpus card and learned-policy model card;
  environment digests, durable raw per-seed outputs, separate research-data
  privacy/license attestation, paper, and reproducibility/DOI bundle.
