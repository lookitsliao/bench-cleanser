# Release readiness

**Target:** 0.1.0 engineering alpha.
**Verdict:** the current follow-up tree clears the local engineering-alpha code,
type, coverage, clean-install, installed-CLI, and automated supply-chain gates,
but it is **not a release candidate**. It is not yet a clean committed candidate
and has no current-tree freeze receipt, signed annotated tag, observed Linux CI
run, named human dependency-license attestation, or durable release/DOI evidence
deposit. This is not ready for a stable, empirical, or headline research
release.

**Published-baseline validation (commit `6b26448`, 2026-07-14):** 862 tests
passed with 72.25% statement coverage against the 70% gate; Ruff passed
repository-wide; mypy passed across 47 package files; all 17 strict CI mypy
invocations passed; and `git diff --check` passed. An external freeze receipt
binds that clean commit, but reports activation false with 14 substantive
blockers. Those results do not cover the current follow-up tree.

**Current follow-up validation (2026-07-14):** 891 tests passed with 72.25%
statement coverage against the 70% gate; repository-wide Ruff passed; package
mypy passed across 47 files; all 18 strict CI mypy invocations passed; and
`git diff --check` passed. The literature, release, protocol, scientific-ledger,
task-joint-propensity, substrate-accounting, and adversarial supply contracts
are included. The default protocol check remains valid and fail-closed with 15
blockers, including the missing current-candidate receipt. These are local
results on a dirty macOS tree, not canonical clean-commit or Linux receipts.

**Current working-tree supply-chain validation (2026-07-14):** a fresh
wheel built through the sdist plus `[structural]` resolved to 55 installed
distributions (including the root, `pip`, and `setuptools`) in a new Python 3.11
environment. PyPI's index endpoint was unavailable, so all 54 public dependency
wheels were reconstructed from the prior install report and local HTTP cache
only after exact SHA-256 matching; pip then ran with `--no-index`. The
CycloneDX 1.6 SBOM and full license-text inventory passed exact coverage checks;
automated policy reported 55 allow, 0 deny, and 0 review. The 58-member wheel
and 212-member sdist passed metadata, confinement, proprietary-dependency, and
offline secret scans with zero actionable findings; 351 exact
schema/path/source-bound public provenance hashes remained visible rather than
being silently baselined. Clean installation, `pip check`, and all eight
installed entry points plus the manifest-to-route pipeline passed outside the
checkout. The Linux-only canonical environment lock was intentionally not
emitted from this dirty macOS tree. This is automated local evidence, not a
clean Git candidate, observed Linux evidence, or completed legal review.

Passing unit tests is necessary but not sufficient. Bench Cleanser can influence
training-data admission, RL rewards, rollout selection, and reported rankings;
false confidence is therefore a release blocker.

## Gates

