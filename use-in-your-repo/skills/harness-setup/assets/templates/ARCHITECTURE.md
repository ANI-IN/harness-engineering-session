# Architecture

<!-- A top-level map of domains and package layering ([Harness engineering](https://openai.com/index/harness-engineering/): "Architecture documentation provides a
top-level map of domains and package layering."). Keep this file at the repository root, next to
AGENTS.md. Link to design docs for detail instead of copying it here. Replace every <placeholder>. -->

## Domains

| Domain | What it owns | Code |
|---|---|---|
| <domain> | <the data and behaviour this domain is responsible for> | `<path/>` |
| <domain> | <...> | `<path/>` |

## Layers

Dependencies point in one direction only:

```
<api>  ->  <services>  ->  <repositories>  ->  <db>
```

| Layer | Holds | May import | Must not import |
|---|---|---|---|
| `<api>` | HTTP handlers, request and response models | `<services>` | `<repositories>`, `<db>` |
| `<services>` | Business rules, permission checks | `<repositories>` | `<api>` |
| `<repositories>` | Queries, always scoped to the caller | `<db>` | `<api>`, `<services>` |
| `<db>` | Tables, sessions, migrations | nothing above it | everything above it |

How this is enforced: `<import-linter contract or structural test>` runs in `<command>` and in CI. A
violation fails the build and the message names the import to remove ([Harness engineering](https://openai.com/index/harness-engineering/) enforces layering "via
custom linters ... and structural tests").

## Cross-cutting concerns

Auth, configuration, logging, and telemetry enter through one module: `<path>`. Do not read
settings or create loggers anywhere else. (Source 1 routes cross-cutting concerns through "a single
explicit interface".)

## Patterns to copy

| Task | Copy from |
|---|---|
| New list endpoint | `<path::function>` |
| New write endpoint | `<path::function>` |
| New migration | `<path>` |

## Legacy code: do not copy

| Path | Why it is legacy | Copy this instead |
|---|---|---|
| `<path>` | <what is wrong with it> | `<path>` |

## Where to read more

- Design decisions: [docs/design-docs/index.md](docs/design-docs/index.md)
- Security rules: [docs/SECURITY.md](docs/SECURITY.md)
- Reliability rules: [docs/RELIABILITY.md](docs/RELIABILITY.md)

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world,
  <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
