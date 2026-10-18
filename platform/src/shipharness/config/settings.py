"""Settings loaded from the environment and `.env`. Keys are SecretStr (§20)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shipharness.config.prices import DEFAULT_PRICES_FILE, REPO_ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required keys (None when unset or empty; `shipharness doctor` reports them as missing).
    openai_api_key: SecretStr | None = None
    langsmith_api_key: SecretStr | None = None

    # Models
    openai_model: str = "gpt-6-luna"
    openai_reasoning_effort: str = "medium"
    openai_eval_model: str = "gpt-5.6-luna"
    openai_eval_reasoning_effort: str = "medium"
    # "fast": the Fast tier (class profile, agent arms only); calls are priced by the tier the
    # response reports, so a Fast request downgraded to standard is charged standard rates.
    openai_service_tier: Literal["auto", "default", "flex", "fast"] = "auto"

    # LangSmith
    langsmith_tracing: bool = True
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    shipharness_class_date: str = Field(default="", validate_default=True)

    # Cost caps (USD)
    max_run_cost_usd: float = 0.20
    max_final_run_cost_usd: float = 0.25
    max_review_cost_usd: float = 0.04
    max_session_cost_usd: float = 2.50
    max_batch_cost_usd: float = 2.50
    max_experiment_total_usd: float = 25.00
    # Every model call in this ledger, from its first entry.
    max_build_total_usd: float = 15.00

    # Run limits
    max_turns_per_session: int = 30
    max_output_tokens: int = 8000
    wrapup_turns: int = 3
    tool_timeout_s: int = 120
    run_timeout_s: int = 300
    harness_timeout_s: int = 120  # harness work per arm per run; RUN_TIMEOUT_S excludes it
    max_concurrency: int = 4

    # Sandbox
    sandbox_mode: Literal["docker", "none"] = "docker"
    sandbox_runtime: Literal["docker", "podman"] = "docker"
    sandbox_image_agent: str = "shipharness-agent:1"
    sandbox_image_referee: str = "shipharness-referee:1"
    sandbox_cpus: float = 1.0  # per arm, referee, and preview container (class profile: 2)

    # Paths
    runs_dir: Path = Path(".shipharness/runs")
    exports_dir: Path = Path("exports")
    prices_file: Path = DEFAULT_PRICES_FILE

    @field_validator("shipharness_class_date", mode="before")
    @classmethod
    def _default_today(cls, value: object) -> str:
        """The class day, set explicitly in .env for class commands (they refuse without it); the
        class session cost cap and the class LangSmith project are keyed by it. Never today by
        default."""
        return str(value).strip() if value is not None else ""

    @field_validator("openai_api_key", "langsmith_api_key", mode="before")
    @classmethod
    def _blank_is_missing(cls, value: object) -> object:
        if value is None:
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        return raw.strip() or None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