| Gate | Required evidence | Current state |
|---|---|---|
| Portable install | wheel and sdist build; clean virtualenv install; every CLI works outside checkout | fresh working-tree build, clean install, and installed-CLI smoke pass on macOS and are enforced in CI; clean-commit binding and an observed Linux run remain open |
| Public dependencies | no proprietary code/auth; public dependency resolution; machine-readable SBOM/inventory; fail-closed allow/deny/review policy; human attestation | the fresh default+structural snapshot has 55 allowed distributions, no deny/review result, exact SBOM/inventory coverage, and zero archive findings; commit-scoped CI plus human/legal attestation remain open |
| Safe untrusted input | repository/commit/patch/source/report paths confined; symlink escapes and hostile identifiers tested | core boundaries covered by focused regressions; fuzz/threat-model review open |
| Failure integrity | real timeouts; bounded concurrency; stale/error checkpoints rerun; all-failed invocations nonzero | implemented with focused regressions |
| Analytic integrity | regressions for F2P matching/reconstruction, taxonomy, fusion, and trajectory evidence | known code defects covered; empirical precision/recall remains unknown |
| Verification trust | authority is usable only under explicit policy bindings and independently identified acquisitions; contradictory or weak-oracle evidence fails closed | schema/router contract and focused regressions exist; bindings are allowlists, not producer authentication or signatures |
| Paired-corpus integrity | pre-execution feature separation; distinct decision/event/acquisition identities; candidate/artifact/time bindings; repeated execution; blinded task/candidate/evidence truth; repository/time-disjoint splits | strict corpus `0.5.0` separates task validity from conditional candidate correctness, requires provenance-bearing `EvidenceValidityAdjudication`, and makes determinate paired-ready labels pass blinding, reviewer-count, and agreement gates; no populated research corpus exists |
| Metric integrity | truth joined from the exact corpus; task/candidate/verifier metrics separated; policy/run/seed/calibration/corpus identities preserved; undefined rates remain undefined; every rate exposes counts | strict evaluation `0.4.0` rejects caller-declared truth, binds corpus/record/acquisition-trajectory digests, reports evidence-adjudication source/protocol/exclusion counts, scores quarantine separately, and computes no unsupported OPE estimate; only retrospective hosted-label proxies and a negative v2 matched development result exist, not a prospective independently executed comparison |
| Reproducibility | immutable input/config/model/prompt/scaffold/environment identities and costs in outputs | input/config digests and validity manifests exist; complete run provenance is not yet end-to-end |
| Coverage | critical-path branch coverage measured; adversarial and installed-behavior fixtures included | current local tree is 72.25% overall against a 70% CI floor; coverage remains sharply uneven and is not release-grade research evidence |
| Research validity | blinded paired semantic/execution/hardened-oracle/human labels; disjoint calibration/test repositories | not met |
| Downstream value | controlled SFT, RL, rollout, and evaluation experiments with uncertainty | not met |
| Public research release | version/tag/changelog/artifacts, cards, manifests, environments, and raw outputs agree | not met |

## Closed engineering defects

“Closed” means the specific implementation defect has code and focused test
evidence. It does **not** imply that the research method is validated.

