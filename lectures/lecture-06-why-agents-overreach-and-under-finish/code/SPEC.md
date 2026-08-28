# SPEC: scope-run

A deterministic scripted worker replays one session script against a
workspace and reports what the session finished. The script is the same
for every run; the workspace decides whether a task boundary exists. Both
tracks read the same files and must emit the same report; `expected/` is
the grading authority.

## CLI surface

```text
main <workspace-dir> <session-script.json> [--budget N]
```

`--budget` is the step budget (default 12; must be a positive integer).

## Inputs

- `<workspace-dir>/feature_list.json`: the scope surface, in the shape of
  the library's `feature_list.schema.json` (`project`, `updated`,
  `features[]` with `id`, `title`, `behavior`, `verification`, `status`).
  Exactly one feature is `in-progress` at the start: the **assigned**
  feature.
- `<workspace-dir>/AGENTS.md`: the work rules. A line matching
  `- WIP limit: N` (whole line, ASCII digits) draws the boundary; its
  absence means no boundary (`wip_limit: null`).
- `<session-script.json>`: `{"impulses": [{"feature", "kind", "action",
  "noticed"}]}`, the fake agent's recorded stream of what it wanted to do
  next. `kind` is `step` or `verify`; `noticed` is the observation that
  provoked a tangent (`null` for steps on the assigned feature). Every
  impulse names a listed feature.

## The run

Impulses are processed in script order. The run stops as soon as
`steps_spent` reaches the budget; later impulses are never seen.

| Impulse targets | Boundary | Result | Cost |
| --- | --- | --- | --- |
| a feature that is `in-progress` | any | acted on | 1 step |
| a feature that is not `in-progress` | none (`wip_limit: null`), or fewer than `wip_limit` features in progress | the feature becomes `in-progress` and the impulse is acted on | 1 step |
| a feature that is not `in-progress` | `wip_limit` features already in progress | **parked**: recorded in the queue, never acted on | 0 steps |

Acting on a `step` impulse produces an event whose `outcome` is, for the
assigned feature, `progress on the assigned feature (step k)` (k counts
that feature's steps so far); for a newly activated tangent,
`scope crossed: n features in flight` (n counts every `in-progress`
feature after the activation); for a tangent already in flight,
`the tangent deepens; the assigned feature waits`.

Acting on a `verify` impulse runs the feature's `verification` command
from the feature list: the event's `action` is
`run the verification command (<command>)`, the outcome is
`pass: <id> moves to passing with evidence`, and the feature's status
becomes `passing`. In this scripted world the recorded verification run
passed; the demo's subject is whether the session ever reaches it.

Parking records `{"feature", "action", "noticed", "noticed_at_step",
"times_provoked"}` once per feature, in the order features were first
parked; `noticed_at_step` is `steps_spent` at that moment and a repeat
impulse for an already-parked feature only increments `times_provoked`.

## Output

```json
{
  "workspace": "<dir basename>",
  "wip_limit": 1,
  "assigned": "search-endpoint",
  "budget": 12,
  "events": [{ "step": 1, "feature": "...", "action": "...", "outcome": "..." }],
  "parked": [{ "feature": "...", "action": "...", "noticed": "...", "noticed_at_step": 2, "times_provoked": 2 }],
  "steps_spent": 7,
  "steps_on_assigned": 7,
  "steps_on_tangents": 0,
  "features_started": 1,
  "features_passing": 1,
  "in_progress_at_end": [],
  "assigned_verified": true
}
```

`events` holds only budget spends (parked impulses never appear there).
`steps_on_assigned` includes the assigned feature's verification step;
`features_started` counts features that received at least one step;
`in_progress_at_end` lists `in-progress` features in feature-list order
(an obligation of this SPEC, since the normalizer never sorts arrays).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | the assigned feature reached `passing` with its verification run |
| 1 | the session ended without that evidence; the report on stdout shows where the budget went |
| 2 | usage error, `<workspace-dir>` not a directory or lacking `feature_list.json` or `AGENTS.md`, script not a file, or not exactly one `in-progress` feature; stdout empty |

## Fixtures and the seeded condition

`workspaces/open-scope` and `workspaces/bounded-scope` carry
byte-identical `feature_list.json` files (five features, `search-endpoint`
assigned); their `AGENTS.md` files differ by exactly one line,
`- WIP limit: 1`, present only in `bounded-scope`. That absence is the
seeded condition, and `session-script.json` (twelve `step` impulses, six
on the assigned feature and six tangents across four other features,
then the assigned feature's `verify`) is the shared stimulus.

| Case | Observable symptom | Caught by |
| --- | --- | --- |
| `open-scope-overreaches` (budget 12) | twelve steps spent, five features `in-progress`, zero `passing`; the verify impulse is never reached; exit 1 | the pinned `expected/open-scope.json` and the exit code |
| `bounded-scope-finishes` (budget 12) | seven steps, one feature `passing`, four tangents parked with their provocations recorded; exit 0 | `expected/bounded-scope.json` |
| `open-scope-big-budget` (budget 18) | the same open workspace finishes at step 13 with four features left in flight; exit 0 | `expected/open-scope-big-budget.json`: the failure is scope meeting a finite budget, not an impossible task |
