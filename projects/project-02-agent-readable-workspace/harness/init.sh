#!/usr/bin/env bash
# init.sh, project 02 workspace: initialize the kb data directory,
# smoke-check the app, and gate the session on workspace readability.
#
# One file serves both tracks (the module's declared single-file exception
# for init scripts): set KB to your track's interpreter command.
#   Python track (default):  KB="uv run python src/main.py"
#   TypeScript track:        KB="pnpm exec tsx src/main.ts"
set -euo pipefail

KB="${KB:-uv run python src/main.py}"
read -r -a KB_CMD <<< "$KB"

"${KB_CMD[@]}" init --data-dir kb-data --seed data/sample-documents
"${KB_CMD[@]}" list --data-dir kb-data >/dev/null
"${KB_CMD[@]}" workspace-check --workspace . >/dev/null

echo "init: ready"
