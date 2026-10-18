---
# [walkthrough:Final:skill_template] start
name: skill-template
description: >
  Starting point for writing a new Agent Skill: frontmatter with the spec's fields and a guide to
  the sections of the body. Use when creating a new skill: copy this folder, rename it, set name to
  the new folder name, and replace every placeholder.
license: MIT
# Optional spec fields. Uncomment the ones you need; the spec allows no other fields.
# compatibility: Python 3.12+ and uv
# allowed-tools: Bash Read
# metadata:
#   author: your-name
#   version: "0.1.0"
---

# <Skill title>

<One paragraph: what this skill does and the result the user gets.>

## When to use

- <A situation, in the words a user would type, where this skill applies.>
- <When not to use it, and what to use instead.>

## Steps

1. <First action. Name the exact command, for example `python scripts/<script>.py <args>`.>
2. <What to check in the output before going on.>
3. <...>

## Checks before you finish

- [ ] <A check the agent can run, with the command and the expected result.>
<!-- [walkthrough:Final:skill_template] end -->

## Files in this skill

- `scripts/`: Python scripts the steps run. Keep them deterministic; print short output.
- `references/`: detail loaded only when a step needs it. Link each file from this page; do not
  link reference files to each other.
- `assets/`: templates and static files the steps copy.

## Sources

<!-- Where the method comes from: papers, docs, or your team's decisions. One line per
source, numbered in the order the body first links them. -->

- Source 1: <title>, <https://example.org/replace-with-the-source-link>, <author>, n.d.
