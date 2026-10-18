"""A small course repository for the features dataset tests.

B-features writes the F1-F7 manifests, hidden tests, feature mutants, and `checkpoints.toml` in
parallel with B-dataset-a, so these tests build stand-ins for them in a temporary directory. The
control tasks (C1-C8), the module mutant files, and the ticket sources are copied from this
repository, so the generator and the checks run on the real control data.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))
FEATURES = ("F1", "F2", "F3", "F4", "F5", "F6", "F7")
CONTROLS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
START = {
    "F1": "m1-s1-start",
    "F2": "m1-s2-start",
    "F3": "m1-s3-start",
    "F4": "m1-s4-start",
    "F5": "m1-final-start",
    "F6": "m1-final-start",
    "F7": "m1-final-start",
}
SECTION = {"F1": "S1", "F2": "S2", "F3": "S3", "F4": "S4"}
PRIMARY = {
    "F1": "r1_new_violations>=1",
    "F2": "continuity_failure",
    "F3": "out_of_scope_files>=1 or test_phase_source_edits>=1",
    "F4": "hidden_passed,mutants_killed",
}
TWO_SESSIONS = {"F2", "F6", "F7"}
CHECKPOINTS = {
    "m1-s1-start": [],
    "m1-s2-start": ["f1"],
    "m1-s3-start": ["f1", "f2"],
    "m1-s4-start": ["f1", "f2", "f3"],
    "m1-final-start": ["f1", "f2", "f3", "f4"],
    "m1-complete": ["f1", "f2", "f3", "f4", "f5", "f6", "f7"],
    "m1-alt-a": ["f5", "f6"],
    "m1-alt-b": ["f7"],
}

HIDDEN_TEST = """\
from hidden_support import auth


def test_{task}_one(client, acme):
    assert client.get("/health", headers=auth(acme.admin)).status_code == 200


def test_{task}_two(client):
    assert client.get("/health").status_code == 200
"""


def _toml_list(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(v) for v in values) + "]"


def feature_manifest(feature: str) -> str:
    task = feature.lower()
    start = START[feature]
    hidden_file = f"tests/hidden/{task}/test_{task}_fixture.py"
    checkpoints = [start] + (["m1-alt-a", "m1-alt-b"] if feature in PRIMARY else [])
    budget = [12, 30] if feature in TWO_SESSIONS else [30]
    lines = [
        f'id = "{feature}"',
        f'title = "Fixture feature {feature}"',
        f'section = "{SECTION.get(feature, "final")}"',
        f'start_checkpoint = "{start}"',
        f'primary_measure = "{PRIMARY.get(feature, "")}"',
        f'mutant_set = "features/{task}"',
        f"session_budget = {budget}",
        f'canonical_ticket = """Fixture canonical ticket for {feature}."""',
        "",
        "[allowed_paths]",
        f"build = {_toml_list(['app/api/issues.py', 'tests/visible/**'])}",
        f"test = {_toml_list(['tests/visible/**'])}",
        "",
        "[hidden]",
    ]
    lines += [f'"{cp}" = {_toml_list([hidden_file])}' for cp in checkpoints]
    return "\n".join(lines) + "\n"


def feature_mutant(task: str) -> str:
    record = {
        "id": f"features.{task}-m1",
        "target": f"features.{task}",
        "set": "referee",
        "file": "app/api/issues.py",
        "line": 1,
        "original": "from __future__ import annotations",
        "replacement": "",
        "rationale": "fixture mutant",
    }
    return json.dumps(record) + "\n"


def checkpoints_toml() -> str:
    parts = [
        f'[checkpoints."{name}"]\ntasks = {_toml_list(tasks)}\n'
        for name, tasks in CHECKPOINTS.items()
    ]
    return "\n".join(parts)


def make_repo(
    root: Path, *, features: tuple[str, ...] = FEATURES, real_sources: bool = True
) -> Path:
    """A course repository with fixture F manifests and (with `real_sources`) the real controls
    and ticket sources."""
    tt = root / "teamtrack"
    for feature in features:
        task = feature.lower()
        ref = tt / "reference" / task
        ref.mkdir(parents=True)
        (ref / "task.toml").write_text(feature_manifest(feature), encoding="utf-8")
        hidden = tt / "tests" / "hidden" / task
        hidden.mkdir(parents=True)
        (hidden / f"test_{task}_fixture.py").write_text(
            HIDDEN_TEST.format(task=task), encoding="utf-8"
        )
        mutants = tt / "mutants" / "features"
        mutants.mkdir(parents=True, exist_ok=True)
        (mutants / f"{task}.jsonl").write_text(feature_mutant(task), encoding="utf-8")
    (tt / "reference").mkdir(parents=True, exist_ok=True)
    (tt / "reference" / "checkpoints.toml").write_text(checkpoints_toml(), encoding="utf-8")
    for path in (REPO / "platform" / "teamtrack" / "mutants").glob("*.jsonl"):
        shutil.copy2(path, tt / "mutants" / path.name)
    if not real_sources:
        return root
    for control in CONTROLS:
        task = control.lower()
        shutil.copytree(
            REPO / "platform" / "teamtrack" / "reference" / task, tt / "reference" / task
        )
        shutil.copytree(
            REPO / "platform" / "teamtrack" / "tests" / "hidden" / task,
            tt / "tests" / "hidden" / task,
        )
    sources = root / "datasets" / "sources"
    sources.mkdir(parents=True)
    shutil.copy2(
        REPO / "platform" / "datasets" / "sources" / "tickets.toml", sources / "tickets.toml"
    )
    return root
