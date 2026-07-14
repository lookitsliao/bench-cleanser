# Paired execution smoke: SymPy 15976

Status: **retrospective, post-draft, locally constructed paired-container
feasibility**.

This record changes the substrate of the earlier
`independent_execution_smoke` while reusing its five already-prepared SymPy
workspaces as read-only mounts. The base control, three published candidates,
and canonical gold sanity control were each run three times in a local
Linux/arm64 container. The same targeted 39-test file was used in both arms.

This is not prospective evidence, an official SWE-bench image or harness run,
a routing evaluation, a benchmark estimate, or evidence for H1-H6. Execution
remains a fallible measurement rather than semantic ground truth.

## Bound substrate

- Constructed image ID:
  `sha256:131da93f75269d9db60c3e1e7e5f412d6b05445d6b92e55b134d202fd83d074e`.
- Locally observed base image ID:
  `sha256:c6ae79e38498325db67193d391e6ec1d224d96c693a8a4d943498556716d3783`.
- Dockerfile SHA-256:
  `ab835600739006acdf122a11a246561499f2eca13e02a5bbc86d46f7c23296a9`.
- Platform: Linux/arm64 under Docker Engine 28.1.1 and Docker Desktop 4.41.2.
- CPython: python-build-standalone 3.9.25; archive SHA-256
  `6112d46355857680b81849764a6cf9f38cc4cd0d1cf29d432bc12fe5aeedf9d0`.
- Dependency mount: `mpmath==1.3.0`, mounted read-only. Its package metadata
  and 174-file mounted-tree receipt are preserved, but were collected after
  execution and are not a before-and-after attestation.

The Dockerfile says `FROM node:18`, not a digest-pinned `FROM`. The manifest
therefore binds the base image observed during local setup separately and
explicitly records that no contemporaneous base-image inspect receipt was
preserved in the evidence archive.

## Execution contract

The exact runner is content-bound in the external archive. Each run used the
constructed image by ID with no pull or network, a read-only root filesystem,
all capabilities dropped, `no-new-privileges`, UID/GID 65534, read-only source
and dependency mounts, a bounded tmpfs, 128 PIDs, 2 GiB memory, and 2 CPUs.
The command was:

```text
/opt/python/bin/python -W ignore::UserWarning -W ignore::SyntaxWarning \
  bin/test -C --verbose sympy/printing/tests/test_mathml.py
```

The runner did not impose a wall-clock timeout. Random and hash-randomization
seeds varied across repeats.

## Evidence

The compact external artifact is identified only by content:

```text
filename  bench-cleanser-paired-sympy-15976-evidence.tar.gz
bytes     18299
sha256    90729da3d543fb3ac75405bb782d056a90ae6b1bbb9219a7016404f489aaea3c
```

It contains the 15 raw logs, acquisition table, image/Docker/host receipts,
exact Dockerfile and runner, and the post-execution mpmath receipts. Mutable
scratch paths in the raw runner and build receipt remain covered evidence, but
none appears in the canonical manifest.

Validate the checked-in claim and its relationship to the earlier independent
smoke:

```bash
python3 experiments/paired_execution_smoke/verify_evidence.py
```

Also authenticate the external archive and recompute all 15 summaries from raw
logs:

```bash
python3 experiments/paired_execution_smoke/verify_evidence.py \
  --bundle /path/to/bench-cleanser-paired-sympy-15976-evidence.tar.gz
```

The verifier rejects duplicate or non-finite JSON, unknown manifest fields,
identity drift, aggregate drift, unsafe or duplicate archive members, links or
special files, member tampering, malformed acquisition rows, ambiguous test
summaries, and return-code/result disagreement.
