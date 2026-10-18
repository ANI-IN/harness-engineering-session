# [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)

Reading time: about 15 minutes.
Source: [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler), Nicholas Carlini (Anthropic), 2026-02-05 ([evidence](../../docs/evidence/s3.md#src-anthropic-c-compiler)).

> **Terms on this page**
>
> - **Sandbox**: The container every tool command runs in, the same for both arms.
> - **Out-of-scope file**: A file in the shipped diff that matches none of the allowed paths.

## Why it matters

The post describes a team of agents that worked unattended for a long time, without asking for
permission, on one large codebase. When nobody watches each command, the machine has to set the
limits. This page sums up the parts on running agents unattended and in parallel, and on how the
work was evaluated. They are the course's basis for running every tool command in a container.

## Three key ideas

1. **Unattended agents belong in a container.** The loop ran the agent without permission prompts,
   and the author's advice is short: "(Run this in a container, not your actual machine)." The reason
   is not malice. An agent with a shell can make mistakes that hurt the machine it runs on.

2. **Agents do surprising things by accident.** The author reports that "in one instance, I did see
   Claude pkill -9 bash on accident, thus killing itself and ending the loop." No instruction asked
   for that. A container turns such a mistake into a contained event: the run ends, the host is fine.

3. **One container per agent, and no internet.** "for each agent, a Docker container is spun up with
   the repo mounted to /upstream." And for the result: "Claude did not have internet access at any
   point during its development". Each agent works in its own box, and nothing it does reaches the
   network.

The post also shows what a container does not do. Agents in their own boxes still copied and
duplicated code, so the author added agents to clean it up. A container limits what an agent can
reach, not which files in its own workspace it changes. That second limit is the scope layer.

## Apply it to your repo

1. Run your agent's commands in a container, not on your laptop. Mount only the repository, as a
   working copy.
2. Turn the network off and bake the dependencies into the image, as `platform/sandbox/Dockerfile`
   does. Then a refused install is a fast, clear error, not a silent download.
3. Keep the API keys and the agent loop on the host. Pass no variable named like a key, token, or
   secret into the container.
4. Set limits that stop accidents: a memory cap with no swap, a process limit, and a time limit per
   command. The course's values are in `platform/src/shipharness/sandbox/policy.py`.
5. Then ask the second question: inside the workspace, which files may this task change? A container
   does not answer it.

## Sources

- Source 1: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
