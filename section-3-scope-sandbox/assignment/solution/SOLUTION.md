# Assignment 3: Scope and sandbox. Solution: scope you can check

This folder is a finished work folder for [Assignment 3](../README.md): the `a3scope` package, the
denial test, the live evidence, and the captured checks. This page explains how it was built and
why. The grader and its hidden cases are not in this repository.

> **Terms on this page**
>
> - **Allowed paths**: The globs a ticket lists for each phase; the files the agent may change then.
> - **Changed path**: A path whose content or existence a diff changes.
> - **Header-only section**: A diff section with no `---`/`+++` lines, such as an empty new file or a mode change.
> - **Refusal**: One path your policy rejects, with a code and a message.
> - **Evidence**: A passing gate result or visible-test run that lets the harness set `passes`.
> - **Deny rule**: A pattern on a command's text that the sandbox refuses before the command runs.
> - **Command position**: The start of a command, or the point right after `;`, `&&`, `|`, or `$(`.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Live evidence**: The files your real A/B run wrote, collected into `live/`.
> - **Referee**: The program that scores each run after the agent stops.
> - **Mutant**: A copy of the code with one small bug planted on purpose; good tests catch (kill) it.

What is in this folder:

| Path | What it is |
|---|---|
| `a3scope/` | `diffparse.py`, `scope.py`, `status.py`, `policy.py`, and the given `sandbox.py` |
| `tests/test_a3_sandbox_rule.py` | The denial test: passes with the rule, fails without it |
| `tests/test_a3_docker_rule.py` | The optional real-container check, as given |
| `live/` | The live A/B's evidence and this package's verdicts on it |
| `captured/` | Real output of the self-check, the checks, and the grades |

## The approach, step by step

1. **Parse first, in one pass.** `diffparse.py` splits lines on `\n` only, because
   `str.splitlines()` also splits on form feeds that can sit inside content. It reads git sections
   and plain unified sections, and skips every hunk by its line counts. Counting is what makes a
   content line such as `--- note` content, not a header.

2. **Take each path from the best source.** Rename and copy lines first, then `---`/`+++`, then the
   `diff --git` line. That last line is the only source for header-only sections, so it is parsed
   with care: quoted names are unquoted, and an unquoted `a/X b/X` is split where both halves are
   equal, as `platform/src/shipharness/ab/artifacts.py` does.

3. **Decide what changed before deciding what is allowed.** `changed_paths` lists added, deleted,
   and modified paths, both sides of a rename, and only the new side of a copy. A copy source is read,
   not changed.

4. **Apply the rules in a fixed order.** `check_diff` walks every path named by the diff. A path
   escape is refused first, for every name, copy sources included: a patch that reads
   `../../home/agent/.netrc` leaks a file even though it changes nothing. Then the harness-only files,
   the state files, a phase with no list, and the phase's globs. A parse failure becomes one
   `unparseable` refusal, so the policy fails closed.

5. **Gate `passes` on evidence, cheapest check first.** `update_status` returns "none" at once when
   there is no done claim for this phase, so a session without a claim runs nothing. With the verify
   layer on, the gate is the evidence and nothing runs again. With it off, the visible tests run once
   and the last pytest summary line decides. The document is deep-copied, so the caller's object never
   changes.

6. **Anchor the history patterns at a command position.** `policy.py` has nine patterns with one
   message and the reason code `write_outside_workspace`. Eight start at a command position, then
   allow `VAR=value` words, `sudo`, a path to the binary, and git's own options; the ninth catches a
   redirect into `.git`. Each stays inside one simple command, so `git status; git log` cannot borrow
   a flag from its neighbour.

7. **Prove the rule with a test that fails without it.** The denial test wraps a fake sandbox in
   `PolicySandbox(policy(), inner)`, runs a history rewrite, and checks the reason code, exit code 126,
   and that the command never reached the inner sandbox.

8. **Run the A/B once, live, after the code was final.** The command from the spec, then
   `live.py collect` and `live.py verify`. Its evidence is in `live/`.

## Design choices and why

