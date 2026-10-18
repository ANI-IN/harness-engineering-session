"""Reference solution tests for filter 6."""

from __future__ import annotations

from pathlib import Path

from a4_verification.dedup_filter import NoDuplicateTest, normalized

from shipharness.filters import CandidateTest, CoverageMap, FilterContext

ORIGINAL = '''\
def test_a(client):
    """Docstring."""
    r = client.get("/x")  # a comment
    assert r.status_code == 200
'''


def ctx(tmp_path: Path) -> FilterContext:
    return FilterContext(
        workspace=tmp_path,
        sandbox=None,
        baseline_coverage=CoverageMap(),
        filter_mutants=[],
        source_shas_at_phase_start={},
    )


def cand(source: str, test_id: str) -> CandidateTest:
    return CandidateTest(test_id=test_id, file=test_id.split("::")[0], source=source)


def test_name_docstring_comments_and_layout_are_ignored() -> None:
    other = (
        "def test_b(client):\n"
        '    r = client.get(\n        "/x"\n    )\n'
        "    assert r.status_code == 200\n"
    )
    assert normalized(ORIGINAL, "t.py::test_a") == normalized(other, "u.py::test_b")


def test_literals_and_locals() -> None:
    renamed = ORIGINAL.replace("r =", "resp =").replace("r.status", "resp.status")
    changed = ORIGINAL.replace("200", "201")
    assert normalized(ORIGINAL, "t.py::test_a") == normalized(renamed, "t.py::test_a")
    assert normalized(ORIGINAL, "t.py::test_a") != normalized(changed, "t.py::test_a")


def test_missing_function_or_bad_source_gives_none() -> None:
    assert normalized(ORIGINAL, "t.py::test_missing") is None
    assert normalized("def broken(:\n", "t.py::broken") is None
    assert normalized(ORIGINAL, "t.py") is None


def test_duplicate_of_existing_is_discarded_and_named(tmp_path: Path) -> None:
    flt = NoDuplicateTest([cand(ORIGINAL, "tests/test_old.py::test_a")])
    copy = cand(ORIGINAL.replace("test_a", "test_copy"), "tests/test_new.py::test_copy")
    result = flt.evaluate(copy, ctx(tmp_path))
    assert (result.filter, result.passed) == (6, False)
    assert "tests/test_old.py::test_a" in result.reason


def test_new_test_is_kept_then_its_copy_is_discarded(tmp_path: Path) -> None:
    flt = NoDuplicateTest([cand(ORIGINAL, "tests/test_old.py::test_a")])
    fresh = ORIGINAL.replace("200", "404").replace("test_a", "test_new")
    first = flt.evaluate(cand(fresh, "tests/test_new.py::test_new"), ctx(tmp_path))
    again = flt.evaluate(
        cand(fresh.replace("test_new", "test_again"), "tests/test_new.py::test_again"),
        ctx(tmp_path),
    )
    assert first.passed is True and "1 existing tests" in first.reason
    assert again.passed is False and "tests/test_new.py::test_new" in again.reason


def test_unparseable_candidate_is_discarded(tmp_path: Path) -> None:
    result = NoDuplicateTest().evaluate(cand("def x(:\n", "t.py::x"), ctx(tmp_path))
    assert result.passed is False and result.reason
