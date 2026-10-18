"""Grade one assignment submission (instructor only; the graders are private to the instructor).

    make grade-assignment-N SUBMISSION=<folder or git URL>
    uv run python platform/scripts/grade_assignment.py N <folder or git URL>

A git URL is cloned shallow into a temporary folder; a folder is graded in place. The grader for
assignment N sits in the grader folder of the section's reference solution: the solution ships
in the public release, its grader does not. The grader's exit code is passed through.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
FLAGS = {1: "--work", 2: "--impl", 3: "--impl", 4: "--impl"}
_URL_PREFIXES = ("https://", "http://", "ssh://", "git://", "file://", "git@")


class SubmissionError(RuntimeError):
    """The submission or the grader cannot be found."""


def is_git_url(value: str) -> bool:
    return value.startswith(_URL_PREFIXES)


def resolve_submission(value: str, clone_dir: Path) -> Path:
    if is_git_url(value):
        done = subprocess.run(
            ["git", "clone", "-q", "--depth", "1", value, str(clone_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode != 0:
            raise SubmissionError(f"git clone failed: {done.stderr.strip()[:300]}")
        return clone_dir
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise SubmissionError(f"submission folder not found: {path}")
    return path


def grader_command(n: int, submission: Path) -> list[str]:
    grader = f"section-{n}-*/assignment/solution/grader/grade.py"  # private, not shipped
    found = sorted(REPO.glob(grader))
    if not found:
        raise SubmissionError(
            f"no grader for assignment {n}: graders are private to the instructor"
        )
    return [sys.executable, str(found[0]), FLAGS[n], str(submission)]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] not in {"1", "2", "3", "4"}:
        print("usage: grade_assignment.py N <folder or git URL>   (N = 1..4)", file=sys.stderr)
        return 2
    n = int(args[0])
    with tempfile.TemporaryDirectory(prefix=f"grade-a{n}-") as tmp:
        try:
            submission = resolve_submission(args[1], Path(tmp) / "submission")
            command = grader_command(n, submission)
        except SubmissionError as exc:
            print(f"! {exc}", file=sys.stderr)
            return 2
        print(f"grading assignment {n}: {args[1]}")
        return subprocess.run(command, cwd=REPO, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
