from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trademiner.market_data.cache import MarketDataCache
from trademiner.market_data.models import Instrument
from trademiner.strategy.repository import StrategyRecord


@dataclass(frozen=True)
class Candidate:
    instrument_id: str
    score: float
    explanation: str
    rank_basis: str | None = None
    tags: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_response(self) -> dict[str, Any]:
        return asdict(self)


class StrategyContext:
    def __init__(
        self,
        cache: MarketDataCache,
        as_of: str,
        adjustment: str = "hfq",
    ):
        self._cache = cache
        self.as_of = as_of
        self.adjustment = adjustment

    def universe(self, types: list[str] | None = None) -> list[Instrument]:
        instruments = self._cache.list_instruments()
        if types is None:
            return instruments
        requested = set(types)
        return [
            instrument
            for instrument in instruments
            if instrument.instrument_type in requested
        ]

    def daily_bars(
        self,
        instruments: list[str | Instrument] | None = None,
        lookback: int | None = None,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        instrument_ids = _instrument_ids(instruments)
        bars = [
            bar
            for bar in self._cache.list_daily_bars(adjustment=self.adjustment)
            if bar.trade_date <= self.as_of
            and (instrument_ids is None or bar.instrument_id in instrument_ids)
        ]
        if lookback is not None:
            bars = _last_n_bars_per_instrument(bars, lookback)

        rows = [bar.as_response() for bar in bars]
        if fields is not None:
            allowed = set(fields)
            return [
                {field: value for field, value in row.items() if field in allowed}
                for row in rows
            ]
        return rows

    def indicators(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []


class StrategyRuntime:
    def __init__(self, cache: MarketDataCache):
        self.cache = cache

    def run(
        self,
        strategy: StrategyRecord,
        params: dict[str, Any],
        as_of_date: str,
        adjustment: str = "hfq",
    ) -> list[Candidate]:
        namespace: dict[str, Any] = {
            "__file__": strategy.file_path,
            "__name__": f"trademiner_strategy_{strategy.strategy_id}",
        }
        exec(
            compile(
                strategy.latest_version.source_snapshot,
                strategy.file_path,
                "exec",
            ),
            namespace,
        )
        select = namespace.get("select")
        if not callable(select):
            raise ValueError(f"Strategy {strategy.strategy_id} does not define select")

        context = StrategyContext(
            cache=self.cache,
            as_of=as_of_date,
            adjustment=adjustment,
        )
        raw_candidates = select(context, params)
        candidates = [_coerce_candidate(candidate) for candidate in raw_candidates]
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def _coerce_candidate(value: Any) -> Candidate:
    if isinstance(value, Candidate):
        return value
    if isinstance(value, dict):
        return Candidate(
            instrument_id=value["instrument_id"],
            score=float(value["score"]),
            explanation=value["explanation"],
            rank_basis=value.get("rank_basis"),
            tags=list(value.get("tags") or []),
            metrics=dict(value.get("metrics") or {}),
        )
    raise ValueError("Strategy returned an invalid Candidate")


def _instrument_ids(
    instruments: list[str | Instrument] | None,
) -> set[str] | None:
    if instruments is None:
        return None
    return {
        instrument.instrument_id if isinstance(instrument, Instrument) else instrument
        for instrument in instruments
    }


def _last_n_bars_per_instrument(bars: list[Any], lookback: int) -> list[Any]:
    grouped: dict[str, list[Any]] = {}
    for bar in bars:
        grouped.setdefault(bar.instrument_id, []).append(bar)

    selected: list[Any] = []
    for instrument_bars in grouped.values():
        selected.extend(instrument_bars[-lookback:])
    return sorted(selected, key=lambda bar: (bar.instrument_id, bar.trade_date))
