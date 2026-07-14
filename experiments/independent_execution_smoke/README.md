# Independent execution smoke: SymPy 15976

Status: **post-draft/pre-freeze feasibility execution**.

This directory preserves one container-free execution bring-up for
`sympy__sympy-15976`. It is a source-locked infrastructure smoke, not a
prospective pilot, benchmark estimate, routing result, or semantic-truth
oracle. Draft protocol bytes existed before acquisition, but they had not been
bound to a clean commit or registration freeze. Candidate patches and hosted
labels were accessible before task selection and execution.

The smoke exercised five roles three times each: base plus the oracle test
patch, three published candidate patches, and the canonical gold patch as a
sanity control. Each run targeted
`sympy/printing/tests/test_mathml.py`; it did not run the complete official
SWE-bench harness or full SymPy suite.

## Files

- `evidence-manifest.json` is the path-independent claim and identity record.
- `run_smoke.py` strictly validates the manifest and optionally the external
  raw-evidence bundle. It does not download inputs or execute SymPy.
- `RESULTS.md` reports the observed outcomes and their limits.

The external raw bundle is content addressed as:

```text
bench-cleanser-independent-sympy-15976-evidence.tar.gz
bytes   7652
sha256  fe563f4f7b7dda0168dfdd3e9bde7d91f0c6363b36a0c825dc2e6da343f12553
```

It contains 15 observation records and 15 bounded execution artifacts. The
manifest records relative member names only. Absolute scratch paths remain in
the original raw receipts and are covered by their digests, but no mutable
`/private/tmp` location is a canonical artifact identity.

## Verification

Validate the checked-in claim:

```bash
python experiments/independent_execution_smoke/run_smoke.py
```

Also validate the exact external archive and recompute every test summary from
raw stdout:

```bash
python experiments/independent_execution_smoke/run_smoke.py \
  --bundle /path/to/bench-cleanser-independent-sympy-15976-evidence.tar.gz
```

The verifier rejects duplicate or unknown manifest fields, non-finite JSON,
identity drift, missing repeats, hosted-label substitution, unsafe archive
members, raw-file tampering, stream-digest/count drift, and outcomes that do
not match the independently captured logs.

## Claim boundary

The result establishes only that this exact macOS-arm64, Python 3.9,
container-free targeted runner could reproduce a base-fails/gold-passes sanity
check and the same one-task candidate pattern previously reported by hosted
evaluation. It supplies no routing evidence, no population estimate, and no
evidence for H1-H6. See `evidence-manifest.json` for the complete fixed
limitations list.
