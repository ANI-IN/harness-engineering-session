"""Reviewer data models. `Review` is the strict structured-output schema; findings
come before the verdict so the model reasons about problems before it decides."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: str  # ticket text
    diff: str  # blinded unified diff
    grading_criteria: str  # stable text from SECURITY.md + ARCHITECTURE.md


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str
    line: int | None
    severity: Literal["blocker", "major", "minor"]
    criterion: str
    comment: str


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    findings: list[ReviewFinding]
    tenant_isolation_risk: Literal["none", "possible", "likely"]
    verdict: Literal["accept", "reject"]
    summary: str
