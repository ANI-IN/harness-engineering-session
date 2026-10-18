# Codex: agent approvals and security

Reading time: about 20 minutes.
Source: OpenAI, Codex documentation, [Agent approvals & security](https://developers.openai.com/codex/agent-approvals-security), with [Sandboxing concepts](https://developers.openai.com/codex/concepts/sandboxing) and the [Configuration reference](https://developers.openai.com/codex/config-reference), read 2026-10-16 ([evidence](../../docs/evidence/s3.md#src-codex-security)).

> **Terms on this page**
>
> - **Sandbox**: The container every tool command runs in, the same for both arms.
> - **Approval policy**: When an agent must ask a person before it acts.
> - **bwrap and seccomp**: Linux tools that limit which files a process sees and which system calls it may make.
> - **Allowed paths**: The globs a ticket lists for each phase; the files the agent may change then.

## Why it matters

Section 3: Scope and sandbox builds its own boundaries: a container for every command and a scope layer for files.
Coding agents you use every day ship their own. Codex's documentation is a clear example to compare
with: it names the sandbox modes, the approval policies, and the files it protects. Reading it helps
you see what your own agent already does, and what you still have to add.

## Three key ideas

1. **A sandbox mode sets what the agent can touch.** Codex has three modes: `read-only`,
   `workspace-write`, and `danger-full-access`. In `workspace-write`, "The agent can read files, edit
   within the workspace, and run routine local commands inside that boundary." Network is off by
   default: "By default, the agent runs with network access turned off." On Linux, "Linux uses bwrap
   plus seccomp by default."

2. **An approval policy sets when a person is asked.** The valid values are `on-request`, `never`,
   and a granular form. The reference is direct about older names: "untrusted is unsupported, and
   on-failure is deprecated; use on-request for interactive runs or never for non-interactive runs."
   The course's runs are non-interactive, so nobody approves anything; the container and the scope
   layer do that job.

3. **The agent's own control files stay read-only.** In `workspace-write`, `.git`, `.agents`,
   `.codex`, and `.aws` under the writable folders stay read-only. The agent can edit the code but
   not its configuration or history. The course protects the same kind of file one level up: the
   scope layer refuses any change to `feature_list.json`, and the referee removes harness files
   before it judges.

What Codex does not decide is which files belong to this task. Its workspace boundary is the whole
project. Per-task allowed paths, like the list in the ticket for Feature 4: Version checks on issue edits, are
something you add on top, in your harness or in review.

## Apply it to your repo

1. Find your agent's sandbox setting and write it down. Is the network on? Which folders can it
   write?
2. Choose the approval policy by how you run the agent: asked before risky actions when you watch,
   no prompts only inside a sandbox when you do not.
3. List the files that grade or configure the agent: test configuration, CI files, the feature list,
   agent instructions. Check that the agent cannot edit them.
4. For your next ticket, write the allowed paths as globs. After the run, compare them with
   `git diff --name-only` and count the files outside the list.
5. If the count is often above zero, add a check that refuses those changes before they land, as
   `platform/src/shipharness/harness/scope/guard.py` does.

## Sources

- Source 1: Agent approvals & security, <https://developers.openai.com/codex/agent-approvals-security>, OpenAI (Codex documentation), n.d.
- Source 2: Sandboxing concepts, <https://developers.openai.com/codex/concepts/sandboxing>, OpenAI (Codex documentation), n.d.
- Source 3: Configuration reference, <https://developers.openai.com/codex/config-reference>, OpenAI (Codex documentation), n.d.
