#!/usr/bin/env bash
# project-02 verify: run the kb v2 app and the workspace doctor through the
# conformance runner, assert the starter is a genuine starting point (it
# must FAIL the v2 cases), then run the project's own test suites.
# Usage: verify.sh [--stack=python|typescript|both]   (default: both)
set -euo pipefail
cd "$(dirname "$0")"
REPO_ROOT="$(cd ../.. && pwd)"
# Resolve the pinned Node 20 toolchain (pnpm lives beside it); bare `pnpm`
# would resolve through PATH order, which a newer Node elsewhere can shadow.
NODE20_BIN="$(bash "$REPO_ROOT/tools/find_node20.sh")"

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

echo "verify(project-02 agent-readable-workspace): stack=${STACK}"
uv run --project "$REPO_ROOT" python "$REPO_ROOT/tools/conformance/runner.py" \
  --unit "$(pwd)" --stack "$STACK"

if uv run --project "$REPO_ROOT" python "$REPO_ROOT/tools/conformance/runner.py" \
  --unit "$(pwd)" --stack "$STACK" --stage starter >/dev/null 2>&1; then
  echo "verify: FAIL: the starter already passes the v2 cases; it must be a genuine starting point" >&2
  exit 1
fi
echo "verify: starter stage fails the v2 cases as intended (genuine starting point)"

if [ "$STACK" = "python" ] || [ "$STACK" = "both" ]; then
  (cd "$REPO_ROOT" && uv run pytest projects/project-02-agent-readable-workspace -q)
fi
if [ "$STACK" = "typescript" ] || [ "$STACK" = "both" ]; then
  (cd "$REPO_ROOT" && "$NODE20_BIN/pnpm" exec vitest run --silent=true \
    projects/project-02-agent-readable-workspace)
fi
