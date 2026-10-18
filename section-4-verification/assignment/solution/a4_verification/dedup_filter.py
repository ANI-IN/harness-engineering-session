"""Filter 6: discard a proposed test that duplicates an existing test or an earlier kept candidate.

TestGen-LLM added a filter that removes previously seen test cases (B11 F-b-26). This filter
follows the shipharness Filter protocol (`shipharness.filters.models.Filter`): a `number`, a
`name`, and `evaluate(cand, ctx) -> FilterResult`, so `run_pipeline(..., filters=[...])` can run it.

Two tests are duplicates when their decorators, parameter lists, and bodies are equal as syntax
trees after this normalisation:

1. the function name, comments, blank lines, and formatting are ignored;
2. a docstring (a string literal as the first statement) is dropped;
3. every local variable (a name the test binds in its body: `=`, `+=`, annotated assignment, `for`,
   `with ... as`, `:=`, comprehension targets, `except ... as`) is renamed to a placeholder in
   order of first appearance in the source.

Parameters (pytest fixtures), global names, imported names, attribute names, and literal values
are never renamed.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable

from shipharness.filters.models import CandidateTest, FilterContext, FilterResult

_Function = ast.FunctionDef | ast.AsyncFunctionDef


def _find(tree: ast.Module, test_id: str) -> _Function | None:
    """The function a test id names: "file::name" or "file::Class::name" (last definition wins,
    as in Python)."""
    parts = test_id.split("::")[1:]
    if not parts:
        return None
    nodes: list[ast.stmt] = tree.body
    for index, name in enumerate(parts):
        last = index == len(parts) - 1
        match: ast.stmt | None = None
        for node in nodes:
            if getattr(node, "name", None) != name:
                continue
            if (last and isinstance(node, _Function)) or (
                not last and isinstance(node, ast.ClassDef)
            ):
                match = node
        if match is None:
            return None
        if last:
            return match  # type: ignore[return-value]
        nodes = match.body  # type: ignore[attr-defined]
    return None


def _parameters(func: _Function) -> set[str]:
    args = func.args
    every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    every += [a for a in (args.vararg, args.kwarg) if a is not None]
    return {a.arg for a in every}


def _local_order(body: list[ast.stmt], parameters: set[str]) -> list[str]:
    """Names bound in the body (minus parameters), in order of first appearance in the source."""
    bound: set[str] = set()
    seen: list[tuple[int, int, str]] = []
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name):
                seen.append((node.lineno, node.col_offset, node.id))
                if isinstance(node.ctx, ast.Store):
                    bound.add(node.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                seen.append((node.lineno, node.col_offset, node.name))
                bound.add(node.name)
    bound -= parameters
    order: list[str] = []
    for _line, _col, name in sorted(seen):
        if name in bound and name not in order:
            order.append(name)
    return order


class _Rename(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self.mapping.get(node.id, node.id)
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        if node.name:
            node.name = self.mapping.get(node.name, node.name)
        self.generic_visit(node)
        return node


def normalized(source: str, test_id: str) -> str | None:
    """A comparable text form of one test function, or None if the source does not parse or has
    no function with that test id ("file::name" or "file::Class::name")."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    func = _find(tree, test_id)
    if func is None:
        return None
    body = list(func.body)
    first = body[0] if body else None
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        body = body[1:]
    order = _local_order(body, _parameters(func))
    renamer = _Rename({name: f"_v{index}" for index, name in enumerate(order)})
    body = [renamer.visit(stmt) for stmt in body]
    parts = [type(func).__name__]
    parts += [ast.dump(d, include_attributes=False) for d in func.decorator_list]
    parts.append(ast.dump(func.args, include_attributes=False))
    parts += [ast.dump(stmt, include_attributes=False) for stmt in body]
    return "\n".join(parts)


class NoDuplicateTest:
    number = 6
    name = "not a duplicate of an existing or earlier test"

    def __init__(self, existing: Iterable[CandidateTest] = ()) -> None:
        """`existing`: the existing suite's tests, captured at the start of the test phase
        (for example with `shipharness.filters.collect_candidates(workspace, files)`)."""
        self.existing = list(existing)
        self._known: dict[str, list[str]] = {}
        for test in self.existing:
            key = normalized(test.source, test.test_id)
            if key is not None:
                self._known.setdefault(key, []).append(test.test_id)
        self._kept: dict[str, str] = {}  # normalised form -> first kept candidate id

    def _result(self, cand: CandidateTest, passed: bool, reason: str) -> FilterResult:
        return FilterResult(test_id=cand.test_id, filter=self.number, passed=passed, reason=reason)

    def evaluate(self, cand: CandidateTest, ctx: FilterContext) -> FilterResult:
        key = normalized(cand.source, cand.test_id)
        if key is None:
            return self._result(
                cand,
                False,
                "cannot check for duplicates: the file does not parse or has no such test function",
            )
        same = [tid for tid in self._known.get(key, []) if tid != cand.test_id]
        if same:
            return self._result(
                cand,
                False,
                f"duplicate of existing test {same[0]} (equal after ignoring names, docstring, "
                "comments, and layout)",
            )
        earlier = self._kept.get(key)
        if earlier is not None and earlier != cand.test_id:
            return self._result(cand, False, f"duplicate of earlier candidate {earlier}")
        kept_before = len(self._kept)
        self._kept.setdefault(key, cand.test_id)
        return self._result(
            cand,
            True,
            f"no duplicate among {len(self.existing)} existing tests and {kept_before} earlier "
            "kept candidates",
        )
