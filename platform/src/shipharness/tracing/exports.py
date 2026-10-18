"""Local exports so reports keep working after LangSmith traces expire."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from shipharness.log_setup import redact

ExportKind = Literal["scores", "experiments", "traces", "batches"]
_KINDS = {"scores", "experiments", "traces", "batches"}


def write_export(
    kind: ExportKind, name: str, payload: BaseModel | dict[str, Any], exports_dir: Path
) -> Path:
    if kind not in _KINDS:
        raise ValueError(f"unknown export kind: {kind!r}")
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    path = Path(exports_dir) / kind / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(data), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_exports(kind: ExportKind, exports_dir: Path) -> list[dict[str, Any]]:
    folder = Path(exports_dir) / kind
    if not folder.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]
