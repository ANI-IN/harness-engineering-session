# Final project checklist

The final project is done when you can show the five items below. There is no grader for the
final project; [Assignment 4: Verification](../section-4-verification/assignment/README.md) asks for the same
pieces as part of its portfolio.

## What to show

1. **One live A/B.** You ran `./final-project/run.sh` with `bulk-close`, `watchers`, or `labels`
   (or `make final FEATURES=` with the same name) to the end. Keep terminal 2's two arm lines and the cost line, and the A/B id from the console.
2. **The five screens.** One screenshot of each console screen for that A/B, as in
   [expected/](expected/README.md).
3. **Your reading of it.** Three to five sentences: the counts per arm (hidden tests, mutants
   killed, that is planted bugs the arm's own tests caught, claim, files outside the allowed paths), and which of the three outcomes it is: harness
   ahead, no measurable difference, or bare ahead. Say that one A/B is one dot.
4. **One layer tested.** Either a second A/B with one layer removed (`make final FEATURES=bulk-close
   LAYERS=-scope`), or a written reason, from [walkthrough.md](walkthrough.md), for the layer you
   would remove first and what would show you were wrong.
5. **The harness on your own repository.** The steps of [your-repo/](your-repo/README.md) on a
   repository you choose: `init --check` at 0 markers, one house-rule check that passes and one you
   made fail on purpose, one capped `shipharness testgen` run, and your layer decisions with the date.

## Self-check

- [ ] Every number you report comes from your terminal, your screens, or `exports/scores/`; none is
      estimated.
- [ ] Results are counts ("46 of 46 hidden tests"), not percentages.
- [ ] You compared each arm's claim with its counts, not with the agent's summary.
- [ ] If an arm ended `ABORTED`, you said so and still reported its counts.
- [ ] Your total model spend is in your report, from the cost lines.
- [ ] No key, `.env` content, or customer data appears in anything you hand in.
