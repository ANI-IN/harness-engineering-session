# Clean-state checklist, project 03 working copy

Walk this before declaring a work stream finished. Every item is a
command and the outcome that counts as clean; prose impressions do not.

## Verification

- [ ] Every feature's `verification` command in `feature_list.json`
      exits 0 (run them; do not trust the recorded status).
- [ ] `kb status --data-dir kb-data` reports state `ready` with no stale
      documents.
- [ ] `kb continuity` exits 0 (a fresh process chain can resume this
      workspace).

## State files

- [ ] `feature_list.json`: every passing feature carries evidence
      (command, observed, date); nothing passing on faith.
- [ ] `session-handoff.md` updated: what is verified, what is broken or
      unverified, the next best step.
- [ ] `claude-progress.md` has this session's entry with decisions and a
      next best step.

## Workspace

- [ ] `kb workspace-check --workspace .` exits 0.
- [ ] No stray working files outside `kb-data/` and the harness
      artifacts; the data directory can be deleted and rebuilt from
      `init` plus `import` alone.
