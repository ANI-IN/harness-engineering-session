# [Agent Skills Specification](https://agentskills.io/specification)

Reading time: about 5 minutes.
Source: Agent Skills project, [Agent Skills Specification](https://agentskills.io/specification), undated ([evidence](../../docs/evidence/s1.md#src-agent-skills-spec)); also [Agent Skills Overview](https://agentskills.io/home) and the [skills-ref reference validator](https://github.com/agentskills/agentskills).

> **Terms on this page**
>
> - **Agent Skill**: A folder with a `SKILL.md` recipe that the agent loads only when a task needs it.
> - **Frontmatter**: The block between `---` lines at the top of `SKILL.md`.
> - **Tier**: One of the three loading stages of a skill: metadata, instructions, resources.
> - **Skills catalogue**: One line per skill (name, description, path), given to the agent at the start.

## Why it matters

A skill is the cheapest way to give an agent a recipe for a task it meets again and again. It costs
almost nothing until it is used, but only if it is written for the way agents load it. The agent
decides from one line whether to open a skill, and most weak skills fail at that line.

## Three key ideas

1. **Three tiers, loaded at three moments.** The `name` and `description` "are loaded at startup for
   all skills"; the full `SKILL.md` body loads when the skill is activated; files in `references/`,
   `scripts/`, and `assets/` load "only when required". The body loads whole, so the specification
   says to keep `SKILL.md` under 500 lines and file references "one level deep from `SKILL.md`".

2. **The description does the deciding.** At tier 1 the description is the only text the agent has
   about the skill. It "Should describe both what the skill does and when to use it". A skill whose
   description never matches a ticket is never opened, however good its steps are.

3. **Stay inside the six standard fields.** The specification defines `name`, `description`,
   `license`, `compatibility`, `metadata`, and `allowed-tools`, and `name` "Must match the parent
   directory name". The reference validator rejects any other field: "Unexpected fields in
   frontmatter: {extras}. Only {allowed} are allowed." Its own README says it is "intended for
   demonstration purposes only", so treat it as a format check, not a quality check.

## Apply it to your repo

1. Pick the task your agent gets wrong most often. Write one skill for it, not one per rule.
2. Write the description with the words your tickets use, and end it with "Use when ...".
3. Keep `SKILL.md` short. Put long examples in `references/`, one level deep, and point to them from a
   step.
4. Use only the six standard fields, so one folder loads in every agent that follows the standard.
5. Validate the course skill, then yours:

   ```bash
   uv run shipharness skills validate platform/teamtrack/harness/instructions/.agents/skills
   ```

   > Your output will differ: line counts and warnings depend on the skills you check.

   The course skill gives:

   ```text
   + add-endpoint: valid (SKILL.md 100 lines)
   1 skill checked, 0 errors, 0 warnings
   Cost: $0.000000 (no model calls)
   ```

6. Log which tier your agent reads. In one round of test runs before class, every harness arm opened
   the skill body and none opened `references/tests.md`
   ([evidence](../../docs/evidence/s1.md#s1-reads)). If tier 3 is never read, the body says enough or the
   pointer to it is too weak.

## Sources

- Source 1: Agent Skills Specification, <https://agentskills.io/specification>, Agent Skills project, n.d.
- Source 2: Agent Skills Overview, <https://agentskills.io/home>, Agent Skills project, n.d.
- Source 3: skills-ref reference validator, <https://github.com/agentskills/agentskills>, Agent Skills project, n.d.
