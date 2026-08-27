# One entry point for both stacks. Every target prints what it checked and
# exits non-zero on the first failure. See docs/conventions.md for the
# verification contract these targets enforce.

SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help setup doctor verify conformance lint lint-py lint-ts lint-md lint-sh lint-links lint-links-external lint-mermaid lint-structure

help: ## List available targets
	@grep -E '^[a-z][a-z-]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-22s %s\n", $$1, $$2}'

setup: ## Install both toolchains (uv sync + pnpm install)
	uv sync
	pnpm install --frozen-lockfile || pnpm install
	@echo "setup: OK (python + typescript toolchains installed)"

doctor: ## Print toolchain versions and check them against the pins
	@uv run python tools/lint/doctor.py

verify: ## Run every unit's verify.sh (both stacks) + all test suites
	@uv run pytest
	@pnpm run --silent test
	@set -e; \
	scripts=$$(find lectures projects -name verify.sh -type f 2>/dev/null | sort); \
	if [ -z "$$scripts" ]; then \
	  echo "verify: no curriculum verify.sh scripts present yet (skeleton state)"; \
	else \
	  for s in $$scripts; do echo "verify: running $$s"; bash "$$s" --stack=both; done; \
	fi
	@echo "verify: OK"

conformance: ## Diff python vs typescript vs expected/ for every SPEC.md unit
	@uv run python tools/conformance/runner.py

lint: lint-py lint-ts lint-md lint-sh ## All source linters (ruff + eslint + markdownlint + shellcheck)
	@echo "lint: OK"

lint-py: ## ruff over all Python sources
	uv run ruff check .

lint-ts: ## eslint + tsc --noEmit over all TypeScript sources
	pnpm run --silent lint
	pnpm run --silent typecheck

lint-md: ## markdownlint over all Markdown
	pnpm exec markdownlint-cli2

lint-sh: ## shellcheck over every shell script
	@set -e; \
	scripts=$$(find . -name '*.sh' -type f -not -path './node_modules/*' -not -path './_reference/*' -not -path './.venv/*' | sort); \
	if [ -z "$$scripts" ]; then echo "lint-sh: no shell scripts present yet"; \
	else shellcheck $$scripts && echo "lint-sh: OK ($$(echo "$$scripts" | wc -l | tr -d ' ') scripts)"; fi

lint-links: ## Verify every relative markdown link resolves
	@uv run python tools/lint/check_links.py

lint-links-external: ## Also fetch external URLs (network; run before committing lectures)
	@uv run python tools/lint/check_links.py --external

lint-mermaid: ## Parse every mermaid block in every markdown file
	@node tools/lint/mermaid-parse.mjs

lint-structure: ## Check README section order, unit completeness, dir READMEs
	@uv run python tools/lint/check_structure.py
