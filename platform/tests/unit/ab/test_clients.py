from __future__ import annotations

import pytest

from shipharness.ab.clients import MissingKey, make_openai_client
from shipharness.config import Settings

from ..fakes import fake_openai_key


def test_production_openai_client_never_retries_on_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", fake_openai_key())
    client = make_openai_client(Settings(_env_file=None))
    assert client.max_retries == 0  # every error reaches classify_openai_error (ruling I-10)


def test_missing_key_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingKey, match="OPENAI_API_KEY"):
        make_openai_client(Settings(_env_file=None))
