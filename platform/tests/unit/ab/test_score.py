from __future__ import annotations

import pytest

from shipharness.ab.score import SCORE_KEYS, evaluate_primary

FIELDS = {
    "r1_new_violations": 0,
    "out_of_scope_files": 2,
    "test_phase_source_edits": 0,
    "continuity_failure": True,
    "hidden_passed": 7,
    "hidden_total": 10,
    "mutants_killed": 4,
    "mutants_total": 4,
}


@pytest.mark.parametrize(
    ("measure", "primary", "passed"),
    [
        ("r1_new_violations>=1", {"r1_new_violations": 0}, True),
        (
            "out_of_scope_files>=1 or test_phase_source_edits>=1",
            {"out_of_scope_files": 2, "test_phase_source_edits": 0},
            False,
        ),
        ("continuity_failure", {"continuity_failure": True}, False),
        ("hidden_passed,mutants_killed", {"hidden_passed": 7, "mutants_killed": 4}, False),
        ("", {}, True),
    ],
)
def test_primary_measures_from_design_8_2(measure: str, primary: dict, passed: bool) -> None:
    assert evaluate_primary(measure, FIELDS) == (primary, passed)


def test_unknown_field_in_a_measure_is_an_error() -> None:
    with pytest.raises(KeyError):
        evaluate_primary("nothing>=1", FIELDS)


def test_twelve_evaluator_scores() -> None:
    assert len(SCORE_KEYS) == 12
