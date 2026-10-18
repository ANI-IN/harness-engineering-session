# Product specs

What TeamTrack does, from the user's side. Feature specs are added here as features are planned.

| Spec | Covers |
|---|---|
| [teamtrack-base.md](teamtrack-base.md) | the base product: orgs, users and roles, projects, members, issues, audit log |
| [f1.md](f1.md) | Feature 1: Org-wide issue search (`GET /issues` with filters and cursor pagination) |
| [f2.md](f2.md) | Feature 2: Comments on issues, and the board's comments panel |
| [f3.md](f3.md) | Feature 3: Safe retries for issue creation (`Idempotency-Key` on issue creation) |
| [f4.md](f4.md) | Feature 4: Version checks on issue edits (`ETag`, `If-Match`), issue history, the board's conflict page |
| [f5.md](f5.md) | Feature 5: Bulk close (in-progress issues in one project) |
| [f6.md](f6.md) | Feature 6: Watchers (watch issues, list an issue's watchers, list what I watch) |
| [f7.md](f7.md) | Feature 7: Labels (org labels, labels on issues, label filters) |
| [c1.md](c1.md) | Control task: filter the user list by role |
| [c2.md](c2.md) | Control task: search projects by name |
| [c3.md](c3.md) | Control task: filter a project's issues by priority |
| [c4.md](c4.md) | Control task: store issue titles without surrounding whitespace |
| [c5.md](c5.md) | Control task: admins cannot change their own role |
| [c6.md](c6.md) | Control task: filter the audit log by action |
| [c7.md](c7.md) | Control task: show user details in project member lists |
| [c8.md](c8.md) | Control task: show the assignee on the board's issue page |

Each feature spec is also in `docs/features/` of the repository; the two copies are identical.
