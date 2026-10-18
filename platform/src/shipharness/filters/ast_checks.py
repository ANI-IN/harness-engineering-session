"""Filter 4 (course filter): real assertions, and no mocking of the unit under test.

Static checks on the test's syntax tree; nothing is executed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

_RAISES = frozenset({"raises", "warns", "deprecated_call"})


@dataclass
class _ModuleNames:
    """How the test file refers to the target module and to objects defined in it."""

    target: str
    unit_names: frozenset[str] | None  # top-level names defined in the module; None = unknown
    module_aliases: set[str] = field(default_factory=set)  # names bound to the module itself
    object_aliases: dict[str, str] = field(default_factory=dict)  # local name -> unit name

    def is_unit_attr(self, attr: str) -> bool:
        return self.unit_names is None or attr in self.unit_names

    def describe_string_target(self, text: str) -> str | None:
        if text == self.target:
            return f"replaces the whole module {self.target}"
        prefix = self.target + "."
        if text.startswith(prefix):
            attr = text[len(prefix) :].split(".", 1)[0]
            if self.is_unit_attr(attr):
                return f"patches {text}"
        return None


def defined_names(module_source: str) -> frozenset[str] | None:
    """Top-level functions, classes, and assigned names of a module (imports excluded)."""
    try:
        tree = ast.parse(module_source)
    except SyntaxError:
        return None
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return frozenset(names)


def _collect_aliases(tree: ast.Module, names: _ModuleNames) -> None:
    target = names.target
    parent, _, leaf = target.rpartition(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == target:
                    names.module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                local = alias.asname or alias.name
                if node.module == parent and alias.name == leaf:
                    names.module_aliases.add(local)
                elif node.module == target and names.is_unit_attr(alias.name):
                    names.object_aliases[local] = alias.name


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else ""
    return ""


def _string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _mocking(node: ast.AST, names: _ModuleNames) -> str | None:
    """A description if `node` replaces the unit under test, else None."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Attribute) and (
                _dotted(target.value) in names.module_aliases and names.is_unit_attr(target.attr)
            ):
                return f"assigns {_dotted(target)}"
        return None
    if not isinstance(node, ast.Call):
        return None
    func = _dotted(node.func)
    last = func.rsplit(".", 1)[-1]
    first = node.args[0] if node.args else None
    second = _string(node.args[1]) if len(node.args) > 1 else None
    if last in ("patch", "setattr", "setitem", "delattr") or func.endswith("patch.object"):
        text = _string(first)
        if text is not None:
            found = names.describe_string_target(text)
            if found:
                return f"{last}('{text}'): {found}"
        if first is not None and (func.endswith(".object") or last in ("setattr", "delattr")):
            owner = _dotted(first)
            if owner in names.module_aliases and second and names.is_unit_attr(second):
                return f"{func}({owner}, '{second}') patches the unit under test"
            if owner in names.object_aliases:
                return f"{func}({owner}, ...) patches {names.object_aliases[owner]}"
    return None


def _is_tautology(test: ast.expr) -> bool:
    """Constant-only expressions, or a value compared with itself."""
    if not any(isinstance(n, ast.Name | ast.Attribute | ast.Call) for n in ast.walk(test)):
        return True
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
        return ast.dump(test.left) == ast.dump(test.comparators[0]) and isinstance(
            test.ops[0], ast.Eq | ast.Is | ast.GtE | ast.LtE
        )
    return False


def _direct_assertion(node: ast.AST) -> bool:
    if isinstance(node, ast.Assert):
        return not _is_tautology(node.test)
    if isinstance(node, ast.Call):
        func = _dotted(node.func)
        last = func.rsplit(".", 1)[-1]
        return last in _RAISES or last.startswith("assert") or last == "fail"
    return False


def _has_assertion(fn: ast.AST, helpers: dict[str, ast.AST]) -> bool:
    for node in ast.walk(fn):
        if _direct_assertion(node):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            helper = helpers.get(node.func.id)
            if helper is not None and any(_direct_assertion(n) for n in ast.walk(helper)):
                return True
    return False


def _find_test(tree: ast.Module, parts: list[str]) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    scope: list[ast.stmt] = tree.body
    for index, part in enumerate(parts):
        name = part.split("[", 1)[0]
        last = index == len(parts) - 1
        match = None
        for node in scope:
            if last and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name == name:
                    match = node
            elif not last and isinstance(node, ast.ClassDef) and node.name == name:
                match = node
        if match is None:
            return None
        if last:
            return match  # type: ignore[return-value]
        scope = match.body  # type: ignore[union-attr]
    return None


def _fixtures(tree: ast.Module, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Fixtures in the same file that the test requests by name, plus autouse fixtures."""
    wanted = {arg.arg for arg in fn.args.args}
    found: list[ast.AST] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or node is fn:
            continue
        for deco in node.decorator_list:
            text = ast.unparse(deco)
            if "fixture" in text and (node.name in wanted or "autouse=True" in text):
                found.append(node)
                break
    return found


def check_test(
    source: str, test_id: str, target_module: str | None, module_source: str | None
) -> tuple[bool, str]:
    """(passed, reason) for filter 4."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, f"test file does not parse: line {exc.lineno}: {exc.msg}"
    parts = test_id.split("::")[1:]
    fn = _find_test(tree, parts) if parts else None
    if fn is None:
        return False, f"test function {'::'.join(parts) or test_id} not found in the file"
    helpers = {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n is not fn
    }
    if not _has_assertion(fn, helpers):
        return False, (
            "no real assertion: the test never checks a result "
            "(asserting a constant or comparing a value with itself does not count)"
        )
    if target_module:
        names = _ModuleNames(
            target=target_module,
            unit_names=defined_names(module_source) if module_source is not None else None,
        )
        _collect_aliases(tree, names)
        for scope in [fn, *_fixtures(tree, fn)]:
            for node in ast.walk(scope):
                found = _mocking(node, names)
                if found:
                    return False, f"mocks the unit under test ({target_module}): {found}"
        return True, f"has real assertions and does not mock {target_module}"
    return True, "has real assertions (no target module given, mocking not checked)"
