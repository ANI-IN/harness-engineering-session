# Session handoff

A structured handoff that carries the previous session's state and the next steps. No harness runs
the sessions here, so the agent writes both parts at the end of every session.

## Machine summary

No session has ended yet. At the end of a session, write: the files changed, the result of
`python -m pytest --doctest-modules boltons tests -q`, and the last five commits
(`git log --oneline -5`).

## Notes from the agent

- What I was doing:
- What is left:
- What to watch out for:
