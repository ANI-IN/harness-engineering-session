#!/usr/bin/env bash
# why-agents-overreach-and-under-finish demo verify: runs this unit through the conformance runner.
# Usage: verify.sh [--stack=python|typescript|both]   (default: both)
set -euo pipefail
cd "$(dirname "$0")"
REPO_ROOT="$(cd ../../.. && pwd)"

STACK="both"
for arg in "$@"; do
  case "$arg" in
    --stack=python|--stack=typescript|--stack=both) STACK="${arg#--stack=}" ;;
    *)
      echo "usage: verify.sh [--stack=python|typescript|both]" >&2
      exit 64
      ;;
  esac
done

# Dedup mode (make status): this script's only work is a solution-stage
# conformance run, which `make conformance` performs itself; coverage
# equality is proven by tools/test_dedup_coverage.py.
if [ "${HARNESS_SKIP_UNIT_CONFORMANCE:-0}" = "1" ]; then
  echo "verify: skipped (unit conformance covered by make conformance in dedup mode)"
  exit 0
fi

echo "verify(lecture-07 scope-run demo): stack=${STACK}"
uv run --project "$REPO_ROOT" python "$REPO_ROOT/tools/conformance/runner.py" \
  --unit "$(pwd)" --stack "$STACK"
