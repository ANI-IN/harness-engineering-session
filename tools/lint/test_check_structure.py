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


def _declare_non_code_starter(unit):
    (unit / "SPEC.md").write_text(
        f"# spec\n\n{check_structure.NON_CODE_STARTER_MARKER} (the starter is a task prompt)\n",
        encoding="utf-8",
    )


def test_declared_non_code_starter_unit_passes(tmp_path):
    unit = _tree(
        tmp_path,
        "projects/project-01-x",
        files=("SPEC.md", "cases.json"),
        dirs=("fixtures", "expected", "starter", "solution/python", "solution/typescript"),
    )
    _declare_non_code_starter(unit)
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert errors == []


def test_non_code_starter_shape_requires_the_marker(tmp_path):
    # Same directories, no marker in SPEC.md: the shape must never be
    # inferred from the absence of starter code.
    _tree(
        tmp_path,
        "projects/project-01-x",
        files=("SPEC.md", "cases.json"),
        dirs=("fixtures", "expected", "starter", "solution/python", "solution/typescript"),
    )
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert len(errors) == 1
    assert "starter without both stacks is only valid" in errors[0]
    assert "starter/python, starter/typescript" in errors[0]


def test_project_missing_one_starter_track_detected(tmp_path):
    # A project-02-shaped unit (real dual-track starter intended) with the
    # typescript starter missing must be rejected, marker or not.
    _tree(
        tmp_path,
        "projects/project-02-x",
        files=("SPEC.md", "cases.json"),
        dirs=(
            "fixtures", "expected",
            "starter/python", "solution/python", "solution/typescript",
        ),
    )
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert len(errors) == 1
    assert "missing starter/typescript" in errors[0]


def test_marker_with_starter_code_is_a_contradiction(tmp_path):
    unit = _tree(
        tmp_path,
        "projects/project-02-x",
        files=("SPEC.md", "cases.json"),
        dirs=(
            "fixtures", "expected",
            "starter/python", "solution/python", "solution/typescript",
        ),
    )
    _declare_non_code_starter(unit)
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert any("remove the marker or the code" in error for error in errors)


def test_solution_staged_unit_missing_a_stack_detected(tmp_path):
    unit = _tree(
        tmp_path,
        "projects/project-01-x",
        files=("SPEC.md", "cases.json"),
        dirs=("fixtures", "expected", "starter", "solution/python"),
    )
    _declare_non_code_starter(unit)
    errors: list[str] = []
    check_structure.check_units(errors, tmp_path)
    assert any("missing" in error and "solution/typescript" in error for error in errors)


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


def test_formatting_only_divergence_rejected(tmp_path):
    # The exact signature lecture 05's first exercise shipped with: a markdown
    # bullet prefix. Identical content on both sides, so the learner would be
    # trimming a string, not learning round-trips.
    exercise = _exercise_with_divergence(
        tmp_path,
        "diverges at $.sections[0].items[0]: "
        "'- `./verify.sh import-notes`: exit 0' != '`./verify.sh import-notes`: exit 0'\n",
    )
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert len(errors) == 1
    assert "formatting-only" in errors[0]


def test_formatting_only_whitespace_divergence_rejected(tmp_path):
    exercise = _exercise_with_divergence(tmp_path, "diverges at $.name: 'a  b' != 'a b'\n")
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert len(errors) == 1
    assert "formatting-only" in errors[0]


def test_formatting_only_with_justification_accepted(tmp_path):
    exercise = _exercise_with_divergence(
        tmp_path,
        "diverges at $.rendered: '-item' != '- item'\n",
        "# spec\n\nStarter-divergence justification: this exercise IS about the marker syntax.\n",
    )
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert errors == []


def test_content_string_divergence_still_passes(tmp_path):
    exercise = _exercise_with_divergence(
        tmp_path,
        "diverges at $.checks[0].detail: 'pyproject.toml' != 'pyproject.toml + .python-version'\n",
    )
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert errors == []


def test_numeric_sign_flip_not_treated_as_formatting(tmp_path):
    # -2 != 2 have equal alphanumeric skeletons, but numbers are unquoted in
    # signatures and a sign flip is content; the rule must not touch it.
    exercise = _exercise_with_divergence(tmp_path, "diverges at $.savings.drift_events: -2 != 2\n")
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert errors == []


