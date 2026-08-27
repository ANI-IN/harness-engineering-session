"""Negative proof for the link checker: broken links and anchors must be found."""

from pathlib import Path

from tools.lint import check_links


def _md(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_broken_relative_link_detected(tmp_path):
    md = _md(tmp_path, "a.md", "See [missing](./does-not-exist.md).\n")
    errors = check_links.check_relative([md], tmp_path)
    assert len(errors) == 1
    assert "broken link ./does-not-exist.md" in errors[0]
    assert errors[0].startswith("a.md")


def test_fixture_markdown_is_not_collected(tmp_path):
    # fixtures/ and expected/ hold unit test data; a seeded-defect fixture
    # may deliberately contain a broken link for a doctor to catch, so the
    # collector must never hand those files to the checker.
    _md(tmp_path, "unit/fixtures/workspaces/stale/AGENTS.md", "[ghost](docs/GHOST.md)\n")
    _md(tmp_path, "unit/expected/report.md", "[ghost](docs/GHOST.md)\n")
    real = _md(tmp_path, "unit/README.md", "plain text, no links\n")
    assert check_links.markdown_files(tmp_path) == [real]


def test_broken_anchor_detected(tmp_path):
    _md(tmp_path, "target.md", "# Title\n\n## Real section\n")
    md = _md(tmp_path, "a.md", "See [anchor](./target.md#no-such-heading).\n")
    errors = check_links.check_relative([md], tmp_path)
    assert len(errors) == 1
    assert "missing anchor" in errors[0]


def test_broken_same_file_anchor_detected(tmp_path):
    md = _md(tmp_path, "a.md", "Jump to [here](#nowhere).\n\n## Somewhere\n")
    errors = check_links.check_relative([md], tmp_path)
    assert len(errors) == 1
    assert "missing anchor #nowhere" in errors[0]


def test_valid_links_pass(tmp_path):
    _md(tmp_path, "target.md", "## Real section\n")
    md = _md(
        tmp_path,
        "a.md",
        "Good: [file](./target.md), [anchor](./target.md#real-section), "
        "[self](#local), [ext](https://example.com/x).\n\n## Local\n",
    )
    assert check_links.check_relative([md], tmp_path) == []


def test_links_inside_code_fences_ignored(tmp_path):
    md = _md(tmp_path, "a.md", "```text\n[not a link](./missing.md)\n```\n")
    assert check_links.check_relative([md], tmp_path) == []


# ---- link-exception gates -------------------------------------------------

import datetime as dt  # noqa: E402

VALID_ENTRY = {
    "expect": 403,
    "reason": "bot protection",
    "added": "2026-08-27",
    "removal_trigger": {"type": "manual", "condition": "serves 2xx consistently"},
}


def test_exception_older_than_30_days_fails():
    exceptions = {"https://example.com/": {**VALID_ENTRY, "added": "2026-07-01"}}
    errors = check_links.check_exception_hygiene(exceptions, dt.date(2026, 8, 27))
    assert len(errors) == 1
    assert "57 days old" in errors[0]


def test_exception_within_30_days_passes():
    exceptions = {"https://example.com/": VALID_ENTRY}
    assert check_links.check_exception_hygiene(exceptions, dt.date(2026, 8, 27)) == []


def test_exception_missing_fields_fails():
    exceptions = {"https://example.com/": {"expect": 403, "reason": "x"}}
    errors = check_links.check_exception_hygiene(exceptions, dt.date(2026, 8, 27))
    assert len(errors) == 1
    assert "added" in errors[0] and "removal_trigger" in errors[0]


def test_repo_public_trigger_fails_once_repo_is_public(monkeypatch):
    exceptions = {
        "https://github.com/x/y/issues": {
            **VALID_ENTRY,
            "expect": 404,
            "removal_trigger": {"type": "repo_public", "repo": "x/y"},
        }
    }
    monkeypatch.setattr(check_links, "repo_is_public", lambda _repo: True)
    errors = check_links.check_removal_triggers(exceptions)
    assert len(errors) == 1
    assert "now PUBLIC" in errors[0]

    monkeypatch.setattr(check_links, "repo_is_public", lambda _repo: False)
    assert check_links.check_removal_triggers(exceptions) == []


def test_retries_stop_on_first_success(monkeypatch):
    statuses = iter([403, 200])
    monkeypatch.setattr(check_links, "fetch_status", lambda _url: next(statuses))
    monkeypatch.setattr(check_links.time, "sleep", lambda _s: None)
    status, attempts = check_links.fetch_with_retries("https://example.com/")
    assert status == 200
    assert attempts == 2


def test_retries_exhaust_then_report_last_status(monkeypatch):
    monkeypatch.setattr(check_links, "fetch_status", lambda _url: 403)
    monkeypatch.setattr(check_links.time, "sleep", lambda _s: None)
    status, attempts = check_links.fetch_with_retries("https://example.com/")
    assert status == 403
    assert attempts == check_links.RETRY_ATTEMPTS


def test_committed_exception_file_is_hygienic():
    exceptions = check_links.load_exceptions()
    assert check_links.check_exception_hygiene(exceptions, dt.date.today()) == []
