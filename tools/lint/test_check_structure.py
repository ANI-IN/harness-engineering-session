"""Negative proof for the structure checker: incomplete units must be found."""

from pathlib import Path

from tools.lint import check_structure


def _tree(root: Path, rel: str, files: tuple[str, ...] = (), dirs: tuple[str, ...] = ()) -> Path:
    base = root / rel
    base.mkdir(parents=True, exist_ok=True)
    for directory in dirs:
        (base / directory).mkdir(parents=True, exist_ok=True)
        (base / directory / ".keep").write_text("", encoding="utf-8")
    for name in files:
        (base / name).write_text("placeholder content for structure tests\n", encoding="utf-8")
    return base


def test_unit_missing_spec_detected(tmp_path):
    _tree(tmp_path, "lectures/lecture-01-x/code", files=("cases.json",))
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert any("cases.json without SPEC.md" in error for error in errors)


def test_fixture_pair_without_spec_detected(tmp_path):
    _tree(tmp_path, "lectures/lecture-01-x/code", dirs=("fixtures", "expected"))
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert any("fixtures/+expected/ without SPEC.md" in error for error in errors)


def test_unit_missing_typescript_detected(tmp_path):
    _tree(
        tmp_path,
        "lectures/lecture-01-x/code",
        files=("SPEC.md", "cases.json"),
        dirs=("fixtures", "expected", "python"),
    )
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert any("missing typescript" in error for error in errors)


def test_complete_unit_passes(tmp_path):
    _tree(
        tmp_path,
        "lectures/lecture-01-x/code",
        files=("SPEC.md", "cases.json"),
        dirs=("fixtures", "expected", "python", "typescript"),
    )
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert errors == []


def test_readme_sections_out_of_order_detected(tmp_path):
    lecture = _tree(tmp_path, "lectures/lecture-01-x")
    sections = [
        "Learning objectives", "Prerequisites", "The problem", "Concepts",
        "Architecture", "Demo", "Implementation notes", "Key takeaways",
        "Exercises", "Further exploration",
    ]
    swapped = sections.copy()
    swapped[4], swapped[5] = swapped[5], swapped[4]  # Demo before Architecture
    body = "# Lecture 01\n\n" + "\n\n".join(f"## {s}\n\ntext" for s in swapped) + "\n"
    (lecture / "README.md").write_text(body, encoding="utf-8")
    errors: list[str] = []
    check_structure.check_section_orders(errors, tmp_path)
    assert any("out of required order" in error for error in errors)


def test_readme_missing_section_detected(tmp_path):
    lecture = _tree(tmp_path, "lectures/lecture-01-x")
    (lecture / "README.md").write_text("# Lecture 01\n\n## Demo\n\ntext\n", encoding="utf-8")
    errors: list[str] = []
    check_structure.check_section_orders(errors, tmp_path)
    assert any("missing section '## Learning objectives'" in error for error in errors)


def test_floor_violation_detected(tmp_path):
    errors: list[str] = []
    check_structure.check_floors(errors, tmp_path, {"min_lectures": 1})
    assert any("fail-on-empty" in error for error in errors)


def _exercise_with_divergence(tmp_path, signature: str, spec: str = "# spec\n"):
    exercise = tmp_path / "lectures" / "lecture-01-x" / "exercises" / "exercise-01-y"
    (exercise / "expected").mkdir(parents=True)
    (exercise / "expected" / "starter-divergence.txt").write_text(signature, encoding="utf-8")
    (exercise / "SPEC.md").write_text(spec, encoding="utf-8")
    return exercise


def test_value_mismatch_divergence_passes(tmp_path):
    exercise = _exercise_with_divergence(tmp_path, "diverges at $.rate: 0.25 != 0.875\n")
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert errors == []


def test_null_vs_value_divergence_rejected(tmp_path):
    exercise = _exercise_with_divergence(tmp_path, "diverges at $.answer: None != 'real'\n")
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert len(errors) == 1
    assert "null-vs-value" in errors[0]


def test_length_diff_without_justification_rejected(tmp_path):
    exercise = _exercise_with_divergence(tmp_path, "diverges at $.items: length 0 != 3\n")
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert len(errors) == 1
    assert "no \njustification" in errors[0] or "no justification" in errors[0].replace("\n", " ")


def test_length_diff_with_justification_accepted(tmp_path):
    exercise = _exercise_with_divergence(
        tmp_path,
        "diverges at $.items: length 2 != 3 (missing element: 'x')\n",
        "# spec\n\nStarter-divergence justification: the missing row IS the lesson here.\n",
    )
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert errors == []
