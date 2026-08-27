#!/usr/bin/env bash
# Template: init.sh — session initialization: install -> verify -> next step.
# Use when: any repo an agent starts sessions in; run it first, every session.
# Don't use when: the environment is guaranteed pre-built (CI images that
#   already ran setup) — then run only the verify step.
# Motivated by: Lecture 06 (Why initialization needs its own phase).
#
# This template shows BOTH ecosystems' install steps side by side — init.sh is
# a shared, language-neutral artifact; delete the branch you don't have.
set -euo pipefail

say() { printf '\n[init] %s\n' "$1"; }

# --- 1. Install dependencies ------------------------------------------------
if [ -f "pyproject.toml" ]; then
  say "Python project detected: syncing environment with uv"
  uv sync
fi

if [ -f "package.json" ]; then
  say "Node project detected: installing with pnpm"
  corepack enable pnpm >/dev/null 2>&1 || true
  pnpm install --frozen-lockfile
fi

# --- 2. Verify the environment actually works -------------------------------
# A session must start from a known-good state; an install that succeeded but
# a test suite that fails is a finding, not a detail.
if [ -f "pyproject.toml" ]; then
  say "Verifying Python track"
  uv run pytest
fi

if [ -f "package.json" ]; then
  say "Verifying TypeScript track"
  pnpm test
fi

# --- 3. Point at the state files and the next step ---------------------------
say "Environment ready."
if [ -f "claude-progress.md" ]; then
  say "Read claude-progress.md for the current verified state."
fi
if [ -f "feature_list.json" ]; then
  say "Pick the next feature from feature_list.json (WIP=1)."
fi
say "Start with: ./verify.sh"
