# SymPy 15976 feasibility-execution results

## Result

All three repeats agreed within each role:

| Role | Targeted result per repeat | Target test | Hosted prior measurement |
|---|---:|---|---|
| Base + oracle test patch | 38 passed, 1 failed | failed | n/a |
| GPT-5 candidate | 39 passed | passed | resolved |
| Kimi K2 candidate | 38 passed, 1 failed | failed | unresolved |
| Claude 4 Sonnet candidate | 39 passed | passed | resolved |
| Canonical gold sanity control | 39 passed | passed | n/a |

The candidate pattern was therefore resolved / unresolved / resolved in both
the independent targeted run and the already-visible hosted reports. This is
one-task, non-blinded retrospective corroboration only. Hosted labels are
stored separately as prior measurements and never impute an executed outcome.

## Bound execution

- Task: `sympy__sympy-15976`, SymPy 1.4.
- Base commit: `701441853569d370506514083b995d11f9a130bd`.
- Base tree: `d1b60b750de1bab2c5a69738e93fcd7110423117`.
- Environment commit: `73b3f90093754c5ed1561bd885242330e3583004`.
- Canonical all-column row: 15,708 canonical JSON bytes, SHA-256
  `080f2dad36f0177744524af22b615564da264c05e660d6fc0a87f5b41f9dfebf`.
- Oracle test patch: 8,407 bytes, SHA-256
  `a63da41ccb4b4bb9ece78bd8350dc3dd9702ba18c6f1c09a540552296df56ac7`.
- Official scoring lists: one FAIL_TO_PASS target and 37 PASS_TO_PASS tests.
  `test_print_random_symbol` was an additional unscored test in the targeted
  file, yielding 39 executed tests.
- Harness source: `SWE-bench/SWE-bench` at
  `f7bbbb2ccdf479001d6467c9e34af59e44a840f9`; the three relevant harness-file
  digests are fixed in the manifest.

The preparation order reproduced the official reset behavior: apply the
candidate (or gold, or no patch for base), reset every file touched by the
oracle test patch to the base commit, then apply the exact oracle test patch.
That reset matters here because the Kimi and Claude candidates modified
`sympy/printing/tests/test_mathml.py`; directly applying the oracle patch to
their modified test file would conflict.

The normalized argv was:

```text
{runtime_root}/bin/python -W ignore::UserWarning -W ignore::SyntaxWarning bin/test -C --verbose sympy/printing/tests/test_mathml.py
```

The runner used `shell=false`, a 120-second timeout, and the
`minimal-allowlist-v1` environment policy. The raw receipts retain the exact
absolute argv and workspace paths. The manifest records a portable argv
template and logical path suffixes; environment key names were captured, but
their values were not.

## Substrate and cost

The substrate was container-free macOS 26.5.1 (build 25F80), Darwin 25.5.0,
arm64, with CPython 3.9.25 from a fixed python-build-standalone archive. The
archive, runtime binary, and complete installed dependency list are bound in
the manifest.

The 15 acquisitions span timestamps from
`2026-07-13T05:22:44.699265Z` through `2026-07-13T05:28:32.539823Z`. Their sum
of measured per-run wall time is 12.503239334968384 seconds, and their recorded
artifact storage cost is 60,311 bytes. Some runs overlapped, so the wall-time
sum is not end-to-end elapsed study time. The compressed 30-file evidence
bundle is 7,652 bytes.

## Protocol timing and limitations

This was a `post_draft_pre_freeze_feasibility_execution`. Two old draft
artifacts are bound by SHA-256 in the manifest, but their byte counts were not
recorded and their local mtimes are not authenticated identity evidence. The
bench-cleanser commit/dirty-tree identity at execution time, base-source
retrieval URL, preparation command transcript, prepared-tree digest, and
environment values were also not recorded. None is reconstructed after the
fact.

Consequently, this record is useful as a durable infrastructure bring-up and
as motivation for a future cleanly frozen prospective pilot. It is not itself
prospective evidence, a full-harness reproduction, semantic truth, a routing
evaluation, or evidence for H1-H6.
