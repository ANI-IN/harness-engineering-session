from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipharness.events import EventBus, read_events
from shipharness.filters.mutants import (
    Mutant,
    MutantError,
    apply_mutant,
    check_against_source,
    load_mutant_ref,
    load_mutants,
    locate,
    run_mutant,
    run_mutant_detailed,
    run_mutant_set,
)
from shipharness.sandbox import ExecResult, FakeSandbox

from .helpers import PY, local_sandbox, make_repo


def mutant(**overrides: object) -> Mutant:
    base = dict(
        id="calc-m1",
        target="calc",
        set="filter",
        file="calc.py",
        line=2,
        original="    return a + b",
        replacement="    return a - b",
        rationale="wrong operator",
    )
    base.update(overrides)
    return Mutant(**base)  # type: ignore[arg-type]


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_mutant_id_must_start_with_target() -> None:
    with pytest.raises(ValueError, match="id"):
        mutant(id="other-m1")


def test_mutant_file_must_be_relative_posix() -> None:
    with pytest.raises(ValueError, match="file"):
        mutant(file="../calc.py")
    with pytest.raises(ValueError, match="file"):
        mutant(file="C:/calc.py")


def test_load_mutants_validates_original_against_source(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    good = mutant().model_dump()
    path = write_jsonl(tmp_path / "calc.jsonl", [good])
    assert [m.id for m in load_mutants(path, repo)] == ["calc-m1"]

    bad = mutant(id="calc-m2", original="    return a * b").model_dump()
    path = write_jsonl(tmp_path / "bad.jsonl", [good, bad])
    with pytest.raises(MutantError, match=r"bad.jsonl:2: calc-m2: original not found in calc.py"):
        load_mutants(path, repo)


def test_load_mutants_treats_the_line_as_a_hint_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    path = write_jsonl(tmp_path / "x.jsonl", [mutant(line=999).model_dump()])
    assert [m.line for m in load_mutants(path, repo)] == [999]  # found by its text
    path = write_jsonl(tmp_path / "y.jsonl", [mutant().model_dump(), mutant().model_dump()])
    with pytest.raises(MutantError, match="duplicate id"):
        load_mutants(path, repo)


def test_load_mutants_rejects_an_original_that_matches_several_lines(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    source = (repo / "calc.py").read_text(encoding="utf-8")
    (repo / "calc.py").write_text(source + "\n\ndef again(a, b):\n    return a + b\n", "utf-8")
    path = write_jsonl(tmp_path / "x.jsonl", [mutant().model_dump()])
    with pytest.raises(MutantError, match="original matches 2 lines"):
        load_mutants(path, repo)


def test_check_against_source_finds_a_moved_line(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    source = (repo / "calc.py").read_text(encoding="utf-8")
    (repo / "calc.py").write_text("# header\n# another\n" + source, encoding="utf-8")
    check_against_source(mutant(), repo)  # recorded at line 2, now at line 4
    assert locate((repo / "calc.py").read_text(encoding="utf-8"), mutant()) == 4


def test_load_mutants_reports_schema_errors_with_line(tmp_path: Path) -> None:
    path = tmp_path / "z.jsonl"
    path.write_text('{"id": "calc-m1"}\n', encoding="utf-8")
    with pytest.raises(MutantError, match="z.jsonl:1"):
        load_mutants(path, None)


def test_load_mutant_ref_selects_one_set(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    rows = [
        mutant().model_dump(),
        mutant(id="calc-m2", set="referee", replacement="    return b").model_dump(),
    ]
    path = write_jsonl(tmp_path / "calc.jsonl", rows)
    assert [m.id for m in load_mutant_ref(f"{path}#referee", repo)] == ["calc-m2"]
    assert [m.id for m in load_mutant_ref(str(path), repo)] == ["calc-m1", "calc-m2"]


def test_apply_mutant_replaces_exactly_one_line() -> None:
    text = "def add(a, b):\r\n    return a + b\r\n"
    assert apply_mutant(text, mutant()) == "def add(a, b):\r\n    return a - b\r\n"
    with pytest.raises(MutantError, match="original not found"):
        apply_mutant("def add(a, b):\n    return a+b\n", mutant())


def test_apply_mutant_still_applies_after_lines_are_inserted_above() -> None:
    text = "import os\n\n\ndef add(a, b):\n    return a + b\n"
    assert apply_mutant(text, mutant()) == "import os\n\n\ndef add(a, b):\n    return a - b\n"


def test_apply_mutant_refuses_an_ambiguous_original() -> None:
    text = "def add(a, b):\n    return a + b\n\n\ndef plus(a, b):\n    return a + b\n"
    with pytest.raises(MutantError, match=r"calc-m1: original matches 2 lines of calc.py \(2, 6\)"):
        apply_mutant(text, mutant())


def test_apply_mutant_refuses_a_missing_original() -> None:
    with pytest.raises(MutantError, match="calc-m1: original not found in calc.py"):
        apply_mutant("def add(a, b):\n    return b + a\n", mutant())


def test_apply_mutant_compares_whole_lines_only() -> None:
    # A line that merely contains the original (more indentation, a trailing comment) is no match.
    text = "def add(a, b):\n        return a + b\n    return a + b  # sum\n"
    with pytest.raises(MutantError, match="original not found"):
        apply_mutant(text, mutant())


def test_run_mutant_killed_and_survived(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    sandbox = local_sandbox(repo)
    before = (repo / "calc.py").read_bytes()
    killed = run_mutant_detailed(mutant(), ["tests/test_calc.py"], repo, sandbox, 60, python=PY)
    assert killed.outcome == "killed"
    assert killed.killed_by == "tests/test_calc.py::test_add"
    # clamp() has no test, so a mutant there survives.
    survivor = mutant(
        id="calc-m3",
        line=14,
        original="    if x < low:",
        replacement="    if x <= low:",
    )
    assert run_mutant(survivor, ["tests/test_calc.py"], repo, sandbox, 60, python=PY) == (
        "survived"
    )
    # The workspace itself is never changed and the temporary copies are removed.
    assert (repo / "calc.py").read_bytes() == before
    assert not [p for p in repo.iterdir() if p.name.startswith(".shipharness-")]


def test_copy_workspace_prunes_scratch_dirs_and_tolerates_vanishing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from shipharness.filters import scratch

    repo = make_repo(tmp_path / "repo")
    busy = repo / ".shipharness-mutant-other" / "deep"
    busy.mkdir(parents=True)
    (busy / "calc.py").write_text("x = 1\n", encoding="utf-8")
    visited: list[str] = []
    real_walk = scratch.os.walk

    def spy(top, **kwargs):  # type: ignore[no-untyped-def]
        for dirpath, dirnames, filenames in real_walk(top, **kwargs):
            visited.append(Path(dirpath).name)
            yield dirpath, dirnames, filenames

    monkeypatch.setattr(scratch.os, "walk", spy)
    real_read = Path.read_bytes

    def flaky_read(self: Path) -> bytes:
        if self.name == "pytest.ini":
            raise FileNotFoundError(self)  # deleted by a concurrent run
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", flaky_read)
    dest = tmp_path / "copy"
    scratch.copy_workspace(repo, dest)
    assert "deep" not in visited and ".shipharness-mutant-other" not in visited
    assert (dest / "calc.py").is_file() and not (dest / "pytest.ini").exists()


def test_run_mutant_error_when_original_does_not_match(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    stale = mutant(original="    return a+b")
    assert run_mutant(stale, ["tests"], repo, FakeSandbox(), 60) == "error"


def test_run_mutant_rejects_unsafe_test_ids(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    sandbox = FakeSandbox()
    result = run_mutant_detailed(mutant(), ["tests; rm -rf /"], repo, sandbox, 60)
    assert result.outcome == "error"
    assert "unsafe test id" in result.detail
    assert sandbox.commands == []


@pytest.mark.parametrize(
    ("exec_result", "outcome"),
    [
        (ExecResult(exit_code=0, output="1 passed in 0.1s", duration_ms=1), "survived"),
        (ExecResult(exit_code=1, output="FAILED t.py::a - x\n1 failed", duration_ms=1), "killed"),
        (ExecResult(exit_code=2, output="ERROR t.py\n1 error in 0.1s", duration_ms=1), "killed"),
        (ExecResult(exit_code=124, output="", duration_ms=1, timed_out=True), "timeout"),
        (ExecResult(exit_code=5, output="no tests ran", duration_ms=1), "error"),
        (ExecResult(exit_code=0, output="no tests ran in 0.1s", duration_ms=1), "error"),
    ],
)
def test_run_mutant_outcome_mapping(tmp_path: Path, exec_result: ExecResult, outcome: str) -> None:
    repo = make_repo(tmp_path / "repo")
    sandbox = FakeSandbox(default=exec_result)
    assert run_mutant(mutant(), ["tests"], repo, sandbox, 60) == outcome
    assert sandbox.commands[0].startswith('cd ".shipharness-mutant-')


def test_run_mutant_set_emits_events(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    sandbox = FakeSandbox(
        default=ExecResult(
            exit_code=1, output="FAILED tests/test_calc.py::test_add - x", duration_ms=1
        )
    )
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        runs = run_mutant_set(
            [mutant()], ["tests"], repo, sandbox, 60, bus=bus, run_id="r-1", arm="bare"
        )
    assert runs["calc-m1"].outcome == "killed"
    events = [e for e in read_events(log) if e.type == "mutant_result"]
    assert events[0].data == {
        "mutant_id": "calc-m1",
        "set": "filter",
        "outcome": "killed",
        "killed_by": "tests/test_calc.py::test_add",
    }
