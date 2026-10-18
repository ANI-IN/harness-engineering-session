"""Test-phase hook of the verify layer: every test the agent proposed in the test phase goes through
the five filters (owned by the filters package); discarded tests are removed from
the workspace with their reason, kept tests are committed. Proposed tests are the new or changed
test functions under the run's visible-test directory (TeamTrack: tests/visible).

Workspace files are read and written on the host without following links (untrusted workspace).
"""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from shipharness.runner.models import TEAMTRACK_VISIBLE_TESTS
from shipharness.runner.paths import resolve_in_workspace
from shipharness.runner.tools import iter_workspace_files

TEST_ROOT = f"{TEAMTRACK_VISIBLE_TESTS}/"
Pipeline = Callable[[list[dict[str, str]], Any, dict[str, str]], list[Any]]


class PipelineUnavailable(RuntimeError):
    """The filter pipeline cannot run (package or helper missing)."""


def visible_prefix(visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS) -> str:
    """The path prefix of visible test files ("" when the directory is the repository root)."""
    return "" if visible_tests_dir == "." else f"{visible_tests_dir}/"


def snapshot(
    workspace: Path, visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS
) -> tuple[dict[str, str], dict[str, str]]:
    """(sha256 of every workspace file, text of every visible test file)."""
    shas: dict[str, str] = {}
    texts: dict[str, str] = {}
    root = Path(workspace)
    prefix = visible_prefix(visible_tests_dir)
    for path in iter_workspace_files(root):
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        shas[rel] = hashlib.sha256(data).hexdigest()
        if rel.startswith(prefix) and rel.endswith(".py"):
            texts[rel] = data.decode("utf-8", errors="replace")
    return shas, texts


