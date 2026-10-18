"""Part C (reference solution): "git history in the workspace is append-only".

Every pattern starts at a command position (start of the command, or after ; & | ( ` $( or a
newline, then optional VAR=value assignments, sudo, and a path to the binary), so a git command
quoted inside another command's argument (grep -rn "git rebase" docs/) is not refused. Git's
global options (-c k=v, -C dir, --no-pager, --git-dir=...) may come before the subcommand.
"""

from __future__ import annotations

from shipharness.sandbox.policy import DEFAULT_DENY_RULES, DenyRule, SandboxPolicy

HISTORY_MESSAGE = (
    "git history in this workspace is append-only: the harness records evidence by commit SHA. "
    "Make a new commit instead (git revert, or git checkout -- <path> / git restore <path> to "
    "drop changes to one file)."
)

_CMD = r"(?:^|[;&|(`\n]|\$\()\s*(?:\w+=\S*\s+)*(?:sudo\s+)?(?:\S*/)?"
_GIT = _CMD + r"git(?:\s+(?:-[cC]\s+\S+|--?[\w-]+(?:=\S+)?))*\s+"
_ARGS = r"[^;&|\n]*"  # the rest of this simple command
_END = r"(?=\s|$|[;&|)])"
_GIT_DIR = r"(?:\./|/work/)?\.git(?:/(?:refs|logs|objects|HEAD|packed-refs)\S*)?/?"

_PATTERNS: tuple[str, ...] = (
    _GIT + r"commit\b" + _ARGS + r"\s--amend\b",
    _GIT + r"rebase\b",
    _GIT
    + r"reset\b"
    + _ARGS
    + r"\s(?:--hard|--soft|--keep|--merge|(?:HEAD|@)[~^]\S*|ORIG_HEAD|[0-9a-f]{7,40})"
    + _END,
    _GIT + r"(?:update-ref|filter-branch|filter-repo|replace)\b",
    _GIT + r"reflog\s+(?:expire|delete)\b",
    _GIT + r"branch\b" + _ARGS + r"\s(?:-[dDfM]|--delete|--force)" + _END,
    _GIT + r"(?:checkout|switch)\b" + _ARGS + r"\s--orphan\b",
    _CMD + r"(?:rm|mv)\s" + _ARGS + r"?(?<![\w./-])" + _GIT_DIR + _END,
    r">>?\s*(?:\./|/work/)?\.git/(?:refs|logs|HEAD|packed-refs)",
)

HISTORY_RULES: tuple[DenyRule, ...] = tuple(
    DenyRule(pattern=p, reason_code="write_outside_workspace", message=HISTORY_MESSAGE)
    for p in _PATTERNS
)


def policy() -> SandboxPolicy:
    """The default policy plus the history rule, defaults first."""
    return SandboxPolicy(deny_command_patterns=(*DEFAULT_DENY_RULES, *HISTORY_RULES))
