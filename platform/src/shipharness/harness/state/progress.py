"""progress.md: the agent edits every section; the harness appends the log."""

from __future__ import annotations

from shipharness.log_setup import mask_keys
from shipharness.runner.models import SessionResult

SESSION_LOG = "## Session log"


# [walkthrough:S2:write] start
def session_entry(
    result: SessionResult, files_changed: int, tests: str, claim_summary: str = ""
) -> str:
    """One log line: index, start/end commit, how the session ended, and a summary."""
    entry = (
        f"- Session {result.index} ({result.phase}): start {result.start_sha[:7] or 'none'}, "
        f"end {result.end_sha[:7] or 'none'}, ended by {result.ended_by} after "
        f"{result.turns} turns. {files_changed} files changed; visible tests {tests}."
    )
    summary = " ".join(mask_keys(claim_summary).split())[:200]
    return entry + (f' Agent summary: "{summary}"' if summary else "")


def append_session_entry(text: str, entry: str) -> str:
    """Append `entry` under "## Session log", restoring the heading if the agent removed it.

    The log is the last section, so appending at the end keeps the agent's other edits intact.
    """
    lines = text.replace("\r\n", "\n").rstrip("\n")
    if not any(line.strip() == SESSION_LOG for line in lines.splitlines()):
        lines += f"\n\n{SESSION_LOG}"
    separator = "\n\n" if lines.endswith(SESSION_LOG) else "\n"
    return f"{lines}{separator}{entry}\n"


# [walkthrough:S2:write] end
