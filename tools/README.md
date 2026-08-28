# Tools

The repository's own verification machinery: the conformance runner that
holds the two language tracks to one behavior, and the linters that keep
structure, links, and diagrams from rotting. These run via the `make` targets
and in CI on every push.

**Single-track decision:** tools are written in **Python**. They are
tooling, not curriculum, so the module's dual-track parity requirement does
not apply; duplicating them would double maintenance for zero teaching
value. Two exceptions, each for a reason: `lint/mermaid-parse.mjs` is Node
because mermaid's grammar exists only as a JavaScript implementation, and
`find_node20.sh` is shell because it has to resolve a Node binary before
any Node is known to work.

| Directory | What it does |
| --- | --- |
| [`conformance/`](./conformance/) | Runs every unit's cases against both tracks and diffs three ways (python vs expected, typescript vs expected, python vs typescript) after the defined normalization pass |
| [`lint/`](./lint/) | Structure checker (README orders, unit completeness), link checker (relative + external), mermaid parser, prose checker, shared-helper drift checker, toolchain doctor |
| [`check_readme_commands.py`](./check_readme_commands.py) | Executes every `sh` fence in the Setup, Usage, Demo and Demo flow sections of every lecture and project README, so a documented command is a working command. Toolchain-mutating fences run alone, before the rest |
| [`check_fresh_checkout.py`](./check_fresh_checkout.py) | Exports `HEAD` and runs conformance inside the export, so a fixture present on disk but absent from git fails here rather than in a clone (`make check-fresh`) |
| [`gen_readme_blocks.py`](./gen_readme_blocks.py) | Regenerates every `<!-- generated-block: ... -->` from the command it names, and `--check` fails on drift |
| [`run_verify.py`](./run_verify.py) | Runs every unit's `verify.sh`, with a dedup mode for `make status` |
| [`run_acceptance.py`](./run_acceptance.py) | The four acceptance runs for one exercise, the transcript exercise READMEs embed |
| [`check_build_state.py`](./check_build_state.py) | Requires those four runs to be recorded for every exercise when the local build-state file exists |
| [`report_status.py`](./report_status.py) | Runs every gate and prints exit codes, counts, and floors as one artifact (`make status`) |
| [`expected_counts.json`](./expected_counts.json) | The fail-on-empty floors: discovery reporting fewer units than this is a build failure, not a pass |
| [`find_node20.sh`](./find_node20.sh) | Resolves the pinned Node 20 binary absolutely, so a newer Node cannot shadow it |

The normalization pass in `conformance/normalize.py` is part of the module's
parity contract; it is documented for learners in
[docs/conventions.md](../docs/conventions.md).
