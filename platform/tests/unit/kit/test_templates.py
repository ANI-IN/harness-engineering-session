"""Drift tests: every kit template still matches the TeamTrack source it was taken from.

A template is its source plus REPLACE marker lines. When a source changes (a section renamed, a
step added to init.sh, a field added to the feature list schema), the matching test fails and names
the file to recopy (`uv run python -m shipharness.kit.sources <file>` prints rendered ones).
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

from shipharness.checks.adapter import TenantAppAdapter
from shipharness.checks.params import ALL_NAMES
from shipharness.config.prices import REPO_ROOT
from shipharness.datasets.names import rule_label
from shipharness.kit import sources
from shipharness.kit.files import TEMPLATES, template_files
from shipharness.kit.markers import find_markers
from shipharness.sandbox.policy import SandboxPolicy, docker_run_args

OTHER_SOURCES = {
    "feature_list.json": "src/shipharness/harness/scope/features.py (build_feature, F1)",
    "feature_list.schema.json": "src/shipharness/harness/scope/assets/feature_list.schema.json",
    "docs/clean-state-checklist.md": "skills/harness-setup/assets/templates and verify/clean_state",
    "docs/house-rules.md": "src/shipharness/checks/ (House rules 1 to 7) and checks/adapter.py",
    "harness/shipharness_adapter.py": "src/shipharness/checks/adapter.py (TeamTrackAdapter)",
    "harness/check-params.json": "src/shipharness/checks/params.py",
    "harness/sandbox-policy.toml": "src/shipharness/sandbox/policy.py (SandboxPolicy)",
    ".github/workflows/shipharness.yml": ".github/workflows/ci.yml and the check/testgen CLIs",
}
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def kit(rel: str) -> str:
    return (TEMPLATES / rel).read_text(encoding="utf-8")


def without_markers(text: str) -> list[str]:
    return [line for line in text.splitlines() if not find_markers(line)]


def is_subsequence(small: list[str], big: list[str]) -> bool:
    it = iter(big)
    return all(any(line == other for other in it) for line in small)


def drop_replace(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: drop_replace(v) for k, v in value.items() if k != "_replace"}
    if isinstance(value, list):
        return [drop_replace(v) for v in value]
    return value


def test_every_template_names_its_source() -> None:
    known = (
        set(sources.COPIED)
        | set(sources.SUBSET)
        | set(sources.EXTENDED)
        | set(sources.RENDERED)
        | set(OTHER_SOURCES)
    )
    assert set(template_files()) == known


@pytest.mark.parametrize("rel", template_files())
def test_every_template_has_a_replace_marker(rel: str) -> None:
    assert find_markers(kit(rel)), f"{rel} has no REPLACE marker"


@pytest.mark.parametrize("rel", template_files())
def test_markers_sit_on_their_own_lines(rel: str) -> None:
    for line in kit(rel).splitlines():
        for marker in find_markers(line):
            stripped = line.strip()
            assert stripped.startswith(("<!--", "#", '"_replace"')), (rel, line)
            assert marker.text, (rel, line)


@pytest.mark.parametrize(("rel", "source"), sorted(sources.COPIED.items()))
def test_copied_templates_equal_their_teamtrack_source(rel: str, source: str) -> None:
    assert without_markers(kit(rel)) == sources.source_text(source).splitlines(), (
        f"{rel} drifted from teamtrack/harness/instructions/{source}"
    )


@pytest.mark.parametrize(("rel", "source"), sorted(sources.SUBSET.items()))
def test_trimmed_templates_keep_source_lines_in_order(rel: str, source: str) -> None:
    source_lines = sources.source_text(source).splitlines()
    assert is_subsequence(without_markers(kit(rel)), source_lines), rel


@pytest.mark.parametrize(("rel", "source"), sorted(sources.EXTENDED.items()))
def test_extended_templates_hold_every_source_line(rel: str, source: str) -> None:
    source_lines = sources.source_text(source).splitlines()
    assert is_subsequence(source_lines, without_markers(kit(rel))), rel


@pytest.mark.parametrize(("rel", "asset"), sorted(sources.RENDERED.items()))
def test_rendered_templates_equal_the_harness_rendering(rel: str, asset: str) -> None:
    assert without_markers(kit(rel)) == sources.rendered(asset).splitlines(), (
        f"{rel} drifted from src/shipharness/harness/state/assets/{asset}"
    )


def test_agents_map_holds_the_session_steps_the_harness_gives() -> None:
    text = kit("AGENTS.md")
    start, wrap = sources.session_steps()
    steps = [m.group(1) for m in re.finditer(r"^\d+\. (.+)$", start + "\n" + wrap, re.M)]
    assert len(steps) >= 10
    for step in steps:
        assert step in text, step


def test_agents_map_stays_near_one_hundred_lines() -> None:
    assert len(without_markers(kit("AGENTS.md"))) <= 130


def test_feature_list_is_the_harness_rendering_for_f1() -> None:
    document = json.loads(kit("feature_list.json"))
    assert "_replace" in document
    assert drop_replace(document) == sources.feature_document()


def test_feature_list_schema_matches_the_scope_layer_schema() -> None:
    document = json.loads(kit("feature_list.schema.json"))
    assert drop_replace(document) == sources.schema_document()
    item = document["properties"]["features"]["items"]
    assert {"passes", "evidence", "testedAt"} <= set(item["required"])


def test_feature_list_with_a_replace_note_fails_the_schema() -> None:
    """The schema's additionalProperties rejects `_replace`: an unfilled list is invalid."""
    schema = sources.schema_document()
    assert schema["additionalProperties"] is False
    assert "_replace" not in schema["properties"]


