"""Harness decision type shared by the runner and the layers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

DecisionKind = Literal[
    "allow",
    "block",
    "revert",
    "gate_fail",
    "gate_pass",
    "status_set",
    "session_stop",
    "session_resume",
    "note",
]
LayerName = Literal["instructions", "state", "scope", "verify"]


class HarnessDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: DecisionKind
    layer: LayerName
    message: str = ""
    paths: list[str] = []
    data: dict[str, Any] = {}

    @classmethod
    def allow(cls, layer: LayerName = "scope") -> HarnessDecision:
        return cls(kind="allow", layer=layer)
