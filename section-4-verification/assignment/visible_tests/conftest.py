"""Visible A4 tests: run against the implementation in `A4_IMPL` (default: the starter)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from a4_support import (  # noqa: E402, F401
    impl,
    impl_path,
    pytest_collection_modifyitems,
    pytest_configure,
    pytest_runtest_logreport,
    pytest_sessionfinish,
)
