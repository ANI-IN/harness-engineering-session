<!--
  Template: quality-document.md, the long-horizon health snapshot.
  Use when: agent work on a codebase spans weeks; you need to know whether
  the system is getting stronger or weaker over time.
  Don't use when: short-lived work; the evaluator rubric (per-session
  verdict) is the right tool there. The two answer different questions:
  rubric = "was this session's work good?", quality document = "is the
  project trending up or down?".
  Motivated by: Lecture 05 (Why every session must leave a clean state) and
  the harness-simplification practice: snapshot -> remove one component ->
  re-run the benchmark tasks -> snapshot -> compare. If grades didn't drop,
  the component was overhead; remove it for good.
-->

# Quality document

Grading scale: **A** solid, verified, no known debt · **B** works, minor debt
recorded · **C** works with caveats or thin verification · **D** fragile or
unverified.

- Project: example-notes-app
- Snapshot date: 2026-08-27
- Benchmark task set: `./verify.sh` (all features) + fresh-clone startup

## Product domains

| Domain | Grade | Evidence | Trend |
| --- | --- | --- | --- |
| Note creation | A | verify green since 2026-08-26; fresh-clone tested | steady |
| Note listing | C | implemented; sort assertion failing | up from D |
| Note search | D | not started | none |

## Architectural layers

| Layer | Grade | Evidence |
| --- | --- | --- |
| CLI surface | B | commands stable; help text tested |
| Core services | B | unit-tested; no cross-layer imports (checker green) |
| Storage | A | round-trip tests; survives fresh clone |

## Harness components in force

| Component | Since | Last ablation check | Keep? |
| --- | --- | --- | --- |
| AGENTS.md + CLAUDE.md | 2026-08-26 | not yet ablated | yes |
| feature_list.json + schema | 2026-08-26 | not yet ablated | yes |
| init.sh | 2026-08-26 | not yet ablated | yes |

## Change history

Append one line per snapshot; never rewrite old lines.

- 2026-08-27: listing D→C (implemented, one failing assertion); no
  components removed.
- 2026-08-26: initial snapshot after setup + `note-create` (A).
