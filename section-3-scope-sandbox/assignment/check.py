"""Self-check for assignment A3 (make check-assignment-3).

Usage (from the repository root):
    uv run python section-3-scope-sandbox/assignment/check.py [--impl PATH]

--impl names the folder that holds your `a3scope` package and `tests/` (default: the starter).
The check runs the visible tests, your denial test (with your rule, then with the rule removed),
checks the live A/B evidence in <impl>/live/ if it is there (live.py verify), and lists the TODO
markers left. It needs no API keys and no container runtime. Exit code 0 means every visible check
passed and the live evidence, if present, is valid; the grader adds hidden diffs, commands, and
status cases, and requires the live evidence.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _course_root(assignment: Path) -> Path:
    """The course repository root: the nearest folder above `assignment` with a pyproject.toml
    (found by that marker, not a fixed depth), else the folder that holds the section folder."""
    for folder in assignment.parents:
        if (folder / "pyproject.toml").is_file():
            return folder
    return assignment.parents[1]


ASSIGNMENT = Path(__file__).resolve().parent
REPO = _course_root(ASSIGNMENT)
VISIBLE = ASSIGNMENT / "visible_tests"
STARTER = ASSIGNMENT / "starter"
LEARNER_TEST = Path("tests") / "test_a3_sandbox_rule.py"
PLUGIN_DIR = ASSIGNMENT / "visible_tests" / "plugins"
LIVE_TOOL = ASSIGNMENT / "live.py"

# Test-name prefix -> group. Groups feed the grading criteria in README.md.
GROUPS: dict[str, tuple[str, str]] = {
    "parse": ("test_parse_", "diff parsing and path matching"),
    "bad": ("test_bad_", "out-of-scope diffs rejected"),
    "good": ("test_good_", "legitimate diffs accepted"),
    "sets": ("test_status_sets_", "passes set with evidence"),
    "keeps": ("test_status_keeps_", "passes kept false without evidence"),
    "denies": ("test_rule_denies_", "history rule denies"),
    "allows": ("test_rule_allows_", "history rule allows (no false positives)"),
}
WHERE: dict[str, str] = {
    "parse": "a3scope/diffparse.py, a3scope/scope.py (glob_matches)",
    "bad": "a3scope/scope.py (check_diff)",
    "good": "a3scope/scope.py (check_diff)",
    "sets": "a3scope/status.py",
    "keeps": "a3scope/status.py",
    "denies": "a3scope/policy.py",
    "allows": "a3scope/policy.py",
}


@dataclass(frozen=True)
class Case:
    name: str  # test function name with parameters, e.g. test_bad_diff_rejected[bad-x]
    passed: bool
    message: str

    @property
    def function(self) -> str:
        return self.name.split("[", 1)[0]


def run_pytest(
    targets: list[Path], impl: Path, extra_args: tuple[str, ...] = ()
) -> tuple[list[Case], str]:
    """Run pytest in a subprocess against `impl`; return one Case per test and the output."""
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        env = {**os.environ, "A3_IMPL": str(impl)}
        paths = [str(impl), str(PLUGIN_DIR), env.get("PYTHONPATH", "")]
        env["PYTHONPATH"] = os.pathsep.join(p for p in paths if p)
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--rootdir",
                str(REPO),
                f"--junitxml={junit}",
                *extra_args,
                *map(str, targets),
            ],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        output = done.stdout + done.stderr
        if not junit.exists():
            return [], output
        cases = []
        for node in ET.parse(junit).getroot().iter("testcase"):
            problem = next((c for c in node if c.tag in ("failure", "error")), None)
            if any(c.tag == "skipped" for c in node):
                continue
            message = (problem.get("message") or "")[:300] if problem is not None else ""
            cases.append(Case(node.get("name", "?"), problem is None, message))
        return cases, output


def group_counts(cases: list[Case]) -> dict[str, dict[str, int]]:
    counts = {key: {"passed": 0, "total": 0} for key in GROUPS}
    for case in cases:
        for key, (prefix, _label) in GROUPS.items():
            if case.function.startswith(prefix):
                counts[key]["total"] += 1
                counts[key]["passed"] += int(case.passed)
    return counts


def uses_policy_code(test_file: Path) -> bool:
    """The denial test calls check_command or PolicySandbox and uses a3scope.policy."""
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    calls_policy_code = bool({"check_command", "PolicySandbox"} & names)
    return calls_policy_code and "a3scope.policy" in modules


def denial_test_checks(impl: Path) -> tuple[dict[str, bool], list[Case]]:
    """passes: every test in tests/test_a3_sandbox_rule.py passes (and there is one).
    fails_without_rule: at least one fails when HISTORY_RULES is emptied.
    uses_policy_code: the denial goes through check_command or PolicySandbox."""
    test_file = impl / LEARNER_TEST
    if not test_file.is_file():
        return {"passes": False, "fails_without_rule": False, "uses_policy_code": False}, []
    cases, _ = run_pytest([test_file], impl)
    passes = bool(cases) and all(c.passed for c in cases)
    fails_without_rule = False
    if passes:
        mutated, _ = run_pytest([test_file], impl, ("-p", "a3_rule_removed"))
        fails_without_rule = bool(mutated) and not all(c.passed for c in mutated)
    checks = {
        "passes": passes,
        "fails_without_rule": fails_without_rule,
        "uses_policy_code": uses_policy_code(test_file),
    }
    return checks, cases


def live_verify(impl: Path, live: Path | None = None) -> dict[str, Any]:
    """live.py verify on <impl>/live (or `live`), in a subprocess: your a3scope is imported."""
    folder = live or impl / "live"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "live.json"
        done = subprocess.run(
            [
                sys.executable,
                str(LIVE_TOOL),
                "verify",
                "--impl",
                str(impl),
                "--live",
                str(folder),
                "--json",
                str(out),
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if out.exists():
            return json.loads(out.read_text(encoding="utf-8"))
    tail = (done.stdout + done.stderr)[-600:]
    return {
        "live": str(folder),
        "present": folder.is_dir(),
        "evidence_ok": False,
        "verdicts_ok": False,
        "evidence_problems": [f"live.py verify did not finish: {tail}"],
        "verdict_problems": [],
    }


def todo_markers(impl: Path) -> list[str]:
    found = []
    for path in sorted([*(impl / "a3scope").glob("*.py"), impl / LEARNER_TEST]):
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = re.search(r"TODO\(A3[^)]*\)", line)
            if match:
                found.append(f"{path.relative_to(impl).as_posix()}:{number}: {match.group(0)}")
    return found


def _status(passed: int, total: int) -> str:
    return "ok" if total and passed == total else "FAIL"


def shown(path: Path) -> str:
    """The path relative to the repository root when it is inside it."""
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--impl", type=Path, default=STARTER, help="folder holding a3scope/")
    args = parser.parse_args(argv)
    impl = args.impl.resolve()
    if not (impl / "a3scope").is_dir():
        print(f"x no a3scope package in {impl}")
        return 2

    print(f"A3 self-check: {shown(impl)}")
    cases, output = run_pytest([VISIBLE], impl)
    if not cases:
        print("x the visible tests did not run; pytest said:\n" + output[-2000:])
        return 1
    counts = group_counts(cases)
    ok = True
    print(f"  {'check':<50} {'visible tests':>13}  status  where")
    for key, (_prefix, label) in GROUPS.items():
        passed, total = counts[key]["passed"], counts[key]["total"]
        status = _status(passed, total)
        ok &= status == "ok"
        where = "" if status == "ok" else WHERE[key]
        print(f"  {label:<50} {f'{passed}/{total}':>13}  {status:<6}  {where}".rstrip())

    checks, _ = denial_test_checks(impl)
    labels = {
        "passes": "your denial test passes",
        "fails_without_rule": "your denial test fails with the rule removed",
        "uses_policy_code": "your denial test uses check_command/PolicySandbox",
    }
    for key, label in labels.items():
        status = "ok" if checks[key] else "FAIL"
        ok &= checks[key]
        where = "" if checks[key] else LEARNER_TEST.as_posix()
        print(f"  {label:<50} {'':>13}  {status:<6}  {where}".rstrip())

    live = live_verify(impl)
    label = "live A/B evidence (live/)"
    if not live["present"]:
        print(f"  {label:<50} {'':>13}  missing (required for the grade: README step 8)")
    else:
        live_ok = live["evidence_ok"] and live["verdicts_ok"]
        ok &= live_ok
        print(f"  {label:<50} {'':>13}  {'ok' if live_ok else 'FAIL':<6}  live/".rstrip())
        for problem in [*live["evidence_problems"], *live["verdict_problems"]][:8]:
            print(f"    - {problem}")

    failed = [c for c in cases if not c.passed]
    if failed:
        print(f"\n  Failing visible tests ({len(failed)}; first 10):")
        for case in failed[:10]:
            print(f"    - {case.name}: {case.message.splitlines()[0] if case.message else ''}")
    markers = todo_markers(impl)
    if markers:
        print(f"\n  TODO markers left ({len(markers)}):")
        for marker in markers:
            print(f"    - {marker}")
    print()
    if ok and not live["present"]:
        print("Self-check PASSED. Next: the live A/B (README step 8), then submit your")
        print("folder; the instructor grades it with make grade-assignment-3 SUBMISSION=<folder>")
        print("(adds the hidden cases and requires live/).")
        return 0
    if ok:
        print("Self-check PASSED. Next: submit your folder; the instructor grades it with")
        print("make grade-assignment-3 SUBMISSION=<folder> (adds the hidden cases).")
        return 0
    print("Self-check FAILED: fix the FAIL rows above (README 'Step by step').")
    return 1


if __name__ == "__main__":
    sys.exit(main())
