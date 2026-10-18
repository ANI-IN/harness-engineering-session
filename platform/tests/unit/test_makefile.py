"""The Makefile targets are thin wrappers over real `shipharness` commands, and the default pytest
run deselects slow validations while `make test-all` keeps them.

No make binary is needed: the Makefile is parsed as text, and each `shipharness` command line is
parsed by the real CLI (click make_context), so an option the CLI does not accept fails here.
"""

from __future__ import annotations

import re
import shlex
import tomllib
from pathlib import Path

import pytest
import typer
from _pytest.mark.expression import Expression

from shipharness.cli import app
from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))
MAKEFILE = REPO / "Makefile"
PYPROJECT = REPO / "pyproject.toml"
CONFTEST = REPO / "platform" / "tests" / "conftest.py"

# Sample values substituted for make variables before the CLI parses a recipe line.
SAMPLES = {
    "$(FEATURE)": "safe-retries",
    "$(LAYERS_OPT)": "--layers=-scope",
    "$(SESSION_BUDGET_OPT)": "--session-budget=12,38",
    "$(MAX_TESTS_OPT)": "--max-tests=3",
    "$(PURPOSE)": "pilot",
    "$(PROFILE)": "standard",
    "$(RUNTIME)": "docker",
    "$(AB)": "ab-20261016-000000-abcdef",
    "$(RUN)": "r-20261016-000000-abcdef",
    "$(CONSOLE_PORT)": "8766",
    "$(VERBOSE_OPT)": "--verbose",
    "$$f": "bulk-close",
}


def _rules() -> dict[str, list[str]]:
    """target -> recipe lines (continuations joined), for every explicit rule in the Makefile."""
    text = MAKEFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    rules: dict[str, list[str]] = {}
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("\t"):
            current.append(line.strip())
            continue
        match = re.match(r"^([A-Za-z0-9_. -]+?)\s*:(?!=)", line)
        if match and not line.startswith((".PHONY", "#")):
            current = []
            for target in match.group(1).split():
                rules[target] = current
        elif line.strip() and not line.startswith("#"):
            current = []
    return rules


def _variables() -> dict[str, str]:
    out = {}
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z_]+)\s*(\?=|:=|=)\s*(.*)$", line)
        if match:
            out[match.group(1)] = match.group(3).strip()
    return out


def _shipharness_calls(target: str) -> list[list[str]]:
    """Every `$(UV) run shipharness ...` call in a target's recipe, as argv after `shipharness`."""
    calls = []
    for line in _rules()[target]:
        for chunk in line.split(";"):
            if "$(UV) run shipharness " not in chunk:
                continue
            rest = chunk.split("$(UV) run shipharness ", 1)[1]
            rest = rest.split("||", 1)[0]
            for name, value in SAMPLES.items():
                rest = rest.replace(name, value)
            calls.append(shlex.split(rest))
    return calls


def _parse(argv: list[str]) -> tuple[str, dict]:
    """Parse argv with the real CLI without running it; return (command, params)."""
    group = typer.main.get_command(app)
    command = group.commands[argv[0]]  # type: ignore[attr-defined]
    ctx = command.make_context(argv[0], list(argv[1:]), resilient_parsing=False)
    return argv[0], ctx.params


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_demo_target_runs_the_section_canonical_task(n: int) -> None:
    calls = _shipharness_calls(f"demo-{n}")
    assert len(calls) == 1
    command, params = _parse(calls[0])
    assert command == "ab"
    assert params["section"] == f"demo-{n}"
    assert params["feature"] == f"F{n}"  # section N runs feature FN, canonical variant
    assert params["variant"] == "canonical"
    assert params["layers"] == "-scope"  # LAYERS=-<layer> reaches the CLI


def test_layers_option_is_empty_unless_layers_is_set() -> None:
    assert _variables()["LAYERS_OPT"] == "$(if $(LAYERS),--layers=$(LAYERS))"


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_swap_target_runs_the_swap_test_on_ab(n: int) -> None:
    calls = _shipharness_calls(f"swap-{n}")
    assert len(calls) == 1
    command, params = _parse(calls[0])
    assert command == "ab"
    assert params["swap"] == SAMPLES["$(AB)"]
    assert params["section"] == f"demo-{n}"
    assert _variables()["AB"] == "latest"  # make swap-N needs no id; AB=<id> still overrides


