"""Project 05 Python test suite: delete end to end, orphan reconciliation,
each rubric item against its violation fixture, the pinned ladder, the
dogfood check, and the independent evidence contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]

spec = importlib.util.spec_from_file_location(
    "p05_kb", PROJECT_DIR / "solution/python/main.py"
)
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)

EXPECTED_FAILURE = {
    "violates-r1": "verification-before-done",
    "violates-r2": "evidence-true",
    "violates-r3": "findings-addressed",
    "violates-r4": "scope-fidelity",
    "violates-r5": "clean-state",
}


def indexed_dir(tmp_path: Path) -> str:
    data_dir = (tmp_path / "kb-data").as_posix()
    seed = (PROJECT_DIR / "fixtures" / "kb-data" / "documents").as_posix()
    assert kb.cmd_init(data_dir, seed)[0] == 0
    assert kb.cmd_index(data_dir)[0] == 0
    return data_dir


class TestDelete:
    def test_delete_removes_file_entry_record_and_logs(self, tmp_path):
        data_dir = indexed_dir(tmp_path)
        exit_code, out, _ = kb.cmd_delete(data_dir, "team-meeting")
        assert exit_code == 0
        report = json.loads(out)
        assert report["deleted"]["filename"] == "team-meeting.txt"
        assert report["removed_chunk_record"] is True
        assert not (Path(data_dir) / "documents" / "team-meeting.txt").exists()
        ids = [e["id"] for e in kb.read_meta(Path(data_dir))]
        assert "team-meeting" not in ids
        assert kb.index_state(Path(data_dir))["state"] == "ready"
        assert any(
            e["command"] == "delete" for e in kb.read_log(Path(data_dir))
        )

    def test_unknown_id_is_a_named_error(self, tmp_path):
        data_dir = indexed_dir(tmp_path)
        exit_code, out, err = kb.cmd_delete(data_dir, "no-such-document")
        assert (exit_code, out) == (1, "")
        assert "no document with id" in err

    def test_half_done_delete_is_orphan_corrupt_and_reconciled(self, tmp_path):
        data_dir = indexed_dir(tmp_path)
        # the half-done delete: file and entry gone, chunk record left
        (Path(data_dir) / "documents" / "team-meeting.txt").unlink()
        entries = kb.read_meta(Path(data_dir))
        kb.write_meta(Path(data_dir), [e for e in entries if e["id"] != "team-meeting"])
        state = kb.index_state(Path(data_dir))
        assert state["state"] == "corrupt"
        assert state["corrupt"] == ["team-meeting"]
        _, out, _ = kb.cmd_index(data_dir)
        assert json.loads(out)["dropped"] == ["team-meeting"]
        assert kb.index_state(Path(data_dir))["state"] == "ready"


class TestRubric:
    def test_each_violation_fixture_fails_exactly_its_item(self):
        for name, failing in EXPECTED_FAILURE.items():
            exit_code, out, _ = kb.cmd_score(
                (PROJECT_DIR / "fixtures" / "scoreruns" / name).as_posix()
            )
            assert exit_code == 1, name
            report = json.loads(out)
            failed = [item["id"] for item in report["items"] if not item["passed"]]
            assert failed == [failing], name
            assert report["score"] == 4, name

    def test_scoring_never_mutates_the_run_it_grades(self, tmp_path):
        source = PROJECT_DIR / "fixtures" / "scoreruns" / "violates-r2"
        shutil.copytree(source, tmp_path / "run")
        before = sorted(
            (p.relative_to(tmp_path).as_posix(), p.read_bytes())
            for p in (tmp_path / "run").rglob("*") if p.is_file()
        )
        kb.cmd_score((tmp_path / "run").as_posix())
        after = sorted(
            (p.relative_to(tmp_path).as_posix(), p.read_bytes())
            for p in (tmp_path / "run").rglob("*") if p.is_file()
        )
        assert before == after


class TestLadder:
    def test_pinned_scores_climb(self, tmp_path):
        exit_code, out, _ = kb.cmd_ladder((tmp_path / "runs").as_posix())
        assert exit_code == 0
        report = json.loads(out)
        assert report["scores"] == [0, 4, 5]
        assert report["monotonic"] is True
        gen_eval_failed = [
            item["id"] for item in report["runs"]["gen-eval"]["items"]
            if not item["passed"]
        ]
        assert gen_eval_failed == ["scope-fidelity"]


class TestDogfood:
    def test_committed_harness_passes_its_own_doctor(self):
        exit_code, out, _ = kb.cmd_workspace_check((PROJECT_DIR / "harness").as_posix())
        assert exit_code == 0
        assert json.loads(out)["ready"] is True


def expand_kb(command: str) -> list[str]:
    tokens = kb.split_command(command)
    assert tokens[0] == "kb"
    return [sys.executable, str(PROJECT_DIR / "solution" / "python" / "main.py"), *tokens[1:]]


class TestIndependentEvidence:
    """Every evidence command in the committed feature list executed through
    the real CLI as a subprocess, in feature-list order, in a fresh
    workspace; output must equal the recorded `observed` string."""

    def test_each_evidence_command_reproduces_its_observed_output(self, tmp_path):
        shutil.copytree(
            PROJECT_DIR / "fixtures" / "kb-data" / "documents",
            tmp_path / "data" / "sample-documents",
        )
        (tmp_path / "imports").mkdir()
        shutil.copyfile(
            PROJECT_DIR / "fixtures" / "imports" / "field-guide.md",
            tmp_path / "imports" / "field-guide.md",
        )
        shutil.copytree(PROJECT_DIR / "harness", tmp_path / "workspace")
        committed = json.loads(
            (PROJECT_DIR / "harness" / "feature_list.json").read_text(encoding="utf-8")
        )
        for feature in committed["features"]:
            evidence = feature["evidence"]
            proc = subprocess.run(
                expand_kb(evidence["command"]),
                cwd=tmp_path, capture_output=True, text=True, timeout=600,
            )
            if proc.stdout:
                compact = json.dumps(json.loads(proc.stdout), separators=(",", ":"))
                observed = f"exit {proc.returncode}: {compact}"
            else:
                observed = f"exit {proc.returncode}: {proc.stderr.strip()}"
            assert observed == evidence["observed"], feature["id"]
