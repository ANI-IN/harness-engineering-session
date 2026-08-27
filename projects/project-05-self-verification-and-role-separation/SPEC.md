# SPEC: project-05 self-verification-and-role-separation

kb v5: the same knowledge-base tool, with deletion done honestly and the
course's maker/checker experiment. The product delta is `kb delete` with
index reconciliation and orphan detection; the study delta is the
apparatus: `workrun` replays one scripted work item under three role
configurations, `score` grades a run against a five-item rubric of
executable predicates, and `ladder` runs all three and requires the
scores to climb. Both implementations (`solution/python/main.py`,
`solution/typescript/main.ts`) must produce byte-identical output after
normalization for every case in `cases.json`.

The `kb` canonical command form and its per-track expansions are exactly
as in [project 01's SPEC](../project-01-baseline-vs-minimal-harness/SPEC.md);
paths below expand against this directory.

## Delta from project 04

Contract evolution follows
[project 01's pre-1.0 declaration](../project-01-baseline-vs-minimal-harness/SPEC.md#contract-evolution-pre-10):
rows marked **Breaking** change what a caller of the previous surface
observes; everything else is additive.

The starter IS project 04's solution app, verbatim. The delta:

| Area | v4 (starter) | v5 (solution) |
| --- | --- | --- |
| `delete` | absent (usage error) | removes the document file, the index entry, and the chunk record; logs `delete/done`; exit 1 for unknown ids |
| `status` | corrupt = empty-text chunks | **Breaking**: a chunk record whose document is no longer in the metadata index (an orphan, the half-done delete's signature) is also corrupt, named in the `corrupt` list |
| `index` | writes every known record | **Breaking**: the report gains a `dropped` list; records for documents no longer in the metadata index are reconciled away (both modes), which is also the recovery for orphans |
| `workrun` | absent (usage error) | the scripted work item under one of three role configurations (below) |
| `score` | absent (usage error) | the five-item rubric over a workrun's transcript and workspace |
| `ladder` | absent (usage error) | all three configurations in sequence; exit 0 only when the scores strictly climb |

Harness artifacts accrete monotonically; nothing is dropped:

| Artifact | project 04 | project 05 |
| --- | --- | --- |
| router AGENTS.md, CLAUDE.md, init.sh, feature_list.json, claude-progress.md, session-handoff.md, clean-state-checklist.md, docs/ (ARCHITECTURE, PRODUCT, IMPORTING, INDEXING, OBSERVABILITY) | present | kept, updated for v5 |
| evaluator-rubric.md | absent | new; the five-item rubric as a filled library-template instance |

Corpus-divergence: kb-data/index/documents-meta.json (carried from
project 03's v3 metadata shape; diverges from project 02's v2 copy for
the same declared reason)

Corpus-divergence: workspaces/workspace-stale/feature_list.json (carried
from project 04's fourth seeded defect: two features in-progress)

## The work item and the flaws (pinned)

One scripted maker performs one work item, "implement the delete command
end to end", over a fresh workdir seeded with the corpus, the import
file, and a minimal workspace (router AGENTS.md, canonical handoff, a
two-feature feature list: `delete-command`, verified by the grounded
`ask`, and `surviving-detail`, verified by `show`). The maker makes the
same three flaws in every configuration:

- **Flaw A**: the delete is performed by hand: the document file and the
  metadata entry are removed, the chunk record is forgotten. The index
  is now orphan-corrupt, so the `ask` verification exits 1, and the
  maker records **fabricated evidence** (`exit 0: (assumed)`) for it.
- **Flaw B**: `surviving-detail` is marked passing with no evidence at
  all.
- **Flaw C**: an edit outside the work item
  (`config/retrieval-notes.md`).

## The three configurations (pinned)

| Config | Who checks what | Outcome |
| --- | --- | --- |
| `single-role` | nobody; the maker claims and is done | all three flaws ship |
| `gen-eval` | a checker executes every feature's verification command and audits every evidence entry (re-executing recorded commands); the maker fixes what is found (reconciling the index, recording real evidence) and the checker re-verifies | A and B are caught and fixed; C ships, because nothing declared a scope to diff against |
| `plan-gen-eval` | a planner first writes `workspace/plan.json` with the allowed scope; the checker additionally diffs every edit event against it; the maker also reverts the out-of-scope edit | A, B, and C are caught and fixed |

Canonical commands inside the apparatus execute in-process against the
run's workdir (the project 01 precedent); the conformance cases prove the
same commands behave identically through the real CLIs.

## The transcript (pinned)

`workrun` writes `workspace/transcript.jsonl`, one compact JSON event per
line: `{"turn", "role": planner|maker|checker, "type":
plan|edit|claim|verification|finding|fix|done, "detail", "command"?,
"exit"?, "observed"?}`. Every event carrying a command records the real
exit code and the compact observed output of that command run in the
workdir. The stdout report repeats the events plus the final feature
statuses; `expected/workrun-<config>.json` pins all three.

## The rubric (pinned; every item an executable predicate)

`kb score --workdir DIR` grades a workrun directory; exit 0 only at
5 of 5:

1. **verification-before-done**: the final `done` is preceded by a
   passing (`exit` 0) verification event for every feature's exact
   verification command.
2. **evidence-true**: every passing feature's recorded evidence command
   re-executes to its recorded observed output, in a sandbox copy so
   scoring never mutates the run it grades. Fabricated or missing
   evidence fails here.
3. **findings-addressed**: a transcript with no checker events fails
   outright (nothing was checked); otherwise every finding needs a later
   fix and a later passing verification.
4. **scope-fidelity**: without a plan artifact, fail (nothing declared
   the scope). With one, every edit event's target must be inside the
   scope, or be flagged by a finding and reverted by a fix.
5. **clean-state**: `kb workspace-check` exits 0 on the final workspace.

Score = the count of passed items, an integer. No weights, no decimals,
no invented numbers anywhere.

## The ladder (pinned)

`kb ladder` runs the three configurations and scores each. The pinned
outcomes are 0, 4, and 5, and the report's `monotonic` field (strictly
increasing scores) is the exit code. The numbers are counted predicate
results, regenerable by anyone running the unit; the transcripts, which
show each flaw escaping or being caught, are the demonstration, and the
scores are the supporting metric.

## Seeded defects (fixtures/scoreruns)

Five score-run fixtures each violate exactly one rubric item; every
other item passes, so each pinned report is a 4-of-5 with one named
failure and exit 1:

| Fixture | Violation | Observable symptom |
| --- | --- | --- |
| violates-r1 | no passing pre-done verification of the feature's command | `verification-before-done` fails naming `listing` |
| violates-r2 | evidence observed says `exit 0: (assumed)` | `evidence-true` fails: `listing (does not reproduce)` |
| violates-r3 | a checker finding with no later fix | `findings-addressed` fails naming `listing` |
| violates-r4 | an edit targeting `config/rogue.md`, unflagged | `scope-fidelity` fails naming `config/rogue.md` |
| violates-r5 | the handoff lost its `Next best step` section | `clean-state` fails (the workspace doctor rejects it) |

The workspace-stale fixture carries project 04's four doctor defects
unchanged (see the Corpus-divergence declarations above).

## Starter state

The starter (project 04's solution) must keep passing the carried v4
cases and fail every v5 delta case: `delete`, `workrun`, `score`, and
`ladder` are usage errors (exit 2); `status` output lacks orphan
detection (the orphan directory reads one document short but `ready`,
and the report has no such document in `corrupt`); `index` reports have
no `dropped` list, so the carried index cases fail on shape.
`verify.sh` asserts the starter stage FAILS conformance.

## Cases

`cases.json` carries project 04's twenty cases (re-pinned where the
`index` report gained `dropped`) and adds: delete with both state
artifacts checked, the unknown-id exit, orphan detection, orphan
reconciliation, the three workruns, the ladder, and the five rubric
violations. Thirty-three cases in all.

## Tests

`solution/python/tests/` (pytest) and `solution/typescript/tests/`
(vitest) cover delete end to end (file, entry, record, log), orphan
detection and reconciliation, each rubric item against its violation
fixture, the ladder's pinned 0/4/5, the dogfood check (`harness/`
passes its own doctor), and the independent evidence check over the
committed feature list. `make verify` runs both suites.
