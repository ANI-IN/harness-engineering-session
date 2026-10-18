"""CostTracker: token usage x prices, with run, review, batch, session, experiment, and total
build caps."""

from __future__ import annotations

import contextlib
import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from shipharness.config import ModelPrice, Prices, Settings

try:  # POSIX file locks; the class machine and CI are Linux
    import fcntl
except ImportError:  # pragma: no cover - Windows without WSL
    fcntl = None  # type: ignore[assignment]

ScopeKind = Literal["run", "review"]
CapScope = Literal["run", "review", "session", "batch", "experiment", "build"]


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0  # total input, including cached and cache-write tokens
    cached_tokens: int = 0  # usage.input_tokens_details.cached_tokens
    cache_write_tokens: int = 0  # usage.input_tokens_details.cache_write_tokens
    output_tokens: int = 0  # includes reasoning tokens
    reasoning_tokens: int = 0  # usage.output_tokens_details.reasoning_tokens


class CapExceeded(Exception):
    def __init__(self, scope: CapScope, limit_usd: float, spent_usd: float) -> None:
        super().__init__(f"cost cap reached: {scope} ${spent_usd:.4f} of ${limit_usd:.2f}")
        self.scope = scope
        self.limit_usd = limit_usd
        self.spent_usd = spent_usd


@dataclass(frozen=True)
class Caps:
    run: float
    review: float
    session: float
    batch: float
    experiment: float
    build: float = 15.0  # every ledger entry, whatever its session or experiment flag

    @classmethod
    def from_settings(cls, settings: Settings, *, final: bool = False) -> Caps:
        return cls(
            run=settings.max_final_run_cost_usd if final else settings.max_run_cost_usd,
            review=settings.max_review_cost_usd,
            session=settings.max_session_cost_usd,
            batch=settings.max_batch_cost_usd,
            experiment=settings.max_experiment_total_usd,
            build=settings.max_build_total_usd,
        )


@dataclass
class CostScope:
    kind: ScopeKind
    key: str
    limit_usd: float
    spent_usd: float = 0.0
    reserved_usd: float = 0.0  # worst cases of calls in flight (see CostTracker.reserve)


@dataclass
class Reservation:
    """The worst-case cost of one model call, held against every cap until settled."""

    scope: CostScope
    model: str
    amount_usd: float
    open: bool = True
    service_tier: str | None = None  # the requested tier (the worst case used its rates)


@dataclass(frozen=True)
class CostSummary:
    total_usd: float
    by_model: dict[str, float]
    by_key: dict[str, float]
    batch_total_usd: float
    session_total_usd: float
    experiment_total_usd: float
    caps: Caps
    experiment: bool = False
    build_total_usd: float = 0.0

    def remaining(self) -> dict[str, float]:
        return {
            "batch": round(self.caps.batch - self.batch_total_usd, 6),
            "session": round(self.caps.session - self.session_total_usd, 6),
            "experiment": round(self.caps.experiment - self.experiment_total_usd, 6),
            "build": round(self.caps.build - self.build_total_usd, 6),
        }


def cost_of(price: ModelPrice, usage: Usage) -> float:
    uncached = max(usage.input_tokens - usage.cached_tokens - usage.cache_write_tokens, 0)
    return (
        uncached * price.input
        + usage.cached_tokens * price.cached_input
        + usage.cache_write_tokens * price.cache_write
        + usage.output_tokens * price.output
    ) / 1e6


def usage_from_openai(resp_usage: Any) -> Usage:
    """Build Usage from an OpenAI Responses `usage` object, tolerating missing fields."""

    def num(obj: Any, name: str) -> int:
        value = getattr(obj, name, 0) if obj is not None else 0
        return int(value or 0)

    input_details = getattr(resp_usage, "input_tokens_details", None)
    output_details = getattr(resp_usage, "output_tokens_details", None)
    return Usage(
        input_tokens=num(resp_usage, "input_tokens"),
        cached_tokens=num(input_details, "cached_tokens"),
        cache_write_tokens=num(input_details, "cache_write_tokens"),
        output_tokens=num(resp_usage, "output_tokens"),
        reasoning_tokens=num(output_details, "reasoning_tokens"),
    )


