"""Model prices from `platform/config/prices.toml`."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from shipharness.layout import PLATFORM_DIR, REPO_ROOT

DEFAULT_PRICES_FILE = REPO_ROOT / PLATFORM_DIR / "config" / "prices.toml"

_REQUIRED = ("input", "cached_input", "cache_write", "output")


class UnknownModelPrice(KeyError):
    """Raised when a model has no entry in the prices file (no silent zero cost)."""


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1M tokens."""

    input: float
    cached_input: float
    cache_write: float
    output: float


FAST = "fast"  # OPENAI_SERVICE_TIER value and reported response tier of the Fast tier


def _price(name: str, entry: dict[str, object]) -> ModelPrice:
    missing = [key for key in _REQUIRED if key not in entry]
    if missing:
        raise ValueError(f"prices for {name!r} missing fields: {', '.join(missing)}")
    return ModelPrice(**{key: float(entry[key]) for key in _REQUIRED})  # type: ignore[arg-type]


@dataclass(frozen=True)
class Prices:
    models: dict[str, ModelPrice]  # Standard tier
    source_file: Path
    fast: dict[str, ModelPrice] = field(default_factory=dict)  # Fast tier, where listed

    @classmethod
    def load(cls, path: Path = DEFAULT_PRICES_FILE) -> Prices:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        models: dict[str, ModelPrice] = {}
        fast: dict[str, ModelPrice] = {}
        for name, entry in data.get("models", {}).items():
            models[name] = _price(name, entry)
            if isinstance(entry.get(FAST), dict):
                fast[name] = _price(f"{name}.{FAST}", entry[FAST])
        return cls(models=models, source_file=Path(path), fast=fast)

    def get(self, model: str, tier: str | None = None) -> ModelPrice:
        """Standard rates, or the Fast rates when `tier` is "fast" (any other tier: Standard)."""
        if model not in self.models:
            raise UnknownModelPrice(
                f"no price for model {model!r} in {self.source_file}; add it before running"
            )
        if tier != FAST:
            return self.models[model]
        if model not in self.fast:
            raise UnknownModelPrice(
                f"no Fast tier price for model {model!r} in {self.source_file}; add a "
                f'[models."{model}".fast] table or use another service tier'
            )
        return self.fast[model]

    def check_tier(self, model: str, tier: str) -> None:
        """Startup check: the prices file can price every call of `model` at `tier`."""
        self.get(model, tier)
