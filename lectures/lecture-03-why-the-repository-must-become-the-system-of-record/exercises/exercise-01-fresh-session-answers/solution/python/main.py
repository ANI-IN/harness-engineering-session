"""fresh-session-answers exercise, Python solution: the fresh-session test.

Answers the five questions a brand-new agent session must be able to answer
from repository contents alone, extracting each answer from a specific
language-neutral artifact per SPEC.md. Exit code 1 when any question is
unanswered: a fresh session cannot start work on this repository without
guessing.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def first_prose_line(path: Path) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


def tagged_line(path: Path, tag: str) -> str | None:
    if not path.is_file():
        return None
    match = re.search(
        rf"^- {re.escape(tag)}: (.+)$", path.read_text(encoding="utf-8"), re.MULTILINE
    )
    return match.group(1).strip() if match else None


def instructions_file(repo: Path) -> Path | None:
    for name in ("AGENTS.md", "CLAUDE.md"):
        if (repo / name).is_file():
            return repo / name
    return None


def read_repo(repo: Path) -> dict:
    entry = instructions_file(repo)

    def question(qid: str, text: str, answer: str | None, source: str | None) -> dict:
        return {
            "id": qid,
            "question": text,
            "answered": answer is not None,
            "answer": answer,
            "source": source if answer is not None else None,
        }

    questions = [
        question(
            "what-is-this", "What is this system?",
            first_prose_line(entry) if entry else None,
            entry.name if entry else None,
        ),
        question(
            "how-organized", "How is it organized?",
            first_prose_line(repo / "docs" / "ARCHITECTURE.md"),
            "docs/ARCHITECTURE.md",
        ),
        question(
            "how-to-run", "How do I run it?",
            tagged_line(entry, "Run") if entry else None,
            f"{entry.name} (Run line)" if entry else None,
        ),
        question(
            "how-to-verify", "How do I verify it?",
            tagged_line(entry, "Verification") if entry else None,
            f"{entry.name} (Verification line)" if entry else None,
        ),
        question(
            "where-are-we", "Where are we now?",
            tagged_line(repo / "claude-progress.md", "Next best step"),
            "claude-progress.md (Next best step line)",
        ),
    ]

    answered = sum(1 for q in questions if q["answered"])
    total = len(questions)
    return {
        "questions": questions,
        "answered": answered,
        "total": total,
        "visibility_gap": (total - answered) / total if total else 0.0,
        "ready": answered == total,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <repo-dir>", file=sys.stderr)
        return 2
    repo = Path(argv[1])
    if not repo.is_dir():
        print(f"error: not a directory: {repo}", file=sys.stderr)
        return 2
    report = read_repo(repo)
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
