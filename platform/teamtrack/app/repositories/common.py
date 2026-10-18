from __future__ import annotations

from typing import Any

from sqlalchemy import Select


def page(stmt: Select[Any], id_column: Any, after: int | None, limit: int) -> Select[Any]:
    """Keyset pagination by ascending id: fetch limit + 1 rows to know if more exist."""
    if after is not None:
        stmt = stmt.where(id_column > after)
    return stmt.order_by(id_column).limit(limit + 1)


def split_page[T](rows: list[T], limit: int, key: Any) -> tuple[list[T], int | None]:
    if len(rows) > limit:
        rows = rows[:limit]
        return rows, key(rows[-1])
    return rows, None
