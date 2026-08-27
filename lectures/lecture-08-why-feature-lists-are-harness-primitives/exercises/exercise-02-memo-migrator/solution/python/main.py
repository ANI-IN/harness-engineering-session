"""memo-migrator exercise, Python solution.

Turns a prose progress memo plus the authoritative scope into a canonical
feature_list.json draft. Scope comes from scope.json only; the memo
contributes claims, and a claim is not evidence: a feature the memo calls
done becomes in-progress with the claim preserved in notes, never
passing. Contract: ../../SPEC.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_CONFLICT = 1
EXIT_USAGE = 2

MEMO_LINE = re.compile(r"^- ([a-z][a-z0-9]*(?:-[a-z0-9]+)*): (.+)$")
REMAINING_WORDS = ("need", "todo")


def parse_memo(text: str) -> list[tuple[str, str]]:
    mentions = []
    for line in text.splitlines():
        match = MEMO_LINE.match(line)
        if match:
            mentions.append((match.group(1), match.group(2).strip()))
    return mentions


def reads_as_remaining(prose: str) -> bool:
    lowered = prose.lower()
    return any(word in lowered for word in REMAINING_WORDS)


def migrate(scope: dict, memo_text: str) -> tuple[dict | None, str | None]:
    known = {feature["id"] for feature in scope["features"]}
    claims: dict[str, str] = {}
    for feature_id, prose in parse_memo(memo_text):
        if feature_id not in known:
            return None, (
                f"memo mentions unknown feature '{feature_id}'; scope comes from scope.json"
            )
        if reads_as_remaining(prose):
            claims.pop(feature_id, None)
        else:
            claims[feature_id] = prose
    features = []
    for feature in scope["features"]:
        entry = {
            "id": feature["id"],
            "title": feature["title"],
            "behavior": feature["behavior"],
            "verification": feature["verification"],
        }
        if feature["id"] in claims:
            entry["status"] = "in-progress"
            entry["notes"] = f'unverified claim from notes.md: "{claims[feature["id"]]}"'
        else:
            entry["status"] = "not-started"
        features.append(entry)
    return {"project": scope["project"], "updated": scope["as_of"], "features": features}, None


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: main.py <scope.json> <notes.md>", file=sys.stderr)
        return EXIT_USAGE
    try:
        scope = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        memo_text = Path(argv[2]).read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: cannot read input: {error}", file=sys.stderr)
        return EXIT_USAGE
    draft, conflict = migrate(scope, memo_text)
    if draft is None:
        print(f"error: {conflict}", file=sys.stderr)
        return EXIT_CONFLICT
    print(json.dumps(draft, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
