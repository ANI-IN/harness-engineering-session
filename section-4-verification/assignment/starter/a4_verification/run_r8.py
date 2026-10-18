"""Run R8 through the shipharness check runner (no Docker; the build's code runs in this process).

    uv run python -m a4_verification.run_r8 --build teamtrack --checkpoint m1-base --feature A4 \\
        [--baseline <results.json>] [--params <params.json>] [--adapter module:attr]

Importing `a4_verification` registers `r8_soft_delete`; everything else is
`python -m shipharness.checks.runner` with `--checks r8_soft_delete`: the same JSON document on
stdout, progress lines on stderr, and exit codes 0 (no new violations), 3 (new violations),
1 (error). Pass a previous run's stdout as `--baseline` to count only new findings.
"""

from __future__ import annotations

import sys

import a4_verification  # noqa: F401  (registers the r8_soft_delete check)
from shipharness.checks import runner


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--checks" not in args:
        args = ["--checks", "r8_soft_delete", *args]
    return runner.main(args)


if __name__ == "__main__":
    sys.exit(main())
