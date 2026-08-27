"""handoff-roundtrip exercise, Python solution.

Parses a session-handoff file into structured JSON and renders it back.
The two directions must round-trip byte-identically on the canonical
format, which is what makes the handoff machine-checkable instead of
prose. Contract: ../../SPEC.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def parse(text: str) -> dict:
    title = None
    sections = []
    current: dict | None = None
    for line in text.split("\n"):
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
        elif line.startswith("## "):
            current = {"heading": line[3:].strip(), "items": []}
            sections.append(current)
        elif line.startswith("- ") and current is not None:
            current["items"].append(line[2:].strip())
    return {"title": title, "sections": sections}


def render(document: dict) -> str:
    parts = [f"# {document['title']}"]
    for section in document["sections"]:
        parts.append("")
        parts.append(f"## {section['heading']}")
        parts.append("")
        for item in section["items"]:
            parts.append(f"- {item}")
    return "\n".join(parts) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("parse", "render"):
        print("usage: main.py parse <handoff.md> | render <handoff.json>", file=sys.stderr)
        return 2
    try:
        text = Path(argv[2]).read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: cannot read input: {error}", file=sys.stderr)
        return 2
    if argv[1] == "parse":
        print(json.dumps(parse(text), indent=2))
    else:
        try:
            document = json.loads(text)
        except json.JSONDecodeError as error:
            print(f"error: malformed handoff JSON: {error}", file=sys.stderr)
            return 1
        sys.stdout.write(render(document))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
