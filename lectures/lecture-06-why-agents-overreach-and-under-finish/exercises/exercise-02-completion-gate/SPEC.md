# SPEC: exercise-02 completion-gate

Decides whether a feature list's `passing` claims are backed by evidence
and whether the next feature may be activated. `passing` is a transition
that only a recorded run of the feature's own verification command can
make; a typecheck filed as evidence, or a recorded failing run, is a
claim without evidence. The WIP limit is 1
([glossary](../../../../docs/glossary.md#working-discipline)).

## CLI surface

```text
main <feature_list.json>
```

The input has the library schema's shape: `features[]` with `id`,
`status`, `verification`, and, for `passing` entries, `evidence`
(`{"command", "observed", "date"}`).

## The evidence rule

Every feature whose status is `passing` is a **claim**, audited in
feature-list order:

| Condition (first that applies) | `evidence_ok` | `detail` |
| --- | --- | --- |
| no `evidence` entry | false | `no evidence recorded` |
| `evidence.command` differs from the feature's `verification` | false | `evidence names a different command (<evidence.command>, not <verification>)` |
| `evidence.observed` does not start with `exit 0` | false | `evidence records a failing run (<evidence.observed>)` |
| otherwise | true | `verified: <verification> reported exit 0` |

`unbacked` lists the ids of claims with `evidence_ok: false`, in order.

## The WIP rule and the verdict

`wip.in_progress` lists `in-progress` features in feature-list order;
`wip.limit` is 1. Verdicts, in precedence order:

- more than `limit` features in progress: `wip-exceeded`, exit 1;
- otherwise any unbacked claim: `unbacked-claims`, exit 1;
- otherwise `sound`, exit 0.

`may_activate` is true only when the verdict is `sound` and nothing is
in progress: the next feature starts when the current one is finished
with evidence, never beside it.

## Output

```json
{
  "claims": [{ "id": "search-endpoint", "evidence_ok": true, "detail": "verified: ./verify.sh --feature search-endpoint reported exit 0" }],
  "may_activate": true,
  "unbacked": [],
  "verdict": "sound",
  "wip": { "in_progress": [], "limit": 1 }
}
```

Exit code 2 remains usage error or unreadable input (stdout empty).

## Fixtures and seeded defects

- `ready.json`: two backed claims, nothing in progress; `sound`,
  `may_activate: true`, exit 0.
- `wip-exceeded.json`: one backed claim, two features in progress;
  `wip-exceeded`, exit 1.
- `hollow-evidence.json`: four claims and one feature in progress. Three
  claims are seeded defects, each caught by the evidence rule with the
  exact detail below; exit 1, verdict `unbacked-claims`.

| Seeded defect | Detail |
| --- | --- |
| `delete-endpoint`: evidence records `npx tsc --noEmit` | `evidence names a different command (npx tsc --noEmit, not ./verify.sh --feature delete-endpoint)` |
| `rate-limiting`: evidence records `exit 1; 3 of 5 assertions failed` | `evidence records a failing run (exit 1; 3 of 5 assertions failed)` |
| `test-layout`: `passing` with no evidence entry (which the library schema also rejects) | `no evidence recorded` |

## Starter state (the intended failure)

The starter is a genuine partial implementation. Its evidence rule is
complete and correct: it rejects a missing evidence entry, an entry naming
a different command, and an entry recording a failing run. What it never
asks is whether there is a command to run at all.

A feature whose `verification` is the empty string satisfies every one of
those comparisons. Its evidence names the same empty command, and the run
it records reads as passing, so an unverifiable feature is reported as
verified. That is the empty-input case: the gate's logic is right and its
input is degenerate, and nothing rejects the degenerate input.

`fixtures/empty-verification.json` is the trap. Both drafts exit 1 on it,
because its second feature has no evidence under either rule, so the
recorded divergence is a value and not an exit code:

```text
diverges at $.claims[0].detail: 'verified:  reported exit 0' != 'the feature declares no verification command'
```

The fix is one branch, checked before the evidence branches: a feature that
declares no verification command is unbacked, whatever its evidence says.

## Expected output

- `ready` → `expected/ready.json`, exit 0.
- `hollow-evidence` → `expected/hollow-evidence.json`, exit 1.
- `wip-exceeded` → `expected/wip-exceeded.json`, exit 1.
- `missing-file` → stdout empty, exit 2.
