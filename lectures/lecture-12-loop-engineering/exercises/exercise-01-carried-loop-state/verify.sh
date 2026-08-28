#!/usr/bin/env bash
# Exercise verify: checks an implementation stage against expected/.
#   --stack=python|typescript|both   (default: both)
#   --target=starter|solution|ci     (default: starter, the learner workspace)
# --target=ci performs the four acceptance runs (starter and solution, each
# stack) individually: every starter run must fail with the exact divergence
# recorded in expected/starter-divergence.txt, every solution run must pass.
set -euo pipefail
cd "$(dirname "$0")"
REPO_ROOT="$(cd ../../../.. && pwd)"
RUNNER="$REPO_ROOT/tools/conformance/runner.py"
NAME="exercise-01-carried-loop-state"
TASK_HINT="read every attempt the carried loop state records, not one fewer"

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

run_stage() { # $1=stage $2=stack
  uv run --project "$REPO_ROOT" python "$RUNNER" --unit "$(pwd)" --stack "$2" --stage "$1"
}

case "$TARGET" in
  starter|solution)
    echo "verify(${NAME}): stack=${STACK} target=${TARGET}"
    if run_stage "$TARGET" "$STACK"; then
      echo "verify: PASS (${TARGET})"
    else
      echo "verify: FAIL (${TARGET})"
      if [ "$TARGET" = "starter" ]; then
        echo "The starter is expected to fail until you ${TASK_HINT}"
        echo "in starter/<your stack>/main.(py|ts). See README.md 'Your task' and SPEC.md."
      fi
      exit 1
    fi
    ;;
  ci)
    if [ "$STACK" = "both" ]; then stacks="python typescript"; else stacks="$STACK"; fi
    expected_divergence="$(cat expected/starter-divergence.txt)"
    total=0
    echo "verify(${NAME}): target=ci (acceptance runs: starter must fail as recorded, solution must pass)"
    for stack in $stacks; do
      total=$((total + 1))
      log="$(mktemp)"
      if run_stage starter "$stack" > "$log" 2>&1; then
        echo "ci run ${total}: starter/${stack}: INVARIANT BROKEN (pristine starter passes)"
        cat "$log"; rm -f "$log"; exit 1
      fi
      if ! grep -qF "$expected_divergence" "$log"; then
        echo "ci run ${total}: starter/${stack}: INVARIANT BROKEN (failed, but not with the recorded divergence)"
        echo "expected: ${expected_divergence}"
        cat "$log"; rm -f "$log"; exit 1
      fi
      echo "ci run ${total}: starter/${stack}: fails as intended (${expected_divergence})"
      rm -f "$log"
    done
    for stack in $stacks; do
      total=$((total + 1))
      if ! run_stage solution "$stack" > /dev/null 2>&1; then
        echo "ci run ${total}: solution/${stack}: INVARIANT BROKEN (solution fails)"
        run_stage solution "$stack" || true
        exit 1
      fi
      echo "ci run ${total}: solution/${stack}: PASS"
    done
    if [ "$STACK" = "both" ] && [ "$total" -ne 4 ]; then
      echo "ci: INVARIANT BROKEN: expected 4 acceptance runs, performed ${total}"
      exit 1
    fi
    echo "verify: PASS (ci: ${total} acceptance runs completed)"
    ;;
esac
