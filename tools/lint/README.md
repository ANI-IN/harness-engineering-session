# Lint

Six checkers that keep the repository's conventions true over time. Each
prints what it checked and exits non-zero on any finding; `make lint-*`
targets and CI run them all.

| Tool | Target | Checks |
| --- | --- | --- |
| `check_structure.py` | `make lint-structure` | Every required README exists; every SPEC.md unit is complete (fixtures, expected, both tracks, cases.json); every exercise has starter+solution in both tracks and verify.sh; lecture/project/exercise READMEs follow the required H2 section order; no orphan directories |
| `check_links.py` | `make lint-links` | Every relative markdown link and heading anchor resolves. With `--external` (`make lint-links-external`, network required): every http(s) URL answers 2xx/3xx. Run before committing a lecture; failing URLs are removed, not marked dead |
| `check_prose.py` | `make lint-prose` | No em-dashes (U+2014) or en-dashes (U+2013) in markdown prose, including mermaid node labels; no roadmap language (promising content that does not exist); and no calling this module something it is not (a module is not a sequence of modules). Exempt: code fences, inline code, link targets/URLs, and anything under fixtures/ or expected/ |
| `check_commit_authorship.py` | `make lint-authorship` | CONTRIBUTING.md forbids co-author trailers and tool attributions. The check reads each commit's full body over `main..HEAD`, not `%an`/`%cn`: a trailer lives in the body, so an identity-only check reports green while the trailer sits one field away. Citations to `CLAUDE.md`, `claude-progress.md`, `anthropic.com` and `openai.com` are allowed, since naming a source is not attributing authorship |
| `check_shared_helpers.py` | `make lint-shared-helpers` | Lecture demos duplicate a few helpers rather than importing a shared module, so each demo stays one readable file. Every copy of a registered helper must be byte-identical to the first, or that unit's SPEC.md must carry a `Helper-divergence: <name> (<reason>)` line |
| `mermaid-parse.mjs` | `make lint-mermaid` | Every ` ```mermaid ` block in every markdown file parses with the real mermaid parser (headless via jsdom). Node-based by necessity, because mermaid's grammar only exists in JavaScript |
| `doctor.py` | `make doctor` | Installed toolchain versions match the repo pins (`.python-version`, `.nvmrc`, `packageManager`) |

The section orders `check_structure.py` enforces are the human-readable lists
in [docs/conventions.md](../../docs/conventions.md); change them in both
places or not at all.
