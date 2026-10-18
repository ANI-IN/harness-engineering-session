"""Put the implementation under test first on sys.path.

A3_IMPL names the folder that holds the `a3scope` package (default: ../starter). The self-check
(check.py) and the grader set it; you can also run these tests directly (repository root):
    uv run python -m pytest -q -p no:cacheprovider \
        section-3-scope-sandbox/assignment/visible_tests
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPL = Path(os.environ.get("A3_IMPL") or HERE.parent / "starter").resolve()
for folder in (HERE, IMPL):  # HERE: the shared helpers in a3_checks.py
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