| Defect from strict audit | Resolution evidence |
|---|---|
| Duplicate wheel prompt inclusion | wheel config now includes only the package tree; prompts/default YAML are ordinary resources |
| Installed CLI required checkout-local `config.yaml` | packaged `default_config.yaml`; `tests/test_config.py`; installed-entry-point CI smoke |
| Microsoft-internal CloudGPT and Azure-only auth bundled | standard OpenAI-compatible `AsyncOpenAI`; proprietary package removed; Azure/MSAL dependencies removed |
| Advertised `astred-core` was unavailable publicly | `[structural]` now pins public `tree-sitter-language-pack`; real-backend and fallback tests |
| Release artifacts had no reproducible dependency/license gate | pinned CycloneDX, `pip-licenses`, and `detect-secrets` tools; fresh wheel environment; strict SBOM/inventory agreement; allow/deny/review policy; exact wheel/sdist scan; `tests/test_supply_chain_audit.py`; CI job uses read-only permissions and SHA-pinned actions |
| Stale or fabricated release records could be assembled into a readiness claim | `scripts/build_release_dossier.py` binds clean `HEAD`, signed annotated tag, exact wheel/sdist and metadata, canonical gate commands/logs, Linux evidence, resolved environment, SBOM/license reports, literature lock/claim ledger, study code, and a digest-bound human attestation; adversarial archive/command/metadata tests fail closed |
| CI quality/Linux records depended on manual transcription | each Python 3.11/3.12 job emits canonical quality records and logs; the package job emits a pip-report-checked environment lock; the final job inventories both matrices in Linux CI schema `0.2.0`, binds exact package/audit hashes, includes run attempt and GitHub context, and retains the bundle for 90 days; the record remains declared rather than OIDC/API-authenticated |
| A post-draft execution could be relabeled as prospective evidence | protocol `0.3`, hash-chained `prehistory.json`, both feasibility manifests, and `validate_protocol.py` classify the SymPy and Sphinx runs post-draft/pre-freeze, exclude both task clusters from prospective/OPE claims, and keep activation false until the clean receipt and all external/operational bindings exist |
| Docent extra pulled an unbounded, conflicting provider/telemetry closure | `[trajectory]` dependency extra removed from release metadata after demonstrating current `inspect-ai`/`huggingface-hub` `click` incompatibility; JSON/JSONL/directory/Hugging Face loading remains packaged and Docent remains an explicitly user-constrained integration |
| Production/stable maturity claim | alpha classifier, 0.1.0 candidate copy, and explicit non-result warning |
| Ordinary new tests could imply `APPROACH_LOCK` | `test_ordinary_new_test_patch_does_not_imply_approach_lock` |
| Failed/contradictory trajectory state could become `FAIR_PASS` | outcome normalization and `test_failed_rollout_with_passed_genuine_label_cannot_be_fair_pass` |
| Cross-agent convergence was treated as proof of leakage | convergence now creates an unknown/manual-review signal with non-triviality gate |
| F2P matching ignored filenames/ambiguity; unmatched tests auto-aligned; modified tests reconstructed incompletely | focused regressions in `tests/test_correctness_regressions.py` |
| Untrusted commits, patch paths, source paths, symlinks, and instance IDs could escape roots | confinement validators and hostile-path regressions in `tests/test_pipeline_hardening.py` |
| Resume accepted malformed, stale, incomplete, and pipeline-error reports | provenance-matched complete-success requirement and focused resume regression |
| Main CLI could succeed when every new attempt failed | invocation counters, nonzero exit code, and failure-detail regression |
| Total LLM deadline did not bound in-flight requests | `asyncio.timeout` per attempt plus shared total deadline; timeout regressions |
| LLM-call concurrency setting was inconsistently enforced | API-attempt semaphore plus concurrency regressions |
| Cache identity omitted endpoint/call/schema semantics | canonical v2 identity envelope plus structured/unstructured cache regressions |
| Structural temporary workflow leaked and ignored patch failures | public in-process Tree-sitter backend with conservative fallback |
| `code_visitation.enabled` was ignored | pipeline gate and `test_code_visitation_disabled_avoids_repo_manager` |
| Live trajectory records and tool observations could be omitted | Live rehydration and observation-in-prompt regressions |
| Documentation advertised obsolete provider/model/count/maturity behavior | README, overview, contributing guide, architecture asset, changelog, and sample warning reconciled |
| Serialized `authoritative=true` or a calibration ID could be mistaken for trust | authority and calibration require exact policy bindings; authoritative evidence also requires a unique acquisition ID |
| One full-execution result could be treated as a terminal oracle | terminal full-execution decisions require repeated, consistent, policy-trusted acquisitions meeting the verifier-validity threshold; otherwise reroute, harden, or abstain |
| Candidate failure and verifier failure could share one risk path | router records separate candidate and verifier risk and never converts execution error/unavailability into candidate rejection |
| Paired labels could leak into deployable router inputs | corpus records require an evidence-free, route-free pre-execution manifest; privileged observations and adjudication remain outside it |
| Corpus events were not fully bound to the candidate and acquisition | corpus `0.5.0` binds candidate artifact locator/digest, generation and collection times, subject candidate, distinct event/decision/acquisition identities, evidence artifact digest/locator, replicate identity, decision history, behavior distribution, and collection policy |
| Invalid tasks had to be fabricated as correct/incorrect candidates and evaluation trusted caller-supplied truth | corpus `0.5.0` adds blinded `TaskAdjudication` plus conditional `CandidateCorrectness`; evaluation `0.4.0` requires an exact corpus/record/trajectory join, reports task/candidate/verifier metrics separately, and treats abstention as correct quarantine for invalid or indeterminate truth |
| Collection completeness could be mistaken for scientific adequacy | corpus reports explicitly mark power, representativeness, calibration, and downstream value as unassessed |
| Verification JSON could silently accept ambiguous numeric/object encodings | strict readers reject unknown fields, duplicate keys, non-finite values, duplicate evidence IDs, and duplicate paired observations |
| Verification artifacts could be partially replaced or reported before a durable write | shared atomic writer flushes the temporary file, atomically replaces the target, flushes the directory where supported, and cleans up on failure |
| A completed local acquisition file could be trusted after a crash without rechecking its preimages | strict recovery requires the retained manifest, route decision, and plan, then revalidates the prepared envelope, raw artifact, route provenance, all digests, and the exact one-observation manifest successor without rerunning the command |
| Verification CLI output failures could escape as tracebacks or false success | manifest, route, corpus, and evaluate commands catch read/validation/serialization/write failures and exit with a scoped error; focused output-failure regressions cover each command |
| Policy outcomes could be pooled across runs or emit manufactured zero rates | evaluation preserves policy/version/run/seed/calibration/corpus identity, reports undefined metrics as `null`, and includes reconstructible numerators and denominators |
| Prospective repository strata could be caller-relabelled before analysis | each analysis record derives its repository stratum from the exact frozen task identity; the machine-readable plan and validator fix the rule and a regression rejects relabelling |
| Selective-risk curves could hide abstentions or rank rejects by the wrong confidence | confidence is conditioned on the action taken; abstentions enter an explicit final group and integration extends to full coverage |
| An untested replay module could imply a supported offline-policy product | dormant, unexported replay code was removed; prospective/OPE support remains an explicit empirical deliverable rather than a hidden eighth surface |
| Routing could request evidence without any runnable adapter | `bench-cleanser-acquire` executes one bounded argv-only static, semantic, targeted, full, or hardening command with minimal environment, process-group timeout cleanup, bounded digest-bound artifacts, measured local cost, declared semantic cost, and non-authoritative evidence; the pinned-container builder fixes a conservative digest-only local Docker profile but does not attest it |
| A scalar chosen-action propensity could be presented as sequential logging | the live policy contract requires the full strictly-positive action-level distribution at each typed pre-action state; corpus `0.5.0` embeds it unchanged with the sampler/code/spec/chain identities and reports descriptive support only, with no causal-validity claim |
| Live decision/event/acquisition identities could not be joined losslessly | `bridge_logged_policy_observation` preserves all three namespaces plus the exact action catalog, behavior distribution, sampler draw, policy digest, and chain heads; global collisions, temporal contradictions, trajectory reuse, and stable-action redefinition fail closed |
| Public provenance hashes triggered opaque secret-scan failures | the artifact auditor recognizes only exact typed cohort, hosted/matched/feasibility-study, protocol-prehistory, canonical-dataset, literature-lock, and claim-ledger fields by path, schema, field, value, byte/source contract, line, and scanner identity; the current report preserved all 351 classifications and every other finding still failed |

