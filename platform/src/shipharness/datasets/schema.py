"""JSONL dataset line models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DatasetKind = Literal["features", "testgen"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeatureInputs(_Strict):
    feature_id: str
    checkpoint: str
    ticket_text: str = Field(min_length=1)
    variant: str
    session_budget: list[int] = Field(min_length=1)


class FeatureReference(_Strict):
    hidden_test_ids: list[str]
    allowed_paths: dict[Literal["build", "test"], list[str]]
    mutant_set: str
    primary_measure: str


class FeatureTask(_Strict):
    inputs: FeatureInputs
    outputs: FeatureReference
    metadata: dict[str, Any]
    split: list[str] = Field(min_length=1)


class TestgenInputs(_Strict):
    target_id: str
    repo: str
    pin: str
    module: str
    existing_tests: list[str]


class TestgenReference(_Strict):
    filter_mutants: str
    referee_mutants: str
    known_failures: list[str]


class TestgenTarget(_Strict):
    inputs: TestgenInputs
    outputs: TestgenReference
    metadata: dict[str, Any]
    split: list[str] = Field(min_length=1)


LINE_MODELS: dict[str, type[_Strict]] = {"features": FeatureTask, "testgen": TestgenTarget}
