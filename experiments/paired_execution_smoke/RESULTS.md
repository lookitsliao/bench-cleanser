# Paired Linux-container SymPy feasibility results

## Observed result

All three repeats agreed within every role, and the role pattern matched the
earlier container-free macOS/arm64 smoke:

| Role | Linux container, each repeat | Target | Earlier container-free arm |
|---|---:|---|---:|
| Base + oracle test patch | 38 passed, 1 failed | failed | 38 passed, 1 failed |
| GPT-5 candidate | 39 passed | passed | 39 passed |
| Kimi K2 candidate | 38 passed, 1 failed | failed | 38 passed, 1 failed |
| Claude 4 Sonnet candidate | 39 passed | passed | 39 passed |
| Canonical gold sanity control | 39 passed | passed | 39 passed |

This supplies a one-task paired feasibility observation: for these already
prepared workspaces and this targeted test file, moving from the recorded
container-free macOS substrate to the recorded local Linux container did not
change any observed role result across three repeats. It does not establish
general substrate equivalence, show that Docker is more accurate, or validate
candidate correctness beyond this execution measurement.

## What was paired

- Task: `sympy__sympy-15976` at base commit
  `701441853569d370506514083b995d11f9a130bd`.
- Same five prepared source workspaces used by the independent smoke, mounted
  read-only; preparation was not repeated in the container arm.
- Same targeted file, `sympy/printing/tests/test_mathml.py`, with 39 executed
  tests: one FAIL_TO_PASS target, 37 PASS_TO_PASS tests, and one incidental
  unscored test.
- Same normalized Python/SymPy test command.
- Three fresh `docker run --rm` acquisitions for each role.

The acquisition window recorded second-resolution timestamps from
`2026-07-13T13:18:51Z` through `2026-07-13T13:19:09Z`. Summed recorded
intervals are 18 seconds; this coarse figure is not a precise runtime or cost
measurement.

## Substrate receipts

The locally constructed image is Linux/arm64 and 469,094,980 bytes, with image
ID and repo digest both bound to
`sha256:131da93f75269d9db60c3e1e7e5f412d6b05445d6b92e55b134d202fd83d074e`.
It combines a locally available `node:18` base with a fixed Linux/arm64 CPython
3.9.25 archive. The Python archive is 41,536,085 bytes with SHA-256
`6112d46355857680b81849764a6cf9f38cc4cd0d1cf29d432bc12fe5aeedf9d0`.

`mpmath==1.3.0` was supplied as a read-only bind mount. The archive preserves
the distribution metadata plus a path/size/digest list for the exact 174-file,
3,603,837-byte mounted tree observed after execution. That post-execution
receipt is useful provenance, but it cannot prove the dependency tree was
unchanged between setup and all 15 runs.

## Claim boundary

The strongest defensible conclusion is infrastructure-level: a constrained,
locally built Linux container can execute this prepared legacy SymPy task and
reproduce the targeted pattern seen in the container-free arm. The result is
deliberately excluded from prospective pilot inference.

It remains one manually selected, unblinded task; uses no official SWE-bench
image; reuses rather than independently prepares source trees; runs one test
file rather than the official full harness; lacks remote Linux CI and
cross-architecture replication; uses a Dockerfile whose base reference is a
tag; and has no runner timeout. It supplies no population, routing, policy,
training, rollout, H1-H6, or semantic-truth claim.