def test_final_runs_every_feature_in_features() -> None:
    # Two poll-chosen features by default (brief; owner 2026-10-17); the poll offers F5-F7.
    assert _variables()["FEATURES"] == "bulk-close,watchers"  # readable names (owner 2026-10-18)
    recipe = " ".join(_rules()["final"])
    assert "$(FEATURES)" in recipe
    assert "rc=$$?" in recipe and recipe.endswith("exit $$rc")  # one failure does not stop the rest
    raw = MAKEFILE.read_text(encoding="utf-8").splitlines()
    assert not [line for line in raw if "\t" in line.lstrip("\t")]  # continuations kept as lines
    calls = _shipharness_calls("final")
    assert len(calls) == 1
    command, params = _parse(calls[0])
    assert command == "ab"
    assert params["section"] == "final"
    assert params["feature"] == "F5"
    assert params["layers"] == "-scope"


def test_final_hides_the_shell_loop_and_the_cli_names_each_feature() -> None:
    # Owner, 2026-10-18: make prints no shell loop; `shipharness ab --section final` prints
    # "Final A/B: Feature 5: Bulk close" before each A/B (tested in ab/test_record_line.py).
    lines = _rules()["final"]
    assert lines and all(line.startswith("@") for line in lines[:1])
    recipe = " ".join(lines)
    assert "rc=$$?" in recipe and recipe.endswith("exit $$rc")  # non-zero if any A/B fails
    assert "echo" not in recipe.replace('echo "$(FEATURES)"', "")


def test_replay_target_replays_run() -> None:
    calls = _shipharness_calls("replay")
    assert len(calls) == 1
    command, params = _parse(calls[0])
    assert command == "replay"
    assert params["run"] == SAMPLES["$(RUN)"]
    assert any("RUN" in line and "exit 2" in line for line in _rules()["replay"])


def test_no_milestone_stub_remains_for_wired_targets() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "available after milestone M4" not in text
    rules = _rules()
    for target in [*(f"demo-{n}" for n in range(1, 5)), *(f"swap-{n}" for n in range(1, 5))]:
        assert not any("is available after" in line for line in rules[target]), target
    for target in ("final", "replay"):
        assert not any("is available after" in line for line in rules[target]), target


# -- fast and full suites -----------------------------------------------------------------------


def _marker_expression(args: list[str]) -> str:
    return args[args.index("-m") + 1]


def _selects(expression: str, *markers: str) -> bool:
    return Expression.compile(expression).evaluate(lambda name, **_: name in markers)


def test_default_pytest_run_deselects_slow_live_and_docker() -> None:
    options = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    expression = _marker_expression(shlex.split(options["addopts"]))
    assert _selects(expression)
    for marker in ("slow", "live", "docker"):
        assert not _selects(expression, marker), marker


def test_make_test_is_the_default_run_and_test_all_adds_slow() -> None:
    rules = _rules()
    assert rules["test"] == ["$(UV) run pytest"]
    (line,) = rules["test-all"]
    assert line.startswith("$(UV) run pytest ")
    args = shlex.split(line)
    assert args[args.index("-n") + 1] == "auto"  # the full suite runs in parallel
    expression = _marker_expression(args)
    assert _selects(expression)
    assert _selects(expression, "slow")
    assert not _selects(expression, "live")
    assert not _selects(expression, "docker")


def test_conftest_slow_list_names_existing_test_files() -> None:
    from tests.conftest import SLOW_TESTS, _is_slow

    assert SLOW_TESTS
    for pattern in SLOW_TESTS:
        path, _, name = pattern.partition("::")
        assert (REPO / path).is_file(), pattern
        assert f"def {name.split('::')[-1]}(" in (REPO / path).read_text(encoding="utf-8"), pattern
        assert _is_slow(pattern) and _is_slow(f"{pattern}[x]")
    assert not _is_slow(f"{SLOW_TESTS[0]}_other")


def test_demo_targets_pass_the_purpose_and_an_optional_session_budget() -> None:
    # PURPOSE picks the LangSmith project; SESSION_BUDGET=12,38 applies the
    # pre-registered F2 lever through make.
    assert _variables()["SESSION_BUDGET_OPT"] == (
        "$(if $(SESSION_BUDGET),--session-budget=$(SESSION_BUDGET))"
    )
    for n in (1, 2, 3, 4):
        _, params = _parse(_shipharness_calls(f"demo-{n}")[0])
        assert params["purpose"] == "pilot"
        assert params["session_budget"] == "12,38"


