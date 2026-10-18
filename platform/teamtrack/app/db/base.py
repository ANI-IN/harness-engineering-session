from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


# Import models so Base.metadata is complete wherever Base is imported (Alembic, tests).
from app.db import models as _models  # noqa: E402,F401
