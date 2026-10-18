"""Test helpers. Fake keys are assembled at runtime so no key-shaped literal is ever committed."""

from __future__ import annotations


def fake_openai_key() -> str:
    return "sk-" + "proj-" + "A1b2C3d4" * 4


def fake_langsmith_key() -> str:
    return "lsv2" + "_pt_" + "f00dbabe" * 4