def test_replay_target_passes_the_purpose() -> None:
    _, params = _parse(_shipharness_calls("replay")[0])
    assert params["purpose"] == "pilot"


# -- class profile, show-N, warm --------------------------------------------


def test_class_targets_run_the_class_profile_by_default() -> None:
    # demo-N, final, and show-N pass PROFILE (default class); PROFILE=standard reaches the CLI.
    assert _variables()["PROFILE"] == "class"
    targets = [*(f"demo-{n}" for n in range(1, 5)), "final", *(f"show-{n}" for n in range(1, 5))]
    for target in targets:
        _, params = _parse(_shipharness_calls(target)[0])
        assert params["profile"] == "standard", target  # the sample value of $(PROFILE)
    for target in [*(f"swap-{n}" for n in range(1, 5)), "replay"]:  # no new arm runs: no profile
        assert "$(PROFILE)" not in " ".join(_rules()[target]), target


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_show_target_runs_the_harness_arm_alone_on_the_section_task(n: int) -> None:
    calls = _shipharness_calls(f"show-{n}")
    assert len(calls) == 1
    command, params = _parse(calls[0])
    assert command == "ab"
    assert params["section"] == f"demo-{n}"
    assert params["feature"] == f"F{n}"
    assert params["arms"] == "harness"
    assert params["purpose"] == "pilot"  # the same PURPOSE handling as demo-N
    assert params["session_budget"] == "12,38"  # SESSION_BUDGET reaches show-N as it does demo-N
    assert params["swap"] is None and params["replay"] is None  # a live run: the live guard holds


def test_demo_targets_still_run_both_arms() -> None:
    for n in (1, 2, 3, 4):
        _, params = _parse(_shipharness_calls(f"demo-{n}")[0])
        assert params["arms"] == "both"


def test_warm_target_runs_the_warm_command_with_the_profile() -> None:
    calls = _shipharness_calls("warm")
    assert len(calls) == 1
    command, params = _parse(calls[0])
    assert command == "warm"
    assert params["profile"] == "standard"
    assert ".PHONY" in MAKEFILE.read_text(encoding="utf-8")
    phony = " ".join(
        line for line in MAKEFILE.read_text(encoding="utf-8").replace("\\\n", " ").splitlines()
        if line.startswith(".PHONY")
    )  # fmt: skip
    for target in ("warm", "show-1", "show-2", "show-3", "show-4"):
        assert f" {target} " in f" {phony} ", target


def test_doctor_and_warm_pass_the_purpose() -> None:
    # Owner message 9.4: make warm and make doctor check SHIPHARNESS_CLASS_DATE when PURPOSE=class
    # (the default); PURPOSE=pilot or assignment needs no date.
    assert _variables()["PURPOSE"] == "class"
    for target in ("doctor", "warm"):
        calls = _shipharness_calls(target)
        assert len(calls) == 1, target
        command, params = _parse(calls[0])
        assert command == target
        assert params["purpose"] == "pilot", target  # the sample value of $(PURPOSE)


def test_images_target_tags_the_images_the_settings_name() -> None:
    # make warm rebuilds through `make images` with the image names it uses.
    variables = _variables()
    assert variables["AGENT_IMAGE"] == "shipharness-agent:1"
    assert variables["REFEREE_IMAGE"] == "shipharness-referee:1"
    recipe = " ".join(_rules()["images"])
    assert "-t $(AGENT_IMAGE)" in recipe and "-t $(REFEREE_IMAGE)" in recipe


def test_make_n_warm_is_a_dry_run() -> None:
    # GNU make runs a recipe line that references $(MAKE) even under -n, so `make -n warm` used to
    # start `shipharness warm` (content audit, 2026-10-17).
    assert not any("$(MAKE)" in line or "${MAKE}" in line for line in _rules()["warm"])


# -- constructed examples -----------------------------------------------------


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_example_target_runs_the_section_constructed_example(n: int) -> None:
    calls = _shipharness_calls(f"example-{n}")
    assert len(calls) == 1
    command, params = _parse(calls[0])
    assert command == "example"  # never `ab`: no model, and the live guard is not involved
    assert params["section"] == f"demo-{n}"
    assert params["profile"] == "standard"  # PROFILE reaches the command
    phony = " ".join(
        line for line in MAKEFILE.read_text(encoding="utf-8").replace("\\n", " ").splitlines()
        if line.startswith(".PHONY")
    )  # fmt: skip
    assert f" example-{n} " in f" {phony} "


