"""Negative proof for the acceptance-run count checker."""

from tools import check_build_state


def test_missing_exercise_entry_detected():
    errors = check_build_state.check({"acceptance_runs": {}}, ["lecture-01/exercise-01-x"])
    assert len(errors) == 1
    assert "no acceptance runs recorded" in errors[0]


def test_partial_runs_detected():
    state = {
        "acceptance_runs": {
            "lecture-01/exercise-01-x": {
                "starter-python": {"exit": 1},
                "solution-python": {"exit": 0},
                "solution-typescript": {"exit": 0},
            }
        }
    }
    errors = check_build_state.check(state, ["lecture-01/exercise-01-x"])
    assert len(errors) == 1
    assert "3/4 acceptance runs recorded" in errors[0]
    assert "starter-typescript" in errors[0]


def test_complete_record_passes():
    state = {
        "acceptance_runs": {
            "lecture-01/exercise-01-x": {
                "starter-python": {"exit": 1},
                "starter-typescript": {"exit": 1},
                "solution-python": {"exit": 0},
                "solution-typescript": {"exit": 0},
            }
        }
    }
    assert check_build_state.check(state, ["lecture-01/exercise-01-x"]) == []