def _test_nodes(tree: ast.Module) -> list[tuple[str, ast.AST]]:
    nodes: list[tuple[str, ast.AST]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            nodes.append((node.name, node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and (
                    item.name.startswith("test")
                ):
                    nodes.append((f"{node.name}::{item.name}", item))
    return nodes


def _span(node: ast.AST) -> tuple[int, int]:
    decorators = getattr(node, "decorator_list", [])
    start = min([node.lineno, *(d.lineno for d in decorators)])  # type: ignore[attr-defined]
    return start, node.end_lineno or node.lineno  # type: ignore[attr-defined]


def _sources(text: str) -> dict[str, str]:
    lines = text.splitlines()
    out = {}
    for name, node in _test_nodes(ast.parse(text)):
        start, end = _span(node)
        out[name] = "\n".join(lines[start - 1 : end])
    return out


def find_candidates(
    workspace: Path, start_texts: dict[str, str], visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """(candidates {test_id, file, source}, unparseable test files -> reason). A candidate is a
    test function that is new or changed since the start of the test phase."""
    _shas, now_texts = snapshot(workspace, visible_tests_dir)
    candidates: list[dict[str, str]] = []
    broken: dict[str, str] = {}
    for rel, text in sorted(now_texts.items()):
        if not Path(rel).name.startswith("test") or start_texts.get(rel) == text:
            continue
        try:
            current = _sources(text)
        except SyntaxError as exc:
            broken[rel] = f"does not parse: {exc.msg} (line {exc.lineno})"
            continue
        try:
            before = _sources(start_texts.get(rel, ""))
        except SyntaxError:
            before = {}
        for name, source in current.items():
            if before.get(name) != source:
                candidates.append({"test_id": f"{rel}::{name}", "file": rel, "source": source})
    return candidates, broken


def remove_tests(
    workspace: Path, by_file: dict[str, list[str]], visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS
) -> list[str]:
    """Remove the named tests (`name` or `Class::name`) from each file; delete a file left with no
    tests. Returns the files changed."""
    changed = []
    prefix = visible_prefix(visible_tests_dir)
    for rel, names in by_file.items():
        path = resolve_in_workspace(workspace, rel)
        if not rel.startswith(prefix) or path.is_symlink() or not path.is_file():
            raise ValueError(f"not a visible test file in the workspace: {rel!r}")
        text = path.read_bytes().decode("utf-8", errors="replace")
        tree = ast.parse(text)
        nodes = dict(_test_nodes(tree))
        lines = text.splitlines(keepends=True)
        remove = {n for n in names if n in nodes}
        edits: list[tuple[int, int, str]] = []  # (first line, last line, replacement)
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef) or not cls.body:
                continue
            members = [f"{cls.name}::{getattr(item, 'name', '')}" for item in cls.body]
            if all(m in remove for m in members):
                # Removing every statement would leave `class TestX:` with no body.
                first = cls.body[0]
                indent = lines[first.lineno - 1][: first.col_offset]
                edits.append((_span(first)[0], _span(cls.body[-1])[1], f"{indent}pass\n"))
                remove -= set(members)
        edits += [(*_span(nodes[n]), "") for n in remove]
        for start, end, replacement in sorted(edits, reverse=True):
            lines[start - 1 : end] = [replacement] if replacement else []
        remaining = "".join(lines)
        if not _test_nodes(ast.parse(remaining)):
            path.unlink()
        else:
            path.write_text(remaining, encoding="utf-8", newline="")
        changed.append(rel)
    return changed


def delete_files(
    workspace: Path, rels: list[str], visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS
) -> None:
    prefix = visible_prefix(visible_tests_dir)
    for rel in rels:
        path = resolve_in_workspace(workspace, rel)
        if rel.startswith(prefix) and path.is_file() and not path.is_symlink():
            path.unlink()


def filters_pipeline(
    candidates: list[dict[str, str]], ctx: Any, source_shas: dict[str, str]
) -> list[Any]:
    """Default pipeline: the filters package.

    `source_shas` is the phase-start snapshot of every workspace file. The filter context is built
    now, with baseline coverage measured by running only the tests that existed at phase start
    (filter 5 guarantees the source is unchanged, so this equals the phase-start baseline), and
    with phase-start fingerprints restricted to source files, the format filter 5 compares.
    """
    try:
        from shipharness.filters import CandidateTest, build_context
        from shipharness.filters.pipeline import run_pipeline_parallel
        from shipharness.filters.source import is_source_path, is_test_path
    except ImportError as exc:
        raise PipelineUnavailable(f"shipharness.filters is not available ({exc})") from None
    prefix = visible_prefix(
        getattr(getattr(ctx, "spec", None), "visible_tests_dir", TEAMTRACK_VISIBLE_TESTS)
    )
    existing = sorted(
        rel
        for rel in source_shas
        if rel.startswith(prefix)
        and rel.endswith(".py")
        and is_test_path(rel)
        and pathlib_name(rel).startswith("test_")
    )
    fctx = build_context(ctx.workspace, ctx.sandbox, existing_tests=existing or None)
    fctx = fctx.model_copy(
        update={
            "source_shas_at_phase_start": {
                rel: sha for rel, sha in source_shas.items() if is_source_path(rel)
            }
        }
    )
    cands = [CandidateTest(**c) for c in candidates]
    spec = getattr(ctx, "spec", None)
    return list(
        run_pipeline_parallel(
            cands,
            fctx,
            ctx.bus,
            run_id=getattr(spec, "run_id", None),
            arm=getattr(spec, "arm", None),
            phase="test",
            workers=filter_workers(ctx.sandbox),
        )
    )


def filter_workers(sandbox: Any) -> int:
    """Proposed tests filtered at the same time: one per CPU of the sandbox (its policy's
    `cpus`, rounded down), at least one. A sandbox without a policy filters one at a time."""
    cpus = getattr(getattr(sandbox, "policy", None), "cpus", 1)
    try:
        return max(1, int(cpus))
    except (TypeError, ValueError):
        return 1


def pathlib_name(rel: str) -> str:
    return rel.rsplit("/", 1)[-1]


def _field(result: Any, name: str) -> Any:
    return result.get(name) if isinstance(result, dict) else getattr(result, name)


def discarded_reasons(results: list[Any]) -> dict[str, str]:
    """test_id -> reason of the first failing filter."""
    out: dict[str, str] = {}
    for r in sorted(results, key=lambda r: int(_field(r, "filter"))):
        if not _field(r, "passed"):
            out.setdefault(str(_field(r, "test_id")), str(_field(r, "reason")))
    return out
