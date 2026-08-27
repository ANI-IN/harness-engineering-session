# SPEC: project-01 baseline-vs-minimal-harness

Two contracts live here. First, the **kb app**: a local knowledge-base
tool (CLI + loopback HTTP server) whose four features are assertable by
command, replacing the reference course's Electron GUI (see README,
"Overview", for the deviation rationale). Second, the **controlled
experiment**: a deterministic fake agent performs the same build task
twice, without and with the minimal harness, and the difference is
measured, not narrated.

Both implementations (`solution/python/main.py`,
`solution/typescript/main.ts`) must produce byte-identical output after
normalization for every case in `cases.json`.

Starter-shape: non-code (declared). The starter is the weak experimental
condition, a task prompt and nothing else; there is deliberately no
starter implementation in either track. `lint-structure` accepts this
shape only because this marker line declares it.

## The `kb` canonical command form

Every command in this project is written as `kb <subcommand> ...`. Each
track expands the prefix:

| Track | `kb` expands to |
| --- | --- |
| Python | `uv run python <project>/solution/python/main.py` (from the repository root) |
| TypeScript | `pnpm exec tsx <project>/solution/typescript/main.ts` (from the repository root) |

Evidence entries and experiment reports use the canonical form so they are
identical across tracks; commands run from the repository root because
unit directories deliberately carry no package manifest (`pnpm exec`
resolves tools from the root workspace). The conformance cases execute the same
subcommands through both real CLIs, which is what makes the notation
honest.

## CLI surface

```text
kb init --data-dir DIR [--seed SRC]     # create DIR, DIR/documents, DIR/index; copy SRC's *.md/*.txt in
kb list --data-dir DIR                  # document inventory, JSON
kb ask --data-dir DIR "QUESTION"        # grounded answer with citations, JSON
kb serve --data-dir DIR [--port N] [--self-check]
kb experiment [--workdir DIR]           # the controlled experiment (below)
```

| Exit code | Meaning |
| --- | --- |
| 0 | success |
| 1 | data directory not initialized (`list`, `ask`, `serve`); experiment control violated |
| 2 | usage error, unknown subcommand, unreadable seed directory, invalid port |

Error messages are pinned because the experiment report embeds one:
an uninitialized data directory produces exactly
`error: data directory DIR is not initialized; run kb init first` on
stderr with empty stdout.

## Output shapes

- `init`: `{"data_dir", "created": [paths], "seeded": [filenames]}`; paths
  are POSIX-relative exactly as given on the command line; re-running
  reports only what was newly created or seeded (idempotent).
- `list`: `{"documents": [{"id", "title", "filename", "lines"}]}` sorted
  by `id`. `id` is the filename without extension; `title` is the first
  markdown title line (`#` plus a space) or the filename; `lines` counts content lines with trailing
  newlines stripped.
- `ask`: `{"question", "citations": [{"document", "title", "line",
  "excerpt", "score"}], "answer"}`.
- `serve --self-check`: `{"self_check": {"health": {"status",
  "documents"}, "documents"}}` where `health` is the parsed `/health`
  response fetched over a real loopback socket on an ephemeral port; the
  port never appears in the output.

JSON object key order inside `observed` evidence strings is part of this
contract (those are strings, so the normalizer cannot re-sort them): keys
appear exactly in the orders listed above.

## Retrieval semantics (pinned)

1. Tokenize question and candidate identically: lowercase, ASCII
   alphanumeric runs (`[a-z0-9]+`), keep tokens of length >= 4.
2. Candidates are the non-empty lines (after trimming) of every stored
   document; line numbers are 1-based over the raw file.
3. Score = number of **distinct** question tokens present in the
   candidate's token set. Repetition never adds.
4. Rank by score descending, then document id ascending, then line number
   ascending; keep the top 2 with score >= 1.
5. The answer composer is deterministic and is the **model seam**: with
   citations, exactly
   `Based on "TITLE" (line N): EXCERPT` plus, when a second citation
   exists, a space followed by `See also "TITLE2" (line M).`; with none,
   exactly
   `No matching lines in the document set. Import more documents or
   rephrase the question.` A real model may replace the composer but must
   preserve the citation contract and the no-match refusal.

## HTTP surface

`GET /health` -> `{"status": "ok", "documents": N}` ·
`GET /documents` -> the `list` payload · `GET /ask?q=...` -> the `ask`
payload · anything else -> 404 `{"error": "not found"}`. Loopback
(`127.0.0.1`) only; the server calls the same functions as the CLI.

## The controlled experiment

`kb experiment` runs the fake agent twice in isolated working directories
under `--workdir` (default: a private temp directory, removed afterwards)
and prints one report. Protocol, in order:

