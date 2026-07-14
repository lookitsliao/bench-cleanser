# Evidence availability

**Status:** local development inventory, not a release manifest.

This table separates checked-in summaries from the bytes needed to audit or
rerun them. A `/private/tmp` pathname is not a durable locator. Public source
URLs identify upstream inputs but do not preserve derived reports, execution
logs, environments, or adjudications. Until the objects below are committed to
a clean release or deposited under a durable DOI, the associated results must
be described as local development evidence.

| Evidence object | Bytes | SHA-256 | Code identity | Durable locator | Independently reproducible from a clone? |
|---|---:|---|---|---|---|
| Synthetic seed local report | not recorded | `d6134fa3a3840226119c771c1f4f3e192430730872ef2bef4641702cc95f57dd` | `experiments/seed_study/run_seed_study.py` | none | No; raw acquisitions and machine-local report are not preserved. |
| Synthetic seed container report | not recorded | `123fc9a31678a8215bb623eeb2c880c7e109abf6b0fe26eac0e97cbbe8efdabd` | `experiments/seed_study/run_seed_study.py` | none | No; image digest is recorded, but raw acquisitions/report are not preserved. |
| Real-agent cohort manifest | 5,397 | `c1e7e57269e0989fc9b05c94a502d06b3628156651e88d58fa18a951d12b98e5` | `experiments/real_agent_pilot/run_pilot.py` | checked into this dirty working tree; no signed tag/DOI | Partly; the manifest retains public S3 inputs, but no independent execution was performed. |
| Hosted 500-row report v3 | 12,628,326 | `ed04d503f4475dc370e009abe25286a99ab2f6a7868e6249fbc86b22713da32f` | `experiments/hosted_outcome_study/run_study.py` | local temporary bundle only | No; upstream identities are recorded, but the derived report/acquisition bundle is not durably published. |
| Matched-rollout acquisition manifest | 289,653 | `f79578fb9860ef0eb4bf02a62691e98c4002a5de96b8dda9ab2d3616f082b574` | `experiments/matched_rollout_study/run_study.py` | local temporary bundle only | No; public inputs can be reacquired, but the audited manifest is not durably published. |
| Matched-rollout feature freeze | 301,852 | `b01e8c9408acce759b75bd299f4323a37398e417e80a97ef52f09b8a14abc01c` | `experiments/matched_rollout_study/run_study.py` | local temporary bundle only | No; exact bytes are absent from a clone. |
| Matched-rollout report | 871,115 | `377198204b1423e9e17415547a1ea35479b0dc1a8678ee31b1f53ee1539cae76` | `experiments/matched_rollout_study/run_study.py` | local temporary bundle only | No; exact bytes are absent from a clone. |
| SymPy targeted feasibility bundle | 7,652 | `fe563f4f7b7dda0168dfdd3e9bde7d91f0c6363b36a0c825dc2e6da343f12553` | `experiments/independent_execution_smoke/run_smoke.py` | local temporary bundle only | The checked-in manifest can validate supplied bytes, but the bundle, source-retrieval receipt, and full environment are not durably published. |
| Paired Linux-container SymPy feasibility bundle | 18,299 | `90729da3d543fb3ac75405bb782d056a90ae6b1bbb9219a7016404f489aaea3c` | `experiments/paired_execution_smoke/verify_evidence.py` | local temporary bundle only | The verifier can authenticate supplied bytes and recompute 15 targeted outcomes. The run reused prepared source trees in a locally constructed, non-official image and has no runner timeout, cross-architecture replication, or population/routing claim. |
| Container-free Sphinx feasibility bundle | 27,754 | `a6fef4316b9e60759b35eb9ecad27a1a162c80c9265e6746a4eb29041fba3a5b` | `experiments/sphinx_execution_smoke/verify_evidence.py` | local temporary bundle only | The verifier can authenticate supplied bytes and recompute 15 observations. Proxy-sensitive phases deviate from the official harness, public-link checks are mutable, and all candidates share the gold functional change, so the task supplies no candidate discrimination or routing evidence. |
| Primary-arXiv metadata lock | 45,656 | `36120b5f1a685cf8b1c74d952ad02629da97f3fe53e67558de85ec6c617cf5e2` | `scripts/lock_literature.py` | checked into this dirty working tree; no signed tag/DOI | Metadata validation for all 70 entries is reproducible offline; upstream refresh requires network access. |
| Partial claim ledger | 33,608 | `28c3f70de03fc56d0b6b8d71d472e7bb683ec6e4dada38e81cf6752f3f6a921d` | `scripts/verify_claim_ledger.py` | checked into this dirty working tree; exact PDFs have no public artifact locator | Ledger validation covers 26 exact PDFs and 35 page-bound claims. All 26 listed PDF hashes were reverified during reviews through 2026-07-14, but a clone cannot rehash absent PDF bytes and no claim has human confirmation. |

Working-tree package/SBOM/license evidence is intentionally absent from this
table. Temporary local reports are neither bound to a clean candidate commit
nor durably available, even when generated from the same source bytes. The
bundle must be rebuilt from the final clean commit, then preserved together
with the signed release dossier.

## Publication gate

A public evidence manifest must replace every `none` or local-only locator with
an immutable release asset or DOI, record byte count and digest, bind the exact
code/commit/environment, and state redistribution/privacy status. Missing,
failed, unknown, abstained, and excluded cases remain part of that manifest.
