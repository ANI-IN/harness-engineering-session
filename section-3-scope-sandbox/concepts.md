# Section 3: Scope and sandbox. Concepts: what the agent may change and reach

Reading time: about 15 minutes.

## The problem

**Illustrative scenario.** Sam's team runs TeamTrack, a multi-tenant issue tracker. Two people
editing the same issue overwrite each other, so Sam asks a coding agent for version checks: an ETag
on every issue, and a clear error when a save is stale. The ticket lists the files to change: the
issue and audit modules, the board, and the tests.

The agent needs a new error for stale saves. The handbook says errors live in `app/services/errors.py`,
so it adds one there. That module is shared: every endpoint imports it. The ticket's tests pass, and
the reviewer sees a small, tidy change. A month later another team changes how that module maps
errors, and the version checks start answering the wrong status. Nobody thinks of the concurrency
ticket, because it never listed that file.

The list of files was written down, but nothing checked it.

> **Terms on this page**
>
> - **Harness**: The files and code around the agent that decide what it sees and may do.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Referee**: The program that scores each run after the agent stops.
> - **Phase**: One stage of a run: build (write the feature), then test (add tests only).
> - **Allowed paths**: The globs a ticket lists for each phase; the files the agent may change then.
> - **Feature list**: `feature_list.json`, the one feature of the run and its `passes` field.
> - **Out-of-scope file**: A file in the shipped diff that matches none of the allowed paths.
> - **Block**: A patch the scope layer refuses before anything is written; the agent sees `BLOCKED`.
> - **Revert**: A command's change outside the allowed paths, undone right after the command runs.
> - **Sandbox**: The container every tool command runs in, the same for both arms.
>
> All terms: [glossary](../docs/glossary.md).

## The idea in one sentence

Turn the ticket's scope into a boundary that code checks: one feature, a list of files per phase that
the harness enforces, a `passes` field only the harness sets, and a container that limits what any
command can reach.

## How it works