1. **Weak run** (`runs/weak`): seed the task prompt
   (`starter/task-prompt.md`) and the corpus
   (`fixtures/kb-data/documents`). No harness files. Run the weak agent.
   Archive its record, then delete the directory.
2. **Strong run** (`runs/strong`): created only after the weak directory
   is gone. Seed the same prompt bytes and the same corpus, plus the
   harness seed (`harness/`: AGENTS.md, CLAUDE.md, init.sh,
   feature_list.json, claude-progress.md, docs/). **Reset the checked-in
   evidence** before the agent starts: every feature to `not-started`,
   evidence entries removed, progress log cleared to its title line. Run
   the strong agent. Archive, delete.
3. Emit the report. If any control failed, exit 1 instead.

### Controls (measured, not asserted in prose)

| Report field | What it proves |
| --- | --- |
| `controls.isolated_directories` | the strong directory did not exist when the weak run started |
| `controls.weak_deleted_before_strong` | the weak directory was gone before the strong one was created |
| `controls.evidence_reset_applied` | after reset, no feature was `passing` and none carried evidence |
| `controls.identical_prompts` | both runs were seeded from the same prompt bytes (`prompt_sha256` is that hash) |
| `controls.identical_corpus` | sha256 over each run's seeded corpus (sorted filename + bytes) matched |

### The fake agent (deterministic; the agent seam)

The fake agent stands exactly where a model-driven agent would: same
working directory, same prompt, same files. Its behavior is scripted:

- **Weak** (no harness found): derives its goals from the prompt's nouns
  alone (`document-list`, `question-answer`); materializes the app source;
  runs one smoke check, `kb list --data-dir kb-data`, which exits 1
  because nothing told it initialization is a phase; ships anyway, writing
  SUMMARY.md and claiming success. `premature_done: true`.
- **Strong** (harness found): follows AGENTS.md's startup order,
  materializes the app source, then walks `feature_list.json` in order,
  executing each feature's declared `verification` command and recording
  `evidence` `{command, observed, date}` on exit 0, where `observed` is
  `exit N:` then a space then the command's compact stdout (or its stderr
  when stdout is empty). Updates the progress log with the session and the next best
  step. `premature_done: false`.

Canonical commands are executed in-process against the run's working
directory (relative paths resolve exactly as a shell invocation would);
the conformance cases prove the identical commands behave the same
through the real CLIs. Replacing `fake_agent_weak` / `fake_agent_strong`
(`fakeAgentWeak` / `fakeAgentStrong`) with calls to a real agent is the
documented plug-in point and changes nothing else.

### Determinism rules

No wall clock (`date` fields use the pinned experiment date 2026-08-27),
no randomness, no network beyond the loopback self-check, no absolute
paths in any output. The report is byte-identical across tracks and
across machines; `expected/experiment.json` pins it.

### Report schema

```json
{
  "task": "...",
  "prompt_sha256": "...",
  "controls": {"...": true},
  "weak":   {"harness_files_found": [], "app_materialized": true,
             "features_attempted": [], "features_verified": [],
             "verification_runs": [{"command", "exit", "observed"}],
             "claims": [], "premature_done": true},
  "strong": {"... same fields ...", "feature_list_final": {"...": "..."}},
  "comparison": {"features_verified": {"weak", "strong"},
                 "verification_runs": {"weak", "strong"},
                 "premature_done": {"weak", "strong"},
                 "missing_when_done_declared": {"weak": [], "strong": []},
                 "unverified_but_claimed": {"weak": [], "strong": []}}
}
```

`strong.feature_list_final` must equal the committed
`harness/feature_list.json` (the committed evidence is the machine-derived
product of this run; the test suites assert the equality), and
`harness/feature_list.json` must satisfy
`library/templates/feature_list.schema.json`.

## Cases

`cases.json` covers: init creating and seeding (plus a byte-check that a
seeded document equals its fixture), the document list, the
uninitialized-directory failure (exit 1), a grounded answer with two
citations (exercising the score and both tie-break keys), the no-match
refusal, the HTTP self-check, a usage error (exit 2), and the full
controlled experiment.

## Tests

`solution/python/tests/` (pytest) and `solution/typescript/tests/`
(vitest) cover tokenization and scoring rules, tie-breaks, title
fallback, init idempotency, the evidence-reset control, the
isolated-directories control, the canonical command splitter, and the
committed-evidence equality above. Additionally, an **independent
evidence check** in each suite executes every feature's evidence command
through the real CLI as a subprocess in a fresh working copy, with the
experiment runner and its fake agent entirely out of the loop, and
asserts the output equals the recorded `observed` string; the committed
evidence is thereby true on its own, not merely consistent with its
generator. `make verify` runs both suites.
