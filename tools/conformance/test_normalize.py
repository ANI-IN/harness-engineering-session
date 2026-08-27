"""Tests for the normalization pass that defines cross-stack byte-identity."""

import json

import pytest

from tools.conformance.normalize import (
    looks_like_json,
    normalize,
    normalize_json,
    normalize_lines,
    normalize_paths_in_text,
)


class TestNormalizeLines:
    def test_crlf_and_cr_become_lf(self):
        assert normalize_lines("a\r\nb\rc\n") == "a\nb\nc\n"

    def test_trailing_whitespace_stripped(self):
        assert normalize_lines("a  \nb\t\n") == "a\nb\n"

    def test_exactly_one_final_newline(self):
        assert normalize_lines("a\n\n\n") == "a\n"
        assert normalize_lines("a") == "a\n"

    def test_empty_stays_empty(self):
        assert normalize_lines("") == ""
        assert normalize_lines("\n\n") == ""


class TestNormalizeJson:
    def test_keys_sorted_recursively(self):
        out = normalize_json('{"b": 1, "a": {"d": 2, "c": 3}}')
        assert out == '{\n  "a": {\n    "c": 3,\n    "d": 2\n  },\n  "b": 1\n}\n'

    def test_float_formatting_is_stack_neutral(self):
        # 0.1 + 0.2 prints as 0.30000000000000004 in both languages' shortest
        # repr; canonical serialization keeps them identical.
        assert normalize_json("[0.30000000000000004]") == "[\n  0.30000000000000004\n]\n"
        assert normalize_json("[1.0]") == "[\n  1.0\n]\n"

    def test_path_separators_inside_strings(self):
        out = normalize_json(json.dumps({"p": "a\\b\\c.txt"}))
        assert json.loads(out) == {"p": "a/b/c.txt"}

    def test_unicode_preserved(self):
        assert '"héllo"' in normalize_json('{"x": "héllo"}')


class TestNormalizeDispatch:
    def test_auto_detects_json(self):
        assert normalize('{"b":1,"a":2}') == '{\n  "a": 2,\n  "b": 1\n}\n'

    def test_auto_falls_back_to_text_for_invalid_json(self):
        assert normalize("{not json") == "{not json\n"

    def test_text_kind_skips_json_canonicalization(self):
        assert normalize('{"b":1,"a":2}', kind="text") == '{"b":1,"a":2}\n'

    def test_json_kind_raises_on_invalid(self):
        with pytest.raises(json.JSONDecodeError):
            normalize("nope", kind="json")

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError):
            normalize("x", kind="yaml")

    def test_posix_separators_in_text(self):
        assert normalize_paths_in_text("dir\\file.txt") == "dir/file.txt"

    def test_looks_like_json(self):
        assert looks_like_json(' {"a": 1} ')
        assert looks_like_json("[1, 2]")
        assert not looks_like_json("plain text")


class TestRunnerDiscovery:
    def test_discovery_requires_spec_and_cases(self, tmp_path, monkeypatch):
        from tools.conformance import runner

        (tmp_path / "lectures" / "u1").mkdir(parents=True)
        (tmp_path / "lectures" / "u1" / "SPEC.md").write_text("# spec")
        (tmp_path / "lectures" / "u2").mkdir(parents=True)
        (tmp_path / "lectures" / "u2" / "SPEC.md").write_text("# spec")
        (tmp_path / "lectures" / "u2" / "cases.json").write_text("{}")

        units = runner.discover_units(tmp_path)
        assert [u.name for u in units] == ["u2"]
