#!/usr/bin/env bash
# init.sh for timer-tool. This file is the course's declared single-file
# exception to dual-track duplication (docs/conventions.md, command-block
# exceptions): init.sh is one shared, language-neutral artifact that shows
# BOTH ecosystems' install paths side by side; delete the branch your
# project does not have.
set -euo pipefail

say() { printf '\n[init] %s\n' "$1"; }

if [ -f "pyproject.toml" ]; then
  say "Python: syncing environment with uv"
  uv sync
fi

if [ -f "package.json" ]; then
  say "Node: installing with pnpm"
  corepack enable pnpm >/dev/null 2>&1 || true
  pnpm install --frozen-lockfile
fi

say "Verifying baseline"
./verify.sh

say "Ready. Read claude-progress.md for the next best step."