## Open blockers

- A one-step programmatic route-action executor now binds and precommits an
  operator-supplied local request, but direct execution is explicitly
  unsafe/non-isolated and is not an automatic end-to-end loop. The
  pinned-container builder fixes a conservative local Docker argv without
  contacting the daemon; image construction, daemon/image/workspace attestation,
  the semantic producer/model, human adapters, and authenticated authority
  remain external. The prospective pilot now has an experiment-local
  single-host ledger and claim-before-launch dispatcher with exact stored-spec
  joins, permanent claims, acknowledgement-loss recovery, and explicit
  worker-exit-gated halt. It is still activation-blocked because the real action
  registry and activation context are absent, provisioning assertions are not
  authenticated, and raw artifacts have no externally immutable store. The
  semantic transport schema is strict and
  raw-byte bound, but model/input/calibration/token/USD declarations are not
  authenticated facts.
- The live policy-log schema records typed router state, concrete action offers,
  terminal actions, full behavior propensities, and a chained pre-action
  decision. Corpus `0.5.0` now preserves it losslessly beside observations. The
  experiment-local dispatcher proves pre-launch commit and exactly-once claim
  only inside its declared single-host SQLite boundary; an unsigned provisioner
  or executor artifact still does not prove the declared substrate/spec ran. The
  prospective analysis implements support- and ESS-gated self-normalized
  sequential importance-sampling point diagnostics only; it supplies no causal
  OPE claim, interval, doubly robust estimator, nuisance model, or cross-fitting.
