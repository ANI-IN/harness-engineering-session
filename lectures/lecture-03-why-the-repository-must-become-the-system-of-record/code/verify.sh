#!/usr/bin/env bash
# why-the-repository-must-become-the-system-of-record demo verify: runs this unit through the conformance runner.
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

echo "verify(lecture-03 fresh-session-reader demo): stack=${STACK}"
uv run --project "$REPO_ROOT" python "$REPO_ROOT/tools/conformance/runner.py" \
  --unit "$(pwd)" --stack "$STACK"
