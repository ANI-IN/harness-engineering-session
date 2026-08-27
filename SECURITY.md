# Security policy

## Scope

This repository is an offline learning curriculum: lecture demos, exercises,
and projects that run locally with no network access, no services, and no
credentials. The realistic security surface is:

- shell scripts a learner is instructed to run (`init.sh`, `verify.sh`,
  project scripts);
- the tooling under `tools/` executed by `make` targets and CI;
- dependency supply chain (pinned in `uv.lock` and `pnpm-lock.yaml`).

## Reporting a vulnerability

If you find anything that could harm a learner's machine — a script that
writes outside its unit directory, a command with destructive side effects, a
dependency with a known vulnerability, or anything that exfiltrates data —
please report it via
[GitHub Security Advisories](https://github.com/ANI-IN/harness/security/advisories/new)
(preferred, private) or a GitHub issue if the problem is not sensitive.

Include the file path, the command that triggers the behavior, and what you
observed. You can expect an acknowledgment within a week.

## Hard guarantees this repo maintains

- No unit requires network after `make setup`; nothing calls external APIs.
- No API keys, tokens, or credentials exist anywhere in the tree.
- Verification scripts write only inside their own unit directory or a
  temporary directory (enforced by the verification contract in
  [docs/conventions.md](docs/conventions.md)).
- All shell scripts pass shellcheck in CI.

A violation of any of these is a security bug — please report it.
