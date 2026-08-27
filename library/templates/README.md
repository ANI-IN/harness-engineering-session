# Templates

The nine harness artifacts plus the JSON Schema that validates the feature
list, each a valid, filled-in exemplar. Copy the file, replace the example
content with your project's, keep the structure.

| Template | Purpose | Failure mode it addresses |
| --- | --- | --- |
| [`AGENTS.md`](./AGENTS.md) | Agent entry point and working contract | Agent doesn't know what the system is, how to verify, or when it's done |
| [`CLAUDE.md`](./CLAUDE.md) | Claude Code entry pointer to the same contract | Two drifting instruction files |
| [`feature_list.json`](./feature_list.json) | Machine-readable scope + state | Scope sprawl; "done" with no evidence |
| [`feature_list.schema.json`](./feature_list.schema.json) | The contract for the file above | Feature lists that rot into free-form notes |
| [`init.sh`](./init.sh) | Session initialization: install → verify → next step | Fragile, improvised startup every session |
| [`claude-progress.md`](./claude-progress.md) | Cross-session progress log | Cold-start archaeology at every session start |
| [`session-handoff.md`](./session-handoff.md) | Compact end-of-session note | Weak handoffs; the next session repeats work |
| [`clean-state-checklist.md`](./clean-state-checklist.md) | Session exit gate | Sessions that end "green" but leave debris |
| [`evaluator-rubric.md`](./evaluator-rubric.md) | Checker's scorecard over a maker's work | Self-approval bias |
| [`quality-document.md`](./quality-document.md) | Long-horizon codebase health snapshot | No signal whether weeks of agent work help or hurt |

Motivating lectures (linked as they exist in this release): AGENTS.md is
motivated by [Lecture 02](../../lectures/lecture-02-what-a-harness-actually-is/) and [Lecture 04](../../lectures/lecture-04-why-one-giant-instruction-file-fails/); CLAUDE.md by [Lecture 04](../../lectures/lecture-04-why-one-giant-instruction-file-fails/);
init.sh by [Lecture 06](../../lectures/lecture-06-why-initialization-needs-its-own-phase/); claude-progress.md and session-handoff.md
by [Lecture 05](../../lectures/lecture-05-why-long-running-tasks-lose-continuity/). The remaining templates (feature list
and schema, clean-state checklist, evaluator rubric, quality document)
are motivated by lectures 08, 09, and 12, which arrive with the full
curriculum.

Notes:

- `feature_list.json` is validated against the schema by this repository's own
  test suite; if you edit the template, `make verify` tells you whether it is
  still a valid instance.
- File names are part of the convention: agents are instructed (in
  `AGENTS.md`) to read these files by exact name. Rename them only if you also
  rename them in your instructions.
- Each file's header states its purpose, when to use it, when not to, and the
  course lecture that motivates it.
