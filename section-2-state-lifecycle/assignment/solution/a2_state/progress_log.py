"""progress.md kept whole: its sections in order and one log entry per session.

The agent owns Done, In progress, and Next; the harness owns the Session log. When the agent
rewrites the file, the missing sections come back from the template, what the agent wrote is kept,
and the log is rebuilt from the harness's own list of entries (it never trusts the file's copy).
"""

from __future__ import annotations

TITLE = "# Progress"
AGENT_SECTIONS = ("## Current feature", "## Done", "## In progress", "## Next")
SESSION_LOG = "## Session log"


def _blocks(text: str) -> list[tuple[str, list[str]]]:
    """(heading, body lines) in order; the text before the first heading has heading ""."""
    blocks: list[tuple[str, list[str]]] = [("", [])]
    for line in text.replace("\r\n", "\n").splitlines():
        if line.startswith(("# ", "## ")):
            blocks.append((line.strip(), []))
        else:
            blocks[-1][1].append(line)
    return blocks


def _trim(lines: list[str]) -> list[str]:
    start = next((i for i, line in enumerate(lines) if line.strip()), len(lines))
    end = len(lines) - next((i for i, line in enumerate(reversed(lines)) if line.strip()), 0)
    return [line.rstrip() for line in lines[start:end]]


def normalise_progress(text: str, template: str, entries: list[str]) -> str:
    have: dict[str, list[str]] = {}
    extras: list[str] = []
    for heading, body in _blocks(text):
        if heading in have:
            have[heading] += body
            continue
        have[heading] = list(body)
        if heading not in ("", TITLE, SESSION_LOG, *AGENT_SECTIONS):
            extras.append(heading)
    defaults = dict(_blocks(template))
    title = _trim(have.get(TITLE, defaults.get(TITLE, [])))
    preamble = _trim(have.get("", []))
    parts: list[tuple[str, list[str]]] = [(TITLE, title + ([""] if title and preamble else []))]
    parts[0][1].extend(preamble)
    for heading in AGENT_SECTIONS:
        parts.append((heading, _trim(have.get(heading, [])) or _trim(defaults.get(heading, []))))
    parts += [(heading, _trim(have[heading])) for heading in extras]
    parts.append((SESSION_LOG, list(entries)))
    rendered = [f"{h}\n\n" + "\n".join(body) if body else h for h, body in parts]
    return "\n\n".join(rendered) + "\n"
