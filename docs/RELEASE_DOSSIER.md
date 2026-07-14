# Release dossier

`scripts/build_release_dossier.py` builds and verifies the evidence bundle for
the `public-engineering-alpha` release profile. It is a release gate, not a
release command: it never uploads artifacts, creates a Git tag, or turns an
automated policy result into a legal opinion.

The gate is deliberately fail-closed. A missing, malformed, stale, unsigned,
unbound, or failing input either blocks readiness or makes the invocation
invalid. A dossier may say `release_ready: true` only when every readiness
check passes.

## What the dossier proves

The generator directly inspects and cross-links:

- the current Git commit and tree, full porcelain status, `git diff --check`,
  exact release tag target and type, and `git verify-tag` result;
- version parity among `pyproject.toml`, `bench_cleanser.__version__`, the
  changelog release heading, the README citation, wheel metadata, sdist
  metadata, and the exact `VERSION` or `vVERSION` tag;
- wheel `RECORD`, installable topology, metadata, entry points, license, and
  package bytes against `pyproject.toml` and tracked `HEAD` blobs;
- the complete sdist source manifest and every source byte against the
  committed Hatch packaging projection;
- wheel/sdist hashes recorded by the artifact audit and Linux CI record;
- SBOM, license inventory, license-policy report, and policy identities;
- commit/tree-bound test, coverage, lint, and type evidence plus each exact
  log digest;
- Linux CI, resolved-environment, literature-lock, and study-code identities;
- a canonical human approval attestation whose exact bytes are named by a
  cryptographically verified annotated Git tag.

The output includes every input identity and a
`release_subjects_sha256`. That digest is the SHA-256 of canonical JSON
containing the source commit/tree and the sorted list of release-subject byte
identities. The human attestation binds this digest; the signed tag binds the
attestation digest.

The dossier does **not** query GitHub, Sigstore, a transparency log, PyPI, or
arXiv. It verifies the supplied local records and their internal bindings.
Authenticity ultimately rests on the verified Git tag and the configured
local signing trust. It also does not establish scientific validity, legal
advice, or empirical support for the router's research claims.

## Invocation

Build a new dossier at a path that does not already exist:

```text
python scripts/build_release_dossier.py \
  --repo-root . \
  --wheel /path/to/bench_cleanser-VERSION-py3-none-any.whl \
  --sdist /path/to/bench_cleanser-VERSION.tar.gz \
  --artifact-report /path/to/artifact-report.json \
  --sbom /path/to/sbom.cdx.json \
  --license-inventory /path/to/license-inventory.json \
  --license-report /path/to/license-report.json \
  --test-evidence /path/to/test.json \
  --coverage-evidence /path/to/coverage.json \
  --lint-evidence /path/to/lint.json \
  --type-evidence /path/to/type.json \
  --linux-ci-evidence /path/to/linux-ci.json \
  --literature-lock docs/literature.lock.json \
  --literature-claims docs/literature.claims.json \
  --environment-lock /path/to/environment-lock.json \
  --study-artifact real-agent=/path/to/real-agent-study.json \
  --attestation /path/to/release-attestation.json \
  --output /path/to/release-dossier.json
```

`--study-artifact NAME=PATH` is repeatable. At least one study is required for
readiness. Omit `--attestation` only during the preliminary pass described
below.

To verify a previously written dossier, replace `--output` with:

```text
--check /path/to/release-dossier.json
```

Check mode rebuilds the expected dossier from the current repository and all
current inputs. It rejects non-canonical bytes and any semantic or identity
drift.

Exit codes are part of the interface:

- `0`: the dossier is valid and `release_ready` is true;
- `1`: the dossier was built or matched successfully but has one or more
  explicit blockers;
- `2`: an input, archive, attestation, output, or existing dossier is malformed,
  unsafe, stale, non-canonical, unreadable, or otherwise invalid.

Output creation is exclusive; the builder will not overwrite an existing
dossier. CLI output must be outside the repository. This prevents writing the
dossier from invalidating the clean-worktree fact that the dossier records.

## Input contracts

All JSON is UTF-8, rejects duplicate object keys, and is bounded in size.
Fields described as exact admit no missing or additional keys. SHA-256 values
are 64 lowercase hexadecimal characters. Git object IDs may use 40 or 64
lowercase hexadecimal characters. Times use `YYYY-MM-DDTHH:MM:SSZ`.

