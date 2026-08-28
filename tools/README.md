# Tools

The repository's own verification machinery: the conformance runner that
holds the two language tracks to one behavior, and the linters that keep
structure, links, and diagrams from rotting. These run via the `make` targets
and in CI on every push.

**Single-track decision:** tools are written in **Python only**. They are
tooling, not curriculum, so the module's dual-stack parity requirement does
not apply; duplicating them would double maintenance for zero teaching
value. The one exception is `lint/mermaid-parse.mjs` (Node): mermaid's
grammar only exists as a JavaScript implementation, and reimplementing a
parser in Python would itself be a drift risk.

| Directory | What it does |
| --- | --- |
| [`conformance/`](./conformance/) | Runs every unit's cases against both tracks and diffs three ways (python vs expected, typescript vs expected, python vs typescript) after the defined normalization pass |
| [`lint/`](./lint/) | Structure checker (README orders, unit completeness), link checker (relative + external), mermaid parser, prose punctuation checker, toolchain doctor |

The normalization pass in `conformance/normalize.py` is part of the module's
parity contract; it is documented for learners in
[docs/conventions.md](../docs/conventions.md).
