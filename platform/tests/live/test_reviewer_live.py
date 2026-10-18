"""Live test of the blinded reviewer against the real Responses API (cap $0.01).

Run with: uv run pytest -m live tests/live/test_reviewer_live.py -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.ab.clients import make_openai_client
from shipharness.config import Prices, Settings
from shipharness.cost import Caps, CostTracker
from shipharness.reviewer import Review, ReviewInput, blind, grading_criteria, run_review
from shipharness.tracing import make_tracer

pytestmark = pytest.mark.live

LEAKY_DIFF = """diff --git a/app/repositories/issues.py b/app/repositories/issues.py
index 1111111..2222222 100644
--- a/app/repositories/issues.py
+++ b/app/repositories/issues.py
@@ -20,6 +20,10 @@ def list_for_project(session, org_id, project_id, cursor, limit):
     return rows
+
+
+def search(session, text):
+    return session.query(Issue).filter(Issue.title.contains(text)).all()
diff --git a/progress.md b/progress.md
--- a/progress.md
+++ b/progress.md
@@ -1 +1,2 @@
 # Progress
+- added search
"""


def test_reviewer_returns_a_structured_review_within_one_cent(tmp_path: Path) -> None:
    settings = Settings()
    if settings.openai_api_key is None:
        pytest.skip("OPENAI_API_KEY is required")
    cost = CostTracker(
        Prices.load(settings.prices_file),
        Caps(run=0.0, review=0.01, session=0.01, batch=0.01, experiment=0.01),
        tmp_path / "ledger.jsonl",
        session_id="live-reviewer",
    )
    tracer = make_tracer(settings, "shipharness-pilot")  # never a class project
    diff = blind(LEAKY_DIFF)
    assert "progress.md" not in diff
    outcome = run_review(
        ReviewInput(
            task="Add GET /issues/search?q= that searches issue titles in the caller's org.",
            diff=diff,
            grading_criteria=grading_criteria(),
        ),
        cost,
        tracer,
        client=tracer.wrap_openai(make_openai_client(settings)),
        model=settings.openai_eval_model,
        effort="low",
        limit_usd=0.01,
    )
    if outcome.review is not None:
        print("\n" + outcome.review.model_dump_json(indent=2))
    ledger = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip()
    print(f"\nledger: {ledger}")
    print(f"review status={outcome.status} cost=${outcome.cost_usd:.6f} {outcome.detail}")
    assert outcome.cost_usd <= 0.01
    assert outcome.status in ("ok", "incomplete")
    if outcome.status == "ok":
        assert isinstance(outcome.review, Review)