### Repository and project state

`--repo-root` must resolve to the exact Git top-level directory. Readiness
requires:

- no tracked or untracked porcelain status entries;
- a passing `git diff --check`;
- one exact `VERSION` or `vVERSION` tag at `HEAD`;
- an annotated tag object, not a lightweight tag;
- a tag target equal to `HEAD` and a successful `git verify-tag`;
- project name `bench-cleanser` and identical version values in project
  metadata, package metadata, README citation, wheel, and sdist;
- semantic `Requires-Python` parity between `pyproject.toml`, wheel metadata,
  and sdist metadata;
- a dated `## [VERSION] - YYYY-MM-DD` or equivalent dash-form changelog
  heading, with no Unreleased heading presenting the same version as a
  candidate.

Every packaged source and study-code byte is independently hashed as a Git
blob and compared with the object named by `HEAD:path`. This rejects ignored or
otherwise untracked files even though ordinary Git status would omit them. The
public builder samples the full Git identity again after all reads and rejects
concurrent source, tag, or status changes.

### Wheel and sdist

The wheel filename and dist-info root must be canonical
`bench_cleanser-VERSION-py3-none-any.whl` and
`bench_cleanser-VERSION.dist-info`. The wheel must be an unencrypted, confined
ZIP archive with no duplicate or symlink members. Its only roots are
`bench_cleanser/` and that dist-info directory; `.data`, `.pth`, foreign
packages, and other installable payloads are rejected.

The dist-info member set is exact: `METADATA`, `WHEEL`, `licenses/LICENSE`,
`RECORD`, and `entry_points.txt` when project scripts exist. `WHEEL` must claim
pure Python and only `py3-none-any`; license bytes must equal the tracked
repository license; console scripts and runtime/optional dependency declarations must
match `pyproject.toml` as full PEP 508 requirement contracts, including extras,
version specifiers, URLs, and runtime markers. `Requires-Python` must match the
project's normalized specifier. Every `RECORD` row is checked against the
actual member SHA-256 and byte count, and the record must enumerate the exact
archive member set. Every file under `bench_cleanser/` must equal its tracked
`HEAD` blob; empty tracked source files are valid.

The sdist must use the exact filename and root
`bench_cleanser-VERSION.tar.gz` / `bench_cleanser-VERSION`, and contain only
confined directories or regular files. `PKG-INFO` is the sole generated source
member and must have the same digest as wheel `METADATA`. Every other member
must equal a tracked `HEAD` blob. The member set must equal the complete
committed Hatch source projection, dynamically derived from `git ls-tree` and
the explicit build exclusions. In particular, `scripts/codex/**`, `/tmp`, and
`copilot-codex-claude-bootstrap.sh` are excluded, while
`supply-chain/license-policy.toml`, this generator, and this document are
required once committed.

Both archive readers enforce compressed-file, member-count, per-member, and
total-uncompressed-byte limits.

### Artifact audit report

The top-level object has exactly:

```json
{
  "artifacts": [],
  "automation_result": "pass",
  "custom_findings": [],
  "detect_secrets": {},
  "policy_sha256": "<sha256>"
}
```

Each `artifacts` item has exactly `name`, `sha256`, `members`, and
`uncompressed_regular_bytes`. There must be exactly one item for the supplied
wheel filename and one for the supplied sdist filename, with their actual
digests. Counts are positive integers.

`detect_secrets` has exactly `version`, `network_verification`, `findings`, and
`declared_provenance_hashes`. Readiness requires `automation_result: "pass"`,
no custom findings, and no secret findings. The policy digest is cross-checked
against both the license report and the actual tracked bytes of
`supply-chain/license-policy.toml`; two mutually consistent reports cannot
substitute a different policy.

### CycloneDX SBOM

The SBOM is a JSON object with:

- `bomFormat: "CycloneDX"`;
- `specVersion: "1.6"`;
- an integer `version`;
- `metadata.component.name` and `.version` matching the project;
- non-empty `components` and `dependencies` arrays.

Component name/version identities must be unique. Their union with the root
component must contain every direct runtime dependency declared by the
project, and each resolved version must satisfy its PEP 440 project specifier.
The resulting package-set digest is compared with the inventory, policy report,
and environment lock.

The exact SBOM bytes are bound by the license report, release-subject digest,
and human attestation.

### License inventory and policy report