def test_no_target_mentions_build_milestones_or_internal_words() -> None:
    text = MAKEFILE.read_text(encoding="utf-8").lower()
    for phrase in ("milestone", "this release", "class host", "build repository", "owner"):
        assert phrase not in text, phrase


def test_experiments_and_report_show_the_command_help() -> None:
    # Both commands take many options, so the make targets show the options and exit 0.
    assert _shipharness_calls("experiments") == [["experiments", "--help"]]
    assert _shipharness_calls("report") == [["report", "--help"]]
    assert "pilot" not in _rules()  # the pilot script is not part of the course


def test_testpaths_hold_the_platform_and_the_section_assignment_tests() -> None:
    # Course-first layout (owner messages 12.2, 13): the suite runs from platform/ and from the
    # section folders; every listed folder exists in the build repository.
    options = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    paths = options["testpaths"]
    assert paths[:2] == ["platform/tests/unit", "platform/teamtrack/tests/visible"]
    for number in ("1", "2"):
        assert any(p.startswith(f"section-{number}-") for p in paths), number
    assert not [p for p in paths if "grader" in p.split("/")]  # private: not in the public file
    for path in paths:
        assert (REPO / path).is_dir(), path
    assert options["pythonpath"] == ["platform/teamtrack"]


def test_demo_3_runs_the_s3_confirmation_task_by_feature() -> None:
    # S3 confirmation (pre-registered, 2026-10-17): harness ahead on the F4 ticket, so the S3 class
    # demo is a live A/B on F4: `make demo-3 FEATURE=F4`. Without FEATURE it stays F3.
    command, params = _parse(_shipharness_calls("demo-3")[0])
    assert command == "ab" and params["section"] == "demo-3"
    assert _variables()["FEATURE"] == "safe-retries"
    assert "--feature $(FEATURE)" in " ".join(_rules()["demo-3"])


# -- readable feature names ---------------------------------------------------------------------


def _calls_with(target: str, **values: str) -> list[list[str]]:
    """The target's shipharness calls with some make variables set to other values."""
    saved = dict(SAMPLES)
    SAMPLES.update(values)
    try:
        return _shipharness_calls(target)
    finally:
        SAMPLES.clear()
        SAMPLES.update(saved)


@pytest.mark.parametrize(
    ("value", "code"),
    [("version-checks", "F4"), ("Version-Checks", "F4"), ("F4", "F4"), ("idempotent-create", "F3")],
)
def test_demo_3_feature_takes_the_readable_name_or_the_code(value: str, code: str) -> None:
    # make demo-3 FEATURE=version-checks passes the name straight to the CLI, which normalises it.
    [call] = _calls_with("demo-3", **{"$(FEATURE)": value})
    assert value in call
    _, params = _parse(call)
    assert params["feature"] == code


@pytest.mark.parametrize(
    ("value", "code"), [("watchers", "F6"), ("bulk-close", "F5"), ("F6", "F6")]
)
def test_final_features_take_the_readable_names_or_the_codes(value: str, code: str) -> None:
    # make final FEATURES=watchers,bulk-close: the loop hands each name to the CLI unchanged.
    recipe = " ".join(_rules()["final"])
    assert "--feature $$f" in recipe and "tr ',' ' '" in recipe
    [call] = _calls_with("final", **{"$$f": value})
    _, params = _parse(call)
    assert params["feature"] == code


def test_make_help_names_the_readable_feature_names() -> None:
    from shipharness.datasets.names import FEATURE_ALIASES

    text = " ".join(_rules()["help"])
    for code, alias in FEATURE_ALIASES.items():
        assert alias in text and code in text, alias
    assert "FEATURE=version-checks" in text and "FEATURES=watchers,bulk-close" in text
    assert "idempotent-create" in text  # the earlier name of safe-retries still works


def test_no_target_passes_a_bare_feature_code_to_the_cli() -> None:
    # make echoes each recipe line, so `--feature org-search` reads plainly; the CLI turns the
    # name into the code (owner, 2026-10-18).
    from shipharness.datasets.names import FEATURE_ALIASES

    for target, lines in _rules().items():
        recipe = " ".join(lines)
        assert not re.search(r"--feature F\d", recipe), target
    for n in range(1, 5):
        for target in (f"demo-{n}", f"show-{n}"):
            recipe = " ".join(_rules()[target])
            if target != "demo-3":
                assert f"--feature {FEATURE_ALIASES[f'F{n}']} " in recipe, target
    for name in ("FEATURE", "FEATURES"):
        assert not re.search(r"\bF\d", _variables()[name]), name


