from __future__ import annotations

import pytest
import structlog
from pydantic import SecretStr

from shipharness.log_setup import REDACTED, configure_logging, redact

from .fakes import fake_langsmith_key, fake_openai_key


def test_credential_named_fields_are_redacted() -> None:
    out = redact({"api_key": "anything", "Authorization": "Bearer x", "safe": "visible"})
    assert out == {"api_key": REDACTED, "Authorization": REDACTED, "safe": "visible"}


def test_key_patterns_inside_strings_are_masked() -> None:
    key = fake_openai_key()
    out = redact(f"calling with {key} now")
    assert key not in out
    assert out == f"calling with {REDACTED} now"


def test_langsmith_key_pattern_is_masked() -> None:
    key = fake_langsmith_key()
    assert key not in redact(["x", {"nested": key}])


def test_secretstr_is_redacted() -> None:
    assert redact(SecretStr("abc")) == REDACTED


def test_non_secret_values_pass_through() -> None:
    assert redact({"count": 3, "items": [1, 2], "flag": None}) == {
        "count": 3,
        "items": [1, 2],
        "flag": None,
    }


def test_log_output_never_contains_a_key(capsys: pytest.CaptureFixture[str]) -> None:
    key = fake_openai_key()
    configure_logging(json=True)
    structlog.get_logger().info("doctor", openai_api_key=key, detail=f"using {key}")
    err = capsys.readouterr().err
    assert key not in err
    assert REDACTED in err


def test_token_counts_and_non_secret_key_fields_survive() -> None:
    data = {
        "input_tokens": 10,
        "output_tokens": 5,
        "cached_tokens": 2,
        "max_output_tokens": 800,
        "accepts_idempotency_key": True,
        "key": "WEB",
        "monkey": "banana",
    }
    assert redact(data) == data


def test_credential_field_variants_are_redacted() -> None:
    out = redact(
        {
            "openai_api_key": "a",
            "x-api-key": "b",
            "client_secret": "c",
            "token": "d",
            "access_token": "e",
            "password": "f",
        }
    )
    assert set(out.values()) == {REDACTED}
