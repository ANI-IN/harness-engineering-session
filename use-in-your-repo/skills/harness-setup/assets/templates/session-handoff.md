# Session handoff

<!-- A structured handoff that the next session reads first ([Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps): a context reset is "combined with
a structured handoff that carries the previous agent's state and the next steps"). The machine
summary is filled in by the harness or a script at session stop, so it exists even if the agent
writes nothing. The agent writes the notes during wrap-up. Overwrite this file every session. -->

## Machine summary

- Feature: <feature id>
- Files changed this session: <paths>
- Visible tests: <passed>/<total>, failing: <test ids>
- Last 5 commits: <sha subject, one per line>
- Open TODO markers: <path:line>
- Migration heads: <count and ids>

## Notes from the agent

- What I was doing when the session stopped: <...>
- What works now: <...>
- What is broken or unfinished: <...>
- Approaches that failed, so the next session does not repeat them: <...>
- First step for the next session: <...>