- **Interfaces mirror the real code** (`PathRules`, `update_status`, `DenyRule`, `check_command`), so
  the class code and the assignment read the same way. The package still stands alone: grading needs
  no keys, no Docker, and no harness context.
- **Path escapes come before the feature list, and the feature list before any list.** Order is the
  policy. If the allow list came first, a wide glob such as `**` would open the feature list, and the
  agent could mark its own feature as passing.
- **A phase with no list allows the path**, as `PathRules(allowed=None)` does in
  `platform/src/shipharness/harness/scope/guard.py`. Failing closed would be stricter, but learners
  would then learn two rules for one layer.
- **The gate's items must agree with `passed`.** A gate result that says `passed: true` next to a
  failed item is refused. One field alone is weak evidence, which is the point of separating the
  agent that works from the one that judges
  ([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)).
- **The reason code is `write_outside_workspace`**, the closest of the fixed codes in
  `platform/src/shipharness/sandbox/base.py`. The scope layer's snapshot skips `.git`, so a history
  rewrite is a change the harness cannot restore. A production version would add its own code.
- **Revert commands stay allowed.** Anthropic's harness used git "to revert bad code changes and
  recover working states of the code base."
  ([Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)) So
  `git revert`, `git restore`, and `git checkout -- <path>` keep running.

### Known limits

The history rule is a pattern on the command text, so it is a guard rail, not a boundary:

- Git accepts short forms of long options: `git commit --amen` and `git reset --har` get through.
- Aliases and indirection get through: `git -c alias.r=reset r --hard`, or a Python one-liner that
  deletes `.git`.
- A branch name as a reset target (`git reset main`) is allowed; telling it from a file name needs the
  repository.
- A `;` inside a quoted message ends the simple command early, so `git commit -m "a; b" --amend` is
  not refused.

A boundary would need the harness to own history, for example by keeping the evidence commit where
the agent cannot write. The parser also trusts hunk counts: a hand-written patch with wrong counts can
fool it, though `git apply` would then refuse the same patch.

## Alternatives considered

- **List paths with `git apply --numstat`.** Exact for what git will do, but it needs a repository
  and the old files, and it hides the parsing problem the assignment teaches.
- **A shell parser such as `shlex` for the history rule.** It removes the quoting problem, but the real
  policy matches patterns with `re.search`. A word-level check would mean changing
  `platform/src/shipharness/sandbox/policy.py`.
- **Another sandbox rule.** More network refusals only make an existing denial faster, and writes
  outside `/work` already fail on the read-only root. History rewrites are the gap nothing else covers.
- **Refuse copy sources outside the list.** Simpler, but it is a false positive on a test fixture
  copied from application code.

## Common mistakes this avoids

- Reading a `---` content line inside a hunk as a header: hunks are skipped by count.
- Missing a header-only section, such as an empty new file or a mode change: the `diff --git` line is
  the fallback.
- Splitting `diff --git a/x b/y b/x b/y` at the first ` b/`: halves are compared.
- Keeping git's trailing tab or the quotes on a name: both are removed.
- Matching `tests/visible/../../app/x.py` against `tests/visible/**`: `..` is refused before any glob.
- Matching `tests/visible_extra/a.py` or `app/api/issues.py.orig`: globs match whole segments and the
  whole path.
- Trusting `"passed": "true"` or exit code 0 alone: `passed` must be `True`, and the last summary line
  must show no failures.
- Refusing `git commit -m "reset the cache"` or `grep "git reset" docs/`: patterns start at a command
  position.
- Refusing the harness's own `git apply ... .git/shipharness-patch.diff`: no pattern matches it.

The grader's hidden cases cover the same ground with more diffs, commands, and status cases: renames
and copies in and out of scope, quoted and spaced names, binary sections, a phase without a list, and
a dozen ways a test run or a gate can look like a pass without being one.

## Run and verify it

From the repository root. These commands need no keys; the last one needs Docker:

```bash
make check-assignment-3 A3_IMPL=section-3-scope-sandbox/assignment/solution
uv run python section-3-scope-sandbox/assignment/live.py verify --impl section-3-scope-sandbox/assignment/solution
uv run python -m pytest -q -p no:cacheprovider -m docker section-3-scope-sandbox/assignment/solution/tests
```

