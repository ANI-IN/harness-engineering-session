"""Project 04 Python test suite: the log rules, corrupt-state detection
and recovery, each guard check against a deliberately violating condition,
the WIP limit, the dogfood check, and the independent evidence contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]

spec = importlib.util.spec_from_file_location(
    "p04_kb", PROJECT_DIR / "solution/python/main.py"
)
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)


def initialized_dir(tmp_path: Path) -> str:
    data_dir = (tmp_path / "kb-data").as_posix()
    seed = (PROJECT_DIR / "fixtures" / "kb-data" / "documents").as_posix()
    assert kb.cmd_init(data_dir, seed)[0] == 0
    return data_dir


class TestLogging:
    def test_sequence_numbers_stand_in_for_timestamps(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        kb.cmd_index(data_dir)
        entries = kb.read_log(Path(data_dir))
        assert [entry["seq"] for entry in entries] == list(range(1, len(entries) + 1))
        assert all("timestamp" not in entry for entry in entries)

    def test_level_and_event_filters(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        kb.cmd_index(data_dir)
        _, out, _ = kb.cmd_logs(data_dir, "INFO", "done")
        report = json.loads(out)
        assert report["total"] == 2  # init/done + index/done
        assert {entry["event"] for entry in report["entries"]} == {"done"}

    def test_read_surfaces_do_not_log(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        kb.cmd_index(data_dir)
        before = len(kb.read_log(Path(data_dir)))
        kb.cmd_list(data_dir)
        kb.cmd_status(data_dir)
        kb.cmd_logs(data_dir, "DEBUG", None)
        assert len(kb.read_log(Path(data_dir))) == before

    def test_refused_ask_logs_a_warn_naming_the_state(self, tmp_path):
        data_dir = initialized_dir(tmp_path)  # unindexed: state empty
        exit_code, _, _ = kb.cmd_ask(data_dir, "anything at all")
        assert exit_code == 1
        warns = [e for e in kb.read_log(Path(data_dir)) if e["level"] == "WARN"]
        assert len(warns) == 1
        assert warns[0]["event"] == "refused"
        assert warns[0]["detail"]["state"] == "empty"


class TestCorruption:
    def corrupt(self, data_dir: str) -> None:
        chunks_path = Path(data_dir) / kb.CHUNKS_FILE
        records = json.loads(chunks_path.read_text(encoding="utf-8"))
        records[0]["chunks"][0] = {"index": 0, "chars": 0, "words": 0, "text": ""}
        chunks_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

    def test_corrupt_beats_stale_and_names_the_document(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        kb.cmd_index(data_dir)
        self.corrupt(data_dir)
        target = Path(data_dir) / "documents" / "team-meeting.txt"
        target.write_text(target.read_text(encoding="utf-8") + "\nEdited.\n", "utf-8")
        state = kb.index_state(Path(data_dir))
        assert state["state"] == "corrupt"
        assert state["corrupt"] == ["architecture-notes"]
        assert state["stale"] == ["team-meeting"]

    def test_plain_index_cannot_heal_what_rebuild_can(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        kb.cmd_index(data_dir)
        self.corrupt(data_dir)
        kb.cmd_index(data_dir)  # sha gate skips the corrupt document
        assert kb.index_state(Path(data_dir))["state"] == "corrupt"
        _, out, _ = kb.cmd_index(data_dir, rebuild=True)
        assert len(json.loads(out)["indexed"]) == 3
        assert kb.index_state(Path(data_dir))["state"] == "ready"


class TestGuardDetection:
    """Each guard check against a deliberately violating condition: the
    checks must be able to fail, not merely pass on healthy input."""

    def sandbox(self, tmp_path: Path) -> Path:
        data_dir = initialized_dir(tmp_path)
        kb.cmd_index(data_dir)
        box = tmp_path / "sandbox"
        box.mkdir()
        shutil.copytree(data_dir, box / "kb-data")
        (box / "probe.md").write_text("# Probe\n", encoding="utf-8")
        return box

    def test_server_read_only_detects_a_writing_server(self, tmp_path, monkeypatch):
        def treacherous_post(self):
            (Path(self.data_dir) / "sneaky.md").write_text("leak", encoding="utf-8")
            self._send_json(200, {"ok": True})

        monkeypatch.setattr(kb.KbHandler, "do_POST", treacherous_post)
        check = kb.guard_server_read_only(self.sandbox(tmp_path))
        assert check["passed"] is False
        assert "not 405" in check["detail"]

    def test_storage_containment_detects_an_escaping_write(self, tmp_path, monkeypatch):
        real_import = kb.cmd_import

        def leaky_import(data_dir_arg, files):
            Path(data_dir_arg).parent.joinpath("escaped.md").write_text("x", "utf-8")
            return real_import(data_dir_arg, files)

        monkeypatch.setattr(kb, "cmd_import", leaky_import)
        check = kb.guard_storage_containment(self.sandbox(tmp_path))
        assert check["passed"] is False
        assert "escaped.md" in check["detail"]

    def test_derived_rebuildable_detects_a_broken_chunker(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            kb, "chunk_text",
            lambda text: [{"index": 0, "chars": 0, "words": 0, "text": ""}],
        )
        check = kb.guard_derived_rebuildable(self.sandbox(tmp_path))
        assert check["passed"] is False
        assert "state corrupt" in check["detail"]


class TestWipLimit:
    def test_two_in_progress_features_fail_the_doctor(self, tmp_path):
        shutil.copytree(PROJECT_DIR / "harness", tmp_path / "ws")
        feature_path = tmp_path / "ws" / "feature_list.json"
        feature_list = json.loads(feature_path.read_text(encoding="utf-8"))
        for feature in feature_list["features"][:2]:
            feature["status"] = "in-progress"
            feature.pop("evidence", None)
        feature_path.write_text(json.dumps(feature_list, indent=2), encoding="utf-8")
        check = kb.check_wip_limit(tmp_path / "ws")
        assert check["passed"] is False
        assert "the WIP limit is 1" in check["detail"]

    def test_dogfood_the_committed_harness_passes_all_four_checks(self):
        exit_code, out, _ = kb.cmd_workspace_check((PROJECT_DIR / "harness").as_posix())
        assert exit_code == 0
        report = json.loads(out)
        assert [check["id"] for check in report["checks"]] == [
            "router-targets", "session-handoff", "feature-evidence", "wip-limit",
        ]


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
                cwd=tmp_path, capture_output=True, text=True, timeout=300,
            )
            if proc.stdout:
                compact = json.dumps(json.loads(proc.stdout), separators=(",", ":"))
                observed = f"exit {proc.returncode}: {compact}"
            else:
                observed = f"exit {proc.returncode}: {proc.stderr.strip()}"
            assert observed == evidence["observed"], feature["id"]
