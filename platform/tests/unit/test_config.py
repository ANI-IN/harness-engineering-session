from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.config import Prices, Settings, UnknownModelPrice
from shipharness.config.prices import DEFAULT_PRICES_FILE

from .fakes import fake_langsmith_key, fake_openai_key


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in ("OPENAI_API_KEY", "LANGSMITH_API_KEY", "OPENAI_MODEL", "MAX_RUN_COST_USD"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_defaults_match_contracts(clean_env: pytest.MonkeyPatch) -> None:
    s = Settings(_env_file=None)
    assert s.openai_model == "gpt-6-luna"
    assert s.openai_eval_model == "gpt-5.6-luna"
    assert s.openai_service_tier == "auto"
    assert s.max_run_cost_usd == 0.20
    assert s.max_final_run_cost_usd == 0.25
    assert s.max_review_cost_usd == 0.04
    assert s.max_session_cost_usd == 2.50
    assert s.max_batch_cost_usd == 2.50
    assert s.max_experiment_total_usd == 25.00
    assert s.run_timeout_s == 300
    assert s.max_concurrency == 4
    assert s.sandbox_mode == "docker"


def test_empty_keys_are_treated_as_missing(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("OPENAI_API_KEY", "")
    clean_env.setenv("LANGSMITH_API_KEY", "   ")
    s = Settings(_env_file=None)
    assert s.openai_api_key is None
    assert s.langsmith_api_key is None


def test_keys_never_appear_in_repr_or_dump(clean_env: pytest.MonkeyPatch) -> None:
    openai_key, langsmith_key = fake_openai_key(), fake_langsmith_key()
    clean_env.setenv("OPENAI_API_KEY", openai_key)
    clean_env.setenv("LANGSMITH_API_KEY", langsmith_key)
    s = Settings(_env_file=None)
    assert s.openai_api_key is not None
    assert s.openai_api_key.get_secret_value() == openai_key
    for text in (repr(s), str(s), s.model_dump_json()):
        assert openai_key not in text
        assert langsmith_key not in text


def test_env_file_is_read(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("OPENAI_MODEL=gpt-test\nMAX_RUN_COST_USD=0.15\n", encoding="utf-8")
    s = Settings(_env_file=env)
    assert s.openai_model == "gpt-test"
    assert s.max_run_cost_usd == 0.15


def test_prices_file_values_for_agent_model() -> None:
    price = Prices.load(DEFAULT_PRICES_FILE).get("gpt-6-luna")
    assert (price.input, price.cached_input, price.cache_write, price.output) == (
        0.10,
        0.01,
        0.125,
        0.50,
    )


def test_prices_file_values_for_eval_model() -> None:
    price = Prices.load(DEFAULT_PRICES_FILE).get("gpt-5.6-luna")
    assert (price.input, price.cached_input, price.cache_write, price.output) == (
        0.20,
        0.02,
        0.25,
        1.20,
    )


def test_unknown_model_price_raises() -> None:
    with pytest.raises(UnknownModelPrice, match="gpt-unknown"):
        Prices.load(DEFAULT_PRICES_FILE).get("gpt-unknown")


def test_prices_file_missing_field_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "prices.toml"
    bad.write_text('[models."m"]\ninput = 1.0\noutput = 2.0\n', encoding="utf-8")
    with pytest.raises(ValueError, match="cache_write"):
        Prices.load(bad)


def test_class_date_is_empty_unless_set_for_the_class_day(clean_env: pytest.MonkeyPatch) -> None:
    # The class date is set explicitly for the class day, never today by default
    # (pilot runs of 2026-10-16 were traced into a class project).
    clean_env.delenv("SHIPHARNESS_CLASS_DATE", raising=False)
    assert Settings(_env_file=None).shipharness_class_date == ""
    clean_env.setenv("SHIPHARNESS_CLASS_DATE", "2026-10-20")
    assert Settings(_env_file=None).shipharness_class_date == "2026-10-20"
