"""Build the visible scripted diffs for assignment A3 from real `git diff` output.

Usage (from the repository root):
    uv run python section-3-scope-sandbox/assignment/fixtures/make_fixtures.py

Each case starts from the same small TeamTrack-shaped tree (BASE), applies a list of file
operations, stages them, and records `git diff --cached`. Hand-written patches (the agent's
`apply_patch` tool accepts them) are stored as given. The output is `diffs/<id>.diff` plus
`cases.json` with the phase, the allowed paths, and the expected result of each case.
The diffs are committed; rerun this script only when a case changes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# The allowed paths of every F3 example in datasets/teamtrack-features-v1.jsonl.
F3_ALLOWED: dict[str, list[str]] = {
    "build": [
        "app/api/issues.py",
        "app/services/issues.py",
        "docs/HANDBOOK.md",
        "tests/visible/**",
    ],
    "test": ["tests/visible/**"],
}

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"

BASE: dict[str, str | bytes] = {
    "app/api/issues.py": (
        '"""Issue endpoints."""\n\n'
        "from app.services import issues as service\n\n\n"
        "def create_issue(project_id: int, body: dict, user: dict) -> dict:\n"
        "    return service.create(project_id, body, user)\n\n\n"
        "def list_issues(project_id: int, user: dict) -> list[dict]:\n"
        "    return service.list_for(project_id, user)\n"
    ),
    "app/services/issues.py": (
        '"""Issue service.\n\n'
        "-- legacy: issue creation takes no idempotency key\n"
        '"""\n\n'
        "from app.repositories import issues as repo\n\n\n"
        "def create(project_id: int, body: dict, user: dict) -> dict:\n"
        '    return repo.insert(project_id, body, org_id=user["org_id"])\n\n\n'
        "def list_for(project_id: int, user: dict) -> list[dict]:\n"
        '    return repo.select(project_id, org_id=user["org_id"])\n'
    ),
    "app/services/idempotency.py": (
        '"""run_once: replay the first response for a repeated Idempotency-Key."""\n\n\n'
        "def run_once(key: str, scope: str, fn):\n"
        "    return fn()\n"
    ),
    "app/repositories/issues.py": (
        "def insert(project_id: int, body: dict, org_id: int) -> dict:\n"
        '    return {"id": 1, "project_id": project_id, "org_id": org_id, **body}\n\n\n'
        "def select(project_id: int, org_id: int) -> list[dict]:\n"
        "    return []\n"
    ),
    "app/core/config.py": 'DATABASE_URL = "sqlite:///teamtrack.db"\nPAGE_SIZE = 50\n',
    "app/static/logo.png": PNG + b"\x00" * 16,
    "docs/HANDBOOK.md": (
        "# TeamTrack handbook\n\n"
        "## House rules\n\n"
        "R4 Idempotency. Changes to this rule are recorded as below.\n\n"
        "```text\n"
        "-- R4 covers POST /projects only\n"
        "```\n\n"
        "R5 Audit. Every write adds one audit row.\n"
    ),
    "docs/features/f3.md": "# F3 Idempotent issue creation\n\nSee house rule R4.\n",
    "docs/design notes/f3 retry.md": "# Retry notes\n\nClients retry after 10 s.\n",
    "docs/café.md": "# Café notes\n\nOpen questions.\n",
    "docs/exec-plans/active/F3.md": "# F3 exec plan\n\n## Progress\n\n- [ ] build\n",
    "progress.md": "# Progress\n\n## Current feature\n\nF3\n",
    "session-handoff.md": "# Session handoff\n\n## Machine summary\n",
    "feature_list.json": (
        '{\n  "features": [\n    {"id": "F3", "passes": false, "evidence": null, '
        '"testedAt": null}\n  ]\n}\n'
    ),
    "feature_list.schema.json": '{"type": "object"}\n',
    "AGENTS.md": "# AGENTS.md\n\nThis file is a map. Start with ARCHITECTURE.md.\n",
    ".agents/skills/idempotency/SKILL.md": "---\nname: idempotency\n---\n\nUse run_once.\n",
    "init.sh": "#!/bin/sh\nset -e\npython -m pytest tests/visible -q\n",
    "scripts/deploy.sh": "#!/bin/sh\necho deploy\n",
    "migrations/versions/0007_add_idempotency.py": 'revision = "0007"\ndown_revision = "0006"\n',
    "tests/conftest.py": "import pytest\n",
    "tests/visible/conftest.py": (
        "import pytest\n\n\n@pytest.fixture\ndef org_id() -> int:\n    return 1\n"
    ),
    "tests/visible/test_issues.py": (
        "def test_create_issue_returns_201(client):\n"
        "    assert client.post('/projects/1/issues', json={'title': 'a'}).status_code == 201\n"
    ),
    "tests/visible/test_old.py": "def test_placeholder():\n    assert True\n",
    "tests/visible/fixtures/feature_list.json": '{"features": []}\n',
}

