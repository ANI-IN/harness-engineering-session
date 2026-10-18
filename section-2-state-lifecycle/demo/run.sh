#!/usr/bin/env bash
# Section 2 demo: run the harness arm live on Feature 2: Comments on issues with the instructions and
# state layers. The first session stops after 12 turns; a fresh 38-turn session resumes from the
# files the state layer left.
#
# Usage, from the repository root (the script itself works from any folder):
#   ./section-2-state-lifecycle/demo/run.sh                  # class run (needs SHIPHARNESS_CLASS_DATE in .env)
#   PURPOSE=pilot ./section-2-state-lifecycle/demo/run.sh    # practice run outside class
#
# What it does: checks that both API keys are set, that Docker answers, and that a class run has its
# class date; then runs `make show-2 SESSION_BUDGET=12,38`. Every run is live: one real agent run
# and one real review. There is no recorded or scripted fallback in this script.
#
# Cost: at most $0.24, the per-arm cap ($0.20) plus the per-review cap ($0.04); the caps are set in
# platform/src/shipharness/config/settings.py and .env.example. Three runs, measured 2026-10-18
# with the class profile, cost $0.036 to $0.038 each.
# Time: in those runs session 1 stopped 0:44 to 1:01 after launch, the primary verdict came 3:21 to
# 5:20 and the full verdict 5:10 to 6:59; the command ends a few seconds after the full verdict
# (docs/evidence/general.md, "Demo runs after the speed-up").
#
# Start the console first, in another terminal: `make console`, then open http://127.0.0.1:8765/
set -euo pipefail

# No arguments: settings come from the environment (PURPOSE=pilot ./section-2-state-lifecycle/demo/run.sh).
if [ "$#" -gt 0 ]; then
  case "$1" in
    -h|--help)
      sed -n '2,/^set -euo pipefail/{/^#/s/^# \{0,1\}//p}' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "x unknown argument '$1': ./section-2-state-lifecycle/demo/run.sh takes no arguments" >&2
      echo "  for a practice run: PURPOSE=pilot ./section-2-state-lifecycle/demo/run.sh; for help: ./section-2-state-lifecycle/demo/run.sh --help" >&2
      exit 2
      ;;
  esac
fi

# The repository root is two folders up from this script.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PURPOSE="${PURPOSE:-class}"
fail() { echo "x $1" >&2; exit 2; }

# 1. Keys. Read .env only to see whether each key has a value; never print a value.
[ -f .env ] || fail "no .env in $ROOT: run 'make setup', then add your keys (setup/README.md)"
for key in OPENAI_API_KEY LANGSMITH_API_KEY; do
  if ! grep -Eq "^${key}=.+" .env && [ -z "${!key:-}" ]; then
    fail "$key is not set: add it to .env, then run 'make doctor'"
  fi
done
echo "+ keys present (make doctor checks that they are accepted)"

# 2. Docker. The agent and the referee each run in a container.
command -v docker >/dev/null 2>&1 || fail "docker not found: install Docker (setup/README.md)"
docker info >/dev/null 2>&1 || fail "Docker is not running: start it (Ubuntu: sudo systemctl start docker)"
echo "+ Docker is running"

# 3. Class date or purpose. A class run is traced to the LangSmith project of the class day.
if [ "$PURPOSE" = "class" ]; then
  # The environment wins over .env; quotes around the value in .env are removed.
  CLASS_DATE="${SHIPHARNESS_CLASS_DATE:-$(grep -E '^SHIPHARNESS_CLASS_DATE=' .env | tail -n 1 | cut -d= -f2- | tr -d "\"' " || true)}"
  if [ -z "$CLASS_DATE" ]; then
    fail "SHIPHARNESS_CLASS_DATE is not set: add the class day (YYYY-MM-DD) to .env, or run with PURPOSE=pilot"
  fi
  TODAY="$(date +%Y-%m-%d)"
  if [ "$CLASS_DATE" != "$TODAY" ]; then
    echo "! SHIPHARNESS_CLASS_DATE is $CLASS_DATE but today is $TODAY."
    echo "  The run will be traced to the project of $CLASS_DATE. Outside class, use PURPOSE=pilot."
  fi
  echo "+ class run for $CLASS_DATE"
else
  echo "+ purpose: $PURPOSE"
fi

# 4. The live run: the harness arm alone with a 12-turn first session, then the referee
#    (continuity first) and the review.
echo "Launching make show-2 SESSION_BUDGET=12,38 (at most \$0.24 at the caps). Watch the console: press 1, then 3, 5, 2, 4."
exec make show-2 SESSION_BUDGET=12,38 PURPOSE="$PURPOSE"
