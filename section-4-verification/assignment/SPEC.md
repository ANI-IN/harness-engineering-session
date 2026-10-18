# Assignment 4: Verification. Specification: verification and portfolio

The full requirements for [Assignment 4](README.md). The README gives the story and the steps; this
page is the reference you check your work against.

> **Terms on this page**
>
> - **Implementation folder**: The folder you submit; `section-4-verification/assignment/starter/` unless you pass `A4_IMPL=` to make.
> - **Check**: A shipharness program that probes every endpoint for one rule and reports findings.
> - **Finding**: One violation a check reports, with a rule, an endpoint, a severity, and a detail key.
> - **Baseline**: The findings on the unchanged checkpoint; a check counts only new ones.
> - **Soft delete**: Marking a row as deleted (`deleted_at`) instead of removing it.
> - **Marker**: A title only a soft-deleted test issue carries, so a response that shows it is evidence.
> - **Candidate test**: One test function that a filter judges, with its file and test id.
> - **Referee**: The program that scores each run after the agent stops.
> - **Score record**: The file the referee writes for each run, with every measured result.
> - **Live evidence**: The files your real runs wrote, collected into `live/`.

> Your output will differ: the examples on this page come from the course's reference solution, not
> from your files.

## Inputs

- The rule, from `platform/teamtrack/docs/HANDBOOK.md`: "Deleting an issue is a soft delete: it sets
  `deleted_at`, and deleted issues behave as if they do not exist (404 on read, hidden from lists)".
- The code you extend. Print the two walkthrough excerpts with
  `uv run python platform/scripts/anchors.py extract S4:probe` (how the tenant isolation check plans
  probes and judges one response) and `... extract S4:filters` (the filter pipeline); `S4:probe` and
  `S4:filters` are the names of those marked excerpts.
- The framework files: `platform/src/shipharness/checks/base.py` (`Finding`, `CheckContext`, the
  registry, `mark_baseline`), `checks/_http.py` (`open_target`, `apply_exemptions`),
  `checks/payloads.py` (`fill_path`, generated bodies), `checks/adapter.py` (the TeamTrack adapter),
  and `filters/models.py` (the filter protocol).
- For the live step: your keys in `.env`, Docker for the A/B, and the checkpoint tag `m1-s4-start`
  (the repository state at the start of Section 4: Verification) in your clone (`git tag` lists it).

## Files you must produce

```text
section-4-verification/assignment/starter/   your implementation folder
  a4_verification/
    __init__.py          imports the check (registration) and the filter
    adapter.py           soft_delete
    r8_soft_delete.py    issue_param, plan, judge
    dedup_filter.py      normalized, NoDuplicateTest
    run_r8.py            CLI over the shipharness check runner (complete)
    apply_filter.py      CLI: filter 6 over a testgen output folder (complete)
  tests/                 at least 8 tests of your own
  skill/<your-skill>/    one skill, from use-in-your-repo/skills/skill-template
  portfolio/             evidence-report.md, langsmith.md, case-study.md
  live/                  testgen.txt, testgen-report.json, ab.txt, scores/<run_id>.json
```

## Requirements

### The check for House rule 8: Deleted issues stay hidden

Registered as `r8_soft_delete` with `rule = "R8"` through `shipharness.checks.register_check`.

1. Endpoints come from `open_target`, which reads the app's OpenAPI schema. Never list them by hand.
2. Before probing, the adapter soft-deletes the lowest-id live issue of each of the home org's
   projects and gives each a marker title. The first id it returns is the one path and body probes
   use. A response contains a deleted issue when it contains that issue's marker.
3. An endpoint addresses one issue when its path has `{issue_id}`, or a parameter with no resource
   name (such as `{id}`) whose closest literal segment before it is `issues`. `{project_id}`,
   `{user_id}`, and other `*_id` names never address an issue.
4. Probes run as the home org's admin, lists first:
   - `deleted_list`: every GET endpoint that does not address one issue. Fails when the status is
     2xx and the body contains a marker.
   - `deleted_body`: every write endpoint that does not address one issue and whose generated body
     has an `issue_id` key, sent with the deleted id. Fails when the status is 2xx.
   - `deleted_path`: every endpoint, any method, that addresses one issue, called with the deleted
     id. Fails unless the status is 404.
