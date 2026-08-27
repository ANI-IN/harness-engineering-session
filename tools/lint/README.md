# Lint

Four checkers that keep the repository's conventions true over time. Each
prints what it checked and exits non-zero on any finding; `make lint-*`
targets and CI run them all.

| Tool | Target | Checks |
| --- | --- | --- |
| `check_structure.py` | `make lint-structure` | Every required README exists; every SPEC.md unit is complete (fixtures, expected, both tracks, cases.json); every exercise has starter+solution in both tracks and verify.sh; lecture/project/exercise READMEs follow the required H2 section order; no orphan directories |
| `check_links.py` | `make lint-links` | Every relative markdown link and heading anchor resolves. With `--external` (`make lint-links-external`, network required): every http(s) URL answers 2xx/3xx — run before committing a lecture; failing URLs are removed, not marked dead |
| `mermaid-parse.mjs` | `make lint-mermaid` | Every ` ```mermaid ` block in every markdown file parses with the real mermaid parser (headless via jsdom). Node-based by necessity — mermaid's grammar only exists in JavaScript |
| `doctor.py` | `make doctor` | Installed toolchain versions match the repo pins (`.python-version`, `.nvmrc`, `packageManager`) |

The section orders `check_structure.py` enforces are the human-readable lists
in [docs/conventions.md](../../docs/conventions.md) — change them in both
places or not at all.
