"""Production API clients (contract I-10): the OpenAI client never retries on its own, so the
runner and reviewer see every error and classify it (billing 429s abort; others back off)."""

from __future__ import annotations

from typing import Any

from shipharness.config import Settings


class MissingKey(RuntimeError):
    """A required key is not configured. The message names the variable, never a value."""


def make_openai_client(settings: Settings, timeout_s: float = 120.0) -> Any:
    from openai import OpenAI

    if settings.openai_api_key is None:
        raise MissingKey("OPENAI_API_KEY is missing: add it to .env at the repo root")
    return OpenAI(
        api_key=settings.openai_api_key.get_secret_value(), max_retries=0, timeout=timeout_s
    )


def make_langsmith_client(settings: Settings) -> Any:
    from langsmith import Client

    if settings.langsmith_api_key is None:
        raise MissingKey("LANGSMITH_API_KEY is missing: add it to .env at the repo root")
    return Client(
        api_key=settings.langsmith_api_key.get_secret_value(), api_url=settings.langsmith_endpoint
    )
