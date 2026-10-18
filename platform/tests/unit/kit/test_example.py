"""The worked example (kit/examples/boltons-queueutils/filled) is a filled-in copy of the kit."""

from __future__ import annotations

import configparser
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from shipharness.checks.runner import run_checks
from shipharness.config.prices import REPO_ROOT
from shipharness.kit.files import KIT_DIR, TEMPLATES, template_files
from shipharness.kit.markers import find_markers, unfilled

EXAMPLE = KIT_DIR / "examples" / "boltons-queueutils"
FILLED = EXAMPLE / "filled"
CLONE = REPO_ROOT / ".shipharness" / "libs" / "boltons" / "src"
DELETED = {
    "docs/SECURITY.md",
    "docs/RELIABILITY.md",
    "docs/design-docs/api-conventions.md",
    "docs/design-docs/cursor-pagination.md",
    "docs/product-specs/teamtrack-base.md",
    "docs/references/alembic-llms.txt",
}


def load_adapter():  # type: ignore[no-untyped-def]
    path = FILLED / "harness" / "shipharness_adapter.py"
    spec = importlib.util.spec_from_file_location("example_adapter", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HouseRulesAdapter()


def test_no_marker_is_left_and_only_the_listed_files_are_gone() -> None:
    markers, missing = unfilled(FILLED)
    assert markers == []
    assert set(missing) == DELETED
    assert set(template_files()) - DELETED <= {
        p.relative_to(FILLED).as_posix() for p in FILLED.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("rel", ["feature_list.schema.json", "harness/sandbox-policy.toml"])
def test_files_kept_as_copied_equal_the_kit_without_markers(rel: str) -> None:
    kit_lines = (TEMPLATES / rel).read_text(encoding="utf-8").splitlines()
    kept = [line for line in kit_lines if not find_markers(line)]
    assert (FILLED / rel).read_text(encoding="utf-8").splitlines() == kept


def test_feature_list_follows_the_schema_fields() -> None:
    schema = json.loads((FILLED / "feature_list.schema.json").read_text(encoding="utf-8"))
    document = json.loads((FILLED / "feature_list.json").read_text(encoding="utf-8"))
    item = schema["properties"]["features"]["items"]
    assert set(document) <= set(schema["properties"])
    for feature in document["features"]:
        assert set(feature) == set(item["required"])
        assert feature["passes"] is False and feature["evidence"] is None


def test_adapter_holds_a_layers_contract_for_the_three_modules() -> None:
    adapter = load_adapter()
    assert adapter.exemptions("m1-base") == {}
    config = configparser.ConfigParser()
    config.read_string(adapter.layering_contract())
    layers = config["importlinter:contract:bq1"]["layers"].split()
    assert layers == ["boltons.queueutils", "boltons.listutils", "boltons.typeutils"]


GUIDES = [
    REPO_ROOT / "use-in-your-repo" / "README.md",
    REPO_ROOT / "use-in-your-repo" / "apply-to-your-repo.md",
    KIT_DIR / "README.md",
    EXAMPLE / "README.md",
]
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_PENDING = re.compile(
    r"^\[\[PENDING: [^|\]]+ \| source: (M6 pilot|M8 batch 1|M8 ablation|live class) \| how: .+\]\]$"
)


def _slug(heading: str) -> str:
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {_slug(line.lstrip("#")) for line in lines if line.startswith("#")}


@pytest.mark.parametrize("guide", GUIDES, ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_guide_links_and_anchors_resolve(guide: Path) -> None:
    for target in _LINK.findall(guide.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target):
            continue
        file_part, _, anchor = target.partition("#")
        path = (guide.parent / file_part).resolve() if file_part else guide
        assert path.exists(), (guide.name, target)
        if anchor:
            assert anchor in _anchors(path), (guide.name, target)


def test_guide_pending_markers_use_the_course_form() -> None:
    text = (REPO_ROOT / "use-in-your-repo" / "apply-to-your-repo.md").read_text(encoding="utf-8")
    # Before release the guide holds no PENDING marker; any that remains uses the course form.
    markers = [line for line in text.splitlines() if "[[PENDING" in line]
    for line in markers:
        assert _PENDING.match(line), line


@pytest.mark.slow
@pytest.mark.skipif(not (CLONE / "boltons").is_dir(), reason="boltons clone not fetched")
def test_house_rule_check_passes_on_the_rebuilt_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "boltons-queueutils"
    subprocess.run(
        ["bash", str(EXAMPLE / "make_repo.sh"), str(repo)], check=True, capture_output=True
    )
    shutil.copytree(FILLED, repo, dirs_exist_ok=True)
    monkeypatch.syspath_prepend(str(repo / "harness"))
    monkeypatch.delitem(sys.modules, "shipharness_adapter", raising=False)
    monkeypatch.chdir(repo)
    params = json.loads((repo / "harness" / "check-params.json").read_text(encoding="utf-8"))
    params["adapter"] = "shipharness_adapter:HouseRulesAdapter"
    results, crashed = run_checks(
        repo,
        ["r6_layering", "regression"],
        checkpoint="m1-base",
        feature_id="F1",
        seed=0,
        params=params,
    )
    assert not crashed
    assert {r.check: (r.passed, r.total_probes) for r in results} == {
        "r6_layering": (True, 1),
        "regression": (True, 21),
    }
