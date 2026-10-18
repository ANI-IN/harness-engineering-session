"""Visible tests for filter 6 (no duplicate test), in the shipharness Filter protocol style."""

from __future__ import annotations

from pathlib import Path

import pytest
from a4_support import candidates, dedup_filter, filter_context

EXISTING = '''\
def test_project_list_uses_the_envelope(client, admin_headers):
    """Lists return items and next_cursor."""
    response = client.get("/projects", headers=admin_headers)
    assert response.status_code == 200
    assert set(response.json()) == {"items", "next_cursor"}
'''

RENAMED_AND_REFORMATTED = """\
def test_projects_envelope(client, admin_headers):
    # same steps as the existing test, different name, comment, and layout
    response = client.get(
        "/projects", headers=admin_headers
    )
    assert response.status_code == 200
    assert set(response.json()) == {"items", "next_cursor"}
"""

DIFFERENT_ASSERTION = """\
def test_projects_list_is_ok(client, admin_headers):
    response = client.get("/projects", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["next_cursor"] is None
"""


def _existing(tmp_path: Path) -> list[object]:
    return candidates(tmp_path, {"tests/test_existing.py": EXISTING})


@pytest.mark.criterion("F6-interface")
def test_filter_has_number_6_and_a_name(impl: object) -> None:
    flt = dedup_filter()
    assert flt.number == 6
    assert isinstance(flt.name, str) and flt.name.strip()
    assert callable(flt.evaluate)


@pytest.mark.criterion("F6-interface")
def test_filter_runs_inside_the_shipharness_pipeline(tmp_path: Path) -> None:
    from shipharness.filters import run_pipeline

    existing = _existing(tmp_path)
    cands = candidates(
        tmp_path,
        {"tests/test_new.py": RENAMED_AND_REFORMATTED + "\n\n" + DIFFERENT_ASSERTION},
    )
    results = run_pipeline(cands, filter_context(tmp_path), None, filters=[dedup_filter(existing)])
    assert [r.test_id for r in results] == [c.test_id for c in cands]
    assert all(r.filter == 6 and r.reason for r in results)
    assert [r.passed for r in results] == [False, True]
    assert not any(r.reason.startswith("filter error") for r in results)


@pytest.mark.criterion("F6-visible")
def test_renamed_and_reformatted_copy_is_discarded_with_the_original_named(tmp_path: Path) -> None:
    existing = _existing(tmp_path)
    (cand,) = candidates(tmp_path, {"tests/test_new.py": RENAMED_AND_REFORMATTED})
    result = dedup_filter(existing).evaluate(cand, filter_context(tmp_path))
    assert result.test_id == cand.test_id
    assert result.filter == 6
    assert result.passed is False
    assert "tests/test_existing.py::test_project_list_uses_the_envelope" in result.reason


@pytest.mark.criterion("F6-visible")
def test_a_different_assertion_is_kept(tmp_path: Path) -> None:
    existing = _existing(tmp_path)
    (cand,) = candidates(tmp_path, {"tests/test_new.py": DIFFERENT_ASSERTION})
    result = dedup_filter(existing).evaluate(cand, filter_context(tmp_path))
    assert result.passed is True
    assert result.reason


@pytest.mark.criterion("F6-visible")
def test_a_docstring_alone_does_not_make_a_test_new(tmp_path: Path) -> None:
    existing = _existing(tmp_path)
    source = EXISTING.replace("test_project_list_uses_the_envelope", "test_documented").replace(
        "Lists return items and next_cursor.", "A different docstring."
    )
    (cand,) = candidates(tmp_path, {"tests/test_new.py": source})
    result = dedup_filter(existing).evaluate(cand, filter_context(tmp_path))
    assert result.passed is False
