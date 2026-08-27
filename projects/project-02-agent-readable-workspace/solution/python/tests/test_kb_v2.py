"""Project 02 Python test suite: metadata persistence, the workspace
doctor's three rules in isolation, the dogfood check, and the independent
evidence contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]

spec = importlib.util.spec_from_file_location(
    "p02_kb", PROJECT_DIR / "solution/python/main.py"
)
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)


def initialized_dir(tmp_path: Path) -> str:
    data_dir = (tmp_path / "kb-data").as_posix()
    seed = (PROJECT_DIR / "fixtures" / "kb-data" / "documents").as_posix()
    exit_code, _, _ = kb.cmd_init(data_dir, seed)
    assert exit_code == 0
    return data_dir


class TestMetadataPersistence:
    def test_import_survives_a_fresh_process(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        source = PROJECT_DIR / "fixtures" / "imports" / "field-guide.md"
        exit_code, out, _ = kb.cmd_import(data_dir, [source.as_posix()])
        assert exit_code == 0
        assert json.loads(out)["imported"][0]["origin"] == "imported"
        # A fresh subprocess must see the import from the index alone.
        proc = subprocess.run(
            [sys.executable, str(PROJECT_DIR / "solution/python/main.py"),
             "list", "--data-dir", data_dir],
            capture_output=True, text=True, timeout=120,
        )
        ids = [doc["id"] for doc in json.loads(proc.stdout)["documents"]]
        assert ids == ["architecture-notes", "field-guide", "retrieval-plan", "team-meeting"]

    def test_duplicate_import_is_skipped_not_duplicated(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        duplicate = PROJECT_DIR / "fixtures" / "kb-data" / "documents" / "team-meeting.txt"
        _, out, _ = kb.cmd_import(data_dir, [duplicate.as_posix()])
        report = json.loads(out)
        assert report["imported"] == []
        assert report["skipped"] == [
            {"filename": "team-meeting.txt", "reason": "already-imported"}
        ]

    def test_list_requires_the_index_not_just_files(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        (Path(data_dir) / "index" / "documents-meta.json").unlink()
        exit_code, out, err = kb.cmd_list(data_dir)
        assert (exit_code, out) == (1, "")
        assert "metadata index missing" in err

    def test_show_returns_entry_plus_content(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        _, out, _ = kb.cmd_show(data_dir, "retrieval-plan")
        payload = json.loads(out)
        assert payload["origin"] == "seeded"
        assert payload["content"].startswith("# Retrieval plan")

    def test_extract_title_falls_back_to_filename(self):
        assert kb.extract_title("no heading here\n", "notes.txt") == "notes.txt"
        assert kb.extract_title("# Real title\nbody\n", "notes.txt") == "Real title"


class TestWorkspaceDoctor:
    def make_ready(self, tmp_path: Path) -> Path:
        shutil.copytree(
            PROJECT_DIR / "fixtures" / "workspaces" / "workspace-ready",
            tmp_path / "ws",
        )
        return tmp_path / "ws"

    def test_ready_fixture_passes_all_checks(self, tmp_path):
        workspace = self.make_ready(tmp_path)
        exit_code, out, _ = kb.cmd_workspace_check(workspace.as_posix())
        assert exit_code == 0
        assert json.loads(out)["ready"] is True

    def test_router_defect_alone_is_caught(self, tmp_path):
        workspace = self.make_ready(tmp_path)
        agents = workspace / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8")
            + "\n- Ghost doc: [docs/GHOST.md](docs/GHOST.md)\n",
            encoding="utf-8",
        )
        check = kb.check_router_targets(workspace)
        assert check["passed"] is False
        assert "docs/GHOST.md" in check["detail"]

    def test_handoff_defect_alone_is_caught(self, tmp_path):
        workspace = self.make_ready(tmp_path)
        handoff = workspace / "session-handoff.md"
        text = handoff.read_text(encoding="utf-8").replace("## Next best step", "## Notes")
        handoff.write_text(text, encoding="utf-8")
        check = kb.check_session_handoff(workspace)
        assert check["passed"] is False
        assert "Next best step" in check["detail"]

    def test_evidence_defect_alone_is_caught(self, tmp_path):
        workspace = self.make_ready(tmp_path)
        feature_path = workspace / "feature_list.json"
        feature_list = json.loads(feature_path.read_text(encoding="utf-8"))
        del feature_list["features"][0]["evidence"]
        feature_path.write_text(json.dumps(feature_list, indent=2), encoding="utf-8")
        check = kb.check_feature_evidence(workspace)
        assert check["passed"] is False
        assert "passing without evidence" in check["detail"]

    def test_handoff_parser_keeps_every_section_in_order(self):
        text = (PROJECT_DIR / "harness" / "session-handoff.md").read_text(encoding="utf-8")
        document = kb.parse_handoff(text)
        headings = [section["heading"] for section in document["sections"]]
        assert headings == [
            "Verified now", "Changed this session", "Broken or unverified",
            "Next best step", "Commands",
        ]

    def test_dogfood_the_committed_harness_passes_its_own_doctor(self):
        exit_code, out, _ = kb.cmd_workspace_check((PROJECT_DIR / "harness").as_posix())
        assert exit_code == 0
        report = json.loads(out)
        assert report["ready"] is True
        assert [check["id"] for check in report["checks"]] == [
            "router-targets", "session-handoff", "feature-evidence",
        ]


def expand_kb(command: str) -> list[str]:
    """Expand the canonical `kb ...` form to this track's real CLI."""
    tokens = []
    current = ""
    in_quotes = False
    for char in command:
        if char == '"':
            in_quotes = not in_quotes
        elif char == " " and not in_quotes:
            if current:
                tokens.append(current)
                current = ""
        else:
            current += char
    if current:
        tokens.append(current)
    assert tokens[0] == "kb"
    return [sys.executable, str(PROJECT_DIR / "solution" / "python" / "main.py"), *tokens[1:]]


class TestIndependentEvidence:
    """Every evidence command in the committed feature list executed through
    the real CLI as a subprocess, in feature-list order, in a fresh working
    copy; output must equal the recorded `observed` string."""

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
        committed = json.loads(
            (PROJECT_DIR / "harness" / "feature_list.json").read_text(encoding="utf-8")
        )
        for feature in committed["features"]:
            evidence = feature["evidence"]
            proc = subprocess.run(
                expand_kb(evidence["command"]),
                cwd=tmp_path, capture_output=True, text=True, timeout=120,
            )
            if proc.stdout:
                compact = json.dumps(json.loads(proc.stdout), separators=(",", ":"))
                observed = f"exit {proc.returncode}: {compact}"
            else:
                observed = f"exit {proc.returncode}: {proc.stderr.strip()}"
            assert observed == evidence["observed"], feature["id"]