5. Each failure is one `Finding` with `rule="R8"`, `endpoint` set to the endpoint's label (such as
   `GET /issues/{issue_id}`), `detail_key` set to exactly the probe kind, severity `leak` when a 2xx
   body contains a marker and `violation` otherwise, and a one-line `detail` that says what to change.
6. A numeric id alone is not evidence: project 1, user 1, and org 1 share the deleted issue's id.
7. Findings pass through `apply_exemptions(findings, ctx)`; the result is built with `make_result`;
   progress goes through `ctx.progress`. The check never calls a model.
8. On TeamTrack as shipped, the only counted finding is `GET /v1/issues` with `deleted_list`.

Example: the check on TeamTrack with the reference solution, 15 probes, one finding (the JSON document cut
to the finding, `...` marks the cut; exit code 3):

```text
{"results": [{"check": "r8_soft_delete", "passed": false, "new_violations": 1, "baseline_violations": 0, "total_probes": 15, "findings": [{"rule": "R8", "severity": "leak", "endpoint": "GET /v1/issues", "detail": "GET /v1/issues -> 200 lists soft-deleted issue(s) [1, 11]; add `deleted_at IS NULL` to the query (HANDBOOK: deleted issues are hidden from lists)", "detail_key": "deleted_list", "baseline": false}], ...}]}
```

With that output as `--baseline`, the same finding shows `"baseline": true`, `"new_violations": 0`,
and the command exits 0.

### Filter 6: No duplicate tests