The inventory is a non-empty array. Every element must have non-empty `Name`,
`Version`, and `LicenseText`; normalized name/version pairs must be unique; the
project distribution and every declared runtime dependency must be present;
each direct version must satisfy its declared specifier; and the full
normalized name/version set must match the SBOM, policy report, and environment
lock.

The license report top-level object has exactly:

```text
automation_result, legal_review_complete, limitations, packages, policy,
sbom_coverage_errors, scope_profiles, source_artifacts, summary
```

Nested exact fields are:

- `summary`: `allow`, `deny`, `review`, `total`;
- `source_artifacts`: `inventory_sha256`, `sbom_sha256`;
- `policy`: `name`, `sha256`, `version`.

Every report package needs a unique name/version and an allow, deny, or review
decision. Declared summary counts are recomputed from those records. Automation
passes only when the result is `pass`, every package is allowed, all four
package sets match, direct dependency versions satisfy project specifiers,
limitations are non-empty, scope profiles are exactly `default` and
`structural`, there are no SBOM
coverage errors, source digests match, and the policy digest matches the
authoritative tracked policy and artifact audit.

`legal_review_complete` must remain `false`. This is intentional:
`scripts/audit_supply_chain.py` performs automated policy triage and refuses
to represent it as legal review. Human legal review is a separate attestation
step, bound to the exact inventory and SBOM and authenticated by the signed
tag. An automated report that sets this field to `true` is rejected as a scope
violation.

### Test, coverage, lint, and type evidence

Each gate record has schema
`bench-cleanser-release-gate-evidence-0.1.0` and exactly:

```text
schema_version, kind, source, command, platform, started_at, completed_at,
result, log
```

The exact nested fields are:

- `source`: `commit`, `tree`, both equal to the inspected source;
- `platform`: `os`, `architecture`, `python_version`;
- `result`: `exit_code`, `status`, `summary`;
- `log`: `relative_path`, `bytes`, `sha256`.

`command` must equal one of the canonical argv arrays, with no additional
flags:

```text
test/coverage: pytest tests/ -q --tb=short --cov=bench_cleanser --cov-report=term --cov-fail-under=70
lint:          ruff check .
type:          mypy bench_cleanser
```

Exact matching rejects collect-only, disabled-plugin, version-only, alternate
executable, and appended bypass forms. The confined, non-empty regular log file is resolved
relative to the evidence JSON's directory, then its actual bytes and digest
are checked. Passing requires `status: "pass"`, exit code zero, a current
source identity, a matching log, and a kind-specific summary:

- `test`: exact fields `collected`, `passed`, `failed`, `errors`, `skipped`;
  collected is positive, failed/errors are zero, and passed plus skipped equals
  collected;
- `coverage`: exact fields `measured_files`, `percent`, `minimum_percent`;
  at least one file is measured, the declared minimum is at least 55%, and
  percent meets it;
- `lint` and `type`: exact fields `checked_files`, `errors`, `tool`; at least
  one file is checked and errors are zero.

These records are digest-bound execution records, not remotely authenticated
attestations by themselves. Their inclusion in the signed human release
attestation is the accountability boundary.

### Linux CI evidence

The record has schema `bench-cleanser-linux-ci-evidence-0.2.0` and exactly:

```text
schema_version, source, provider, repository, workflow, run_id, run_attempt,
run_url, runner, conclusion, completed_at, release_artifacts, github_context,
matrix_evidence
```

Nested exact fields are:

- `source`: `commit`, `tree`;
- `runner`: `os`, `architecture`, `python_versions`;
- `release_artifacts`: `wheel_sha256`, `sdist_sha256`,
  `artifact_report_sha256`;
- `github_context`: `event_name`, `job`, `ref`, `runner_arch`, `runner_os`,
  `sha`, `workflow`, `workflow_ref`, `workflow_sha`;
- each `matrix_evidence` item: `python_version`, `platform`, `files`;
- each matrix `platform`: `os`, `architecture`, `python_full_version`;
- each matrix file: `logical_path`, `bytes`, `sha256`.

