"""Project 01 Python test suite: retrieval rules, init idempotency, the
experiment's controls, and the committed-evidence equality contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[3]
REPO_ROOT = PROJECT_DIR.parents[1]

spec = importlib.util.spec_from_file_location("p01_kb", PROJECT_DIR / "solution/python/main.py")
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)


def make_documents() -> list[dict]:
    return [
        {"id": "beta", "title": "Beta", "filename": "beta.md", "lines": ["alpha ridge beta"]},
        {"id": "alpha", "title": "Alpha", "filename": "alpha.md", "lines": ["alpha ridge slope"]},
    ]


class TestTokenize:
    def test_keeps_only_length_four_and_longer(self):
        assert kb.tokenize("The old ridge is far") == ["ridge"]

    def test_lowercases_and_splits_on_non_alphanumerics(self):
        assert kb.tokenize("Ridge-line, RIDGE!") == ["ridge", "line", "ridge"]


class TestRetrieve:
    def test_repetition_never_adds_to_score(self):
        docs = [{"id": "d", "title": "D", "filename": "d.md", "lines": ["ridge ridge ridge"]}]
        citations = kb.retrieve(docs, "ridge slope")
        assert citations[0]["score"] == 1

    def test_tie_breaks_by_document_id_then_line(self):
        citations = kb.retrieve(make_documents(), "alpha ridge")
        assert [c["document"] for c in citations] == ["alpha", "beta"]
        docs = [
            {"id": "d", "title": "D", "filename": "d.md", "lines": ["ridge here", "ridge there"]}
        ]
        citations = kb.retrieve(docs, "ridge")
        assert [c["line"] for c in citations] == [1, 2]

    def test_zero_score_lines_are_never_cited(self):
        assert kb.retrieve(make_documents(), "zeppelin cargo") == []


class TestComposeAnswer:
    def test_no_citations_refuses_instead_of_inventing(self):
        assert kb.compose_answer([]).startswith("No matching lines")

    def test_two_citations_quote_first_and_reference_second(self):
        citations = kb.retrieve(make_documents(), "alpha ridge")
        answer = kb.compose_answer(citations)
        assert answer.startswith('Based on "Alpha" (line 1): alpha ridge slope')
        assert 'See also "Beta" (line 1).' in answer


class TestInit:
    def test_init_is_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        seed = PROJECT_DIR / "fixtures" / "kb-data" / "documents"
        first = json.loads(kb.cmd_init("kb-data", seed.as_posix())[1])
        assert first["created"] == ["kb-data", "kb-data/documents", "kb-data/index"]
        assert len(first["seeded"]) == 3
        second = json.loads(kb.cmd_init("kb-data", seed.as_posix())[1])
        assert second["created"] == []
        assert second["seeded"] == []

    def test_unreadable_seed_is_a_usage_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exit_code, out, err = kb.cmd_init("kb-data", "no-such-dir")
        assert exit_code == 2
        assert out == ""
        assert "cannot read seed directory" in err

    def test_title_falls_back_to_filename_for_txt(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        kb.cmd_init("kb-data", (PROJECT_DIR / "fixtures" / "kb-data" / "documents").as_posix())
        listing = json.loads(kb.cmd_list("kb-data")[1])
        by_id = {doc["id"]: doc for doc in listing["documents"]}
        assert by_id["team-meeting"]["title"] == "team-meeting.txt"
        assert by_id["architecture-notes"]["title"] == "Architecture notes"


class TestSplitCommand:
    def test_double_quotes_hold_arguments_together(self):
        assert kb.split_command('kb ask --data-dir d "two words here"') == [
            "kb", "ask", "--data-dir", "d", "two words here",
        ]


class TestExperimentControls:
    def test_evidence_reset_control(self, tmp_path):
        shutil.copyfile(
            PROJECT_DIR / "harness" / "feature_list.json", tmp_path / "feature_list.json"
        )
        (tmp_path / "claude-progress.md").write_text("# title\n\nold log\n", encoding="utf-8")
        assert not kb.assert_evidence_reset(tmp_path)
        kb.reset_evidence(tmp_path)
        assert kb.assert_evidence_reset(tmp_path)
        assert (tmp_path / "claude-progress.md").read_text(encoding="utf-8") == "# title\n"

    def test_isolated_directories_control_aborts_the_experiment(self, tmp_path):
        (tmp_path / "runs" / "strong").mkdir(parents=True)
        exit_code, out, err = kb.run_experiment(tmp_path.as_posix())
        assert exit_code == 1
        assert out == ""
        assert "isolated_directories" in err


@pytest.fixture(scope="module")
def report():
    exit_code, out, _ = kb.run_experiment(None)
    assert exit_code == 0
    return json.loads(out)


class TestCommittedEvidence:
    def test_all_controls_held(self, report):
        assert all(report["controls"].values())

    def test_committed_feature_list_is_the_strong_run_product(self, report):
        committed = json.loads(
            (PROJECT_DIR / "harness" / "feature_list.json").read_text(encoding="utf-8")
        )
        assert committed == report["strong"]["feature_list_final"]

    def test_committed_feature_list_satisfies_the_library_dialect(self, report):
        committed = json.loads(
            (PROJECT_DIR / "harness" / "feature_list.json").read_text(encoding="utf-8")
        )
        assert set(committed) == {"project", "updated", "features"}
        for feature in committed["features"]:
            assert feature["status"] in ("not-started", "in-progress", "blocked", "passing")
            if feature["status"] == "passing":
                evidence = feature["evidence"]
                assert set(evidence) == {"command", "observed", "date"}
                assert evidence["command"].startswith("kb ")
                assert evidence["observed"].startswith("exit ")
                assert len(evidence["date"]) == 10

    def test_report_matches_the_pinned_expectation(self, report):
        pinned = json.loads((PROJECT_DIR / "expected" / "experiment.json").read_text("utf-8"))
        assert report == pinned