def test_length_diff_with_justification_accepted(tmp_path):
    exercise = _exercise_with_divergence(
        tmp_path,
        "diverges at $.items: length 2 != 3 (missing element: 'x')\n",
        "# spec\n\nStarter-divergence justification: the missing row IS the lesson here.\n",
    )
    errors: list[str] = []
    check_structure.check_starter_divergence(exercise, "x", errors)
    assert errors == []


def _project_fixture(tmp_path, project: str, rel: str, content: str, spec: str = "# spec\n"):
    unit = tmp_path / "projects" / project
    path = unit / "fixtures" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    (unit / "SPEC.md").write_text(spec, encoding="utf-8")
    return unit


def test_identical_corpus_copies_pass(tmp_path):
    _project_fixture(tmp_path, "project-01-a", "docs/corpus.md", "same\n")
    _project_fixture(tmp_path, "project-02-b", "docs/corpus.md", "same\n")
    errors: list[str] = []
    check_structure.check_corpus_copies(errors, tmp_path)
    assert errors == []


def test_silently_diverged_corpus_copy_detected(tmp_path):
    _project_fixture(tmp_path, "project-01-a", "docs/corpus.md", "same\n")
    _project_fixture(tmp_path, "project-02-b", "docs/corpus.md", "shifted\n")
    errors: list[str] = []
    check_structure.check_corpus_copies(errors, tmp_path)
    assert len(errors) == 1
    assert "diverges from" in errors[0]
    assert "Corpus-divergence: docs/corpus.md" in errors[0]


def test_declared_corpus_divergence_accepted(tmp_path):
    _project_fixture(tmp_path, "project-01-a", "docs/corpus.md", "same\n")
    _project_fixture(
        tmp_path, "project-02-b", "docs/corpus.md", "diverged on purpose\n",
        spec="# spec\n\nCorpus-divergence: docs/corpus.md (this project mutates it)\n",
    )
    errors: list[str] = []
    check_structure.check_corpus_copies(errors, tmp_path)
    assert errors == []


def test_single_project_fixture_is_not_grouped(tmp_path):
    _project_fixture(tmp_path, "project-01-a", "docs/only-here.md", "unique\n")
    errors: list[str] = []
    check_structure.check_corpus_copies(errors, tmp_path)
    assert errors == []


def _git_repo(root: Path, ignore: str) -> None:
    """Minimal git work tree with the given .gitignore body."""
    import subprocess

    (root / ".gitignore").write_text(ignore, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, timeout=60)


def test_ignored_fixture_detected(tmp_path):
    """The failure that shipped twice: a broad rule swallows committed content."""
    _git_repo(tmp_path, "*.log\n")
    base = _tree(tmp_path, "lectures/lecture-01-x/code/fixtures/workspace/logs")
    (base / "run.log").write_text("recorded run\n", encoding="utf-8")
    errors: list[str] = []
    check_structure.check_ignored_content(errors, tmp_path)
    assert any("grading authority" in error and "run.log" in error for error in errors)


def test_ignored_expected_output_detected(tmp_path):
    _git_repo(tmp_path, "*.log\n")
    base = _tree(tmp_path, "lectures/lecture-01-x/code/expected")
    (base / "session.log").write_text("pinned output\n", encoding="utf-8")
    errors: list[str] = []
    check_structure.check_ignored_content(errors, tmp_path)
    assert any("session.log" in error for error in errors)


def test_ignored_build_artifact_outside_fixtures_allowed(tmp_path):
    """__pycache__ under an implementation tree is a legitimate ignore."""
    _git_repo(tmp_path, "__pycache__/\n")
    base = _tree(tmp_path, "lectures/lecture-01-x/code/python/__pycache__")
    (base / "main.cpython-312.pyc").write_text("bytecode\n", encoding="utf-8")
    errors: list[str] = []
    check_structure.check_ignored_content(errors, tmp_path)
    assert errors == []


def test_committed_fixture_not_reported(tmp_path):
    _git_repo(tmp_path, "*.log\n!lectures/**/fixtures/**\n")
    base = _tree(tmp_path, "lectures/lecture-01-x/code/fixtures/workspace/logs")
    (base / "run.log").write_text("recorded run\n", encoding="utf-8")
    errors: list[str] = []
    check_structure.check_ignored_content(errors, tmp_path)
    assert errors == []


def test_outside_a_git_work_tree_is_a_no_op(tmp_path):
    _tree(tmp_path, "lectures/lecture-01-x/code/fixtures")
    errors: list[str] = []
    check_structure.check_ignored_content(errors, tmp_path)
    assert errors == []
