# Evidence report: generated tests for TeamTrack's issue repository, and House rule 8: Deleted issues stay hidden

Reference version, with Filter 6: No duplicate tests. "Results" and the Filter 6 section come from
the reference solution's live run, captured on 2026-10-17 (files in `../live/`, run id on the
[evidence page](../../../../docs/evidence/s4.md#s4-a4-solution)); everything in the House rule 8
section is real output with no model call.

## Target

- Dataset target `TG-teamtrack-app-repositories-issues` from `platform/datasets/testgen-targets-v1.jsonl`:
  module `app/repositories/issues.py` in `platform/teamtrack/` (pin `m1-base`, the checkpoint tag of
  TeamTrack as shipped).
- Existing tests (from the target line): `tests/visible/test_tenant_isolation.py`,
  `tests/visible/test_issues.py`, `tests/visible/test_legacy_and_schema.py`.
- Filter mutants: `platform/teamtrack/mutants/app.repositories.issues.jsonl#filter` (2 of the file's 4
  mutants). One of them, `app.repositories.issues-m3`, is "soft-deleted issues still listed": the
  same fault the House rule 8 check looks for, at the unit level.
- Why this module: it holds the live-issue lookups (`get`, `list_for_project`) that every House
  rule 8 finding in this assignment traces back to.

## Commands

```bash
uv run shipharness testgen --target TG-teamtrack-app-repositories-issues --max-tests 10 \
    --out .shipharness/a4/testgen
export PYTHONPATH=section-4-verification/assignment/solution
uv run python -m a4_verification.apply_filter --repo platform/teamtrack --kept .shipharness/a4/testgen \
    --existing tests/visible/test_tenant_isolation.py --existing tests/visible/test_issues.py \
    --existing tests/visible/test_legacy_and_schema.py --update-report
python section-4-verification/assignment/solution/skill/testgen-evidence/scripts/summarize_report.py \
    .shipharness/a4/testgen/testgen-report.json
uv run python -m a4_verification.run_r8 --build platform/teamtrack --checkpoint m1-base --feature A4
```

The testgen command runs without `--image`, so generated tests run on the host and the command
prints an UNSANDBOXED warning. The other three commands make no model calls. `--update-report`
writes the filter-6 rows into `testgen-report.json`, so the summary table counts Filter 6 too;
the command's transcript and the report are the live evidence in `../live/`.

## Results

The testgen run (`../live/testgen.txt`): status `completed`, "kept 1 of 5
proposed tests". The table is the output of `summarize_report.py` on `../live/testgen-report.json`,
the report after `apply_filter --update-report`, with the run id moved to the evidence page:

| Measure | Value |
|---|---|
| Run id | [on the evidence page](../../../../docs/evidence/s4.md#s4-a4-solution) |
| Status | completed |
| Proposed tests (evaluated) | 5 |
| Kept by testgen (filters 1-5) | 1 |
| Not evaluated (over --max-tests) | 0 |
| Kept after Filter 6 | 1 |
| Discarded by Filter 3: Adds coverage or catches a mutant | 4 |

All five proposed tests passed Filter 1: Builds and collects ("collected 1 test") and Filter 2:
Passes five runs ("passed 5 of 5 runs"). Filter 3 discarded four of them, each with the same reason: "adds no line coverage over the
existing suite and kills no filter-set mutant that the existing tests miss (0 checked)":

- `test_add_flushes_issue_with_requested_fields_and_database_defaults`
- `test_get_returns_only_live_issues_for_the_requested_organization`
- `test_list_for_project_filters_tenant_project_and_soft_deleted_rows`
- `test_list_all_legacy_orders_and_pages_across_tenants_including_deleted`

The kept test, `tests/visible/test_issue_repository.py::test_list_for_project_uses_ascending_keyset_pages`,
passed Filter 3 with "adds 3 covered lines: app/repositories/common.py:11,17-18", Filter 4: Real
assertions with "has real assertions and does not mock app.repositories.issues", and Filter 5: No
source changes with "no source file
changed during the test phase". Two of the discarded tests name deleted rows
(`..._soft_deleted_rows`, `..._including_deleted`). Filter 3 judges what a test adds over the
existing suite, not its subject: those lines were covered already, and "0 checked" means the
existing tests already kill both filter-set mutants, so none was left to try
(`AddsCoverageOrKillsMutant` in `platform/src/shipharness/filters/filters.py`).

The cost line the testgen command printed:

```
Cost: $0.003287 (testgen, model gpt-6-luna)
```

## Filter 6 on the kept tests

`apply_filter --update-report` added one filter-6 row to the report, after the 17 rows of filters
1-5, for the one kept test:

| Test | Filter 6 | Reason |
|---|---|---|
| `test_list_for_project_uses_ascending_keyset_pages` | passed | no duplicate among 23 existing tests and 0 earlier kept candidates |

Filter 6 kept 1 of 1 (`filter6.kept` lists that test, `filter6.existing_tests` is 23) and removed
no test as a duplicate. With one kept test there was no earlier kept candidate to compare it with,
so this run shows the filter against the existing suite only; the duplicate cases are in the
reference solution's own tests (`../tests/test_dedup_filter.py`).

## House rule 8 on TeamTrack

Real output of the last command above on `platform/teamtrack/`; the full JSON document is in
`../captured/r8-teamtrack.json`.

| Field | Value |
|---|---|
| `check` | `r8_soft_delete` |
| `passed` | `false` |
| `new_violations` | 1 |
| `total_probes` | 15 |
| Finding | `R8`, `leak`, `GET /v1/issues`, `detail_key` `deleted_list` |

The finding's `detail` reads: "GET /v1/issues -> 200 lists soft-deleted issue(s) [1, 11]; add
`deleted_at IS NULL` to the query (HANDBOOK: deleted issues are hidden from lists)".

The one finding is the legacy `/v1/issues` handler, which reads every row through
`list_all_legacy` with no `deleted_at` filter. It exists at the checkpoint, so it belongs in the
baseline: rerunning with `--baseline` set to this output gives no new violations, like the legacy
tenant isolation leak in that rule's baseline. Every other endpoint in the OpenAPI schema answers
404 for a deleted issue or leaves it out of its list.

## Limits

- Filters 1-3 show that a kept test builds, passed five runs, and added line coverage or killed a
  filter-set mutant (a copy of the code with one planted fault)
  ([Automated Unit Test Improvement using Large Language Models at Meta](https://arxiv.org/abs/2402.09171);
  [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862)).
  They do not show that the test checks the behaviour a reviewer cares about.
- Filter 6 compares syntax trees. Two tests that check the same thing with different calls both
  stay; it removes copies, not overlap.
- The House rule 8 check probes one deleted issue per endpoint with the home org's admin token. A list endpoint whose
  required query parameters filter the deleted row out by accident would hide a leak; so would a
  list longer than one page if the deleted rows were not the first ones.
- The run used one target and one model run; one run is an example, not a rate.

## Sources

- Source 1: Automated Unit Test Improvement using Large Language Models at Meta, <https://arxiv.org/abs/2402.09171>,
  Alshahwan et al. (Meta), 2024-02-14
- Source 2: Mutation-Guided LLM-based Test Generation at Meta, <https://arxiv.org/abs/2501.12862>, Foster et al. (Meta),
  2025-01-22
