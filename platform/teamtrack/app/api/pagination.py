"""Cursor pagination (house rule R3): lists return {"items": [...], "next_cursor": str | null}."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import Query
from pydantic import BaseModel

from app.services.errors import BadRequest


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


class PageParams(BaseModel):
    cursor: str | None
    limit: int


def page_params(
    cursor: str | None = Query(default=None, description="Opaque cursor from next_cursor."),
    limit: int = Query(default=20, ge=1, le=100),
) -> PageParams:
    return PageParams(cursor=cursor, limit=limit)


def encode_cursor(after: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"after": after}).encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        after = data["after"]
        if not isinstance(after, int):
            raise ValueError
        return after
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError):
        raise BadRequest("invalid cursor", code="invalid_cursor") from None


def to_page[T: BaseModel](
    rows: Sequence[Any], next_after: int | None, convert: Callable[[Any], T]
) -> Page[T]:
    return Page[T](
        items=[convert(row) for row in rows],
        next_cursor=encode_cursor(next_after) if next_after is not None else None,
    )