@dataclass
class CostTracker:
    """Records every model call in an append-only ledger and enforces caps.

    `session_id` groups class-session spend (persisted across commands); `experiment=True` marks
    pre-class experiment spend, which counts toward the experiment total instead of the session.
    The batch total covers this tracker instance (one command).
    """

    prices: Prices
    caps: Caps
    ledger_path: Path
    session_id: str
    experiment: bool = False
    # Re-entrant: reserve() runs check_before_call() under the same lock, so the check and the
    # hold are one step for concurrent arms.
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _batch: float = field(default=0.0, init=False)
    _reserved: float = field(default=0.0, init=False)
    _session: float = field(default=0.0, init=False)
    _experiment: float = field(default=0.0, init=False)
    _build: float = field(default=0.0, init=False)
    _offset: int = field(default=0, init=False)  # ledger bytes already counted
    _by_model: dict[str, float] = field(default_factory=lambda: defaultdict(float), init=False)
    _by_key: dict[str, float] = field(default_factory=lambda: defaultdict(float), init=False)

    def __post_init__(self) -> None:
        self.ledger_path = Path(self.ledger_path)
        self._refresh_locked()

    def _absorb(self, data: bytes) -> None:
        """Count complete ledger lines (other commands' entries, or all of them at start)."""
        for raw in data.splitlines():
            if not raw.strip():
                continue
            entry = json.loads(raw)
            self._build += entry["cost_usd"]
            if entry.get("experiment"):
                self._experiment += entry["cost_usd"]
            elif entry.get("session") == self.session_id:
                self._session += entry["cost_usd"]

    def _read_new(self, handle: Any) -> None:
        handle.seek(self._offset)
        data = handle.read()
        complete = data[: data.rfind(b"\n") + 1]  # a line another command is writing waits
        self._absorb(complete)
        self._offset += len(complete)

    def _refresh_locked(self) -> None:
        """Totals include what concurrent commands appended to the shared ledger since the last
        read (session, experiment, and build caps hold across commands)."""
        if self.ledger_path.exists():
            with self.ledger_path.open("rb") as handle:
                self._read_new(handle)

    @property
    def batch_total_usd(self) -> float:
        return self._batch

    @property
    def session_total_usd(self) -> float:
        with self._lock:
            self._refresh_locked()
            return self._session

    @property
    def experiment_total_usd(self) -> float:
        with self._lock:
            self._refresh_locked()
            return self._experiment

    @property
    def build_total_usd(self) -> float:
        with self._lock:
            self._refresh_locked()
            return self._build

    @property
    def reserved_usd(self) -> float:
        """Worst-case cost of the calls in flight on this tracker."""
        return self._reserved

    def scope(self, kind: ScopeKind, key: str, limit_usd: float) -> CostScope:
        return CostScope(kind=kind, key=key, limit_usd=limit_usd)

    def _active_limits(
        self, scope: CostScope, *, held: bool = False
    ) -> list[tuple[CapScope, float, float]]:
        """(cap, limit, spent) per active cap; `held` adds the worst cases of calls in flight.
        Batch, session, and experiment are shared by every scope of this tracker, so their held
        amount is the tracker's; the run or review cap holds only its own scope's calls."""
        own = scope.reserved_usd if held else 0.0
        shared = self._reserved if held else 0.0
        limits: list[tuple[CapScope, float, float]] = [
            (scope.kind, scope.limit_usd, scope.spent_usd + own),
            ("batch", self.caps.batch, self._batch + shared),
            ("build", self.caps.build, self._build + shared),
        ]
        if self.experiment:
            limits.append(("experiment", self.caps.experiment, self._experiment + shared))
        else:
            limits.append(("session", self.caps.session, self._session + shared))
        return limits

    def worst_case(
        self,
        model: str,
        est_input_tokens: int,
        max_output_tokens: int,
        service_tier: str | None = None,
    ) -> float:
        """Upper bound on one call: all input at the dearer uncached rate, full max output, at
        the requested tier's rates (Fast for "fast", Standard otherwise)."""
        price = self.prices.get(model, service_tier)
        return (
            est_input_tokens * max(price.input, price.cache_write)
            + max_output_tokens * price.output
        ) / 1e6

    def check_before_call(
        self,
        scope: CostScope,
        model: str,
        est_input_tokens: int,
        max_output_tokens: int,
        service_tier: str | None = None,
    ) -> None:
        """Raise CapExceeded if the worst case of the next call, on top of what is spent and what
        calls in flight hold, would cross any active cap."""
        worst = self.worst_case(model, est_input_tokens, max_output_tokens, service_tier)
        with self._lock:
            self._refresh_locked()
            for name, limit, spent in self._active_limits(scope, held=True):
                if spent + worst > limit:
                    raise CapExceeded(name, limit, spent)

    def reserve(
        self,
        scope: CostScope,
        model: str,
        est_input_tokens: int,
        max_output_tokens: int,
        service_tier: str | None = None,
    ) -> Reservation:
        """Check and hold the worst case of the next call against every cap, as one step under
        the lock, so concurrent arms cannot both pass the check for the last room under a shared
        cap. Every reservation ends with settle() (call made) or release() (no call or no usage).
        `service_tier` is the requested tier: a Fast request holds its worst case at Fast rates.
        """
        worst = self.worst_case(model, est_input_tokens, max_output_tokens, service_tier)
        with self._lock:
            self.check_before_call(scope, model, est_input_tokens, max_output_tokens, service_tier)
            scope.reserved_usd += worst
            self._reserved += worst
        return Reservation(scope=scope, model=model, amount_usd=worst, service_tier=service_tier)

    def _release_locked(self, reservation: Reservation) -> None:
        if not reservation.open:
            return
        reservation.open = False
        reservation.scope.reserved_usd = max(
            reservation.scope.reserved_usd - reservation.amount_usd, 0.0
        )
        self._reserved = max(self._reserved - reservation.amount_usd, 0.0)

    def release(self, reservation: Reservation) -> None:
        """Drop a reservation without recording a cost (the call failed or was never made)."""
        with self._lock:
            self._release_locked(reservation)

    def settle(
        self, reservation: Reservation, usage: Usage, service_tier: str | None = None
    ) -> float:
        """Replace the reservation with the call's actual cost, in one step under the lock.
        `service_tier` is the tier the response reports. Same contract as record(): returns the
        call cost; raises CapExceeded after recording."""
        with self._lock:
            self._release_locked(reservation)
            return self.record(reservation.scope, reservation.model, usage, service_tier)

    def record(
        self, scope: CostScope, model: str, usage: Usage, service_tier: str | None = None
    ) -> float:
        """Record one call, priced by the tier the response reports (`service_tier`): Fast rates
        for "fast", Standard rates for anything else (a downgraded Fast request reports
        "default"). Raises CapExceeded after recording if a cap is now crossed."""
        cost = round(cost_of(self.prices.get(model, service_tier), usage), 9)
        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "session": self.session_id,
            "experiment": self.experiment,
            "kind": scope.kind,
            "key": scope.key,
            "model": model,
            "service_tier": service_tier,  # as reported by the response (None: not reported)
            **usage.model_dump(),
            "cost_usd": cost,
        }
        with self._lock:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open("a+b") as handle:
                if fcntl is not None:
                    fcntl.flock(handle, fcntl.LOCK_EX)  # one writer at a time across commands
                try:
                    self._read_new(handle)  # entries other commands wrote first
                    handle.seek(0, 2)
                    handle.write((json.dumps(entry) + "\n").encode("utf-8"))
                    handle.flush()
                    self._offset = handle.tell()
                finally:
                    if fcntl is not None:
                        with contextlib.suppress(OSError):
                            fcntl.flock(handle, fcntl.LOCK_UN)
            scope.spent_usd += cost
            self._batch += cost
            self._build += cost
            if self.experiment:
                self._experiment += cost
            else:
                self._session += cost
            self._by_model[model] += cost
            self._by_key[scope.key] += cost
            for name, limit, spent in self._active_limits(scope):
                if spent > limit:
                    raise CapExceeded(name, limit, spent)
        return cost

    def summary(self) -> CostSummary:
        with self._lock:
            self._refresh_locked()
            return CostSummary(
                total_usd=self._batch,
                by_model=dict(self._by_model),
                by_key=dict(self._by_key),
                batch_total_usd=self._batch,
                session_total_usd=self._session,
                experiment_total_usd=self._experiment,
                caps=self.caps,
                experiment=self.experiment,
                build_total_usd=self._build,
            )


def record_opening_balance(ledger_path: Path, amount_usd: float, *, note: str) -> None:
    """Append, once, spend made before the ledger existed (so the build total counts from the
    start). Its timestamp precedes the first entry, so windows by time leave it out."""
    ledger_path = Path(ledger_path)
    lines = [ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    entries = [json.loads(ln) for ln in lines]
    if any(e.get("kind") == "opening" for e in entries):
        raise ValueError("an opening balance is already recorded")
    first = min((str(e.get("ts", "")) for e in entries), default="2026-10-16T00:00:00.000Z")
    entry = {
        "ts": first[:10] + "T00:00:00.000Z",
        "session": "",
        "experiment": False,
        "kind": "opening",
        "key": note,
        "model": "",
        "cost_usd": round(amount_usd, 9),
    }
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