# -- make help covers every target ----------------------------------------------------------------

# A target line of `make help`: two spaces, the target (section targets as `demo-N`), then at least
# two spaces and a one-line description. Other lines (headings, feature names) are not target lines.
_HELP_TARGET = re.compile(r"^  (?P<name>[a-z][a-z0-9-]*[a-zN])\s{2,}(?P<text>\S.*)$")


def _help_lines() -> list[str]:
    """The text of each `@echo "..."` line of the help recipe, as make prints it."""
    lines = []
    for line in _rules()["help"]:
        match = re.fullmatch(r'@echo "(.*)"', line)
        assert match, f"help recipe line is not a plain @echo: {line}"
        lines.append(match.group(1))
    return lines


def _help_entries() -> dict[str, str]:
    entries = {}
    for line in _help_lines():
        match = _HELP_TARGET.match(line)
        if match:
            entries[match.group("name")] = match.group("text")
    return entries


def test_make_help_describes_every_target_in_one_line() -> None:
    entries = _help_entries()
    for target in _rules():
        name = re.sub(r"-[1-4]$", "-N", target)  # demo-1 to demo-4 are listed once as demo-N
        assert name in entries, f"make help does not list {target}"
        assert len(entries[name].split()) >= 3, f"{name}: the description is too short"


def test_make_help_lists_no_target_that_does_not_exist() -> None:
    targets = set(_rules())
    for name in _help_entries():
        expanded = [name]
        if name.endswith("-N"):
            expanded = [name.replace("-N", f"-{n}") for n in range(1, 5)]
        assert all(t in targets for t in expanded), f"make help lists {name}, not in the Makefile"


def test_make_help_names_the_features_by_their_readable_names() -> None:
    text = "\n".join(_help_lines())
    assert "FEATURE=version-checks" in text and "FEATURES=watchers,bulk-close" in text
    for full_name in ("Feature 4: Version checks on issue edits", "Feature 6: Watchers"):
        assert full_name in text, full_name


# -- course style check ---------------------------------------------------------------------------


def test_check_style_target_runs_the_style_checker() -> None:
    # make check-style: errors fail; CHECK_STYLE_OPTS=--strict also fails on warnings.
    assert _variables()["CHECK_STYLE_OPTS"] == ""
    assert _rules()["check-style"] == [
        "$(UV) run python platform/scripts/check_style.py $(CHECK_STYLE_OPTS)"
    ]
    phony = " ".join(
        line for line in MAKEFILE.read_text(encoding="utf-8").replace("\\n", " ").splitlines()
        if line.startswith(".PHONY")
    )  # fmt: skip
    assert " check-style " in f" {phony} "
    assert "check-style" in " ".join(_rules()["help"])


def test_only_show_4_caps_the_filtered_tests() -> None:
    # Demo setting (2026-10-18), disclosed in docs/evidence/s4.md: never on an A/B target.
    assert _variables()["MAX_TESTS"] == "3"
    rules = _rules()
    assert "$(MAX_TESTS_OPT)" in " ".join(rules["show-4"])
    for target in ("demo-3", "demo-4", "final", "show-1", "show-2", "show-3"):
        assert "MAX_TESTS" not in " ".join(rules[target]), target


# -- slides ---------------------------------------------------------------------------------------


def test_there_is_no_slides_target() -> None:
    # The class deck is the owner's PowerPoint file, slides/Harness Engineering for Coding
    # Agents.pptx, kept as it is: the repository builds no slides (2026-10-18).
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "slides" not in _rules()
    assert "slides" not in _help_entries()
    assert "SLIDES_OPTS" not in _variables()
    assert "module1-" not in text and "build_slides" not in text


def test_console_target_passes_the_port_and_verbose_on_request() -> None:
    assert _variables()["CONSOLE_PORT"] == "8765"
    assert _variables()["VERBOSE_OPT"] == "$(if $(filter-out 0,$(VERBOSE)),--verbose)"
    calls = _shipharness_calls("console")
    assert len(calls) == 1
    command, params = _parse(calls[0])
    assert command == "console"
    assert params["port"] == 8766  # CONSOLE_PORT=8766 reaches the CLI
    assert params["verbose"] is True  # VERBOSE=1 reaches the CLI as --verbose


def test_make_help_names_the_console_verbose_option() -> None:
    assert "VERBOSE=1" in _help_entries()["console"]