Readiness requires provider `github-actions`, conclusion `success`, a Linux
runner covering exactly Python 3.11 and 3.12, positive run ID/attempt, a source
identity equal to the current commit/tree, exact release-artifact digests,
repository equal to the canonical project URL, workflow
`.github/workflows/ci.yml`, and the exact HTTPS run path
`/<repository>/actions/runs/<run_id>` without query, credentials, port, or
fragment. The two ordered matrix inventories must bind the exact seven-file
quality receipt for Python 3.11 and 3.12 (four canonical JSON records plus
their three logs), agree on Linux and runner architecture, and carry matching
full Python versions. The embedded GitHub context must name this commit, the
`CI` workflow, the `release-evidence` job, and this workflow path/ref.

This remains declared CI evidence. The captured GitHub environment and receipt
digests narrow what can be substituted, but the generator does not call the
GitHub API or verify an OIDC/Sigstore attestation. Reviewers must inspect the
named run, and the release signer assumes responsibility for the exact record
through the attestation.

### Environment lock

The record has schema `bench-cleanser-environment-lock-0.1.0` and exactly
`schema_version`, `source`, `platform`, `python`, and `packages`.

Nested exact fields are:

- `source`: `commit`, `tree`, `wheel_sha256`, `sdist_sha256`;
- `platform`: `os`, `architecture`;
- `python`: `implementation`, `version`;
- each package: `name`, `version`, `hashes`.

Packages and each package's non-empty SHA-256 list must be unique and sorted.
The project wheel/version and every direct dependency must appear, direct
versions must satisfy project specifiers, and the root package's hash list must
contain the exact supplied wheel digest. The complete name/version set must
equal the inventory/SBOM/report set, and source and artifact identities must
match the current release. The lock must describe Linux CPython whose exact
version satisfies project `Requires-Python`. Non-root dependency hashes are preserved and
syntax-checked but cannot be independently downloaded or authenticated by this
offline verifier.

### Literature lock and claim ledger

The top-level object has exactly `schema_version`, `entries`, and `source`.
Readiness currently requires schema `0.1.0`, a non-empty list sorted uniquely
by `versioned_id`, canonical `https://arxiv.org` PDF URLs, and at least one
`source.responses` item with `raw_atom_sha256`.

The separate required claim ledger has schema
`literature-claim-ledger-0.1.0` and exact top-level fields `schema_version`,
`status`, `reviewed_at`, `coverage`, and `entries`. It is checked against the
locked paper count and each locked version/title/PDF URL. Every sorted ledger
entry binds a canonical PDF artifact name, byte count, SHA-256, machine-review
status, and one or more unique page/section-level claims. Claim types are
limited to author-reported method, result, or limitation.

Both `--literature-lock` and `--literature-claims` must be byte-identical to
the tracked `docs/literature.lock.json` and `docs/literature.claims.json` `HEAD`
blobs that the sdist ships. External substitutes are rejected even when they
are otherwise schema-valid. Canonical titles must be non-empty strings in both
files.

The checked-in ledger is deliberately partial and machine-assisted. Its valid
engineering-alpha summary is currently 21 of 65 papers, 28 claims, zero PDF
files re-verified by this dossier, incomplete coverage, and no human
confirmation. The ledger bytes are release subjects, but the dossier always
reports `scientific_release_ready: false`; it does not turn metadata validation
into a scientific-validity claim.

### Study artifacts

At least one named JSON study artifact is required. Each artifact needs
non-empty `schema_version` and `study_id` fields plus at least one recognized
code-identity object:

```text
study_code, study_code_identity, acquisition_study_code_identity,
analysis_code_identity, acquisition_code_identity
```

The same `analysis_code_identity` and `acquisition_code_identity` keys are also
recognized inside `feature_freeze`. Every identity needs a confined Python
`logical_path` under `experiments/` and a `sha256`; `bytes`, when present, must
match. The referenced regular source file must equal its tracked `HEAD` blob.
Every study must be code-bound for readiness.

### Human release attestation

The attestation has schema
`bench-cleanser-human-release-attestation-0.1.0`. Its exact top-level fields
are:

```text
schema_version, release_version, source_commit, source_tree, tag,
release_subjects_sha256, maintainer, legal_review, approval
```

Nested exact fields are:

- `maintainer`: `identifier`, `name`;
- `legal_review`: `completed`, `reviewed_at`, `reviewed_inventory_sha256`,
  `reviewed_sbom_sha256`, `reviewer`, `scope_profiles`;
- `approval`: `approved_at`, `decision`, `statement`.

