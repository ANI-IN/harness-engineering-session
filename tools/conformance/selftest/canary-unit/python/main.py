"""Canary: proves the conformance gate compares real executions. See SPEC.md.

Deliberate cosmetic divergences from the TypeScript track (all of which the
normalizer must absorb): key insertion order, 2-space indent, and Python's
default ASCII-escaping of non-ASCII JSON strings. stderr diagnostics are
deliberately different in wording across the tracks: stderr is not part of
the observable contract.
"""

from __future__ import annotations

import json
import os
import sys


def read_notes(path: str) -> dict[str, object]:
    # Text mode reads translate CRLF to LF (Python universal newlines); the
    # SPEC requires treating LF and CRLF alike, so this is the whole job here.
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    lines = [line for line in text.split("\n") if line.strip()]
    words = [word for line in lines for word in line.split()]
    longest = max(words, key=len) if words else ""
    return {
        "lines": len(lines),
        "words": {
            "total": len(words),
            # len() counts Unicode code points, as the SPEC requires.
            "longest": {"text": longest, "length": len(longest)},
        },
    }


def canary(raw: str) -> dict[str, object]:
    data = json.loads(raw)
    first, second = data["factors"]
    return {
        "label": data["label"],
        "sum": first + second,
        "path": os.path.join(*data["segments"]),
        "segment_count": len(data["segments"]),
        "tags": data["tags"],
        "meta": data["meta"],
        "parent": data["parent"],
        # Deliberately a float where JS can only emit an integer;
        # canonical JSON unifies 2.0 with 2 (RFC 8785 semantics).
        "whole": float(data["whole_factor"]),
        "notes": read_notes(data["notes_file"]),
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    out_path = None
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]
        args = [a for a in argv[1:] if a != "--out" and a != out_path]
    if len(args) != 1:
        print("usage: main.py <input.json> [--out <file>]", file=sys.stderr)
        return 2
    try:
        with open(args[0], encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as error:
        print(f"error: cannot read input: {error}", file=sys.stderr)
        return 2

    print(f"canary: reading {args[0]}", file=sys.stderr)
    result = canary(raw)
    print("canary: notes loaded, emitting report", file=sys.stderr)

    # json.dumps defaults to ensure_ascii=True: non-ASCII is \uXXXX-escaped
    # here, while the TypeScript track emits literal UTF-8. Deliberate.
    rendered = json.dumps(result, indent=2)
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
        print(f"wrote {out_path}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
