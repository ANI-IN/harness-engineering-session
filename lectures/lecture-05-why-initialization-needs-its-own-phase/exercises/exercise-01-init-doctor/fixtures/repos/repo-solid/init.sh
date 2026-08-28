#!/usr/bin/env bash
set -euo pipefail
uv sync
./verify.sh
echo "[init] ready"
