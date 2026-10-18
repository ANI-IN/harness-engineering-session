"""Deterministic request data for probes, built from the app's OpenAPI schema.

Probes need requests the app accepts (a 422 would hide the behaviour under test), so bodies and
required query parameters are generated from the operation's schema: required fields always,
optional simple fields too (so a PATCH changes something), ids from the adapter by name, and a
counter that keeps unique fields unique across calls.
"""

from __future__ import annotations

import re
from typing import Any

from shipharness.checks.discovery import Endpoint

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _letters(n: int) -> str:
    out = ""
    for _ in range(3):
        n, rest = divmod(n, 26)
        out = _ALPHABET[rest] + out
    return "P" + out


def _resource_param(segments: list[str], index: int, ids: dict[str, int]) -> int | None:
    for previous in reversed(segments[:index]):
        if previous.startswith("{"):
            continue
        singular = previous[:-1] if previous.endswith("s") else previous
        return ids.get(f"{singular}_id")
    return None


def fill_path(path: str, ids: dict[str, int]) -> str:
    """Substitute `{name}` path parameters from `ids`.

    Unknown names (`{id}`, `{widget_id}`) take the id of the resource named by the closest literal
    segment before them (`/issues/{id}` uses `issue_id`), else the first id given.
    """
    fallback = next(iter(ids.values()), 0)
    segments = path.split("/")
    for index, segment in enumerate(segments):
        if not (segment.startswith("{") and segment.endswith("}")):
            continue
        name = segment[1:-1]
        value = ids.get(name)
        if value is None:
            value = _resource_param(segments, index, ids)
        segments[index] = str(fallback if value is None else value)
    return "/".join(segments)


class Payloads:
    """Request bodies and query strings for the operations of one OpenAPI document."""

    def __init__(self, openapi: dict[str, Any]) -> None:
        self.openapi = openapi
        self._counter = 0

    def _operation(self, endpoint: Endpoint) -> dict[str, Any]:
        item = self.openapi.get("paths", {}).get(endpoint.path, {})
        op: dict[str, Any] = item.get(endpoint.method.lower(), {})
        return op

    def resolve(self, schema: dict[str, Any]) -> dict[str, Any]:
        seen = 0
        while "$ref" in schema and seen < 20:
            node: Any = self.openapi
            for part in schema["$ref"].lstrip("#/").split("/"):
                node = node.get(part, {})
            schema = node
            seen += 1
        return schema

    def body(
        self, endpoint: Endpoint, ids: dict[str, int], overrides: dict[str, Any] | None = None
    ) -> Any | None:
        """A JSON body the operation accepts, or None if it takes no JSON body.

        `overrides` (from the adapter, by endpoint label) replace generated fields where the schema
        cannot express a business rule, such as an allowed status transition.
        """
        content = self._operation(endpoint).get("requestBody", {}).get("content", {})
        schema = content.get("application/json", {}).get("schema")
        if schema is None:
            return None
        self._counter += 1
        value = self._value(schema, "", ids, required=True)
        extra = (overrides or {}).get(endpoint.label)
        if isinstance(value, dict) and extra:
            value = {**value, **extra}
        return value

    def query(self, endpoint: Endpoint, ids: dict[str, int]) -> dict[str, Any]:
        """Values for required query parameters only."""
        params: dict[str, Any] = {}
        for param in self._operation(endpoint).get("parameters", []):
            if param.get("in") == "query" and param.get("required"):
                params[param["name"]] = self._value(
                    param.get("schema", {}), param["name"], ids, required=True
                )
        return params

    def _value(self, schema: dict[str, Any], name: str, ids: dict[str, int], required: bool) -> Any:
        schema = self.resolve(schema)
        for key in ("anyOf", "oneOf"):
            if key in schema:
                options = [self.resolve(s) for s in schema[key]]
                non_null = [s for s in options if s.get("type") != "null"]
                return self._value((non_null or options)[0], name, ids, required)
        if "allOf" in schema and schema["allOf"]:
            return self._value(schema["allOf"][0], name, ids, required)
        if "const" in schema:
            return schema["const"]
        if schema.get("enum"):
            return schema["enum"][0]
        kind = schema.get("type")
        if kind in ("integer", "number"):
            if name in ids:
                return ids[name]
            return schema.get("minimum", 1)
        if kind == "string":
            return self._string(schema)
        if kind == "boolean":
            return True
        if kind == "array":
            if schema.get("minItems", 0) == 0:
                return []
            return [self._value(schema.get("items", {}), name, ids, True)]
        if kind == "object" or "properties" in schema:
            return self._object(schema, ids)
        if kind == "null":
            return None
        return f"probe {self._counter}"

    def _object(self, schema: dict[str, Any], ids: dict[str, int]) -> dict[str, Any]:
        required = set(schema.get("required", []))
        out: dict[str, Any] = {}
        for prop, sub in schema.get("properties", {}).items():
            if prop not in required:
                resolved = self.resolve(sub)
                if resolved.get("type") == "object" or (prop.endswith("_id") and prop not in ids):
                    continue
            out[prop] = self._value(sub, prop, ids, prop in required)
        return out

    def _string(self, schema: dict[str, Any]) -> str:
        n = self._counter
        fmt = schema.get("format")
        if fmt == "email":
            return f"probe{n}@example.test"
        if fmt == "date-time":
            return "2026-01-01T00:00:00Z"
        if fmt == "date":
            return "2026-01-01"
        pattern = schema.get("pattern")
        if pattern:
            return _matching(pattern, n)
        text = f"Probe {n}"
        low, high = schema.get("minLength", 0), schema.get("maxLength")
        text = text.ljust(low, "x")
        return text[:high] if high else text


def _matching(pattern: str, n: int) -> str:
    candidates = [_letters(n), f"probe{n}", f"probe{n}@example.test", str(n), "a"]
    for candidate in candidates:
        if re.search(pattern, candidate):
            return candidate
    # Last resort: the simplest string Hypothesis finds for the pattern (deterministic).
    from hypothesis import find
    from hypothesis import strategies as st

    return find(st.from_regex(pattern, fullmatch=True), lambda _s: True)
