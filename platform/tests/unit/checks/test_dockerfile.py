"""The sandbox images carry the check runner (I-1): platform/src/ at /opt/shipharness/src on the
PYTHONPATH."""

from __future__ import annotations

import re

from tests.unit.checks.seeds import REPO

DOCKERFILE = (REPO / "platform" / "sandbox" / "Dockerfile").read_text(encoding="utf-8")


def _stage(name: str) -> str:
    match = re.search(rf"^FROM \S+ AS {name}\n(.*?)(?=^FROM |\Z)", DOCKERFILE, re.M | re.S)
    assert match, name
    return match.group(1)


def test_base_stage_copies_the_package_after_the_dependency_layer() -> None:
    base = _stage("base")
    assert "COPY platform/src/ /opt/shipharness/src/" in base
    assert "PYTHONPATH=/opt/shipharness/src" in base
    # Source changes must not invalidate the baked dependency layer.
    assert base.index("uv sync") < base.index("COPY platform/src/")


def test_agent_and_referee_inherit_the_package() -> None:
    assert re.search(r"^FROM base AS agent$", DOCKERFILE, re.M)
    assert re.search(r"^FROM base AS referee$", DOCKERFILE, re.M)
