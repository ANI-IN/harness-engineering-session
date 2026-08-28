# SPEC: exercise-02 memo-migrator

Unifies a prose progress memo into the single source of truth. The
authoritative scope (`scope.json`) says what the project must deliver;
the memo (`notes.md`) says what someone believed about it. The migrator
produces a canonical `feature_list.json` draft in which prose claims are
preserved as claims and never promoted to `passing`, because the dialect
makes `passing` mean "the verification command passed, and here is the
evidence".

## CLI surface

```text
main <scope.json> <notes.md>
```

- `scope.json`: `{"project", "as_of" (YYYY-MM-DD), "features":
  [{"id", "title", "behavior", "verification"}]}`. It is the only source
  of scope; its feature order is the output order.
- `notes.md`: a prose memo in the lecture demo's grammar: a bullet
  `- <id>: <prose>` mentions a feature; every other line is ignored.

## The migration rules

1. The reading rule is the lecture demo's: a mention whose prose contains
   `need` or `todo` (case-insensitive) is **remaining**; every other
   mention is a **claim** of completion. A later mention of the same
   feature replaces an earlier one.
2. A mention of a feature outside the scope is a conflict: exit 1, nothing
   on stdout, and the conflict named on stderr (`memo mentions unknown
   feature '<id>'; scope comes from scope.json`). Scope never grows from
   prose.
3. Every scope feature becomes one entry carrying `id`, `title`,
   `behavior`, `verification` from the scope, plus:
   - a claimed feature: `status` `in-progress` and `notes`
     `unverified claim from notes.md: "<prose>"`;
   - a remaining or unmentioned feature: `status` `not-started`, no
     `notes`.
4. No entry is ever `passing`: prose is not evidence.

Output: `{"project": scope.project, "updated": scope.as_of, "features":
[...]}`, a document that validates against
`library/templates/feature_list.schema.json`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | draft written to stdout |
| 1 | scope conflict (a memo mention outside `scope.json`); stdout empty |
| 2 | usage error or unreadable input; stdout empty |

## Fixtures

- `scope.json`: the four minishop features.
- `notes-fresh.md`: two remaining mentions, no claims (everything
  `not-started`).
- `notes-midway.md`: the trap: `auth` and `cart` are claimed (one flatly,
  one with a hedge), `payments` is remaining, `csv-export` is unmentioned.
- `notes-unknown.md`: mentions `wishlist`, which the scope does not
  contain.

## Starter state (the intended failure)

Parsing, the scope-conflict exit, and the remaining/unmentioned mapping
are correct. Claims are mapped naively: the memo says done, so the draft
says `passing`, with the claim still sitting in `notes` as unverified.
Verification passes `migrate-fresh` (no claims to mishandle) and fails
first on `migrate-midway` at
`$.features[0].status: 'passing' != 'in-progress'`: the draft promotes a
prose claim to the one status the dialect reserves for evidence. The
starter must run cleanly and fail only by producing that wrong status.

## Expected output

| Case | Inputs | Expected | Exit |
| --- | --- | --- | --- |
| `migrate-fresh` | `scope.json`, `notes-fresh.md` | `expected/fresh.json` | 0 |
| `migrate-midway` | `scope.json`, `notes-midway.md` | `expected/midway.json` | 0 |
| `unknown-mention` | `scope.json`, `notes-unknown.md` | stdout empty | 1 |
| `usage` | `scope.json` only | stdout empty | 2 |
