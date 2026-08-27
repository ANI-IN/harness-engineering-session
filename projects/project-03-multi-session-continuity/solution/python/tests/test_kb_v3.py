"""Project 03 Python test suite: the chunking rule, staleness, the ask
refusal, the continuity proof's process boundary, the dogfood check, and
the independent evidence contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]

spec = importlib.util.spec_from_file_location(
    "p03_kb", PROJECT_DIR / "solution/python/main.py"
)
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)


def initialized_dir(tmp_path: Path) -> str:
    data_dir = (tmp_path / "kb-data").as_posix()
    seed = (PROJECT_DIR / "fixtures" / "kb-data" / "documents").as_posix()
    exit_code, _, _ = kb.cmd_init(data_dir, seed)
    assert exit_code == 0
    return data_dir


class TestChunking:
    def test_paragraphs_pack_up_to_the_limit(self):
        text = "aaa\n\nbbb\n\nccc\n"
        chunks = kb.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "aaa\n\nbbb\n\nccc"

    def test_packing_flushes_at_the_boundary(self):
        text = ("x" * 300) + "\n\n" + ("y" * 300) + "\n\n" + ("z" * 100)
        chunks = kb.chunk_text(text)
        assert [chunk["text"][0] for chunk in chunks] == ["x", "y"]
        assert chunks[1]["text"].endswith("z" * 100)

    def test_oversized_paragraph_stays_whole(self):
        text = "short\n\n" + ("w " * 400).strip() + "\n\nshort again\n"
        chunks = kb.chunk_text(text)
        assert len(chunks) == 3
        assert chunks[1]["chars"] > 500 or chunks[1]["words"] == 400

    def test_chunk_metadata_counts(self):
        chunks = kb.chunk_text("one two three\n")
        assert chunks[0]["chars"] == 13
        assert chunks[0]["words"] == 3

    def test_extract_metadata(self):
        metadata = kb.extract_metadata("a b\n\nc d e\n")
        assert metadata == {"chars": 11, "words": 5, "paragraphs": 2}


class TestIndexAndStatus:
    def test_index_then_status_ready(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        assert kb.cmd_index(data_dir)[0] == 0
        status = json.loads(kb.cmd_status(data_dir)[1])
        assert status["state"] == "ready"
        assert status["indexed"] == status["documents"] == 3

    def test_edited_document_goes_stale_and_reindexes(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        kb.cmd_index(data_dir)
        target = Path(data_dir) / "documents" / "team-meeting.txt"
        target.write_text(target.read_text(encoding="utf-8") + "\nA new line.\n", "utf-8")
        status = json.loads(kb.cmd_status(data_dir)[1])
        assert status["state"] == "stale"
        assert status["stale"] == ["team-meeting"]
        report = json.loads(kb.cmd_index(data_dir)[1])
        assert [item["document"] for item in report["indexed"]] == ["team-meeting"]
        assert json.loads(kb.cmd_status(data_dir)[1])["state"] == "ready"

    def test_ask_refuses_until_the_index_is_ready(self, tmp_path):
        data_dir = initialized_dir(tmp_path)
        exit_code, out, err = kb.cmd_ask(data_dir, "ranking citations")
        assert (exit_code, out) == (1, "")
        assert "index not ready" in err
        kb.cmd_index(data_dir)
        exit_code, out, _ = kb.cmd_ask(data_dir, "Which lines become citations in the ranking?")
        assert exit_code == 0
        citations = json.loads(out)["citations"]
        assert citations and all("chunk" in citation for citation in citations)


class TestContinuity:
    def test_every_step_is_a_child_process(self, tmp_path, monkeypatch):
        spawned = []
        real_run = subprocess.run

        def recording_run(argv, **kwargs):
            spawned.append(list(argv))
            return real_run(argv, **kwargs)

        monkeypatch.setattr(kb.subprocess, "run", recording_run)
        exit_code, out, _ = kb.run_continuity((tmp_path / "work").as_posix())
        assert exit_code == 0
        report = json.loads(out)
        assert report["resume"]["resumed"] is True
        assert report["resume"]["status_matches_session_a"] is True
        assert report["session_b"]["handoff_sections"] == 3
        # The process boundary: 4 session A steps + 3 session B steps, each
        # an exec of this track's CLI, never an in-process call.
        assert len(spawned) == 7
        main_path = str(PROJECT_DIR / "solution" / "python" / "main.py")
        for argv in spawned:
            assert argv[0] == sys.executable
            assert argv[1] == main_path


class TestDogfood:
    def test_committed_harness_passes_its_own_doctor(self):
        exit_code, out, _ = kb.cmd_workspace_check((PROJECT_DIR / "harness").as_posix())
        assert exit_code == 0
        assert json.loads(out)["ready"] is True

    def test_handoff_parses_with_required_sections(self):
        text = (PROJECT_DIR / "harness" / "session-handoff.md").read_text(encoding="utf-8")
        headings = [s["heading"] for s in kb.parse_handoff(text)["sections"]]
        for required in ("Verified now", "Broken or unverified", "Next best step"):
            assert required in headings


def expand_kb(command: str) -> list[str]:
    tokens = kb.split_command(command)
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
                cwd=tmp_path, capture_output=True, text=True, timeout=300,
            )
            if proc.stdout:
                compact = json.dumps(json.loads(proc.stdout), separators=(",", ":"))
                observed = f"exit {proc.returncode}: {compact}"
            else:
                observed = f"exit {proc.returncode}: {proc.stderr.strip()}"
            assert observed == evidence["observed"], feature["id"]
