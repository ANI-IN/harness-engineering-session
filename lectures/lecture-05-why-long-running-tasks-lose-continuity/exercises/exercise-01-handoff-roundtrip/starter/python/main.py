"""handoff-roundtrip exercise, Python starter.

Both directions run, but each carries a naive mistake (see SPEC.md
"Starter state"): the parser keeps the "- " bullet prefix on items, and
the renderer omits the blank line after each section heading. Fix both
until parse and render round-trip byte-identically. Run
../../verify.sh --stack=python until it exits 0.
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
            # Naive draft: the bullet marker is markdown syntax, not item
            # content. Exercise: store the item text without the "- " prefix.
            current["items"].append(line.strip())
    return {"title": title, "sections": sections}


def render(document: dict) -> str:
    parts = [f"# {document['title']}"]
    for section in document["sections"]:
        parts.append("")
        parts.append(f"## {section['heading']}")
        # Naive draft: canonical form separates a heading from its items
        # with a blank line. Exercise: emit it, or the round-trip drifts.
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
