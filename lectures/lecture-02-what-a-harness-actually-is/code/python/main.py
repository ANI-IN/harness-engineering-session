"""minimal-harness-loop: one deterministic loop iteration through the five
subsystems, with single-subsystem ablation.

The harness artifacts live in the workspace directory as ordinary files
(AGENTS.md, feature_list.json, tools.json, environment.json, clock.json).
They are language-neutral: the TypeScript track reads the same bytes and
must produce the same report. `--disable=<subsystem>` removes exactly one
subsystem and the run degrades in that subsystem's characteristic way.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SUBSYSTEMS = ("instructions", "state", "environment", "tools", "feedback")
ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def load(workspace: Path, name: str) -> dict:
    return json.loads((workspace / name).read_text(encoding="utf-8"))


def next_feature(feature_list: dict) -> str:
    statuses = {f["id"]: f["status"] for f in feature_list["features"]}
    for feature in feature_list["features"]:
        if feature["status"] != "not-started":
            continue
        if all(statuses.get(dep) == "passing" for dep in feature.get("depends_on", [])):
            return feature["id"]
    return feature_list["features"][0]["id"]


def guessed_date(today_iso: str) -> str:
    year, month, day = today_iso[:10].split("-")
    return f"{month}/{day}/{year}"


def run_loop(workspace: Path, disabled: str | None) -> dict:
    today = load(workspace, "clock.json")["today"]
    steps = []

    # 1. instructions: the convention comes from AGENTS.md, or gets guessed.
    if disabled == "instructions":
        convention = "MM/DD/YYYY (guessed)"
        rendered = guessed_date(today)
        steps.append({
            "subsystem": "instructions", "ok": False,
            "note": "disabled: no AGENTS.md; guessing convention MM/DD/YYYY",
        })
    else:
        agents_text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
        match = re.search(r"^- Convention: (.+)$", agents_text, re.MULTILINE)
        convention = "ISO 8601 UTC"
        rendered = today
        steps.append({
            "subsystem": "instructions", "ok": True,
            "note": f"read convention from AGENTS.md: {match.group(1) if match else '?'}",
        })

    # 2. state: pick the next feature from feature_list.json, or start over.
    if disabled == "state":
        feature = "stamp-header"
        steps.append({
            "subsystem": "state", "ok": False,
            "note": "disabled: no feature list; starting from stamp-header",
        })
    else:
        feature = next_feature(load(workspace, "feature_list.json"))
        steps.append({
            "subsystem": "state", "ok": True,
            "note": f"feature_list.json: next feature is {feature}",
        })

    # 3. environment: the formatter dependency must be present to render.
    env_ok = disabled != "environment" and (
        load(workspace, "environment.json")["dependencies"].get("formatter") == "installed"
    )
    steps.append({
        "subsystem": "environment", "ok": env_ok,
        "note": "formatter dependency installed" if env_ok
        else "disabled: formatter unavailable",
    })

    # 4. tools: writing the artifact needs the write_file tool.
    tools_ok = disabled != "tools" and (
        "write_file" in load(workspace, "tools.json")["allowed"]
    )
    written = env_ok and tools_ok
    if not tools_ok:
        tools_note = "disabled: write_file not permitted"
    elif not env_ok:
        tools_note = "skipped: nothing to write (environment failure)"
    else:
        tools_note = "write_file: artifact written"
    steps.append({"subsystem": "tools", "ok": tools_ok and env_ok, "note": tools_note})

    if written:
        content = (
            f"date: {rendered}" if feature == "format-dates"
            else f"header: notes v1 ({rendered})"
        )
    else:
        content = None

    # 5. feedback: run the check, unless disabled or there is nothing to check.
    check_ran = False
    check_passed = False
    if disabled == "feedback":
        feedback_note = "disabled: completion claimed without running the check"
        feedback_ok = False
    elif not written:
        feedback_note = "skipped: no artifact to check"
        feedback_ok = False
    else:
        check_ran = True
        check_passed = bool(ISO_RE.search(content or ""))
        feedback_ok = True
        feedback_note = (
            "run_check date-format: pass" if check_passed
            else "run_check date-format: FAIL (convention violation caught)"
        )
    steps.append({"subsystem": "feedback", "ok": feedback_ok, "note": feedback_note})

    # Outcome and issues.
    if disabled == "tools" or (not written and disabled != "environment"):
        outcome = "blocked"
        issues = ["write_file not permitted; work product could not be written"]
    elif disabled == "environment":
        outcome = "error"
        issues = ["formatter dependency unavailable; date rendering failed"]
    elif disabled == "feedback":
        outcome = "claimed-unverified"
        issues = ["completion claimed without running run_check date-format"]
    elif check_ran and not check_passed:
        outcome = "failed-verification"
        issues = [
            f"convention violation: wrote {rendered} where ISO 8601 UTC is "
            "required (caught by run_check)"
        ]
    elif feature != "format-dates":
        outcome = "completed-redundant"
        issues = [
            "re-implemented stamp-header, already passing in feature_list.json; "
            "format-dates remains not-started"
        ]
    else:
        outcome = "completed-verified"
        issues = []

    return {
        "disabled": disabled,
        "feature": feature,
        "convention": convention,
        "steps": steps,
        "artifact": {"written": written, "content": content},
        "outcome": outcome,
        "issues": issues,
    }


def ablation_table(workspace: Path) -> str:
    lines = ["disabled | outcome | issues"]
    for disabled in (None, *SUBSYSTEMS):
        report = run_loop(workspace, disabled)
        label = disabled if disabled else "(none)"
        lines.append(f"{label} | {report['outcome']} | {len(report['issues'])}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = argv[1:]
    disabled: str | None = None
    table = False
    positional = []
    for arg in args:
        if arg.startswith("--disable="):
            disabled = arg.split("=", 1)[1]
            if disabled not in SUBSYSTEMS:
                print(f"error: unknown subsystem {disabled!r}", file=sys.stderr)
                return 2
        elif arg == "--ablation-table":
            table = True
        else:
            positional.append(arg)
    if len(positional) != 1:
        print("usage: main.py <workspace-dir> [--disable=<subsystem> | --ablation-table]",
              file=sys.stderr)
        return 2
    workspace = Path(positional[0])
    if not workspace.is_dir():
        print(f"error: workspace not found: {workspace}", file=sys.stderr)
        return 2

    if table:
        print(ablation_table(workspace))
    else:
        print(json.dumps(run_loop(workspace, disabled), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
