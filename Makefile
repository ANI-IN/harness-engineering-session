# One entry point for both stacks. Every target prints what it checked and
# exits non-zero on the first failure. See docs/conventions.md for the
# verification contract these targets enforce.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Resolve the pinned Node 20 toolchain once. Recipes invoke $(NODE) and
# $(PNPM), the resolved absolute binaries, never bare `node`/`pnpm`, so a
# newer Node elsewhere (e.g. /usr/local/bin) cannot shadow the pin; PATH is
# also exported for child processes (test runners spawning node, doctor's
# probes). GNU make 3.81 resolves bare recipe commands with its own original
# PATH, which is why the explicit variables are load-bearing, not style. If
# no Node 20 exists anywhere, the bare names are used and `make doctor`
# fails hard against the .nvmrc pin.
NODE20_BIN := $(shell bash tools/find_node20.sh 2>/dev/null)
ifneq ($(NODE20_BIN),)
export PATH := $(NODE20_BIN):$(PATH)
NODE := $(NODE20_BIN)/node
PNPM := $(NODE20_BIN)/pnpm
else
NODE := node
PNPM := pnpm
endif

.PHONY: help setup doctor status quick verify verify-dedup conformance lint lint-py lint-ts lint-md lint-sh lint-prose lint-links lint-links-external lint-mermaid lint-structure

help: ## List available targets
	@grep -E '^[a-z][a-z-]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-22s %s\n", $$1, $$2}'

setup: ## Install both toolchains (uv sync + pnpm install)
	uv sync
	$(PNPM) install --frozen-lockfile || $(PNPM) install
	@echo "setup: OK (python + typescript toolchains installed)"

doctor: ## Print toolchain versions and check them against the pins
	@uv run python tools/lint/doctor.py

status: ## Run every gate and print exit codes, floors, and tree counts as one artifact
	@uv run python tools/report_status.py

verify: ## Run every unit's verify.sh (both stacks) + all test suites
	@uv run pytest
	@$(PNPM) run --silent test
	@uv run python tools/run_verify.py
	@uv run python tools/check_build_state.py
	@uv run python tools/gen_readme_blocks.py --check
	@echo "verify: OK"

verify-dedup: ## Verify for make status: unit conformance runs once, in the conformance gate
	@uv run pytest
	@$(PNPM) run --silent test
	@uv run python tools/run_verify.py --skip-unit-conformance
	@uv run python tools/check_build_state.py
	@uv run python tools/gen_readme_blocks.py --check
	@echo "verify-dedup: OK (unit conformance covered by the conformance gate)"

quick: ## Inner loop for ONE unit: doctor + U=<dir>/verify.sh. NOT the commit gate; run make status before committing
	@test -n "$(U)" || { echo "usage: make quick U=<unit-dir>   (e.g. U=projects/project-03-multi-session-continuity)"; exit 2; }
	@uv run python tools/lint/doctor.py
	@bash "$(U)/verify.sh"
	@echo "quick: OK ($(U)); the commit gate is still 'make status'"

conformance: ## Diff python vs typescript vs expected/ for every SPEC.md unit
	@uv run python tools/conformance/runner.py

lint: lint-py lint-ts lint-md lint-sh lint-prose ## All source linters (+ prose punctuation)
	@echo "lint: OK"

lint-prose: ## No em/en dashes in markdown prose (code fences, inline code, URLs exempt)
	@uv run python tools/lint/check_prose.py

lint-py: ## ruff over all Python sources
	uv run ruff check .

lint-ts: ## eslint + tsc --noEmit over all TypeScript sources
	$(PNPM) run --silent lint
	$(PNPM) run --silent typecheck

lint-md: ## markdownlint over all Markdown
	$(PNPM) exec markdownlint-cli2

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
	@$(NODE) tools/lint/mermaid-parse.mjs

lint-structure: ## Check README section order, unit completeness, dir READMEs
	@uv run python tools/lint/check_structure.py
