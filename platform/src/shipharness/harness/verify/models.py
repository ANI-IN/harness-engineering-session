"""Gate result types."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

GateStatus = Literal["pending", "pass", "fail", "skipped"]


class GateItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str  # "visible tests", "existing tests", "R1".."R7", "board", "clean state"
    status: GateStatus
    detail: str = ""


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_id: str
    items: list[GateItem]
    passed: bool
    feedback: str  # sent to the agent on failure: first three failures, one per line
