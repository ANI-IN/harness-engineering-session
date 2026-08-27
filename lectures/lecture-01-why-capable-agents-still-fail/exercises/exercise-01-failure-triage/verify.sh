#!/usr/bin/env bash
# Exercise verify: checks an implementation stage against expected/.
#   --stack=python|typescript|both   (default: both)
#   --target=starter|solution|ci     (default: starter, the learner workspace)
# --target=ci asserts the repo invariant: the pristine starter fails for the
# intended reason (a report mismatch, not a crash) AND the solution passes.
set -euo pipefail
cd "$(dirname "$0")"
REPO_ROOT="$(cd ../../../.. && pwd)"
RUNNER="$REPO_ROOT/tools/conformance/runner.py"

STACK="both"
TARGET="starter"
for arg in "$@"; do
  case "$arg" in
    --stack=python|--stack=typescript|--stack=both) STACK="${arg#--stack=}" ;;
    --target=starter|--target=solution|--target=ci) TARGET="${arg#--target=}" ;;
    *)
      echo "usage: verify.sh [--stack=python|typescript|both] [--target=starter|solution|ci]" >&2
      exit 64
      ;;
  esac
done

run_stage() {
  uv run --project "$REPO_ROOT" python "$RUNNER" --unit "$(pwd)" --stack "$STACK" --stage "$1"
}

case "$TARGET" in
  starter|solution)
    echo "verify(exercise-01-failure-triage): stack=${STACK} target=${TARGET}"
    if run_stage "$TARGET"; then
      echo "verify: PASS (${TARGET})"
    else
      echo "verify: FAIL (${TARGET})"
      if [ "$TARGET" = "starter" ]; then
        cat <<'MSG'
The starter is expected to fail until you implement the three missing rules
(environment, state, feedback) in starter/<your stack>/main.(py|ts).
See README.md "Your task" and SPEC.md for the exact rule definitions.
MSG
      fi
      exit 1
    fi
    ;;
  ci)
    echo "verify(exercise-01-failure-triage): stack=${STACK} target=ci"
    starter_log="$(mktemp)"
    if run_stage starter > "$starter_log" 2>&1; then
      echo "CI INVARIANT BROKEN: pristine starter passes verification"
      cat "$starter_log"
      rm -f "$starter_log"
      exit 1
    fi
    if ! grep -q "diverges at" "$starter_log"; then
      echo "CI INVARIANT BROKEN: starter failed, but not for the intended reason (expected a report mismatch):"
      cat "$starter_log"
      rm -f "$starter_log"
      exit 1
    fi
    echo "starter fails for the intended reason:"
    grep "diverges at" "$starter_log" | head -2
    rm -f "$starter_log"
    if ! run_stage solution; then
      echo "CI INVARIANT BROKEN: solution fails verification"
      exit 1
    fi
    echo "verify: PASS (ci: starter fails as intended, solution passes)"
    ;;
esac
