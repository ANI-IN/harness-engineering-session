"""handoff-roundtrip exercise, Python starter.

Both directions run, but each carries a naive mistake (see SPEC.md
"Starter state"): the parser keeps only a whitelist of "core" sections and
silently drops the rest, and the renderer sorts sections alphabetically.
Fix both until parse and render round-trip byte-identically. Run
../../verify.sh --stack=python until it exits 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Naive draft: the handoff template's "core" sections. Exercise: a
# round-trip must preserve every section; the parser is not the place to
# decide which parts of a handoff matter.
CORE_SECTIONS = ("Verified now", "Changed this session", "Next best step", "Commands")


def parse(text: str) -> dict:
    title = None
    sections = []
    current: dict | None = None
    for line in text.split("\n"):
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
        elif line.startswith("## "):
            heading = line[3:].strip()
            if heading in CORE_SECTIONS:
                current = {"heading": heading, "items": []}
                sections.append(current)
            else:
                current = None
        elif line.startswith("- ") and current is not None:
            current["items"].append(line[2:].strip())
    return {"title": title, "sections": sections}


def render(document: dict) -> str:
    parts = [f"# {document['title']}"]
    # Naive draft: sorted output looked tidy and deterministic. Exercise: a
    # handoff's section order is meaning (read order is priority order), so
    # render must preserve the document's own order.
    for section in sorted(document["sections"], key=lambda section: section["heading"]):
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
