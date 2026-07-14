# Security policy

Bench Cleanser processes repository identifiers, commits, diffs, test names,
trajectories, and model-generated text.  Treat all of them as untrusted input.

## Supported versions

There is not yet a supported stable release.  Security fixes currently target
the latest `master` revision while the project is in engineering alpha.

## Reporting a vulnerability

Please use GitHub's private security-advisory flow for this repository.  Do not
open a public issue containing credentials, exploitable task payloads, private
repository content, or a working path-escape/repository-execution proof.

Include the affected revision, platform/Python version, minimal reproduction,
impact, and whether any model provider received unintended content.  A report
will be acknowledged before a public fix or disclosure timeline is proposed.

## Trust boundaries

- Repository and output paths must remain beneath their configured cache/output
  roots.  Do not weaken path and full-commit validation to accommodate malformed
  datasets.
- Repository visitation is read-only analysis, not a sandbox for executing
  repository code. The packaged local acquisition/coordinator primitives are
  explicitly unsafe and non-isolated when used directly. The pinned-container
  request builder encodes a digest-bound, network-disabled, resource-bounded
  local Docker profile, but cannot attest the Docker CLI, daemon, kernel, image,
  workspace, image-declared volumes, or descendant lifetime. Treat those as
  trusted inputs and do not present the resulting observation as authoritative.
- Prompts may contain issue text, diffs, source snippets, tests, and trajectory
  observations.  Using a hosted LLM provider can therefore disclose that data to
  the provider.  Do not process private code without an approved data-processing
  arrangement.
- API keys belong in environment variables or a secret manager.  They must not
  be placed in YAML files, manifests, logs, cache keys, reports, examples, or bug
  reports.  Rotate any credential pasted into chat, a terminal transcript, or a
  public issue.
- Cached model responses and per-instance reports can contain source code and
  model behavior.  Protect the output/cache directories as research data and
  define a retention policy before processing sensitive repositories.

## Out of scope for current claims

The current pipeline does not claim that a test suite, container image, generated
test, LLM judgment, or gold patch is an infallible correctness oracle.  Verifier
errors must be represented separately from candidate failures; see
`docs/RESEARCH_PROGRAM.md`.