> Your output will differ: your own A/B runs other agent sessions, so its counts, cost, and verdicts
> will not match the ones below.

The self-check prints every row `ok` (`A3` in the output is Assignment 3; the full output is in
`captured/check-solution.txt`):

```text
A3 self-check: section-3-scope-sandbox/assignment/solution
  check                                              visible tests  status  where
  diff parsing and path matching                             28/28  ok
  out-of-scope diffs rejected                                  8/8  ok
  legitimate diffs accepted                                    6/6  ok
  passes set with evidence                                     2/2  ok
  passes kept false without evidence                           5/5  ok
  history rule denies                                          8/8  ok
  history rule allows (no false positives)                     6/6  ok
  your denial test passes                                           ok
  your denial test fails with the rule removed                      ok
  your denial test uses check_command/PolicySandbox                 ok
  live A/B evidence (live/)                                         ok      live/
```

The live verification and the container check (`captured/verify-solution.txt`,
`captured/docker-solution.txt`):

```text
A3 live evidence: section-3-scope-sandbox/assignment/solution/live
  evidence  ok
  verdicts  ok
2 passed, 9 deselected in 11.28s
```

## Evidence

The live A/B ran once, with the class model and caps, as in
[SPEC.md, "Evidence to hand in"](../SPEC.md#evidence-to-hand-in). Its output, with the run id cut
(the full output is in `live/ab-output.txt`); `F3` is the code of its ticket, Feature 3: Safe
retries for issue creation:

```text
A/B <run id> (F3, layers=['instructions', 'scope', 'state'], profile=standard)
  bare     completed         claim=done     primary={"out_of_scope_files": 0, "test_phase_source_edits": 0} passed=True hidden 49/49 mutants 4/4 reviewer=reject cost=$0.0086
  harness  ABORTED: timeout  claim=done     primary={"out_of_scope_files": 0, "test_phase_source_edits": 0} passed=True hidden 49/49 mutants 0/4 reviewer=reject cost=$0.0073
Cost: $0.021708 (this command: gpt-5.6-luna $0.005858, gpt-6-luna $0.015850; ...)
```

Both arms stayed inside the allowed paths. This package's verdicts agree with the referee on the bare
arm. On the harness arm, its build-phase verdict refuses `feature_list.json`, because the harness set
`passes` during the run; the referee removes harness files before it counts. For an agent's patch,
the package is right to refuse that file. For a whole-run diff, the referee is right to ignore it.
One run per arm is an example, not a rate.

The instructor's grade of this folder, from `make grade-assignment-3
SUBMISSION=section-3-scope-sandbox/assignment/solution` (the full output is in
`captured/grade-solution.txt`):

```text
A3 grade: section-3-scope-sandbox/assignment/solution
  criterion                                              tests         points
  1 Diff parsing and path matching                               15.0 / 15
  2 Diff-scope policy                                            40.0 / 40
  3 Evidence-gated status                                        15.0 / 15
  4 Sandbox history rule                                         10.0 / 10
  5 Denial test proves the denial                                10.0 / 10
  6 Live A/B evidence (live/)                                    10.0 / 10
  Total                                                         100.0 / 100
  Every out-of-scope diff rejected: yes; zero false positives: yes; live evidence valid: yes
Result: PASS (needs >= 80 points, every out-of-scope diff rejected, zero false positives, and valid live evidence)
```

The grade output is cut to the criterion lines. Without `live/`, the same folder scores 90.0 / 100
and fails, because valid live evidence is a pass condition. Dates and ids for the run and the grade
are on the [evidence page](../../../docs/evidence/s3.md#s3-a3-solution).

## Sources

- Source 1: Harness design for long-running application development, <https://www.anthropic.com/engineering/harness-design-long-running-apps>, Prithvi Rajasekaran (Anthropic), 2026-03-24
- Source 2: Effective harnesses for long-running agents, <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>, Justin Young (Anthropic), 2025-11-26
