#!/usr/bin/env bash
# Resolve the bin directory of a Node 20 toolchain and print it.
#
# The Makefile prepends this directory to PATH for every target, so a newer
# Node installed elsewhere (e.g. /usr/local/bin) cannot silently shadow the
# repository's Node 20 pin. Resolution order: whatever `node` is on PATH (if
# it is already 20.x, including CI's setup-node), then the Homebrew node@20
# kegs, then nvm installs. Exits 1 with a message when no Node 20 exists;
# `make doctor` then fails against the .nvmrc pin rather than warning.
set -euo pipefail

candidates=()
if command -v node >/dev/null 2>&1; then
  candidates+=("$(dirname "$(command -v node)")")
fi
candidates+=(
  /opt/homebrew/opt/node@20/bin
  /usr/local/opt/node@20/bin
  "$HOME"/.nvm/versions/node/v20*/bin
)

for dir in "${candidates[@]}"; do
  if [ -x "$dir/node" ] && "$dir/node" --version 2>/dev/null | grep -q '^v20\.'; then
    echo "$dir"
    exit 0
  fi
done

echo "find-node20: no Node 20 found (checked PATH, brew node@20 kegs, nvm)" >&2
exit 1
