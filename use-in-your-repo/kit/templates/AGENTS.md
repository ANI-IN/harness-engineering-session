<!-- REPLACE: TeamTrack's map, kept as the example. Rewrite each section for your repository and delete the REPLACE lines. Keep it near 100 lines: a table of contents that points to the documents holding the rules, not the manual. -->
# AGENTS.md

This file is the map of the TeamTrack repository: a table of contents, not the manual. It tells you
where each rule lives. Open the document for the part you are changing before you edit code.

<!-- REPLACE: two sentences: what your repository is, and the one fact every change must respect (TeamTrack: every customer row carries an org_id). -->
TeamTrack is a multi-tenant issue tracker: an HTTP API (FastAPI) plus a small web board (Jinja2 and
HTMX). Each customer is an org, and every customer row carries an `org_id`.

## Where to look

<!-- REPLACE: one row per kind of change, pointing at the document that holds its rules. Every path must exist. TeamTrack's add-endpoint skill is not part of the kit: delete that row or write your own skill (skills/skill-template in shipharness). -->
| When you are about to | Read first |
|---|---|
| add or change an endpoint | `.agents/skills/add-endpoint/SKILL.md` (step by step) |
| touch a router, service, repository, or model | `ARCHITECTURE.md` (layers, House rule 6: Layering) |
| decide who may see or change data | `docs/SECURITY.md` (House rule 1: Tenant isolation, House rule 2: Roles) |
| shape a list, an error, or a status code | `docs/design-docs/api-conventions.md` (House rule 3: API conventions) |
| write a create endpoint or any write | `docs/RELIABILITY.md` (House rule 4: Safe retries, House rule 5: Audit log) |
| change the database schema | `docs/RELIABILITY.md` (House rule 7: Migrations) |
| change issue or project behaviour | `docs/product-specs/teamtrack-base.md` |
| write or run tests | `docs/QUALITY_SCORE.md` (testing, known gaps) |
| plan a change or check the roadmap | `docs/PLANS.md` |
| understand why the code is shaped this way | `docs/design-docs/index.md` |
| look up a tool (Alembic, import-linter) | `docs/references/` |

## House rules at a glance

<!-- REPLACE: your house rules, one line each, with the document that explains it. docs/house-rules.md says how to adapt the seven house rules (House rules 1 to 7) or drop one. -->
Every endpoint follows all seven rules, new endpoints included. Automated checks find endpoints in
the OpenAPI schema, so a new endpoint is checked the moment it exists.

- House rule 1: Tenant isolation. Another org's resource is 404, never 403. See `docs/SECURITY.md`.
- House rule 2: Roles. Viewers get 403 on every write; some writes are admin-only. See `docs/SECURITY.md`.
- House rule 3: API conventions. List envelope, error envelope, status codes. See `docs/design-docs/api-conventions.md`.
- House rule 4: Safe retries. Creates honour `Idempotency-Key`. See `docs/RELIABILITY.md`.
- House rule 5: Audit log. One audit row per write. See `docs/RELIABILITY.md`.
- House rule 6: Layering. `app/api` never imports `app/db`. See `ARCHITECTURE.md`.
- House rule 7: Migrations. One Alembic head; upgrade works on an empty database. See `docs/RELIABILITY.md`.

## Do not copy

<!-- REPLACE: legacy code agents must not copy, and the file that shows the right pattern. Delete this section if it does not apply. -->
`GET /v1/issues` (`app/api/legacy_v1.py`) is a legacy endpoint kept for one old reporting client. It
is not filtered by org, uses offset pagination, and returns a bare array; it is scheduled for removal.
Do not copy it, even when it looks like a quicker starting point. The same applies to
`repositories.issues.list_all_legacy` and `services.legacy`. For a create endpoint, `POST /projects`
shows the pattern. Details: `docs/QUALITY_SCORE.md`.

`app/api/middleware.py` runs on every request. Feature work does not touch it.

## Commands

<!-- REPLACE: the exact commands for your repository. Run each one before you commit this file. -->
Run these from the TeamTrack folder unless noted.

