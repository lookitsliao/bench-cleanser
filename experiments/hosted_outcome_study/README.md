# Hosted-outcome finite-frame development study

This experiment evaluates simple retrospective **hosted-label-reveal allocation
proxies** over the complete public prefix frame of one SWE-bench Verified
submission:
`20250805-openhands-Qwen3-Coder-30B-A3B-Instruct`.

The estimand is deliberately narrow: allocation performance for predicting
this submission's hosted SWE-bench harness `resolved` label. The label is not
semantic correctness, an independently reproduced result, or proof that the
test oracle is valid. The pinned submission metadata says `checked: false`,
uses one model/scaffold and one attempt, and the study supports none of H1-H6.
There is also only one candidate per task, so task difficulty and candidate
risk are confounded; this study cannot identify within-task Best-of-N rollout
selection effects.

No repository, container, or test is executed by this study. The public
`report.json` files contain outcomes from an earlier hosted run. Selecting a row
simulates spending one future execution slot by revealing that preserved label;
runtime and Docker cost are unavailable.

## Acquisition contract

The production acquisition fails closed unless the S3 delimiter listing is a
complete, non-truncated frame of exactly 500 confined instance prefixes. It
then enumerates every object using a strict paginated no-delimiter listing.
Only `patch.diff` and `report.json` are downloaded; trajectories and test-output
logs are not acquired. A missing listed-frame artifact remains an explicit
unavailable row.

Additional controls include:

- exact HTTPS host, revision, prefix, URL, and artifact-name allowlists;
- strict S3 XML token-chain, ordering, count, duplicate, and path validation;
- at most 16 workers, bounded object/total bytes, bounded timeouts, and at most
  five attempts;
- atomic whole-directory publication and exclusive publication locks;
- regular-file/no-symlink validation, exact byte counts, SHA-256 digests, and
  rejection of undeclared files;
- pinned raw metadata and official `results.json`, with byte preservation and
  digest verification. Acquisition treats the official result categories as
  opaque bytes; per-instance outcome/missingness decoding and cross-checking are
  deferred until after the pre-label freeze; and
- the canonical `princeton-nlp/SWE-bench_Verified` test parquet at revision
  `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, pinned to 2,096,679 bytes and
  SHA-256 `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`.
  The authoritative Hugging Face identity and actual immutable Git-mirror
  retrieval transport are recorded separately. Acquisition reads only a typed
  four-field projection (`instance_id`, repository, base commit, environment
  setup commit), checks its 500 IDs exactly against the S3 frame, and rejects
  malformed commits, repository drift, duplicate IDs, or cross-repository
  commit collisions. Gold patches, oracle tests, problem text, and hints never
  enter the feature interface.

Acquire the public snapshot without an LLM or API key:

```bash
python experiments/hosted_outcome_study/run_study.py acquire \
  --artifact-dir /tmp/bench-cleanser-hosted-study \
  --workers 8 --retries 3
```

The target must not already exist. This prevents a stale or partially modified
tree from being mistaken for the requested snapshot.

## Leakage boundary and policies

Analysis enforces a global phase boundary. Acquisition-manifest validation may
verify report bytes and digests, but it does not decode either official result
categories or per-instance reports. The feature builder accepts only a typed,
sanitized projection of `patch.diff` identities plus canonical task identity
(repository and full base/environment commits). Each deployable manifest binds
that identity and the dataset revision. From that projection it builds all 500
reference-free manifests, obtains the existing `ConservativeRouter` initial
`candidate_risk`, and freezes:

- the complete patch-only feature table;
- four full base-policy candidate permutations; and
- all 48 full tie-sensitivity permutations (three policies × sixteen seeds).

Every permutation record binds its policy, seed, complete ordered
instance/candidate identities, and SHA-256; the whole freeze document is also
serialized and hashed. Only after all 52 orders exist does analysis decode the
pinned official results and any `report.json`. Downstream selection validates
and consumes those frozen permutations; it never recomputes them after label
reveal. Report URLs, availability, sizes, digests, labels, and test counts are
excluded from the feature builder, predictors, and tie breaks.

The evaluated policies are:

- `accept_all` and `execute_all` endpoints;
- highest initial router risk;
- largest patch by changed lines/files;
- test-touching indicator first;
- one pinned hash-random order.

Every tie uses a seeded, domain-separated SHA-256 over pre-outcome candidate
identity. A digest collision fails closed instead of falling back to
lexicographic instance order. A fixed grid of sixteen outcome-blind tie seeds
measures cutoff sensitivity. Budgets are 10%, 25%, 50%, and 75% of the full
500-row frame. They are retrospective label-reveal units, not observed
execution costs. A selected row whose hosted report is unavailable consumes its
simulated slot and remains quarantined; the policy never backfills it.

The report includes exact finite-frame micro metrics, macro-repository metrics,
per-repository and feature subgroup slices, fixed-decision leave-one-repository-
out deletion sensitivity, exact uniform-without-replacement hypergeometric
randomization distributions, and an exact repository-stratified
three-category convolution that keeps known failures, known resolved outcomes,
and unknown quarantines distinct under the same terminal rule. A clearly
post-hoc finite-frame diagnostic reports ROC AUC and score ties only to explain
the observed policy behavior; it is not a selection input, calibration result,
or confidence interval. The study does not attach a population interval: this
is the complete finite frame of one submission, while the 12 repository
clusters are highly imbalanced.

```bash
python experiments/hosted_outcome_study/run_study.py analyze \
  --artifact-dir /tmp/bench-cleanser-hosted-study \
  --output /tmp/bench-cleanser-hosted-study-report.json
```

Tests use only local fixtures and injected network responses. They never fetch
public artifacts.

See [RESULTS.md](RESULTS.md) for the reproduced 2026-07-13 development result.