The class is `NoDuplicateTest`, with `number = 6`, a `name`, and `evaluate(cand, ctx) -> FilterResult`.
It follows a later filter of Meta's test generator that removes "previously seen test cases"
([Automated Unit Test Improvement using Large Language Models at Meta](https://arxiv.org/abs/2402.09171));
ignoring renamed local variables is the course's addition.

1. The constructor takes the existing suite's tests as candidate tests (for example from
   `shipharness.filters.collect_candidates`). `evaluate` reads source only; it never runs a test.
2. Two tests are duplicates when their decorators, parameters, and bodies are equal as syntax trees
   after ignoring the function name, comments, and layout, dropping a docstring, and renaming every
   local variable to a placeholder in order of first appearance. A local is a name bound in the body
   by `=`, `+=`, an annotated assignment, `for`, `with ... as`, `:=`, a comprehension, or
   `except ... as`. Parameters, globals, imported names, attributes, and literals keep their names.
3. A candidate that repeats an existing test (other than one with the same test id), or a candidate
   this instance kept earlier, is discarded, and the reason names that test's id. A candidate whose
   file does not parse, or that has no such function, is discarded with a reason. Anything else is
   kept.
4. Every result has `filter=6`, the candidate's `test_id`, and a non-empty reason.

Example: one existing test, and three tests testgen kept, where the first repeats the existing test
and the third repeats the second.

```python
# repo/tests/test_lists.py (the existing suite)
def test_projects_envelope(admin_client):
    body = admin_client.get("/projects").json()
    assert set(body) == {"items", "next_cursor"}

# kept/tests/test_generated.py (kept by testgen)
def test_project_list_shape(admin_client):
    """The list has the standard envelope."""
    data = admin_client.get("/projects").json()  # one page
    assert set(data) == {"items", "next_cursor"}


def test_project_list_first_page_has_no_cursor(admin_client):
    body = admin_client.get("/projects").json()
    assert body["next_cursor"] is None


def test_project_list_no_cursor_again(admin_client):
    page = admin_client.get(
        "/projects"
    ).json()
    assert page["next_cursor"] is None
```

`apply_filter --update-report` on those folders printed:

```text
- tests/test_generated.py::test_project_list_shape: filter 6: duplicate of existing test tests/test_lists.py::test_projects_envelope (equal after ignoring names, docstring, comments, and layout)
+ tests/test_generated.py::test_project_list_first_page_has_no_cursor: filter 6: no duplicate among 1 existing tests and 0 earlier kept candidates
- tests/test_generated.py::test_project_list_no_cursor_again: filter 6: duplicate of earlier candidate tests/test_generated.py::test_project_list_first_page_has_no_cursor
filter 6 kept 1 of 3 kept tests (1 existing tests compared; 0 kept ids not found)
```

### Live evidence

The grader checks these files without a model call:

1. **testgen run.** The command is `shipharness testgen ... --out <dir>`. The output has one
   `testgen <run_id>: <status>; kept N of M proposed tests` line that matches the report, and one
   `Cost: $X (testgen, model gpt-6-luna)` line with X above 0 and at most $0.20.
2. **Filter 6 in the report.** testgen kept at least one test. The report has exactly one row with
   `"filter": 6` and a reason per kept test, after all rows of filters 1 to 5, plus a `filter6`
   object whose `kept` lists the tests those rows passed.
3. **A/B command and cost.** The command is `shipharness ab --section demo-4 --feature F4 --purpose
   assignment --no-preview`, where `F4` is Feature 4: Version checks on issue edits (`--k 1`, `--reviewer`, or
   `--no-reviewer` may be added). The output has
   one `A/B` line with the four layers of demo-4, and one `Cost:` line of at most $2.50 that names
   `gpt-6-luna` and no model other than it and the reviewer's `gpt-5.6-luna`.
4. **A/B score records.** Exactly two, each valid and named `<run_id>.json`: one bare arm and one
   harness arm, both with the `ab_id` that `ab.txt` printed, feature `F4`, variant `canonical`,
   checkpoint `m1-s4-start` at the commit the tag names, `recorded` false, `sandboxed` true, arm cost
   at most $0.20, review cost at most $0.04, and the status `ab.txt` printed for that arm.

The live runs are not graded on their results. An arm that fails its primary measure still counts.

### Portfolio and skill

- `portfolio/evidence-report.md`: sections `## Target`, `## Commands`, `## Results` (with a table),
  `## Filter 6 on the kept tests`, `## House rule 8 on TeamTrack`, `## Limits`; it mentions
  `shipharness testgen` and `run_r8`.
- `portfolio/langsmith.md`: sections `## Trace links` (a `https://smith.langchain.com/` link that is
  the `trace_url` or `referee_trace_url` of one of your two score records), `## Command` (mentions
  `shipharness ab`), and `## What the comparison shows`.
- `portfolio/case-study.md`: sections `## Problem`, `## What I built`, `## Evidence`,
  `## What I learned`, `## Next steps`; 250 to 700 words.
- No leftover template line in any portfolio file.
- `skill/`: exactly one folder whose `SKILL.md` passes `shipharness skills validate`, is not named
  `skill-template`, has no template placeholder left, and has content under "When to use" and
  "Steps" ([Agent Skills specification](https://agentskills.io/specification)).

## Self-check

| What | Command |
|---|---|
| The self-check | `make check-assignment-4` (another folder: `make check-assignment-4 A4_IMPL=<dir>`) |
| Without make | `uv run python section-4-verification/assignment/check.py --impl <dir>` |
| Your tests | `PYTHONPATH=<dir> uv run python -m pytest -q -p no:cacheprovider <dir>/tests` |
| The visible tests, full output | `A4_IMPL=<dir> uv run python -m pytest -q -p no:cacheprovider section-4-verification/assignment/visible_tests` |
| The House rule 8 check on TeamTrack | `PYTHONPATH=<dir> uv run python -m a4_verification.run_r8 --build platform/teamtrack --checkpoint m1-base --feature A4` |
| The skill validator | `uv run shipharness skills validate <dir>/skill` |

On a finished folder the self-check prints `self-check: PASSED (23/23 visible tests pass)` and exits
0. Four of those tests check the live evidence; they fail until `live/` is filled.

## Evidence to hand in

| Path | What it is |
|---|---|
| `live/testgen.txt` | First line `$ <the exact testgen command>`, then everything it printed |
| `live/testgen-report.json` | The report from the testgen `--out` folder, after `apply_filter --update-report` |
| `live/ab.txt` | First line `$ <the exact ab command>`, then everything it printed |
| `live/scores/<run_id>.json` | The two score records that A/B wrote to `exports/scores/` |

### Run the live step

Needs your keys; the A/B also needs Docker. These are the commands the reference solution ran, with
`IMPL` set to your folder. Use a pinned target, as here, or your own repository with
`--repo <repo> --module <pkg/module.py> --tests <tests/test_module.py>` in place of `--target`:

```bash
IMPL=section-4-verification/assignment/starter
export PYTHONPATH=$IMPL
mkdir -p $IMPL/live/scores
echo '$ uv run shipharness testgen --target TG-teamtrack-app-repositories-issues --max-tests 10 --out .shipharness/a4/testgen' > $IMPL/live/testgen.txt
uv run shipharness testgen --target TG-teamtrack-app-repositories-issues --max-tests 10 --out .shipharness/a4/testgen 2>&1 | tee -a $IMPL/live/testgen.txt
uv run python -m a4_verification.apply_filter --repo platform/teamtrack --kept .shipharness/a4/testgen --existing tests/visible/test_tenant_isolation.py --existing tests/visible/test_issues.py --existing tests/visible/test_legacy_and_schema.py --update-report
cp .shipharness/a4/testgen/testgen-report.json $IMPL/live/
echo '$ uv run shipharness ab --section demo-4 --feature F4 --purpose assignment --no-preview' > $IMPL/live/ab.txt
uv run shipharness ab --section demo-4 --feature F4 --purpose assignment --no-preview 2>&1 | tee -a $IMPL/live/ab.txt
AB=$(grep -o 'ab-[0-9]\{8\}-[0-9]\{6\}-[0-9a-f]\{6\}' $IMPL/live/ab.txt | head -1)
grep -l "\"ab_id\": \"$AB\"" exports/scores/*.json | xargs -I{} cp {} $IMPL/live/scores/
```

Without `--image`, testgen runs the generated tests on your machine and prints an UNSANDBOXED
warning. Keep `--purpose assignment` on the A/B: without it the command uses the class purpose, which
refuses to start unless `SHIPHARNESS_CLASS_DATE` is set. If testgen keeps no test, Filter 6 has
nothing to show; run it once more on another module, inside the budget.

## Limits

- Work only in your implementation folder. Do not edit `platform/src/shipharness/`,
  `platform/teamtrack/`, or the visible tests.
- Keep the check name `r8_soft_delete`, the class name `NoDuplicateTest`, and the package name
  `a4_verification`.
- The House rule 8 check runs in process on a TeamTrack copy: no Docker, no network, no model calls.
- One testgen run and one A/B. Every run counts: never re-run for a nicer result, and paste only real
  output into the portfolio.

### Cost and trace budget

| Step | OpenAI | LangSmith traces |
|---|---|---|
| The House rule 8 check, Filter 6, the self-check, the grader | $0 | 0 |
| `shipharness testgen` | At most $0.20 (the per-run cap) | 1 |
| The A/B on Feature 4: 2 arms, 2 reviews | At most $0.48 (two arm caps and two review caps) | 4 |

The caps are in `platform/src/shipharness/config/settings.py` and `.env.example`. The reference
solution's live step cost $0.045425 in all; its output is in [solution/SOLUTION.md](solution/SOLUTION.md#evidence).

### Common mistakes

- Matching deleted issues by numeric id. Project 1 and user 1 share the id, so project lists become
  findings.
- Probing only GET endpoints. A write that resolves a deleted issue (transition, assign) is the same
  violation.
- Hard-coding endpoint paths. The check must cover endpoints that exist only in the build.
- Putting a random value or response text in `detail_key`. Findings then never match the baseline,
  and the legacy finding counts against every arm.
- Comparing tests as text. Formatting and comments change the text, not the test.
- Renaming fixture parameters in Filter 6. `client` and `admin_client` are different fixtures.
- Running `apply_filter` without `--update-report`, or copying the report before running it.
- Copying score records from another A/B or from a replay. The grader matches them to the `ab_id` in
  `live/ab.txt`.
- Editing a transcript. Run ids, kept counts, statuses, and costs are checked against the JSON files.

## Sources

- Source 1: Automated Unit Test Improvement using Large Language Models at Meta, <https://arxiv.org/abs/2402.09171>,
  Alshahwan et al. (Meta), 2024-02-14
- Source 2: Agent Skills Specification, <https://agentskills.io/specification>, Agent Skills project, n.d.
