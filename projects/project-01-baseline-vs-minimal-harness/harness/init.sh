#!/usr/bin/env bash
# init.sh, project 01 workspace: initialize the kb data directory and
# smoke-check the app before any feature work.
#
# One file serves both tracks (the course's declared single-file exception
# for init scripts): set KB to your track's interpreter command.
#   Python track (default):  KB="uv run python src/main.py"
#   TypeScript track:        KB="pnpm exec tsx src/main.ts"
set -euo pipefail

KB="${KB:-uv run python src/main.py}"
read -r -a KB_CMD <<< "$KB"

"${KB_CMD[@]}" init --data-dir kb-data --seed data/sample-documents
"${KB_CMD[@]}" list --data-dir kb-data >/dev/null

echo "init: ready"
