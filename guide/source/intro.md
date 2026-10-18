# Introduction: why this guide exists

A coding agent can write a feature, run the tests, and say "done", while the work is wrong in ways
the tests never check. It copies a query with no tenant filter from old code. It loses its plan
when a session stops and redoes a migration. It edits files the ticket never mentioned. It claims
the work is finished when the hidden tests fail. More prompting does not fix this. What fixes it is
the harness: the files and code around the agent that decide what it sees and what it may do.

This guide walks you through the five live demos of Module 1, one command and one screen at a
time. In each demo the agent works on TeamTrack, a small multi-tenant issue tracker. The referee
(the program that scores each run after the agent stops) then answers one question fixed before
any run. You watch it happen on the console, a browser page with five screens.

Four demos show one harness layer each: instructions, state and sessions, scope and sandbox, and
verification. Section 3: Scope and sandbox and the final project are A/B runs: the same ticket with the harness off (the bare
arm) and on (the harness arm), scored the same way. The results are measured, not promised: some
layers made a clear difference on these tickets, and some made none. Each chapter shows what this
run found, and what to say about it in class.
