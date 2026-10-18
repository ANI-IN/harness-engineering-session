#!/usr/bin/env bash
# Final project: one live A/B. The bare arm and the harness arm with all four layers build the same
# feature, then the referee scores both.
#
# Usage (shown from the repository root; the script works from any folder):
#   ./final-project/run.sh                               # class run, bulk close (needs SHIPHARNESS_CLASS_DATE)
#   PURPOSE=pilot ./final-project/run.sh                 # practice run outside class
#   PURPOSE=pilot ./final-project/run.sh watchers        # another final feature: bulk-close, watchers, or labels
#   PURPOSE=pilot ./final-project/run.sh watchers bulk-close  # several features, one after the other
# Feature names can also come from the environment: FEATURES=watchers,bulk-close.
#
# What it does: checks that both API keys are set, that a class run has its class date, that Docker
# answers, and whether the console is up; then runs `make final FEATURES=<features>`. Every run is
# live: two real agent runs and two real reviews. There is no recorded or scripted fallback here.
#
# Cost: at most $0.58 per feature, two arms at MAX_FINAL_RUN_COST_USD ($0.25) plus two reviews at
# MAX_REVIEW_COST_USD ($0.04); the caps are set in .env.example and
# platform/src/shipharness/config/settings.py. Three runs of bulk close, measured 2026-10-18 with the
# class profile, cost $0.044 to $0.048 each.
# Time: in those runs the bare arm's primary verdict came 1:49 to 5:00 after launch and its full
# verdict 4:16 to 7:58; the harness arm's primary verdict 6:41 to 12:04 and its full verdict 8:41 to
# 15:22. Features run one after another, so two features take about twice as long
# (docs/evidence/general.md, "Demo runs after the speed-up").
#
# Start the console first, in another terminal: `make console`, then open http://127.0.0.1:8765/
set -euo pipefail

# Arguments are feature names (bulk-close, watchers, labels). With none, FEATURES is used, else bulk-close.
ARG_FEATURES=""
for arg in "$@"; do
  case "$arg" in
    -h|--help)
      sed -n '2,/^set -euo pipefail/{/^#/s/^# \{0,1\}//p}' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    -*)
      echo "x unknown argument '$arg': ./final-project/run.sh takes feature names, for example: ./final-project/run.sh watchers" >&2
      echo "  for a practice run: PURPOSE=pilot ./final-project/run.sh watchers; for help: ./final-project/run.sh --help" >&2
      exit 2
      ;;
    *) ARG_FEATURES="${ARG_FEATURES:+$ARG_FEATURES,}$arg" ;;
  esac
done

# The repository root is one folder up from this script.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PURPOSE="${PURPOSE:-class}"
FEATURES="${ARG_FEATURES:-${FEATURES:-bulk-close}}"
# Names may be separated by commas or spaces, in any case; make final takes a comma-separated list.
FEATURES="$(echo "$FEATURES" | tr '[:upper:] ' '[:lower:],' | tr -s ',' | sed 's/^,//; s/,$//')"
CONSOLE_PORT="${CONSOLE_PORT:-8765}"
fail() { echo "x $1" >&2; exit 2; }

# 1. The feature. Only the three final features run here; Features 1 to 4 belong to the section demos.
[ -n "$FEATURES" ] || fail "no feature given: run ./final-project/run.sh bulk-close, watchers, or labels"
for feature in $(echo "$FEATURES" | tr ',' ' '); do
  case "$feature" in
    f5|f6|f7|bulk-close|watchers|labels) ;;
    *) fail "feature '$feature': the final project runs bulk-close, watchers, or labels (codes F5, F6, F7 also work), for example: ./final-project/run.sh watchers" ;;
  esac
done
echo "+ features: $FEATURES"

# 2. Keys. Look in the environment, then in .env, only to see whether each key has a value; never
# print a value.
for key in OPENAI_API_KEY LANGSMITH_API_KEY; do
  if [ -z "${!key:-}" ] && ! { [ -f .env ] && grep -Eq "^${key}=.+" .env; }; then
    fail "$key is not set: add it to .env (make setup copies .env.example), then run 'make doctor'"
  fi
done
echo "+ keys present (make doctor checks that they are accepted)"

# 3. Class date or purpose. A class run is traced to the LangSmith project of the class day.
if [ "$PURPOSE" = "class" ]; then
  # The environment wins over .env; quotes around the value in .env are removed.
  CLASS_DATE="${SHIPHARNESS_CLASS_DATE:-$( { grep -E '^SHIPHARNESS_CLASS_DATE=' .env 2>/dev/null || true; } | tail -n 1 | cut -d= -f2- | tr -d "\"' ")}"
  if [ -z "$CLASS_DATE" ]; then
    fail "SHIPHARNESS_CLASS_DATE is not set: add the class day (YYYY-MM-DD) to .env, or run with PURPOSE=pilot"
  fi
  echo "+ class run for $CLASS_DATE"
else
  echo "+ purpose: $PURPOSE"
fi

# 4. Docker. Each arm and the referee run in their own container.
command -v docker >/dev/null 2>&1 || fail "docker not found: install Docker (setup/README.md)"
docker info >/dev/null 2>&1 || fail "Docker is not running: start it (Ubuntu: sudo systemctl start docker)"
echo "+ Docker is running"

# 5. The console. The run works without it, but the screens are where you watch it.
if curl -fs -o /dev/null "http://127.0.0.1:${CONSOLE_PORT}/" 2>/dev/null; then
  echo "+ console is up at http://127.0.0.1:${CONSOLE_PORT}/"
else
  echo "! console not reachable at http://127.0.0.1:${CONSOLE_PORT}/: start it in another terminal with 'make console'"
fi

# 6. The live run: both arms, then the referee and the review for each.
echo "Launching make final FEATURES=$FEATURES PURPOSE=$PURPOSE (at most \$0.58 per feature at the caps)."
exec make final FEATURES="$FEATURES" PURPOSE="$PURPOSE"
