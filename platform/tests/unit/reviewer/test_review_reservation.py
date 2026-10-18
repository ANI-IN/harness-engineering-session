"""Reviews reserve their worst case against every cap before the call (like the agent loop), so two
concurrent reviews can never both take the last room under a shared cap."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from shipharness.config import DEFAULT_PRICES_FILE, Prices
from shipharness.cost import Caps, CostTracker
from shipharness.reviewer import ReviewInput, run_review
from shipharness.reviewer.review import build_messages, max_output_tokens_for
from shipharness.tracing import NullTracer

from .test_review import GOOD

PRICES = Prices.load(DEFAULT_PRICES_FILE)
MODEL = "gpt-6-luna"
INPUT = ReviewInput(task="Add pagination.", diff="+x = 1\n", grading_criteria="R1 tenant isolation")


class Rendezvous:
    """Holds every model call until both reviews have either called the model or finished."""

    def __init__(self, parties: int) -> None:
        self.parties = parties
        self.arrived = 0
        self.cond = threading.Condition()

    def arrive_and_wait(self) -> None:
        with self.cond:
            self.arrived += 1
            self.cond.notify_all()
            self.cond.wait_for(lambda: self.arrived >= self.parties, timeout=10)

    def leave(self) -> None:
        with self.cond:
            self.arrived += 1
            self.cond.notify_all()


class WorstCaseResponses:
    """Every call spends its full worst case (all input uncached, every output token)."""

    def __init__(self, meeting: Rendezvous) -> None:
        self.meeting = meeting
        self.calls = 0

    def parse(self, **kwargs: Any) -> Any:
        self.calls += 1
        self.meeting.arrive_and_wait()
        est_input = len(json.dumps(build_messages(INPUT))) // 3 + 200
        usage = SimpleNamespace(
            input_tokens=est_input,
            output_tokens=kwargs["max_output_tokens"],
            input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        )
        return SimpleNamespace(
            output_parsed=GOOD, status="completed", usage=usage, output=[], incomplete_details=None
        )


def test_two_concurrent_reviews_never_overshoot_the_session_cap(tmp_path: Path) -> None:
    review_cap = 0.04
    price = PRICES.get(MODEL)
    est_input = len(json.dumps(build_messages(INPUT))) // 3 + 200
    budget = max_output_tokens_for(price, est_input, review_cap)
    worst = (est_input * max(price.input, price.cache_write) + budget * price.output) / 1e6
    session_cap = round(worst * 1.5, 6)  # room for one review's worst case, not two
    tracker = CostTracker(
        PRICES,
        Caps(run=0.2, review=review_cap, session=session_cap, batch=2.5, experiment=25.0),
        tmp_path / "ledger.jsonl",
        session_id="t",
    )
    meeting = Rendezvous(parties=2)
    responses = WorstCaseResponses(meeting)
    client = SimpleNamespace(responses=responses)
    start = threading.Barrier(2)
    outcomes: list[Any] = []

    def review() -> None:
        start.wait()
        try:
            outcomes.append(run_review(INPUT, tracker, NullTracer(), client=client, model=MODEL))
        finally:
            meeting.leave()  # a review that never called the model lets the other one proceed

    threads = [threading.Thread(target=review) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert sorted(o.status for o in outcomes) == ["cap", "ok"]
    assert responses.calls == 1  # the second review never reached the model
    assert tracker.session_total_usd <= session_cap
    assert tracker.reserved_usd == 0  # every reservation was settled or released


def test_a_failed_review_call_releases_its_reservation(tmp_path: Path) -> None:
    tracker = CostTracker(
        PRICES, Caps(0.2, 0.04, 2.5, 2.5, 25.0), tmp_path / "ledger.jsonl", session_id="t"
    )

    class Boom:
        def parse(self, **kwargs: Any) -> Any:
            raise ValueError("bad request")

    outcome = run_review(
        INPUT, tracker, NullTracer(), client=SimpleNamespace(responses=Boom()), model=MODEL
    )
    assert outcome.status == "error"
    assert tracker.reserved_usd == 0