Agents copy what they find: "Codex replicates patterns that already exist in the repository"
([Harness engineering](https://openai.com/index/harness-engineering/)). An agent running
unattended can do damage: one once ran "pkill -9 bash on accident, thus killing itself and ending
the loop" ([Building a C compiler](https://www.anthropic.com/engineering/building-c-compiler)). Anthropic's prompting guide
warns that a model "may take actions that are difficult to reverse or affect shared systems"
([Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)).

Strong words do not check anything. Anthropic's long-running harness told its agent that editing
tests is "unacceptable", and kept the feature list in JSON because "the model is less likely to
inappropriately change or overwrite JSON files compared to Markdown files."
([Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)) "Less likely" is
the point: the wording makes a bad edit rarer, and no code catches the one that happens.

OpenAI's harness team names the alternative: "enforce boundaries centrally, allow autonomy locally."
(Source 1) The agent picks how to build
the feature. The harness decides which files it may touch.

The section has two parts, and they answer different questions:

![Flowchart: a patch to feature_list.json or outside the allowed paths is blocked; a command's changes outside are reverted](diagrams/scope-check-flow.svg)

*A patch is checked before anything is written; a command is checked after it runs.*

### Before and after

**Before: scope in the ticket text.** The bare arm reads the same ticket, spec, and handbook. Nothing
stops a patch to `app/services/errors.py`.

**After: scope as a checked list.** The harness arm gets the same ticket, plus this block in its
context, written from the task's allowed paths:

```markdown
<!-- section-3-scope-sandbox/demo/harness/scope-rules.txt (lines 4-8) -->
Files you may change in each phase:
- build: app/api/issues.py, app/api/schemas.py, app/services/issues.py, app/repositories/issues.py, app/services/audit.py, app/repositories/audit.py, app/web/**, tests/visible/**
- test: tests/visible/**
- any phase: progress.md, session-handoff.md, docs/exec-plans/**
A patch that touches any other file is rejected before it is applied. Changes that a command makes to any other file are reverted after it runs.
```

When it tried the same patch, it got `BLOCKED` and nothing was written. It then put the new error
class in `app/services/issues.py`, a file on the list.

### The four rules of the scope layer

1. **The feature list is the scope.** The harness writes `feature_list.json` before the first
   session: one feature, `passes: false`.
2. **One feature per session.** Anthropic's agent "was then asked to work on only one feature at a
   time." The scope block names that one feature.
3. **Only the harness sets `passes`.** In Anthropic's harness the agent edits the list "only by
   changing the status of a passes field". Here the agent may not edit it at all. It calls `finish`,
   and the harness sets `passes: true` after its own test run: separating the worker from the judge
   "proves to be a strong lever"
   ([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)).
4. **Allowed paths per phase, enforced.** A patch with any path outside the phase's list is refused
   before it applies. After each command, a byte snapshot restores any file outside the list. The test
   phase allows tests only, so the agent cannot make a failing test pass by changing the code.

![Two columns: what the bare arm and the harness arm may change, with the shared tools and sandbox below](diagrams/least-privilege.svg)

*Only the file rights differ between the arms; the tools and the sandbox are the same.*

### The sandbox

Every tool command runs in one container per arm ([docker container run](https://docs.docker.com/reference/cli/docker/container/run/));
the agent loop and the API keys stay on the host.

| Limit | Docker flag | What it stops |
|---|---|---|
| No network | `--network none` | Installs, downloads, any call out |
| Read-only root | `--read-only`, writable `/work` and `/tmp` | Writes outside the workspace |
| Memory, CPU, processes | `--memory 1024m`, `--cpus 2.0` in class, `--pids-limit 256` | Runaway memory, fork bombs |
| Non-root | `--user 1000:1000`, `--cap-drop ALL` | Root inside the container |

![The host holds the agent loop and the keys; the container holds the workspace and has no network](diagrams/sandbox-boundary.svg)

*The model calls leave from the host; the container has no network and never sees the keys.*

With `--network none`, "only the loopback device is created"
([None network driver](https://docs.docker.com/engine/network/drivers/none/)).

Two different refusals come from the two parts:

| | `blocked` | `sandbox_denied` |
|---|---|---|
| Decided by | The scope layer, on the host | The container policy |
| Arms | Harness arm only | Both arms |
| Question | Is this file in scope now? | Can this machine do this at all? |

## How shipharness does it

The scope layer writes the feature list, adds the scope block to every session, checks each patch
and command, and decides `passes`. Every check asks the same method about one path:

```python
# platform/src/shipharness/harness/scope/guard.py (lines 68-78)
    def reason(self, path: str) -> str | None:
        """None if the agent may change `path`; otherwise the reason it sees."""
        rel = normalise(path)
        if rel in HARNESS_ONLY:
            return HARNESS_ONLY[rel]
        if self.state_files and any(glob_matches(rel, p) for p in STATE_FILES):
            return None
        if self.allowed is None or any(glob_matches(rel, p) for p in self.allowed):
            return None
        listed = ", ".join(self.allowed) or "(none)"
        return f"{rel} is outside the allowed paths for the {self.phase} phase ({listed})"
```

The harness's own files come first, so no list can open them; then state files; then the phase's
globs. The returned sentence is what the agent reads after `BLOCKED:`. The
[walkthrough](demo/walkthrough.md) reads the rest.

## What we measured

Before class, the course ran both arms on two tickets: Feature 4: Version checks on issue edits, and
Feature 3: Safe retries for issue creation (a retried create never makes a duplicate). A run fails
when it ships an out-of-scope file; on safe retries, a source edit in the test phase also fails it.

| Ticket and settings | Bare arm: runs failing | Harness arm: runs failing |
|---|---|---|
| Version checks, class settings | 3 of 3 | 0 of 3 |
| Safe retries, plain ticket | 0 of 3 | 0 of 3 |
| Safe retries, with a nearby middleware temptation | 0 of 7 | 0 of 7 |

![Dot chart: on version checks the bare arm failed 3 of 3 runs and the harness arm passed 3 of 3; on safe retries for issue creation all runs passed](diagrams/results-s3.svg)

*On version checks the bare arm left the allowed paths in 3 of 3 runs, the harness arm in 0 of 3.*

On version checks the harness arm was ahead. Every bare arm changed the shared `app/services/errors.py`, and the
scope layer blocked every harness arm on that same file
([evidence](../docs/evidence/s3.md#s3-confirmation)). On safe retries there was no measurable
difference: neither arm ever left the list ([evidence](../docs/evidence/s3.md#s3-pilot)).

Read the version checks result with its limits. Existing tests kept passing in every arm, and no arm
met the feature's own measure. The scope layer kept the change inside the list; it did not make the feature better.

The sandbox is the same for both arms, so no run measures it. It refused no command in any test run
([evidence](../docs/evidence/s3.md#s3-sandbox)).

## When it helps, and when it does not

It helps when:

- A shared file looks like the natural place for the change, as `app/services/errors.py` did on version checks.
- The ticket's files can be listed up front, as globs.

It does not help, or helps less, when:

- The agent already stays inside the list. On safe retries it always did.
- The list is wrong. If the feature truly needs a file that is not listed, the agent must work around
  it, and the result can be worse.
- The change is wrong but in scope. A wrong line in an allowed file passes this check.

Anthropic's harness team gives the test to apply: "every component in a harness encodes an
assumption about what the model can't do on its own, and those assumptions are worth stress testing."
(Source 5) The scope layer assumes
the agent will change files outside the ticket unless code stops it. On version checks that held;
on safe retries it did not.

## Key takeaways

- A list of files in a ticket is a request. A list the harness checks before and after every tool
  call is a boundary.
- Keep the files that grade the agent, such as the feature list, out of its reach, and let the
  harness set `passes` from evidence.
- Measure the bare arm. The harness arm's zero is built in; whether the agent needed the boundary
  shows only in the run without it.

## Check your understanding

1. The bare arm reads the same ticket and allowed paths as text. Why can it still change a file
   outside them?
2. Why does the scope layer check a command's changes after it runs, instead of before?
3. In the demo, where do you see which file left the list?
4. The container refused nothing in any test run. Name one reason to keep it.

<details>
<summary>Answers</summary>

1. Text is not a check. Nothing stops the patch, so the agent's own judgement decides.
2. A shell command can write any file, and its text does not say which. The snapshot comparison sees
   what actually changed, and restores it.
3. On screen 3: the diff map marks the file changed or blocked, and the referee's Files outside the allowed paths (`diff_scope`) row
   gives the count.
4. With no network and a read-only root, a bad command cannot install,
   download, or write outside the workspace.

</details>

## Further reading

- [The feature list as scope](post-class-reading/01-effective-harnesses-feature-list.md).
- [Containers for unattended agents](post-class-reading/02-c-compiler-containers.md).
- [Sandboxes in another agent](post-class-reading/03-codex-sandbox-and-approvals.md).

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
- Source 3: Prompting best practices, <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices>, Anthropic (Claude docs), n.d.
- Source 4: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
- Source 5: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 6: docker container run, <https://docs.docker.com/reference/cli/docker/container/run/>, Docker documentation, n.d.
- Source 7: None network driver, <https://docs.docker.com/engine/network/drivers/none/>, Docker documentation, n.d.
