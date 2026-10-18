"""Helpers for hidden tests. A unique module name, so `from hidden_support import auth` can never
resolve to the arm-controlled tests/visible/conftest.py."""

from __future__ import annotations

from typing import Any


def auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer tt-{user_id}"}


def error_code(response: Any) -> str:
    body = response.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message"}, body
    return body["error"]["code"]
