"""fresh-session-answers exercise, Python starter.

All five questions are attempted, but three extractors are naive first
drafts with a realistic mistake each (see SPEC.md "Starter state"):
how-organized answers from the instructions file instead of the
architecture doc, how-to-verify grabs the first line that MENTIONS
verification instead of the Verification line, and where-are-we returns
the progress file's heading instead of the Next best step line. Fix the
three per SPEC.md. Run ../../verify.sh --stack=python until it exits 0.
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


def line_mentioning(path: Path, needle: str) -> str | None:
    """Naive helper: first line whose text contains the needle (any case)."""
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").split("\n"):
        if needle in line.lower() and line.strip():
            return line.strip()
    return None


def raw_first_line(path: Path) -> str | None:
    """Naive helper: first non-empty line, headings included."""
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            return line.strip()
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
        # Naive draft: answers "how is it organized" from the instructions
        # file's overview line. Exercise: extract the first prose line of
        # docs/ARCHITECTURE.md, source "docs/ARCHITECTURE.md".
        question(
            "how-organized", "How is it organized?",
            first_prose_line(entry) if entry else None,
            entry.name if entry else None,
        ),
        question(
            "how-to-run", "How do I run it?",
            tagged_line(entry, "Run") if entry else None,
            f"{entry.name} (Run line)" if entry else None,
        ),
        # Naive draft: any line that mentions verification. Prose about
        # verifying is not a verification command. Exercise: extract the
        # "- Verification: <command>" line's value.
        question(
            "how-to-verify", "How do I verify it?",
            line_mentioning(entry, "verif") if entry else None,
            f"{entry.name} (Verification line)" if entry else None,
        ),
        # Naive draft: the file's first line, which is its heading.
        # Exercise: extract the "- Next best step: <text>" line's value.
        question(
            "where-are-we", "Where are we now?",
            raw_first_line(repo / "claude-progress.md"),
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
