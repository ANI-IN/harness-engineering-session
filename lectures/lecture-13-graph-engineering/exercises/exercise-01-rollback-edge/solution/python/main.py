"""rollback-edge: the node a rollback edge leads to.

The lecture's graph declares one rollback edge, and the node at the end of
it replays the apply journal. This surface is that node on its own: given
the workspace as it stands after a failed verification and the journal of
what the run wrote, decide for each operation whether it can be reverted,
revert the ones that can, and report the residue.

Reverting is safe only from the tip. An appended line may be removed only
while it is still the last line of its file, and a created file may be
removed only while it still holds exactly the lines the run wrote. The
journal is therefore replayed in reverse: the last write is the first one
undone, which puts each earlier write back at the tip in turn.

The workspace is read once and reverted in memory, so the committed
fixtures never change. SPEC.md pins the journal shape, the two operation
kinds, the report, and the exit codes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_workspace(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


def lines_of(text: str) -> list[str]:
    """Non-empty lines, LF or CRLF alike (docs/conventions.md, semantic rules)."""
    return [line for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line]


def join_lines(lines: list[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


def revert(files: dict[str, str], operation: dict) -> tuple[bool, str, str]:
    """Try to reverse one journalled write. Returns whether it was reverted,
    the target it names, and the sentence explaining the outcome."""
    path = operation["path"]
    body = lines_of(files.get(path, ""))
    if operation["op"] == "create":
        if body == operation["lines"]:
            del files[path]
            return True, path, f"removed {path}, which still held only the lines this run wrote"
        return (
            False,
            path,
            f"{path} no longer holds the lines this run created, so removing it "
            "would discard a later change",
        )
    line = operation["line"]
    if body and body[-1] == line:
        files[path] = join_lines(body[:-1])
        return True, line, f"removed the last line {line} from {path}"
    return (
        False,
        line,
        f"{line} is no longer the last line of {path}, so removing it would "
        "discard a later change",
    )


def rollback(files: dict[str, str], journal: dict) -> list[dict]:
    """Replay the journal so the most recent write is undone first, and
    report the rows in journal order whatever order they were attempted in."""
    operations = journal["operations"]
    rows: list[dict | None] = [None] * len(operations)
    for index in reversed(range(len(operations))):
        operation = operations[index]
        reverted, target, why = revert(files, operation)
        rows[index] = {
            "index": index,
            "op": operation["op"],
            "outcome": "reverted" if reverted else "kept",
            "path": operation["path"],
            "target": target,
            "why": why,
        }
    return [row for row in rows if row is not None]


def residue_of(rows: list[dict]) -> list[str]:
    left = []
    for row in rows:
        if row["outcome"] == "reverted":
            continue
        if row["op"] == "create":
            left.append(f"{row['path']} is still in the workspace")
        else:
            left.append(f"{row['path']} still carries {row['target']}")
    return left


def report(root: Path, journal: dict) -> dict:
    files = load_workspace(root)
    rows = rollback(files, journal)
    residue = residue_of(rows)
    return {
        "workspace": root.name,
        "session": journal["session"],
        "operations": rows,
        "residue": residue,
        "restored": not residue,
        "verdict": "restored" if not residue else "residue-left",
    }


USAGE = "usage: main.py <workspace-dir> <journal-file>"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(USAGE, file=sys.stderr)
        return 2
    root, journal_path = Path(argv[1]), Path(argv[2])
    if not root.is_dir():
        print(f"error: not a workspace directory: {argv[1]}", file=sys.stderr)
        return 2
    if not journal_path.is_file():
        print(f"error: no journal file at {argv[2]}", file=sys.stderr)
        return 2
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    result = report(root, journal)
    print(json.dumps(result, indent=2))
    return 0 if result["restored"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
