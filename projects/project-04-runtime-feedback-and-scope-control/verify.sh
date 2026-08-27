#!/usr/bin/env bash
# project-04 verify: run the kb v4 app, the doctors, the guard, and the continuity proof through the
# conformance runner, assert the starter is a genuine starting point (it
# must FAIL the v2 cases), then run the project's own test suites.
# Usage: verify.sh [--stack=python|typescript|both]   (default: both)
set -euo pipefail
cd "$(dirname "$0")"
REPO_ROOT="$(cd ../.. && pwd)"
# Resolve the pinned Node 20 toolchain (pnpm lives beside it); bare `pnpm`
# would resolve through PATH order, which a newer Node elsewhere can shadow.
NODE20_BIN="$(bash "$REPO_ROOT/tools/find_node20.sh" 2>/dev/null || true)"

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

echo "verify(project-04 runtime-feedback-and-scope-control): stack=${STACK}"

# Dedup mode (make status): the solution-stage conformance run and this
# project's test suites are performed by the root conformance gate and the
# root pytest/vitest runs. The starter-must-fail gate below is unique to
# this script and runs in every mode; coverage equality is proven by
# tools/test_dedup_coverage.py.
if [ "${HARNESS_SKIP_UNIT_CONFORMANCE:-0}" != "1" ]; then
  uv run --project "$REPO_ROOT" python "$REPO_ROOT/tools/conformance/runner.py" \
    --unit "$(pwd)" --stack "$STACK"
fi

if uv run --project "$REPO_ROOT" python "$REPO_ROOT/tools/conformance/runner.py" \
  --unit "$(pwd)" --stack "$STACK" --stage starter >/dev/null 2>&1; then
  echo "verify: FAIL: the starter already passes the v4 cases; it must be a genuine starting point" >&2
  exit 1
fi
echo "verify: starter stage fails the v4 cases as intended (genuine starting point)"

if [ "${HARNESS_SKIP_UNIT_CONFORMANCE:-0}" != "1" ]; then
  if [ "$STACK" = "python" ] || [ "$STACK" = "both" ]; then
    (cd "$REPO_ROOT" && uv run pytest projects/project-04-runtime-feedback-and-scope-control -q)
  fi
  if [ "$STACK" = "typescript" ] || [ "$STACK" = "both" ]; then
    if [ -z "$NODE20_BIN" ]; then
      echo "verify: FAIL: no Node 20 toolchain found (required for --stack=$STACK; see make doctor TRACK=typescript)" >&2
      exit 1
    fi
    (cd "$REPO_ROOT" && "$NODE20_BIN/pnpm" exec vitest run --silent=true \
      projects/project-04-runtime-feedback-and-scope-control)
  fi
fi
