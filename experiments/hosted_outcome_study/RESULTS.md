# Hosted-outcome finite-frame development result

**Status:** retrospective finite-frame development evidence, not a headline
method result or independent SWE-bench audit.

The 2026-07-13 run reproduced the complete 500-prefix frame across 12
repositories. It found 500 patches, 499 reports, and one missing report:
`psf__requests-1142`. That row is `no_logs` in the pinned official results,
remains in every denominator, has a valid frozen patch-only risk profile, and
is mandatory quarantine when its label is needed.

## Source and integrity evidence

- Pinned submission metadata: 693 bytes, SHA-256
  `54c2a3eacf6f51bcb63b66c2aa1e9d74f3fde5070c29604396a233325a24faaf`;
  declares `checked: false` and `attempts: 1`.
- Pinned official results: 7,723 bytes, SHA-256
  `1730846aa8e8f1d91ed6274aee798a02d89ba12a9ef1a66555a3cf12a1a0eac2`.
- Official-results cross-check: exact match for 258 resolved, one `no_logs`,
  and zero `no_generation` IDs. Its categories and all per-instance hosted
  reports were decoded only after the patch-only feature/order freeze.
- Canonical SWE-bench Verified parquet: official dataset revision
  `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, 2,096,679 bytes, SHA-256
  `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`.
  Direct Hugging Face transport was unavailable in this environment, so the
  byte-identical file was retrieved from immutable Git mirror revision
  `f34deb86cca28b6050f181f5514a3eb7d7d70be4`; the manifest records both the
  authoritative URL and actual transport.
- Canonical four-field identity projection: 500 rows, 111,075 bytes, SHA-256
  `7524bf30de2473f870b23d407eccd489ec398cf4af8cedf11c9364d708582507`.
  It exactly matches all 500 S3 IDs and inferred repositories; every base and
  environment setup commit is lowercase 40-hex. There are 499 unique
  repository/base pairs. The sole legitimate duplicate is
  `django__django-15268` and `django__django-15278`, both at
  `0ab58c120939093fea90822f376e1866fc714d1f`; no base commit crosses repository
  boundaries. Gold patches, oracle tests, problem text, and hints are excluded
  from the deployable projection.
- Delimiter listing: 67,574 bytes, SHA-256
  `195ed02d5d7b9b9ae21dee800ef6f0b2be6a3419afc6c2f18fb467536fdad2a4`.
- Complete object inventory: 1,498 objects (500 patches, 499 reports, and
  499 unacquired test-output logs); this is what establishes the missing report.
- Candidate artifacts: 999 downloaded, one explicitly missing, zero download
  errors, 15,228,747 successful bytes.
- Acquisition source manifest v3: 799,716 bytes, SHA-256
  `e70e616943ac405d179098aaae20822c32f0a286528f0a85291238a61e0c7d76`.
  It retains official results as digest-checked opaque bytes, not decoded
  categories, and binds the raw canonical parquet plus its sanitized task
  projection.
- Frozen patch-only feature/order document v3: 500 rows, 4,134,502 bytes,
  SHA-256 `7ef4f036d25a397814b027fb658240410250136258897c9da8e1b8ce81169d05`.
  It binds four base and 48 tie-sensitivity full permutations individually by
  policy, seed, candidate identities, and SHA-256 before any outcome decode;
  every row also binds its full base/environment commits and canonical task
  identity digest.
- Full study report v3: 12,628,326 bytes, SHA-256
  `ed04d503f4475dc370e009abe25286a99ab2f6a7868e6249fbc86b22713da32f`.

S3 continuation tokens can change across otherwise equivalent listings, so the
manifest records each run's raw pages and digests rather than hard-coding page
digests as universal bucket identities.

## Frame

- 258 hosted-harness resolved, 241 hosted-harness failed, one unavailable.
- Failure-prevalence bounds over all 500 rows: 48.2% if the unknown is resolved,
  48.4% if it failed.
- All 500 patch-derived language profiles are Python.
- Django contributes 231/500 (46.2%); Django, SymPy, and Sphinx together
  contribute 350/500 (70.0%). Macro-repository and leave-one-repository-out
  results therefore matter alongside micro totals.
- Zero patch download errors, malformed patches, report download errors, or
  malformed reports. The reference-free manifest parser accepts both legitimate
  empty-file patches that an earlier audit identified.

## Policy results

No row was executed in this study. A selected row reveals the label in its
already-downloaded hosted report as a proxy for spending one future execution
slot; skipped labeled rows are accepted and unavailable rows are quarantined.
“False accept” below therefore means an accepted candidate whose same hosted
harness report says unresolved. The zero false-reject result under
`execute_all` is tautological under this retrospective terminal rule.

| Policy | Label-reveal budget proxy | Hosted failures captured | False accepts / accepted | False-accept fraction | Failures per selected slot | Delta in failures captured vs uniform-random expectation | 16 tie-seed capture range |
|---|---:|---:|---:|---:|---:|---:|---:|
| Accept all | 0 | 0 / 241 | 241 / 499 | 48.30% | — | 0.00 | — |
| Router risk | 50 | 23 / 241 | 218 / 476 | 45.80% | 46.00% | -1.10 | 18–24 |
| Router risk | 125 | 65 / 241 | 176 / 434 | 40.55% | 52.00% | +4.75 | 54–67 |
| Router risk | 250 | 119 / 241 | 122 / 380 | 32.11% | 47.60% | -1.50 | 119–133 |
| Router risk | 375 | 186 / 241 | 55 / 313 | 17.57% | 49.60% | +5.25 | 186–190 |
| Patch size | 50 | 32 / 241 | 209 / 467 | 44.75% | 64.00% | +7.90 | 32–32 |
| Patch size | 125 | 80 / 241 | 161 / 419 | 38.42% | 64.00% | +19.75 | 80–80 |
| Patch size | 250 | 136 / 241 | 105 / 363 | 28.93% | 54.40% | +15.50 | 136–136 |
| Patch size | 375 | 189 / 241 | 52 / 310 | 16.77% | 50.40% | +8.25 | 189–189 |
| Touches tests | 50 | 23 / 241 | 218 / 476 | 45.80% | 46.00% | -1.10 | 19–31 |
| Touches tests | 125 | 56 / 241 | 185 / 443 | 41.76% | 44.80% | -4.25 | 55–70 |
| Touches tests | 250 | 121 / 241 | 120 / 378 | 31.75% | 48.40% | +0.50 | 118–139 |
| Touches tests | 375 | 185 / 241 | 56 / 314 | 17.83% | 49.33% | +4.25 | 183–193 |
| Pinned random | 50 | 30 / 241 | 211 / 469 | 44.99% | 60.00% | +5.90 | — |
| Pinned random | 125 | 67 / 241 | 174 / 432 | 40.28% | 53.60% | +6.75 | — |
| Pinned random | 250 | 122 / 241 | 119 / 377 | 31.56% | 48.80% | +1.50 | — |
| Pinned random | 375 | 180 / 241 | 61 / 319 | 19.12% | 48.00% | -0.75 | — |
| Execute all | 500 | 241 / 241 | 0 / 258 | 0.00% | 48.20% | 0.00 | — |

The missing-report row is selected by every router-risk and patch-size budget,
by `touches_tests_first` only at budget 375, by no pinned-random budget, and by
`execute_all`. Whenever selected, it consumes one simulated label-reveal slot,
remains quarantined, and is never replaced. `execute_all` therefore records 500
proxy units, 499 hosted labels, and one quarantine—not 500 new executions.

At budget 50, the exact repository-stratified three-category reference has
expected hosted failures captured 24.1347298728, expected selected unknowns
0.125, 101 joint support points, and total probability one (within floating
roundoff). Every support row keeps the one unknown outside the accepted/false-
accept denominator; it is quarantine, never an imputed resolved or failed row.

## Tough interpretation

This result validates the study machinery and demonstrates that retrospective
label-reveal allocation differs materially across policies for this frame. It
does **not** validate the current router as a superior policy or measure real
execution cost. The simple patch-size baseline captures more hosted
failures than the router-risk baseline at every matched nonterminal budget and
beats the uniform-random expectation by 7.9 to 19.75 failures. Router risk is
below random expectation at budgets 50 and 250, and its cutoff behavior is
materially tie-sensitive at smaller budgets.

The explicitly post-hoc finite-frame discrimination diagnostic helps explain
that result. With hosted failure as the positive class, overall ROC AUC is
0.53249 for router risk, 0.60119 for changed lines, 0.62697 for changed files,
and 0.52691 for the test-touch indicator. Repository-macro AUC over the ten
repositories containing both outcome classes is respectively 0.60861, 0.61823,
0.64253, and 0.55786. Router risk is also coarse: 198 labeled candidates share
the score represented by 0.30 and 139 share the score represented by 0.46.
These are post-label, finite-frame descriptions with no calibration or
confidence-interval claim and were never policy inputs.

That negative result sharpens the research program: the current risk score is
an inspectable data-collection baseline, not the proposed learned sequential
policy. A publishable headline still requires prospective nonzero action
propensities, independently reproduced execution, blinded adjudication,
calibration on disjoint repositories/time, explicit oracle-validity modeling,
and downstream rollout/SFT/RL evaluation. The earlier canonical
dataset/base-commit provenance blocker is now closed by the exact parquet/S3
cross-check above; that strengthens identity, not outcome validity.
Because there is one candidate per task, candidate-risk signals are confounded
with task and repository difficulty; this is not a within-task rollout-ranking
experiment.
