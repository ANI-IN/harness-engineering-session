#!/usr/bin/env bash
# project-01 verify: run the kb app and the controlled experiment through
# the conformance runner, then the project's own test suites.
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

echo "verify(project-01 baseline-vs-minimal-harness): stack=${STACK}"
uv run --project "$REPO_ROOT" python "$REPO_ROOT/tools/conformance/runner.py" \
  --unit "$(pwd)" --stack "$STACK"

if [ "$STACK" = "python" ] || [ "$STACK" = "both" ]; then
  (cd "$REPO_ROOT" && uv run pytest projects/project-01-baseline-vs-minimal-harness -q)
fi
if [ "$STACK" = "typescript" ] || [ "$STACK" = "both" ]; then
  (cd "$REPO_ROOT" && "$NODE20_BIN/pnpm" exec vitest run --silent=true \
    projects/project-01-baseline-vs-minimal-harness)
fi