The file must use the generator's canonical JSON encoding: UTF-8, sorted keys,
two-space indentation, no NaN/infinity, and one trailing newline. All source,
tag, release-subject, inventory, and SBOM identities must equal the generated
template. The legal review must be completed over the exact default and
structural scopes. Approval must follow review, use decision `approve`, and
retain the template's full review statement.

Finally, the exact raw-file digest must appear on its own line in the verified
annotated tag message:

```text
Release-Attestation-SHA256: <sha256 of release-attestation.json>
```

The attestation does not pass unless its content is valid, this digest binding
is present, and `git verify-tag TAG` succeeds.

## CI enforcement and provenance boundary

The repository CI runs the dossier/capture contract tests and claim-ledger
verifier, invokes both release-evidence CLI help paths, and applies strict mypy
to the release scripts and their contract tests. Each Python 3.11/3.12 matrix
job now runs the canonical lint, package type, test, and coverage commands via
`capture_release_evidence.py quality`, retaining four source-bound records and
three digest-bound logs. The package job emits the complete pip installation
report and an environment lock alongside the wheel, sdist, SBOM, inventory,
license report, and artifact audit. After both matrix jobs and the package job
succeed, `release-evidence` downloads those receipts and emits the schema-0.2.0
Linux record that inventories both matrices and binds the release artifacts.
All three artifact classes include the commit and run attempt in their names
and are retained for 90 days.

CI still does not build the final dossier, authenticate the GitHub run through
OIDC/API evidence, perform human dependency-license or research-data review,
create a signed annotated tag, or preserve evidence beyond artifact retention.
Those steps remain part of the release ceremony. The generator validates the
supplied schemas, hashes, source/artifact bindings, and canonical commands, but
the signed human attestation remains the disclosed accountability boundary for
this engineering-alpha profile.

## Two-pass signing ceremony

The tag names the attestation digest, while the attestation names the tag and
the release-subject digest. Use this two-pass ceremony to resolve that binding
without weakening either side:

1. Prepare one clean release commit. Build the wheel, sdist, audit outputs,
   gate evidence, Linux record, environment lock, literature lock, claim
   ledger, and study records from that exact commit. Do not change their bytes
   afterward.
2. Add the exact release tag name as a provisional annotated tag pointing to
   the release commit. It may be unsigned at this stage. Do not publish it.
3. Run the dossier builder without `--attestation`, writing a preliminary
   dossier outside the repository. Exit `1` is expected. Confirm that all
   blockers other than the final human-attestation/signature ceremony are
   understood.
4. Extract `human_attestation.required_template`, preserve canonical JSON, and
   have the named maintainer and reviewer complete the non-null identity,
   review-time, approval-time, legal-completion, and approval-decision fields.
   Do not weaken or replace the statement.
5. Hash the final attestation bytes. Delete only the unpublished provisional
   tag, then recreate the same tag name as a signed annotated tag at the same
   commit. Put the exact `Release-Attestation-SHA256: ...` line in its message.
6. Run `git verify-tag TAG`, then rebuild the dossier with `--attestation` and
   all original evidence inputs. A result of `0` is the only release-ready
   outcome.
7. Run check mode from a fresh checkout with the same immutable inputs before
   publication. Preserve the dossier, attestation, artifacts, and evidence as
   one release evidence set.

If any source or evidence byte changes after step 3, discard the attestation
and restart. Reusing a signature over a changed evidence set is forbidden by
the digest checks and should be treated as a failed ceremony, not repaired by
editing the dossier.

## Current repository status

As of the current working state, a public release claim must remain blocked:

- the worktree contains many tracked and untracked development changes;
- `CHANGELOG.md` still labels `0.1.0` as an Unreleased engineering-alpha
  candidate;
- no exact release tag points at `HEAD`, let alone a verified signed annotated
  tag carrying the attestation digest;
- no completed canonical human attestation is bound to such a tag;
- the claim ledger remains intentionally partial, has no human-confirmed
  mappings, and has not had its PDF files re-verified by this dossier, so no
  scientific-release claim is available;
- the automated license report correctly keeps
  `legal_review_complete: false`; a separate signed human review has not yet
  been supplied;
- a final immutable wheel/sdist and the complete commit-, artifact-, and
  log-bound evidence set have not been assembled for this release commit.

These are release blockers, not generator defects. The generator either emits
a deterministic blocked dossier or rejects source/artifact inputs that cannot
be bound safely while they remain unresolved.
