"""Negative and positive proof for the generated-block machinery."""

from tools import gen_readme_blocks


def _doc(content: str) -> str:
    return (
        "# Doc\n\n"
        "<!-- generated-block: printf 'alpha\\nbeta\\n' -->\n"
        "```text\n"
        f"{content}"
        "```\n"
        "<!-- /generated-block -->\n"
    )


def test_matching_block_passes(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(_doc("alpha\nbeta\n"), encoding="utf-8")
    assert gen_readme_blocks.process_file(path, write=False) == []


def test_drifted_block_fails_naming_divergence(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(_doc("alpha\nSTALE\n"), encoding="utf-8")
    errors = gen_readme_blocks.process_file(path, write=False)
    assert len(errors) == 1
    assert "drifted" in errors[0]
    assert "line 2" in errors[0]


def test_write_mode_regenerates(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(_doc("alpha\nSTALE\n"), encoding="utf-8")
    assert gen_readme_blocks.process_file(path, write=True) == []
    assert "alpha\nbeta\n" in path.read_text(encoding="utf-8")
    assert gen_readme_blocks.process_file(path, write=False) == []


def test_failing_command_reported(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        "<!-- generated-block: exit 3 -->\n```text\nx\n```\n<!-- /generated-block -->\n",
        encoding="utf-8",
    )
    errors = gen_readme_blocks.process_file(path, write=False)
    assert len(errors) == 1
    assert "exit 3" in errors[0]
