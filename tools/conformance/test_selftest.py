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


def _run_raw(entry: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        runner._entry_command(CANARY, entry) + ["fixtures/input.json"] + (extra_args or []),
        cwd=CANARY,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_raw_outputs_differ_but_normalized_match():
    """The two tracks deliberately differ cosmetically; normalization must absorb it."""
    py = _run_raw("python/main.py")
    ts = _run_raw("typescript/main.ts")
    assert py.returncode == 0, py.stderr
    assert ts.returncode == 0, ts.stderr
    assert py.stdout != ts.stdout, (
        "canary tracks should differ in raw output (key order, indent, trailing spaces)"
    )
    assert normalize(py.stdout) == normalize(ts.stdout)


def test_divergence_classes_are_all_present():
    """Each divergence class the canary claims to cover is actually exercised."""
    py = _run_raw("python/main.py")
    ts = _run_raw("typescript/main.ts")

    # Non-ASCII: Python ASCII-escapes, TypeScript emits literal UTF-8.
    assert "\\u" in py.stdout and "café" not in py.stdout
    assert "café" in ts.stdout and "☕" in ts.stdout and "🚀" in ts.stdout
    normalized = normalize(py.stdout)
    assert "café" in normalized and "🚀" in normalized

    # Trailing whitespace: TypeScript only.
    assert any(line.endswith("  ") for line in ts.stdout.split("\n"))
    assert not any(line.endswith(" ") for line in py.stdout.split("\n"))

    # Empty list, empty object, null, and >2-level nesting survive round-trip.
    import json as jsonlib

    payload = jsonlib.loads(normalized)
    assert payload["tags"] == [] and payload["meta"] == {} and payload["parent"] is None
    assert payload["notes"]["words"]["longest"]["length"] == 11  # code points, not UTF-16

    # Multi-line stderr, deliberately different across tracks, never compared.
    assert py.stderr.count("\n") >= 2 and ts.stderr.count("\n") >= 3
    assert py.stderr != ts.stderr


def test_crlf_fixture_still_has_crlf_bytes():
    """Guard against tooling silently converting the CRLF fixture to LF."""
    raw = (CANARY / "fixtures" / "notes.txt").read_bytes()
    assert b"\r\n" in raw, "fixtures/notes.txt lost its CRLF endings (check .gitattributes)"


def test_written_artifact_in_subdirectory_matches(tmp_path):
    """Non-ASCII through a written file, under a nested output directory."""
    outputs = {}
    for entry in ("python/main.py", "typescript/main.ts"):
        workdir = tmp_path / entry.split("/")[0]
        workdir.mkdir()
        shutil.copytree(CANARY / "fixtures", workdir / "fixtures")
        proc = subprocess.run(
            runner._entry_command(CANARY, entry)
            + ["fixtures/input.json", "--out", "out/nested/report.json"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        outputs[entry] = (workdir / "out" / "nested" / "report.json").read_text(encoding="utf-8")
    assert outputs["python/main.py"] != outputs["typescript/main.ts"]
    assert normalize(outputs["python/main.py"]) == normalize(outputs["typescript/main.ts"])


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
