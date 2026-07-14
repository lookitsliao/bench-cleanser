# Independent execution smoke: Sphinx 8475

Status: **post-draft/pre-freeze retrospective feasibility execution**.

This directory preserves a second, independently reconstructed container-free
execution bring-up for `sphinx-doc__sphinx-8475`. It complements the SymPy
smoke with a network-sensitive repository and the exact SWE-bench Verified
F2P/P2P node list. It is not a prospective pilot, official SWE-bench harness
run, routing result, benchmark estimate, or semantic-truth oracle.

Five roles were observed three times each: base plus the oracle test patch,
three published candidate patches, and the canonical gold patch. All 17 P2P
tests passed in every observation. The base failed the F2P target in all three
repeats; every candidate and gold passed it in all three repeats.

## Files

- `evidence-manifest.json` is the path-independent claim and identity record.
- `verify_evidence.py` strictly validates the checked-in claim and optionally
  recomputes it from the external raw bundle.
- `RESULTS.md` reports the outcome and its limits.

The external raw bundle is content addressed as:

```text
bench-cleanser-independent-sphinx-8475-v2-evidence.tar.gz
bytes   27754
sha256  a6fef4316b9e60759b35eb9ecad27a1a162c80c9265e6746a4eb29041fba3a5b
```

It contains 15 observation records, 30 phase records, complete stdout/stderr,
30 JUnit files, the exact environment inventory, and the acquisition runner.
No mutable `/private/tmp` path is a canonical artifact identity.

## Verification

Validate the checked-in claim:

```bash
python experiments/sphinx_execution_smoke/verify_evidence.py
```

Also verify the exact external archive and recompute every result from JUnit:

```bash
python experiments/sphinx_execution_smoke/verify_evidence.py \
  --bundle /path/to/bench-cleanser-independent-sphinx-8475-v2-evidence.tar.gz
```

The verifier rejects duplicate or non-finite JSON, identity drift, unsafe or
unexpected tar members, stream/JUnit tampering, request drift, missing repeats,
source-tree drift, proxy-policy drift, and outcomes inconsistent with the raw
JUnit cases.

## Harness deviation

The exact 18 scored node IDs were split into two pytest processes per
observation:

1. three public-link P2P tests used managed external egress; and
2. fourteen localhost P2P tests plus the F2P target excluded localhost from
   that proxy.

Without the split, the managed proxy intercepts `localhost`; with localhost
excluded for the public-link phase, public checks can hang. The phase split is
therefore explicit evidence about this reconstructed substrate, not something
presented as official-harness equivalence.

## Claim boundary

The smoke establishes only that this exact macOS-arm64, Python 3.9.25,
container-free reconstruction could reproduce a base-fails/gold-passes sanity
check and execute the three published patches repeatedly. It supplies no
routing evidence and no evidence for H1-H6. All three candidates contain the
same functional two-line change as gold, so this task provides no candidate or
model discrimination. See the manifest for the complete fixed limitations.
