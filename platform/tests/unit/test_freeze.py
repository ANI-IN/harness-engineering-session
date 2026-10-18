"""shipharness.freeze: what the `harness-frozen` tag pins, and how drift is found."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from shipharness import freeze
from shipharness.config import Settings
from shipharness.layout import find_repo_root

IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *IDENT, *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "platform" / "src" / "shipharness" / "runner").mkdir(parents=True)
    (repo / "platform" / "src" / "shipharness" / "runner" / "tools.py").write_text(
        "A = 1\n", encoding="utf-8"
    )
    (repo / "platform" / "src" / "shipharness" / "console").mkdir(parents=True)
    (repo / "platform" / "src" / "shipharness" / "console" / "app.py").write_text(
        "B = 1\n", encoding="utf-8"
    )
    git(repo.parent, "init", "-q", str(repo))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    git(repo, "tag", "m1-s1-start")
    return repo


def frozen(repo: Path, settings: Settings | None = None) -> None:
    freeze.create_tag(repo, settings or Settings(_env_file=None), identity=("t", "t@t"))


def test_frozen_paths_cover_treatment_measurement_tasks_and_environment() -> None:
    paths = set(freeze.FROZEN_PATHS)
    for path in (
        "platform/src/shipharness/harness",
        "platform/src/shipharness/runner",
        "platform/src/shipharness/filters",
        "platform/teamtrack/harness",
        "platform/src/shipharness/checks",
        "platform/src/shipharness/ab/referee.py",
        "platform/src/shipharness/reviewer",
        "platform/datasets",
        "platform/teamtrack/tests/hidden",
        "platform/teamtrack/mutants",
        "platform/teamtrack/reference",
        "platform/sandbox/Dockerfile",
        "platform/src/shipharness/sandbox",
    ):
        assert path in paths, path
    for editable in (
        "platform/src/shipharness/console",
        "platform/src/shipharness/ab/report.py",
        "slides",
        "docs",
    ):
        assert not any(editable == p or editable.startswith(p + "/") for p in paths), editable
    for key in ("openai_model", "openai_reasoning_effort", "max_turns_per_session",
                "run_timeout_s", "harness_timeout_s", "max_run_cost_usd",
                "sandbox_cpus"):  # fmt: skip
        assert key in freeze.RUN_SETTINGS, key


def test_every_frozen_path_exists_in_the_repository() -> None:
    repo = find_repo_root(Path(__file__))
    missing = [p for p in freeze.FROZEN_PATHS if not (repo / p).exists()]
    assert missing == []


def test_no_tag_means_no_record(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert freeze.read_record(repo) is None
    assert freeze.problems(repo, Settings(_env_file=None)) == []


def test_tag_records_checkpoint_commits_and_run_settings(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    frozen(repo)
    record = freeze.read_record(repo)
    assert record is not None
    assert record["checkpoint_tags"] == {"m1-s1-start": git(repo, "rev-parse", "m1-s1-start")}
    assert record["checkpoint_trees"] == {
        "m1-s1-start": git(repo, "rev-parse", "m1-s1-start^{tree}")
    }
    assert record["defaults"]["run_timeout_s"] == 300
    assert record["effective"]["openai_model"] == "gpt-6-luna"
    assert "openai_api_key" not in json.dumps(record)
    assert freeze.problems(repo, Settings(_env_file=None)) == []


def test_change_to_a_frozen_path_is_a_problem_and_an_editable_path_is_not(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    frozen(repo)
    (repo / "platform" / "src" / "shipharness" / "console" / "app.py").write_text(
        "B = 2\n", encoding="utf-8"
    )
    assert freeze.problems(repo, Settings(_env_file=None)) == []
    (repo / "platform" / "src" / "shipharness" / "runner" / "tools.py").write_text(
        "A = 2\n", encoding="utf-8"
    )
    (repo / "platform" / "src" / "shipharness" / "runner" / "new.py").write_text(
        "C = 1\n", encoding="utf-8"
    )
    found = freeze.problems(repo, Settings(_env_file=None))
    assert found == ["content differs: platform/src/shipharness/runner"]


def test_moved_checkpoint_tag_is_a_problem(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    frozen(repo)
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "later")
    git(repo, "tag", "-f", "m1-s1-start")
    assert any("m1-s1-start" in p for p in freeze.problems(repo, Settings(_env_file=None)))


def test_changed_run_setting_is_a_problem(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    frozen(repo)
    changed = Settings(_env_file=None, run_timeout_s=480)
    assert any("run_timeout_s" in p for p in freeze.problems(repo, changed))


def test_tag_is_refused_when_frozen_paths_have_uncommitted_changes(tmp_path: Path) -> None:
    import pytest

    repo = make_repo(tmp_path)
    (repo / "platform" / "src" / "shipharness" / "runner" / "tools.py").write_text(
        "A = 3\n", encoding="utf-8"
    )
    with pytest.raises(freeze.FreezeError, match="uncommitted"):
        frozen(repo)


def test_tag_is_refused_when_it_already_exists(tmp_path: Path) -> None:
    import pytest

    repo = make_repo(tmp_path)
    frozen(repo)
    with pytest.raises(freeze.FreezeError, match="exists"):
        frozen(repo)


def test_the_tag_message_cites_no_private_build_document() -> None:
    # The record tag is pushed to the public repository at release; its message must stand alone.
    from shipharness.freeze import _message

    message = _message({"content_hashes": {}})
    # Private build documents, not included in the public release:
    assert "DESIGN" not in message and "VERIFICATION" not in message  # not included in the release


# -- class-v1: the release tag without an experiment freeze ----------------------------------------

CLASS_SENTENCE = (
    "Class version 1: the code, datasets, and settings used for the class. No experiment freeze; "
    "the pilot gate did not pass (see the course notes)."
)


def class_tagged(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path)
    record = freeze.class_record(repo, Settings(_env_file=None))
    freeze.write_class_tag(repo, record, identity=("ANI-IN", "a@b.invalid"))
    return repo


def test_class_tag_message_is_the_owner_sentence_then_the_record(tmp_path: Path) -> None:
    repo = class_tagged(tmp_path)
    assert freeze.CLASS_TAG == "class-v1"
    assert freeze.CLASS_MESSAGE == CLASS_SENTENCE
    message = git(repo, "tag", "--list", "class-v1", "--format=%(contents)")
    first, blank, marker = message.splitlines()[:3]
    assert (first, blank, marker) == (CLASS_SENTENCE, "", "class-record:")
    assert git(repo, "tag", "--list", "class-v1", "--format=%(taggername)") == "ANI-IN"
    assert git(repo, "rev-parse", "class-v1^{commit}") == git(repo, "rev-parse", "HEAD")
    assert freeze.read_record(repo) is None  # no harness-frozen tag: no freeze


def test_class_record_holds_hashes_checkpoint_trees_and_run_settings(tmp_path: Path) -> None:
    repo = class_tagged(tmp_path)
    record = freeze.read_tag_record(repo, freeze.CLASS_TAG)
    assert record is not None
    assert record["paths"] == list(freeze.FROZEN_PATHS)
    assert record["content_hashes"] == freeze.content_hashes(repo, freeze.FROZEN_PATHS)
    assert record["checkpoint_trees"] == {
        "m1-s1-start": git(repo, "rev-parse", "m1-s1-start^{tree}")
    }
    assert record["run_settings"]["run_timeout_s"] == 300
    assert "openai_api_key" not in json.dumps(record)
    assert freeze.read_tag_record(repo, "no-such-tag") is None


def test_class_tag_is_refused_when_it_already_exists(tmp_path: Path) -> None:
    import pytest

    repo = class_tagged(tmp_path)
    with pytest.raises(freeze.FreezeError, match="exists"):
        freeze.write_class_tag(repo, {"paths": []}, identity=("t", "t@t"))


def test_verify_copy_matches_then_names_each_difference(tmp_path: Path) -> None:
    repo = class_tagged(tmp_path)
    record, found = freeze.verify_copy(repo, freeze.CLASS_TAG)
    assert record is not None and found == []
    (repo / "platform" / "src" / "shipharness" / "runner" / "tools.py").write_text(
        "A = 2\n", encoding="utf-8"
    )
    (repo / "platform" / "src" / "shipharness" / "console" / "app.py").write_text(
        "B = 2\n", encoding="utf-8"
    )
    git(repo, "tag", "-d", "m1-s1-start")
    _, found = freeze.verify_copy(repo, freeze.CLASS_TAG)
    assert found == [
        "content differs: platform/src/shipharness/runner",
        "checkpoint tag missing: m1-s1-start (run git fetch --tags)",
    ]


def test_verify_copy_without_the_tag_returns_no_record(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert freeze.verify_copy(repo, freeze.CLASS_TAG) == (None, [])
