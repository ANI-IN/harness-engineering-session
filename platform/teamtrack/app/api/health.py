from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import HealthOut

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")