| Task | Command |
|---|---|
| install dependencies (repository root) | `uv sync` |
| create the database | `alembic upgrade head` |
| start the API | `uvicorn app.main:create_app --factory --reload` |
| run the tests | `python -m pytest tests/visible -q` |
| check the layering (House rule 6) | `lint-imports --config .importlinter` |
| check the migration head (House rule 7) | `alembic heads` |

<!-- REPLACE: how to authenticate locally, or delete this paragraph. Never write a real key here. -->
Demo login: `POST /auth/login` with `{"email": "admin@acme.test"}` returns a token; send it as
`Authorization: Bearer <token>`. Users exist for each role in each org (`admin@`, `member@`,
`viewer@` at `acme.test` and `globex.test`). The demo token is not secure and is for local use only.

## Repository layout
<!-- REPLACE: your top-level folders, one line each. -->

```
app/api/            routers, schemas, dependencies, error handling (calls services)
app/web/            the web board under /board (Jinja2 and HTMX)
app/services/       business logic; every function takes an Actor
app/repositories/   database queries; every customer query takes org_id
app/db/             SQLAlchemy models and engine setup
app/main.py         wires everything together
app/seed.py         demo data (orgs Acme and Globex)
migrations/         Alembic environment and migrations/versions/
tests/visible/      the tests you run and extend
docs/               the system of record (this map points into it)
```

## How the docs are organised
<!-- REPLACE: where your system of record lives. TeamTrack also has docs/HANDBOOK.md, which the kit does not copy: delete that sentence. -->

`docs/` is the system of record. This map stays short on purpose; the facts live in the files it
points to. `docs/HANDBOOK.md` holds the same rules as one long handbook; when you need a rule, the
focused document above is quicker to read.

## Before you finish
<!-- REPLACE: the checks a change must pass before the agent says it is done; keep them in step with docs/clean-state-checklist.md. -->

- The house rules above hold for every endpoint you added or changed.
- Tests in `tests/visible/` cover the happy path and the rules: another org's IDs give 404, viewers
  get 403 on writes, lists use the envelope, writes add one audit row.
- `python -m pytest tests/visible -q` passes and existing tests keep passing, unchanged.
- `lint-imports --config .importlinter` and `alembic heads` (one head) pass.

## Start of every session

<!-- REPLACE: in TeamTrack the harness gives the agent these steps at the start of every session (src/shipharness/harness/state/lifecycle.py, rendered for the org-wide issue search feature, `F1`). Keep them when no harness runs your sessions: replace run_visible_tests (a shipharness tool) with your test command and `F1` with your feature id. -->

1. Run `pwd` to see the directory you are working in. You can only edit files in this directory.
2. Read progress.md and the git log (`git log --oneline -20`) to see what was recently worked on.
3. Read session-handoff.md (the structured handoff from the last session) and the exec plan docs/exec-plans/active/F1.md.
4. Read the "Notes from the agent" in session-handoff.md before any other document: earlier sessions wrote down the house rules and files that matter for this ticket. Open a document from the AGENTS.md map only for a detail the notes do not cover (in the first session, only the documents for the parts you will change).
5. Read feature_list.json and work on the feature listed there, and only it.
6. Run `bash init.sh` to set up the database and run a basic end-to-end test.
7. Read the "Visible tests" line in session-handoff.md: the harness ran the full visible suite when the last session ended. If it lists failures, fix them before you start new work. In the first session there is no such line yet: run the visible tests once with run_visible_tests.

## End of every session

<!-- REPLACE: the wrap-up steps the harness gives the agent at the end of a session. Keep them when no harness does it for you. -->

1. Update progress.md: Done, In progress, and Next.
2. Update the exec plan docs/exec-plans/active/F1.md: Progress (with timestamps) and Decision Log.
3. Write your notes under "## Notes from the agent" in session-handoff.md: what you were doing, what is left, what to watch out for, and the house rules and file locations from the documents you read that matter for this ticket, so the next session does not need to read them again. The harness writes the machine summary itself.
4. Commit your work to git with a descriptive message (git add, then git commit).
