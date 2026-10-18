"""Constructed examples (`shipharness example --section demo-N`, `make example-N`).

Each class section without a measured gap shows a live harness-arm run (`make show-N`), a real
mistake replayed (RECORDING), and one constructed example from this package. A constructed example
runs the harness arm with section N's layer stack on its canonical task and checkpoint, in the real
sandbox, judged by the real referee; only the model is replaced by scripted steps that make the
mistake the layer exists to catch. It costs $0, needs no API key, and is marked "constructed" in its
run record, its score, and on every console screen; no report or comparison counts it.

One file per scenario: demo1_instructions, demo2_state, demo3_scope, demo4_verify.
"""

from __future__ import annotations

from shipharness.examples import demo1_instructions, demo2_state, demo3_scope, demo4_verify
from shipharness.examples.base import Scenario

CONSTRUCTED_BADGE = "CONSTRUCTED EXAMPLE: scripted steps, no model"
SCENARIOS: dict[str, Scenario] = {
    module.SCENARIO.section: module.SCENARIO
    for module in (demo1_instructions, demo2_state, demo3_scope, demo4_verify)
}

__all__ = ["CONSTRUCTED_BADGE", "SCENARIOS", "Scenario"]
