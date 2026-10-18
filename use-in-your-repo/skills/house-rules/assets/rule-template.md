# {{RULE_ID}} {{TITLE}}

<!-- One rule per file. A house rule is the course's name for what [Harness engineering](https://openai.com/index/harness-engineering/) calls "golden principles" and
"taste invariants": a rule written down in the repository and enforced by a check. Replace every
<placeholder>; keep each section short. -->

Status: <proposed | enforced | retired>. Owner: <team or person>.

## Rule

<One sentence a reviewer can check with yes or no. For example: "Every query on a tenant table
filters by the caller's organisation.">

## Why

<The failure this prevents, with the incident, review, or source that showed it.>

## Applies to

<Paths, layers, or endpoints the rule covers, and anything it deliberately does not cover.>

## Correct

```
<the smallest example that follows the rule, or the file and function to copy>
```

## Incorrect

```
<the smallest example that breaks the rule>
```

## How it is checked

- Check: `{{CHECK_PATH}}` (run `python {{CHECK_PATH}} <repo>`).
- Test: `{{TEST_PATH}}` has one seeded violation the check must catch and one clean case.
- Runs in: <CI job, gate, or pre-commit hook>.

## Error message

The check prints one line per violation, with the reason and the fix on the same line, so an agent
reading the output knows what to change:

```
ERROR {{RULE_ID}} <path>:<line>: <what is wrong>. Fix: <what to do instead; which doc to read>
```

## Exemptions and baseline

<Violations that existed when the rule was adopted are listed in the check's baseline and do not
fail the build. New code must follow the rule. Each exemption names who approved it and why.>
