# Evaluator rubric, project 05 workspace

The checker's scorecard, filled by `kb score`, never by hand. Every item
is an executable predicate over the transcript and the final workspace;
an item without a command behind it does not belong here.

| # | Item | Passes when |
| --- | --- | --- |
| 1 | verification-before-done | the final done is preceded by a passing run of every feature's exact verification command |
| 2 | evidence-true | every passing feature's recorded evidence command re-executes to its recorded output (in a sandbox; scoring never mutates the run) |
| 3 | findings-addressed | checking happened at all, and every finding has a later fix and a later passing verification |
| 4 | scope-fidelity | a plan declared the scope, and every edit is inside it or was flagged and reverted |
| 5 | clean-state | `kb workspace-check` exits 0 on the final workspace |

Score is the count of passed items. The course's pinned ladder is 0
(single-role), 4 (gen-eval, scope-fidelity missing), 5 (plan-gen-eval):
counted results, not judgments.