Op = tuple[Any, ...]


def _git(repo: Path, *args: str) -> bytes:
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "LC_ALL": "C",
    }
    done = subprocess.run(
        ["git", "-c", "core.quotepath=true", "-c", "color.ui=never", *args],
        cwd=repo,
        capture_output=True,
        env=env,
        check=True,
    )
    return done.stdout


def _write(repo: Path, rel: str, content: str | bytes) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="\n")


def base_repo(root: Path) -> Path:
    """A git repository holding BASE in one commit."""
    repo = root / "repo"
    repo.mkdir()
    for rel, content in BASE.items():
        _write(repo, rel, content)
    os.chmod(repo / "scripts/deploy.sh", 0o644)
    os.chmod(repo / "app/api/issues.py", 0o644)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(
        repo, "-c", "user.name=base", "-c", "user.email=base@example.invalid", "commit", "-qm", "b"
    )
    return repo


def staged_diff(ops: list[Op], *, binary: bool = False, copies: bool = False) -> str:
    """Apply `ops` to a fresh BASE repository and return `git diff --cached` as text.

    Ops: ("write", path, content), ("append", path, text), ("replace", path, old, new),
    ("delete", path), ("rename", old, new), ("copy", src, dst), ("chmod", path, mode).
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = base_repo(Path(tmp))
        for op in ops:
            kind = op[0]
            if kind == "write":
                _write(repo, op[1], op[2])
            elif kind == "append":
                text = (repo / op[1]).read_text(encoding="utf-8") + op[2]
                _write(repo, op[1], text)
            elif kind == "replace":
                text = (repo / op[1]).read_text(encoding="utf-8")
                if op[2] not in text:
                    raise ValueError(f"{op[2]!r} not in {op[1]}")
                _write(repo, op[1], text.replace(op[2], op[3]))
            elif kind == "delete":
                (repo / op[1]).unlink()
            elif kind == "rename":
                (repo / op[2]).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(repo / op[1], repo / op[2])
            elif kind == "copy":
                (repo / op[2]).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repo / op[1], repo / op[2])
            elif kind == "chmod":
                os.chmod(repo / op[1], op[2])
            else:
                raise ValueError(f"unknown op {kind}")
        _git(repo, "add", "-A")
        args = ["diff", "--cached", "-M"]
        if copies:
            args.append("--find-copies-harder")
        if binary:
            args.append("--binary")
        return _git(repo, *args).decode("utf-8")


def build(cases: list[dict[str, Any]], out_dir: Path) -> None:
    """Write diffs/<id>.diff and cases.json (everything except the ops) into `out_dir`."""
    diffs = out_dir / "diffs"
    if diffs.exists():
        shutil.rmtree(diffs)
    diffs.mkdir(parents=True)
    meta: list[dict[str, Any]] = []
    for case in cases:
        if "raw" in case:
            text = case["raw"]
        else:
            text = staged_diff(
                case["ops"], binary=case.get("binary", False), copies=case.get("copies", False)
            )
        (diffs / f"{case['id']}.diff").write_bytes(text.encode("utf-8"))
        entry = {k: v for k, v in case.items() if k not in ("ops", "raw", "binary", "copies")}
        entry.setdefault("allowed_paths", F3_ALLOWED)
        entry.setdefault("state_layer", True)
        meta.append(entry)
    text = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
    (out_dir / "cases.json").write_text(text, encoding="utf-8", newline="\n")


# Each case: id, kind ("bad" or "good"), phase, optional allowed_paths / state_layer,
# changed (the paths whose content or existence changes), and for bad cases the refusals
# expected as [path, code] pairs.
VISIBLE_CASES: list[dict[str, Any]] = [
    {
        "id": "bad-middleware-file",
        "kind": "bad",
        "phase": "build",
        "ops": [
            ("append", "app/api/issues.py", "\n# Idempotency-Key handled in middleware\n"),
            ("write", "app/middleware/idempotency.py", "def middleware(request):\n    pass\n"),
        ],
        "changed": ["app/api/issues.py", "app/middleware/idempotency.py"],
        "refusals": [["app/middleware/idempotency.py", "outside_allowed_paths"]],
    },
    {
        "id": "bad-feature-list-edit",
        "kind": "bad",
        "phase": "build",
        "ops": [("replace", "feature_list.json", '"passes": false', '"passes": true')],
        "changed": ["feature_list.json"],
        "refusals": [["feature_list.json", "harness_only"]],
    },
    {
        "id": "bad-test-phase-source-edit",
        "kind": "bad",
        "phase": "test",
        "ops": [
            ("write", "tests/visible/test_f3.py", "def test_replay():\n    assert True\n"),
            ("replace", "app/services/issues.py", "repo.insert(", "repo.insert_once("),
        ],
        "changed": ["app/services/issues.py", "tests/visible/test_f3.py"],
        "refusals": [["app/services/issues.py", "test_phase_source_edit"]],
    },
    {
        "id": "bad-parent-traversal",
        "kind": "bad",
        "phase": "build",
        "raw": (
            "--- a/../teamtrack-secrets.env\n"
            "+++ b/../teamtrack-secrets.env\n"
            "@@ -1 +1 @@\n"
            "-DEBUG=0\n"
            "+DEBUG=1\n"
        ),
        "changed": ["../teamtrack-secrets.env"],
        "refusals": [["../teamtrack-secrets.env", "path_escape"]],
    },
    {
        "id": "bad-rename-out-of-scope",
        "kind": "bad",
        "phase": "build",
        "ops": [("rename", "app/api/issues.py", "app/api/issues_v2.py")],
        "changed": ["app/api/issues.py", "app/api/issues_v2.py"],
        "refusals": [["app/api/issues_v2.py", "outside_allowed_paths"]],
    },
    {
        "id": "bad-binary-out-of-scope",
        "kind": "bad",
        "phase": "build",
        "ops": [("write", "app/static/logo.png", PNG + b"\x01" * 16)],
        "changed": ["app/static/logo.png"],
        "refusals": [["app/static/logo.png", "outside_allowed_paths"]],
    },
    {
        "id": "good-in-scope-build",
        "kind": "good",
        "phase": "build",
        "ops": [
            ("replace", "app/api/issues.py", "body: dict, user", "body: dict, key: str, user"),
            ("replace", "app/services/issues.py", "def create(", "def create_once("),
            ("replace", "docs/HANDBOOK.md", "R5 Audit.", "R5 Audit (replays add none)."),
            ("write", "tests/visible/test_f3_replay.py", "def test_replay():\n    assert True\n"),
        ],
        "changed": [
            "app/api/issues.py",
            "app/services/issues.py",
            "docs/HANDBOOK.md",
            "tests/visible/test_f3_replay.py",
        ],
    },
    {
        "id": "good-state-files",
        "kind": "good",
        "phase": "build",
        "ops": [
            ("append", "progress.md", "\n## Done\n\n- service change\n"),
            ("append", "docs/exec-plans/active/F3.md", "- [x] service\n"),
            ("append", "session-handoff.md", "\n## Notes from the agent\n\nAPI next.\n"),
        ],
        "changed": ["docs/exec-plans/active/F3.md", "progress.md", "session-handoff.md"],
    },
    {
        "id": "good-rename-in-scope",
        "kind": "good",
        "phase": "test",
        "ops": [("rename", "tests/visible/test_issues.py", "tests/visible/test_issues_api.py")],
        "changed": ["tests/visible/test_issues.py", "tests/visible/test_issues_api.py"],
    },
    {
        "id": "good-space-in-path",
        "kind": "good",
        "phase": "build",
        "allowed_paths": {"build": ["docs/**"], "test": ["tests/visible/**"]},
        "ops": [("append", "docs/design notes/f3 retry.md", "Keys expire after 24 h.\n")],
        "changed": ["docs/design notes/f3 retry.md"],
    },
    {
        "id": "good-copy-from-out-of-scope",
        "kind": "good",
        "phase": "test",
        "copies": True,
        "ops": [("copy", "app/core/config.py", "tests/visible/config_snapshot.py")],
        "changed": ["tests/visible/config_snapshot.py"],
    },
    {
        "id": "good-empty-diff",
        "kind": "good",
        "phase": "build",
        "raw": "",
        "changed": [],
    },
]


def main() -> int:
    build(VISIBLE_CASES, HERE)
    print(f"wrote {len(VISIBLE_CASES)} cases to {HERE / 'cases.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
