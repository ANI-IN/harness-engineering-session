"""Live check of both API keys. Run with: uv run pytest -m live tests/live"""

from __future__ import annotations

import pytest

from shipharness.config import Settings
from shipharness.doctor import RealProbes, run_doctor

pytestmark = pytest.mark.live


def test_both_keys_are_valid() -> None:
    settings = Settings()
    if settings.openai_api_key is None or settings.langsmith_api_key is None:
        pytest.skip("both keys are required for live tests")
    report = run_doctor(settings, offline=False, probes=RealProbes())
    statuses = {c.name: c.status for c in report.checks}
    assert statuses["OPENAI_API_KEY"] == "ok", report.render()
    assert statuses["LANGSMITH_API_KEY"] == "ok", report.render()
    assert statuses["agent model"] == "ok", report.render()
    assert statuses["reviewer model"] == "ok", report.render()
