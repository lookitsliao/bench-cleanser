#!/usr/bin/env bash
# Build the exact tree, install the wheel in a new environment, and emit the
# public-alpha SBOM/license/archive reports. Existing target paths are refused
# so a stale developer environment cannot contaminate the evidence.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 FRESH_VENV_PATH FRESH_ARTIFACT_DIR" >&2
  exit 2
fi

TARGET_DIR=$1
ARTIFACT_DIR=$2
PYTHON=${PYTHON:-python}
ROOT=$(cd "$(dirname "$0")/.." && pwd)

if [[ -e "$TARGET_DIR" ]]; then
  echo "target environment already exists: $TARGET_DIR" >&2
  exit 2
fi
if [[ -e "$ARTIFACT_DIR" ]]; then
  echo "artifact directory already exists: $ARTIFACT_DIR" >&2
  exit 2
fi

for command_name in cyclonedx-py pip-licenses twine; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "missing release tool: $command_name (install .[release])" >&2
    exit 2
  fi
done

mkdir -p "$ARTIFACT_DIR"
cd "$ROOT"
"$PYTHON" -m build --no-isolation --outdir "$ARTIFACT_DIR"
twine check "$ARTIFACT_DIR"/*

wheel_files=("$ARTIFACT_DIR"/*.whl)
sdist_files=("$ARTIFACT_DIR"/*.tar.gz)
if [[ ${#wheel_files[@]} -ne 1 || ! -f "${wheel_files[0]}" ]]; then
  echo "expected exactly one wheel in $ARTIFACT_DIR" >&2
  exit 2
fi
if [[ ${#sdist_files[@]} -ne 1 || ! -f "${sdist_files[0]}" ]]; then
  echo "expected exactly one source distribution in $ARTIFACT_DIR" >&2
  exit 2
fi

REPORT_DIR="$ARTIFACT_DIR/supply-chain"
mkdir -p "$REPORT_DIR"

# Build the target without bootstrap packages, then install the entire resolved
# environment—including pip and setuptools—through the outer pinned release
# tool. This makes pip's installation report cover the same complete package
# set later observed by the SBOM and license inventory.
"$PYTHON" -m venv --without-pip "$TARGET_DIR"
"$PYTHON" -m pip --python "$TARGET_DIR/bin/python" install \
  --only-binary=:all: \
  --report "$REPORT_DIR/pip-install-report.json" \
  "${wheel_files[0]}[structural]" pip setuptools
"$TARGET_DIR/bin/python" -m pip check

pip-licenses \
  --python "$TARGET_DIR/bin/python" \
  --from mixed \
  --format json \
  --with-system \
  --with-urls \
  --with-description \
  --with-license-file \
  --no-license-path \
  --output-file "$REPORT_DIR/python-license-inventory.json"

cyclonedx-py environment "$TARGET_DIR/bin/python" \
  --pyproject "$ROOT/pyproject.toml" \
  --mc-type library \
  --sv 1.6 \
  --of JSON \
  --output-reproducible \
  -o "$REPORT_DIR/bench-cleanser.cdx.json"

"$PYTHON" "$ROOT/scripts/audit_supply_chain.py" licenses \
  --inventory "$REPORT_DIR/python-license-inventory.json" \
  --sbom "$REPORT_DIR/bench-cleanser.cdx.json" \
  --policy "$ROOT/supply-chain/license-policy.toml" \
  --output "$REPORT_DIR/license-policy-report.json"

"$PYTHON" "$ROOT/scripts/audit_supply_chain.py" artifacts \
  --policy "$ROOT/supply-chain/license-policy.toml" \
  --output "$REPORT_DIR/artifact-audit-report.json" \
  "${wheel_files[@]}" "${sdist_files[@]}"

if [[ "${BC_CAPTURE_RELEASE_EVIDENCE:-0}" == "1" ]]; then
  "$PYTHON" "$ROOT/scripts/capture_release_evidence.py" environment \
    --repo-root "$ROOT" \
    --pip-report "$REPORT_DIR/pip-install-report.json" \
    --inventory "$REPORT_DIR/python-license-inventory.json" \
    --wheel "${wheel_files[0]}" \
    --sdist "${sdist_files[0]}" \
    --target-python "$TARGET_DIR/bin/python" \
    --output "$REPORT_DIR/environment-lock.json"
fi

echo "supply-chain outputs: $REPORT_DIR"
