"""Harness freeze (owner rule, M6): once the pilot gate passes, `harness-frozen` pins everything
that affects M8 results (treatment, measurement, tasks, environment; `shipharness.freeze`).

After the tag, any change under a frozen path, a moved checkpoint tag, or a changed run setting
fails this test; such a change would require re-running M8. Without the tag (before the gate
passes, or a shallow CI checkout) the test is skipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shipharness import freeze
from shipharness.config import Settings
from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))


def test_nothing_frozen_has_changed_since_the_harness_frozen_tag() -> None:
    if freeze.read_record(REPO) is None:
        pytest.skip(f"no {freeze.TAG} tag yet")
    effective = Settings(_env_file=REPO / ".env")  # values compared, never printed
    found = freeze.problems(REPO, effective)
    assert found == [], "changed since harness-frozen (re-run M8 or revert):\n" + "\n".join(found)
