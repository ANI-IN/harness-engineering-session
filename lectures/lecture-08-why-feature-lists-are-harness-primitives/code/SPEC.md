# SPEC: scope-replay

Two surfaces over the same two workspaces: `replay`, the behavioral demo,
and `plan`, the supporting view of what a fresh session can ground in its
tracker. Both tracks read the same fixtures and must emit the same
reports; `expected/` is the grading authority.

## CLI surface

```text
main replay <workspace-dir>     # the scripted session plus the closing audit
main plan <workspace-dir>       # what a fresh session can know from the tracker alone
```

A workspace carries exactly one tracker: `feature_list.json` (the
canonical dialect, `library/templates/feature_list.schema.json`) or
`notes.md` (a prose memo). `feature_list.json` wins when both exist.
`replay` additionally needs `project.json`, the recorded ground truth.

## Files read

- `notes.md`: a prose memo. The only machine-readable thing in it is
  feature identity: a bullet line `- <id>: <prose>` where `<id>` is a
  kebab-case feature id. Everything after the colon is prose. Lines of any
  other shape are ignored.
- `feature_list.json`: a canonical feature list; `replay` and `plan` read
  each entry's `id`, `status`, and `verification`.
- `project.json` (replay only): `{"project", "features": [{"id", "built",
  "hidden_defect"}]}`. This is the deterministic fake agent's recording of
  the workspace's real state: `built` means the code exists before the
  session starts; `hidden_defect` means the built code fails its
  verification command until a session runs that command, sees the
  failure, and fixes it. The session never reads this file; only the
  closing audit does. The verification commands in the fixtures are data
  the replay quotes; nothing in this unit executes them.

## The memo reading rule

Prose carries no state contract, so the scripted session applies one fixed
interpretation and the SPEC pins it: a mention whose prose contains
`need` or `todo` (case-insensitive) reads as **remaining**; every other
mention reads as **done**. Hedges (`mostly done`, `still buggy`) have no
machine meaning and fall into the second bucket. A feature the memo never
mentions does not exist for the session.

## The replay (the demo, pinned)

Every event costs one step. Under `notes.md`:

1. `read notes.md`: counts mentions, notes that states are prose and no
   verification commands are recorded.
2. One `interpret '<id>'` event per mention, in memo order, applying the
   reading rule; remaining features are planned.
3. Per planned feature, in order: `implement <id>` (the outcome notes when
   the workspace already had the feature built), `self-check <id>` (no
   verification command exists to run), `update notes.md`. Implementing
   sets `built`; it never clears a hidden defect. Steps spent on a feature
   whose verification already passed before the session count as wasted
   (three per such feature).
4. `declare done`: the memo shows nothing remaining.

Under `feature_list.json`:

1. `read feature_list.json`: counts entries; every entry carries an
   explicit status and a verification command.
2. Per entry, in list order: status `passing` is skipped with its evidence
   named (one step, no rework); any other status is worked: `implement
   <id>` (`code written` from `not-started`, `remaining work written`
   otherwise), then `run <verification>`. A hidden defect makes that run
   exit 1, costs a `fix <id>` step, and is followed by a second run that
   exits 0; otherwise the first run exits 0. Either way the entry ends
   `passing` with evidence recorded.
3. `declare done`: every feature passing.

Both scripts end by claiming done. The **audit** then walks
`project.json` in file order and grades the claim per feature:

| Ground truth after the session | `verified` | `note` |
| --- | --- | --- |
| built, no defect, not reworked | true | `verification passes` |
| built, no defect, reworked (already passed before the session) | true | `verification passes; the session rebuilt a feature that already passed` |
| built, defect still hidden | false | `verification fails: the code carries a defect no session run exposed` |
| not built | false | `never attempted: absent from the tracker` |

`believed` is the session's final belief: `done` for every memo mention,
`passing` for every list entry, `untracked` for a feature the tracker
never named.

Output: `{"workspace", "tracker", "events": [{"step", "action",
"outcome"}], "steps_spent", "wasted_steps", "claimed_done",
"features_required", "features_verified", "audit": [{"id", "believed",
"verified", "note"}], "done_claim_honest"}`. `done_claim_honest` is true
when every required feature verified. On the committed fixtures the memo
session declares done after 8 steps with 2 of 4 features verified and
exits 1; the tracked session declares done after 10 steps with 4 of 4
verified and exits 0. The pinned transcripts are the lecture's argument:
the counts are evidence; the false claim is the demonstration.

## The plan (supporting surface)

`plan` reads only the tracker. Output: `{"workspace", "tracker",
"entries": [{"id", "state", "verification", "grounded"}], "next",
"grounded"}`.

- From `feature_list.json`: `state` is the entry's status, `verification`
  its command, `grounded` true; `next` lists every entry not `passing`,
  in list order.
- From `notes.md`: `state` is `done (interpreted from prose)` or
  `remaining (interpreted from prose)` per the reading rule,
  `verification` is `none recorded`, `grounded` false; `next` lists the
  remaining mentions.

`grounded` at the top level is true when the tracker has at least one
entry and every entry is grounded.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `replay`: the done claim is honest (every required feature verified); `plan`: every entry grounded |
| 1 | `replay`: the session claimed done and the audit found unverified or unattempted scope; `plan`: the tracker cannot ground a plan |
| 2 | usage error, `<workspace-dir>` not a directory, no tracker present, or `project.json` missing for `replay`; stdout empty |

## Fixtures and seeded symptoms

Both workspaces describe the same project: `project.json` is a
byte-identical copy in each, so the only variable between the two runs is
the tracking regime. Ground truth: `auth` built and passing, `cart` built
with a hidden defect, `payments` built and passing, `csv-export` not
built.

`workspaces/workspace-tracked/feature_list.json` validates against the
canonical schema: `auth` and `payments` are `passing` with evidence,
`cart` is `in-progress`, `csv-export` is `not-started`.

`workspaces/workspace-memo/notes.md` seeds three defects, each surfacing
at a named point of the replay:

| Seeded defect | Where it bites | Observable symptom |
| --- | --- | --- |
| `cart: mostly done, totals still buggy` (a hedge where a state should be) | `interpret 'cart'` reads it as done; the audit runs the verification the session never ran | `cart` `verified: false`, `verification fails: the code carries a defect no session run exposed` |
| `payments: still need to do this` (stale; the workspace already has it passing) | `implement payments` rebuilds existing code | `wasted_steps: 3`; `payments` note `the session rebuilt a feature that already passed` |
| `csv-export` never mentioned (scope lost between sessions) | nowhere: the session cannot plan what its tracker cannot name | `csv-export` `believed: untracked`, `never attempted: absent from the tracker` |

`plan` shows the same three gaps from the tracker alone: three
ungrounded entries and no fourth, exit 1.
