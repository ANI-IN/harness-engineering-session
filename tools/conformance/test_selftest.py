"""Negative and positive proof that the conformance gate actually gates.

A gate that has never been seen to fail is not a gate. These tests run the
canary unit for real (both stacks, subprocesses), then break parity on
purpose and assert the runner fails naming the diverging field.
"""

import shutil
import subprocess
from pathlib import Path

from tools.conformance import runner
from tools.conformance.normalize import normalize

CANARY = Path(__file__).parent / "selftest" / "canary-unit"


def test_raw_outputs_differ_but_normalized_match():
    """The two tracks deliberately differ cosmetically; normalization must absorb it."""
    outputs = {}
    for stack, entry in (("python", "python/main.py"), ("typescript", "typescript/main.ts")):
        proc = subprocess.run(
            runner._entry_command(CANARY, entry) + ["fixtures/input.json"],
            cwd=CANARY,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, f"{stack}: {proc.stderr}"
        outputs[stack] = proc.stdout
    assert outputs["python"] != outputs["typescript"], (
        "canary tracks should differ in raw output (key order, indent, trailing spaces)"
    )
    assert normalize(outputs["python"]) == normalize(outputs["typescript"])


def test_canary_unit_passes_conformance():
    report = runner.run_unit(CANARY)
    assert report.ok, [r.detail for r in report.results if not r.ok]


def test_conformance_catches_parity_break(tmp_path):
    broken = tmp_path / "canary-unit"
    shutil.copytree(CANARY, broken)
    main_ts = broken / "typescript" / "main.ts"
    main_ts.write_text(
        main_ts.read_text(encoding="utf-8").replace(
            "sum: data.factors[0] + data.factors[1],",
            "sum: data.factors[0] + data.factors[1] + 1,",
        ),
        encoding="utf-8",
    )
    report = runner.run_unit(broken)
    assert not report.ok
    details = " ".join(r.detail for r in report.results if not r.ok)
    assert "$.sum" in details, f"failure must name the diverging field, got: {details}"


def test_fail_on_empty_floor(monkeypatch, capsys):
    monkeypatch.setattr(runner, "discover_units", lambda _root: [])
    monkeypatch.setattr(runner, "minimum_units", lambda: 1)
    monkeypatch.setattr("sys.argv", ["runner.py"])
    assert runner.main() == 1
    out = capsys.readouterr().out
    assert "requires at least 1" in out