def test_clean_state_checklist_follows_the_template_and_the_gate() -> None:
    text = kit("docs/clean-state-checklist.md")
    template = (
        REPO_ROOT
        / "use-in-your-repo/skills/harness-setup/assets/templates/clean-state-checklist.md"
    )
    heads = [ln for ln in template.read_text(encoding="utf-8").splitlines() if ln.startswith("#")]
    assert [ln for ln in without_markers(text) if ln.startswith("#")] == heads
    gate = (REPO_ROOT / "platform/src/shipharness/harness/verify/clean_state.py").read_text(
        encoding="utf-8"
    )
    for needle in ("git status --porcelain --untracked-files=all", "ruff check", "alembic heads"):
        assert needle in gate and needle in text, needle
    for debug in ("print(", "breakpoint()", "import pdb", "pdb.set_trace("):
        assert debug in text, debug


def test_house_rules_doc_covers_r1_to_r7_with_real_adapter_methods() -> None:
    text = kit("docs/house-rules.md")
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        assert f"| {rule_label(rule)} | yes |" in text, rule
    named = set(re.findall(r"`([a-z_]+)\(\)`", text))
    members = {n for n in dir(TenantAppAdapter) if not n.startswith("_")}
    members |= set(TenantAppAdapter.__annotations__)
    assert named and named <= members, named - members


def test_check_params_use_real_param_names() -> None:
    params = drop_replace(json.loads(kit("harness/check-params.json")))
    assert params and set(params) <= set(ALL_NAMES)


def test_sandbox_policy_example_equals_the_course_policy() -> None:
    text = kit("harness/sandbox-policy.toml")
    data = tomllib.loads(text)
    policy = SandboxPolicy()
    for name in (
        "version",
        "network",
        "cpus",
        "memory_mb",
        "swap_mb",
        "pids_limit",
        "user",
        "read_only_root",
        "cap_drop",
        "no_new_privileges",
        "workspace_mount",
        "tool_timeout_s",
        "run_timeout_s",
    ):
        expected = getattr(policy, name)
        actual = data[name]
        assert (tuple(actual) if isinstance(expected, tuple) else actual) == expected, name
    assert data["tmpfs"] == policy.tmpfs
    deny = [(r["pattern"], r["reason_code"], r["message"]) for r in data["deny"]]
    assert deny == [(r.pattern, r.reason_code, r.message) for r in policy.deny_command_patterns]
    detect = [(r["pattern"], r["reason_code"]) for r in data["detect"]]
    assert detect == [(r.pattern, r.reason_code) for r in policy.detect_output_patterns]
    args = docker_run_args(policy, "<image>", Path("/work-host"), "<name>")
    command = " ".join(args).replace(str(Path("/work-host").resolve()), "<workspace>")
    assert f"#   {command}" in text


def test_workflow_runs_check_on_push_and_testgen_on_demand() -> None:
    workflow = yaml.safe_load(kit(".github/workflows/shipharness.yml"))
    triggers = workflow[True] if True in workflow else workflow["on"]  # YAML 1.1 reads `on` as True
    assert "push" in triggers and "workflow_dispatch" in triggers
    check, testgen = workflow["jobs"]["check"], workflow["jobs"]["testgen"]
    check_runs = " ".join(step.get("run", "") for step in check["steps"])
    assert "shipharness check" in check_runs
    assert testgen["if"] == "github.event_name == 'workflow_dispatch'"
    testgen_runs = " ".join(step.get("run", "") for step in testgen["steps"])
    assert "shipharness testgen" in testgen_runs
    env = {**testgen.get("env", {}), **workflow.get("env", {})}
    assert env["OPENAI_API_KEY"] == "${{ secrets.OPENAI_API_KEY }}"
    assert "OPENAI_API_KEY" not in json.dumps(check)
    ci = yaml.safe_load((REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    uv_version = ci["jobs"]["lint"]["steps"][1]["with"]["version"]
    for job in (check, testgen):
        setup = [s for s in job["steps"] if str(s.get("uses", "")).startswith("astral-sh/setup-uv")]
        assert setup and setup[0]["with"]["version"] == uv_version


@pytest.mark.parametrize("rel", [r for r in template_files() if r.endswith(".md")])
def test_relative_links_resolve_inside_the_kit(rel: str) -> None:
    for target in _LINK.findall(kit(rel)):
        if re.match(r"^(?:[a-z]+:|#|/)", target):
            continue
        path = (TEMPLATES / rel).parent / target.split("#", 1)[0]
        assert path.resolve().is_relative_to(TEMPLATES.resolve()), (rel, target)
        assert path.exists(), (rel, target)
