# Supply-chain release gate

The public-alpha gate builds the exact source tree, installs its wheel in a
new Python 3.11 virtual environment, and emits five machine-readable records:

- `bench-cleanser.cdx.json`: reproducible-serialization CycloneDX 1.6 SBOM;
- `pip-install-report.json`: pip's complete resolved-install report, including
  archive identities and target runtime/platform metadata;
- `python-license-inventory.json`: installed distribution metadata and the
  available license text captured by `pip-licenses`;
- `license-policy-report.json`: allow/deny/review decisions plus exact
  SBOM/inventory coverage checks and input hashes;
- `artifact-audit-report.json`: hashes and member-level proprietary import,
  forbidden dependency, archive-confinement, and credential-scan results for
  the wheel and source distribution.

CI creates and validates these files in its isolated runner workspace and also
derives `environment-lock.json` by checking the pip-report runtime/platform and
complete package set against the actual target interpreter. It prints the
output digests and uploads the complete distribution directory under a
source-commit-and-run-attempt-scoped artifact name. The official upload action
is pinned to its immutable v4.6.2 commit; missing files fail the job, and
retention is 90 days. Separate Python 3.11/3.12 jobs automatically capture the
canonical test, coverage, lint, and type records and logs; a final job binds
both matrix inventories and the release artifacts in Linux CI evidence schema
`bench-cleanser-linux-ci-evidence-0.2.0`.

This does not publish a package, create a GitHub release, authenticate the run
cryptographically, or preserve evidence durably. A release maintainer must
export and preserve the evidence with the exact candidate before retention
expires and complete the human checks below.

## Audited scope

The target environment contains the built wheel's default dependencies plus
the public `[structural]` extra. Release tools live in the separate build
environment and therefore do not contaminate the product SBOM. The inventory
includes `pip` and `setuptools` because CycloneDX observes them in the target
environment too; the gate requires exact name/version agreement between both
machine records.

Docent is an external integration, not a public-alpha dependency. As of July
12, 2026, `docent-python` selects a large provider/telemetry closure whose
current `inspect-ai` line requires `click<8.2.2`, while the newest
`huggingface-hub` selected by the default data stack requires `click>=8.4.2`.
An unconstrained install therefore backtracks across many releases. Rather
than bless one incidental transitive resolution, package metadata omits that
extra. JSON, JSONL, JSON-directory, and Hugging Face trajectory ingestion are
unchanged. Docent users may install and constrain a compatible SDK explicitly;
that environment needs its own SBOM and license review.

This is an environment snapshot, not a universal lock. Direct runtime lower
bounds can resolve to different transitive versions on another date, Python
version, or platform. The CI resolution is inventoried and re-evaluated, and
package installation is restricted to binary distributions, but build/dev
tooling and dependencies are still broadly resolved from the network. Fully
reproducible deployment requires preserving the emitted records and adding an
environment-specific hash-locked constraints file and runner/toolchain image
identity.

## License policy

[`license-policy.toml`](../supply-chain/license-policy.toml) has three outcomes:

- **allow**: metadata reports only a narrowly listed permissive, public-domain,
  PSF, or MPL-2.0 family and a non-empty installed license file was captured;
- **deny**: strong/network copyleft, source-available/commercial terms, a
  retired/proprietary package, or an out-of-scope integration is present;
- **review**: metadata is absent, ambiguous beyond the documented aliases,
  belongs to a review family, lacks a captured license file, or contains an
  unrecognized expression.

`deny` and `review` both fail CI. Compound expressions are conservative: every
reported leaf must be allowed, even when metadata joins alternatives with
`OR`. Package-name normalization follows the PEP 503 convention. Adding an
alias or allow decision requires reviewing the captured upstream license text,
recording the rationale in the change, and rerunning the exact wheel gate.

The automated result is **not legal advice or completed legal review**.
Distribution metadata can be inaccurate, a wheel can bundle native material
not described as a Python distribution, and a single Linux/Python resolution
does not cover every platform or optional external integration. The policy
therefore hard-codes `legal_review_complete = false`, and the auditor rejects
a policy that tries to turn that field into an automated attestation.

## Artifact and credential policy

The artifact gate reads wheel and sdist members without trusting archive
paths. Absolute/traversing paths, links/special members, excessive member or
archive sizes, retired provider imports, and forbidden dependency declarations
fail. It applies high-confidence credential patterns without ever serializing
the matched value, then independently runs the maintained `detect-secrets`
scanner offline (`--no-verify`) over confined copies of all regular members.
The keyword-only plugin is disabled because shipped configuration necessarily
names credential environment variables without containing their values; the
built-in non-empty assignment rule still fails literal values. Any remaining
finding fails. Narrow structured recognizers cover public provenance in the
real-agent, hosted, matched, canonical-dataset, feasibility, prospective-
protocol, and literature artifacts. A finding is classified as declared
provenance only when its archive-path suffix, exact schema and field path,
40/64-character lowercase-hex shape, source line, and the scanner's hashed
identity all agree; every classification remains visible in the report. Any
unknown field or schema mismatch disables that recognizer. This is not a
file-wide/plugin-wide entropy suppression or an opaque baseline. Other
exceptions must remove or rotate the value.

No provider key is needed. Dependency downloads are the only network-dependent
part of CI. LLM, dataset, and secret-verification network calls are not made.

## Reproduce locally

Use fresh paths; the script refuses existing environments and artifact
directories so stale packages cannot make the evidence look clean:

```bash
python3.11 -m venv /tmp/bench-cleanser-release-tools
/tmp/bench-cleanser-release-tools/bin/pip install -e ".[release]"
PATH="/tmp/bench-cleanser-release-tools/bin:$PATH" \
PYTHON=/tmp/bench-cleanser-release-tools/bin/python \
scripts/run_supply_chain_gate.sh \
  /tmp/bench-cleanser-release-target \
  /tmp/bench-cleanser-release-artifacts
```

The command succeeds only when the build/Twine check, fresh wheel install,
`pip check`, validated CycloneDX generation, license policy, SBOM/inventory
agreement, archive scan, and offline secret scan all pass.

## Required human release check

Before a public upload, a named maintainer should inspect the exact candidate's
inventory and captured texts, confirm every dependency is necessary, assess
native/vendored components and notices, review the source/wheel hashes, and
record an approval linked to the candidate commit. For a stable or commercial
release, obtain qualified license review and generate platform-specific SBOMs.
Automation passing alone does not close those obligations.