- A separate experimental single-host scientific ledger defines domain-bound
  signed-envelope schemas and local storage for bootstrap, curator, resource-
  reservation, and resource-settlement records. It is empty and unjoined, has
  no human-adjudication record, frozen production authority roles,
  behavior-ledger chronology join, external chain checkpoint, or immutable
  artifact store, and is not a governed activation configuration. Its local row
  chain cannot by itself prove absence of writer reordering or suffix
  truncation. It clears no scientific or activation blocker.
- Prospective protocol `0.3` is internally valid but intentionally reports
  `activation_ready: false`. Its numeric resource ceiling, domain-separated
  seeds, exact-frame scheduler and joint-propensity contract, terminal rule,
  review projection, six truth-free target policies, and cluster-respecting
  analysis are fixed and source-bound. A valid external receipt exists for the
  baseline commit `6b26448`, but it does not bind the current working-tree
  candidate. The current candidate still lacks its own clean-commit receipt,
  Docker/provisioner and execution-architecture attestations, per-task
  image/dependency/execution manifests, a semantic producer identity, an
  opaque-map custodian and reviewer attestations, populated action registry,
  validated dispatcher activation context, authenticated provisioning receipts,
  and externally immutable evidence storage. Those omissions keep the durable
  dispatch and typed-persistence requirements explicitly blocking.
- Its numeric scores are hand-designed and uncalibrated. They are routing
  heuristics, not probabilities and not a false-accept guarantee.
- The deployable manifest/router still exposes candidate and verifier risk only.
  Task validity is represented as privileged corpus/evaluation truth, not as a
  deployable prediction or acquisition target; task-aware routing remains a
  research deliverable.
- There is no **populated** paired verification-gap corpus containing blind
  semantic signals, targeted/full/repeated execution, hardened-oracle outcomes,
  expert labels, and measured compute/token/dollar cost for the same candidates.
  The schema and validator are collection infrastructure, not data.
- Corpus validation checks declared identities, digests, locators, timestamps,
  pairing, and adjudication structure; it does not fetch artifact bytes,
  authenticate producers, prove the declarations, establish power, or make the
  sample representative.
- There is no completed repository- and time-disjoint calibration/test split,
  blinded adjudication, or inter-rater agreement result. The frozen plan and
  packet projection are infrastructure, not reviewer identities or labels.
- There is no learned or calibrated
  task-validity/candidate-correctness/action-observation model and no populated
  history-propensity-logged prospective routing experiment. The six frozen
  hand-designed target policies are analysis definitions, not a learned or
  validated deployment policy.
- There is no controlled evidence that filtering or weighting improves SFT,
  RL, Best-of-N rollout selection, reward robustness, or leaderboard stability.
- The contemporary bibliography has a 70-entry machine-readable primary-arXiv
  metadata lock plus a separate 26-paper/35-claim page-level ledger. All 26
  exact PDF identities passed byte verification during their respective
  reviews through 2026-07-14, but those bytes
  have no durable release locator, 44 papers remain unmapped, and every review
  remains machine-assisted with `human_confirmed: false`.
- The synthetic eight-candidate/40-acquisition seed study validates the local
  and pinned-container plumbing and exposes a weak inherited oracle, but is not
  representative, blinded, randomized, calibrated, or suitable for H1–H6.
- The four-candidate real-agent contrastive pilot source-locks public patches,
  trajectories, and hosted evaluation reports and exposes two optimistic
  self-report false accepts in its selected denominator. It is one repository,
  one model/scaffold, non-random, not independently re-executed, and the source
  submission is marked unchecked; it is not a populated paired corpus or an
  H1–H6 result.
