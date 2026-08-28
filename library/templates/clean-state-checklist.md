<!--
  Template: clean-state-checklist.md, the gate a session must pass to end.
  Use when: every session end, before the final message.
  Don't use when: never skip it; a session that can't pass the gate records
  what failed in the handoff instead of pretending.
  Motivated by: Lecture 05 (Why agents declare victory too early) and
  Lecture 05 (Why every session must leave a clean state).
-->

# Clean state checklist

Every box, every session. "The code compiles" is one line of eight.

- [ ] Build passes from a clean state (fresh install path, not a warm cache).
- [ ] Full verification command exits 0, or the failure is recorded in the
      handoff with a reproduce command.
- [ ] `feature_list.json` statuses match reality; every `passing` has evidence.
- [ ] `claude-progress.md` has this session's entry (goal, done, not done,
      verification run, decisions, next).
- [ ] No stray artifacts: scratch scripts, debug output, temp data, dead code
      paths added this session.
- [ ] No uncommitted changes left silently; commit or explain in the handoff.
- [ ] The documented startup path (`./init.sh`) still works.
- [ ] The next best step is written down where the next session will read it.
