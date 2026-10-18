"""REPLACE markers: the one greppable form every kit template uses for a value to fill.

- Markdown: `<!-- REPLACE: what the field means; the TeamTrack value is shown below -->`
- Shell, YAML, TOML, Python, and text files: `# REPLACE: ...`
- JSON: a `"_replace": "..."` key (the feature list schema rejects it, so an unfilled list fails
  validation)

`grep -rn "REPLACE:\\|_replace" .` finds the same lines as `shipharness init --check`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from shipharness.kit.files import TEMPLATES, template_files

_MARKER = re.compile(
    r"<!--\s*REPLACE:\s*(?P<md>.*?)\s*-->"
    r"|(?:^|\s)#\s*REPLACE:\s*(?P<hash>.*?)\s*$"
    r'|"_replace"\s*:\s*"(?P<json>(?:[^"\\]|\\.)*)"'
)


@dataclass(frozen=True)
class Marker:
    path: str
    line: int
    text: str


def find_markers(text: str, path: str = "") -> list[Marker]:
    """Every marker in `text`, in order, with its line number and explanation."""
    found: list[Marker] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in _MARKER.finditer(line):
            message = match.group("md") or match.group("hash") or match.group("json") or ""
            found.append(Marker(path=path, line=number, text=message))
    return found


def unfilled(target: Path, templates: Path = TEMPLATES) -> tuple[list[Marker], list[str]]:
    """(markers still in the kit files of `target`, kit files not present in `target`)."""
    markers: list[Marker] = []
    missing: list[str] = []
    for rel in template_files(templates):
        path = target / rel
        if not path.is_file():
            missing.append(rel)
            continue
        markers += find_markers(path.read_text(encoding="utf-8", errors="replace"), rel)
    return markers, missing