- The complete 500-row hosted-outcome development study freezes patch-only
  features and 52 full policy permutations before decoding labels, but it only
  simulates selective reveal of an unchecked submission's preserved hosted
  reports. It performs no new execution, has one candidate per task, and finds
  the simple patch-size baseline stronger than the hand-built router. It is a
  negative control and finite-frame plumbing result, not H1–H6 validation. Its
  canonical SWE-bench Verified parquet is now revision/byte/digest pinned and
  matches all 500 S3 IDs, repositories, and full base/environment commits; that
  closes task-identity provenance, not execution or oracle validity.
- The matched three-rollout v2 implementation source-locks three checked
  OpenHands-family submissions, a 499-task common frame, canonical task commits,
  code identity, unknown outcomes, and an outcome-sanitized freeze boundary. Its
  post-outcome full-frame union is a diversity ceiling, not a selector. A fresh
  source-identical 24-task v2 development run is negative: Claude-first reaches
  the 18-task hosted oracle ceiling, the fixed hybrid starts at 15 and only
  catches up with more hosted-label reveals. One SymPy task now has a separate
  post-draft/pre-freeze targeted macOS replay over all three candidates and
  controls, plus a retrospective paired Linux/arm64 container arm. The latter
  reproduces the same five-role pattern across three repeats, but reuses the
  prepared source trees, uses a locally built non-official image and one
  targeted test file, lacks a runner timeout and cross-architecture/remote-CI
  replication, and cannot establish substrate equivalence, correctness,
  prospective policy evidence, or H1–H6 support.
- A second container-free Sphinx task repeatedly gives the base-fails and
  gold-passes sanity pattern: all 255 P2P checks pass, base fails F2P 3/3, and
  all candidates and gold pass F2P. It provides no candidate discrimination
  because every candidate has the gold functional change. Its split proxy
  policy, mutable public-link checks, reconstructed macOS environment, and
  bring-up revisions also make it retrospective feasibility evidence rather
  than official-harness equivalence, semantic truth, routing evidence, or a
  prospective/OPE estimand.
- Coverage remains modest and does not substitute for adversarial end-to-end
  runs across compiled languages, native dependencies, migrations, security,
  concurrency, and broken environments.
- The checked-in sample reports predate the current provenance envelope and are
  illustrative only; publication artifacts must be regenerated.
- The automated SBOM/license policy passed a local macOS/Python 3.11
  default+structural working-tree snapshot. Local working-tree evidence is
  deliberately non-canonical until it is rerun from and bound to a clean
  candidate commit. Even then, it does not prove package metadata,
  bundled/native material, other platforms, or future resolutions are legally
  cleared. Local reports are temporary developer artifacts; a release
  maintainer must regenerate and preserve them with the candidate commit and
  inspect and attest to that exact inventory/license text. Qualified review is
  required for stable/commercial distribution. An observed Linux CI gate and
  optional live compatible-endpoint contract test also remain necessary before
  a public package upload.

## Release policy

- A 0.1.0 **engineering alpha** may be published only after the fresh test,
  lint, type, coverage, artifact, clean-install, and all-entry-point smoke gates
  pass from the exact candidate tree.
- Preserve the candidate SBOM, license inventory, policy report, artifact
  report, wheel/sdist hashes, and a named human dependency-license attestation
  together. Automated `allow` is policy triage, never a legal-clearance claim.
- A research-data release separately requires a named privacy and
  redistribution attestation bound to its exact artifact manifest. The package
  dependency attestation does not authorize third-party patches, repositories,
  issue text, trajectories, execution logs, or adjudications.
- Do not publish a stable classifier or claim calibrated verification until the
  research-validity gates are met on fresh repositories.
- Do not market deterministic router scores as calibrated probabilities.
- Do not publish benchmark-invalidity percentages without their denominator,
  sampling frame, adjudication protocol, and confidence interval.
- Do not claim filtering aids SWE training until a controlled downstream model
  experiment demonstrates it on repository- and time-disjoint data.
- Keep raw per-instance reports—including abstentions, failures, environment
  errors, and invalid-oracle cases—beside every aggregate table so denominators
  remain auditable.
