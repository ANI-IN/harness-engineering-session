"""progress.md kept whole: its six sections in order and one log entry per session.

The sections, in this order: `# Progress`, `## Current feature`, `## Done`, `## In progress`,
`## Next`, `## Session log`. The agent edits the four middle sections; the harness owns the session
log (one `- Session <n> ...` entry per session).
"""

from __future__ import annotations

TITLE = "# Progress"
AGENT_SECTIONS = ("## Current feature", "## Done", "## In progress", "## Next")
SESSION_LOG = "## Session log"


def normalise_progress(text: str, template: str, entries: list[str]) -> str:
    """progress.md with every section in order and the session log rebuilt from `entries`.

    `text` is the file as the agent left it (it may have rewritten the whole file); `template` is
    the initializer's version; `entries` is the harness's own list of session-log lines.

    TODO 4:
    - output `# Progress`, then the four agent sections, then `## Session log` last;
    - keep what the agent wrote in a section; take a missing section from `template`;
    - keep any other section the agent added (before the session log);
    - the session log is exactly `entries`, never the file's old copy (no duplicates, nothing lost).
    """
    return text
