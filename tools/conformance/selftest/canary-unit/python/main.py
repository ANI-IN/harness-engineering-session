"""Canary: proves the conformance gate compares real executions. See SPEC.md.

Keys are emitted in insertion order label, sum, path, segment_count with
2-space indent; the TypeScript track deliberately differs (reverse order,
4-space indent, trailing spaces) so the normalizer is exercised on every run.
"""

from __future__ import annotations

import json
import os
import sys


def canary(raw: str) -> dict[str, object]:
    data = json.loads(raw)
    first, second = data["factors"]
    return {
        "label": data["label"],
        "sum": first + second,
        "path": os.path.join(*data["segments"]),
        "segment_count": len(data["segments"]),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <input.json>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as error:
        print(f"error: cannot read input: {error}", file=sys.stderr)
        return 2
    print(json.dumps(canary(raw), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
