"""The authorship gate must read commit bodies, not identity fields.

Three commits shipped a `Co-Authored-By:` trailer while author and
committer were correct on all three. A check over `%an`/`%cn` reports
green on exactly that input, which is why every test here asserts against
a real commit body rather than a formatted identity.
"""

from __future__ import annotations

import subprocess

from tools.lint import check_commit_authorship as authorship

CLEAN = "Add the router entry files\n\nRoot docs: README, AGENTS.md, CLAUDE.md.\n"
TRAILER = (
    "Point the exercises at the work they actually ask for\n\n"
    "Body text.\n\n"
    "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>\n"
)
LOWER_TRAILER = "Subject\n\nco-authored-by: Someone <s@example.com>\n"
ATTRIBUTION = "Add a thing\n\nGenerated with Claude Code.\n"
CITATION = (
    "Add lecture 08\n\n"
    "Anthropic harness claim cited to anthropic.com; the progress log is\n"
    "claude-progress.md and the entry file is CLAUDE.md.\n"
)


def test_a_clean_body_passes():
    assert authorship.check_commit("abc12345", CLEAN) == []


def test_the_trailer_that_shipped_is_caught():
    errors = authorship.check_commit("abc12345", TRAILER)
    assert len(errors) == 1
    assert "co-author trailer" in errors[0]
    # The offending line is quoted back, so the report is actionable.
    assert "Co-Authored-By: Claude Opus 5" in errors[0]


def test_the_trailer_is_caught_case_insensitively():
    assert len(authorship.check_commit("abc12345", LOWER_TRAILER)) == 1


def test_a_tool_attribution_without_a_trailer_is_caught():
    errors = authorship.check_commit("abc12345", ATTRIBUTION)
    assert len(errors) == 1
    assert "tool attribution" in errors[0]


def test_citing_a_source_is_not_an_attribution():
    """The module names CLAUDE.md and cites Anthropic posts. Neither is an
    attribution, and a gate that cannot tell them apart would be unusable."""
    assert authorship.check_commit("abc12345", CITATION) == []


def test_identity_fields_alone_would_not_catch_it(tmp_path):
    """The regression proof: a real commit whose author and committer are
    clean but whose body carries the trailer. This is the exact shape that
    shipped, and an identity-only check passes it."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def run(*args):
        return subprocess.run(args, cwd=repo, check=True, capture_output=True)

    run("git", "init", "-q", ".")
    run("git", "config", "user.name", "Animesh Kumar")
    run("git", "config", "user.email", "animesh.kcm@gmail.com")
    (repo / "f.txt").write_text("x")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", TRAILER)

    body = subprocess.run(
        ["git", "log", "-1", "--format=%B"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout
    identity = subprocess.run(
        ["git", "log", "-1", "--format=%an|%cn"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    assert identity == "Animesh Kumar|Animesh Kumar", "identity is clean"
    assert authorship.check_commit("abc12345", body), "the body is not"


def test_an_empty_range_is_refused_rather_than_reported_green(tmp_path, capsys):
    """On `main` itself, `main..HEAD` selects nothing. A gate that checks zero
    commits and prints OK is the defect this file exists to prevent, so the
    resolver widens to `--all` and `main()` refuses a genuinely empty range."""
    import sys
    from unittest import mock

    with (
        mock.patch.object(authorship, "commit_list", return_value=[]),
        mock.patch.object(sys, "argv", ["check", "--range", "HEAD..HEAD"]),
    ):
        code = authorship.main()
    out = capsys.readouterr().out
    assert code == 1
    assert "refusing to report green on an empty range" in out


def test_the_resolver_widens_to_all_when_the_branch_range_is_empty():
    """Standing on main, main..HEAD is empty; the check must not shrink to it."""
    from unittest import mock

    with (
        mock.patch.object(authorship, "_rev_exists", return_value=True),
        mock.patch.object(authorship, "commit_list", return_value=[]),
    ):
        assert authorship.resolve_range("main..HEAD") == "--all"
