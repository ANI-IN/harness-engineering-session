"""The solution's package (`a4_verification`) sits beside this folder; put it on the path so
the tests run from the repository root like the other assignments' tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
