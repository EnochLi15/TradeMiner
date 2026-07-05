from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trademiner.market_data.cache import MarketDataCache
from trademiner.market_data.models import DailyBar
from trademiner.strategy.repository import StrategyRecord
from trademiner.strategy.runtime import Candidate, StrategyRuntime


@dataclass(frozen=True)
class SelectionBacktestResult:
    selection_dates: list[str]
    selection_results: list[dict[str, Any]]
    summary_metrics: dict[str, dict[str, float | int | None]]
    market_data_snapshot_ref: str

    @property
    def observation_count(self) -> int:
        return sum(
            metric["observation_count"]
            for metric in self.summary_metrics.values()
        )


class SelectionBacktestService:
    def __init__(self, cache: MarketDataCache, runtime: StrategyRuntime):
        self.cache = cache
        self.runtime = runtime

    def run(
        self,
        strategy: StrategyRecord,
        params: dict[str, Any],
        start_date: str,
        end_date: str,
        top_n: int,
        horizons: list[int],
        adjustment: str = "hfq",
        benchmark: dict[str, Any] | None = None,
    ) -> SelectionBacktestResult:
        selection_dates = self.cache.trade_dates(
            adjustment=adjustment,
            start_date=start_date,
            end_date=end_date,
        )
        bars_by_instrument = _group_bars(
            self.cache.list_daily_bars(adjustment=adjustment)
        )
        benchmark_instrument_id = (
            benchmark.get("instrument_id") if benchmark is not None else None
        )
        observations: dict[int, list[dict[str, Any]]] = {
            horizon: [] for horizon in horizons
        }
        selection_results: list[dict[str, Any]] = []

        for selection_date in selection_dates:
            candidates = self.runtime.run(
                strategy=strategy,
                params=params,
                as_of_date=selection_date,
                adjustment=adjustment,
            )[:top_n]
            horizon_results = {str(horizon): [] for horizon in horizons}

            for candidate in candidates:
                instrument_bars = bars_by_instrument.get(candidate.instrument_id, [])
                entry_index = _bar_index(instrument_bars, selection_date)
                if entry_index is None:
                    continue

                for horizon in horizons:
                    horizon_result = _measure_horizon(
                        candidate=candidate,
                        instrument_bars=instrument_bars,
                        entry_index=entry_index,
                        horizon=horizon,
                        benchmark_bars=bars_by_instrument.get(
                            benchmark_instrument_id,
                            [],
                        )
                        if benchmark_instrument_id
                        else [],
                    )
                    if horizon_result is None:
                        continue
                    horizon_results[str(horizon)].append(horizon_result)
                    observations[horizon].append(horizon_result)

            selection_results.append(
                {
                    "selection_date": selection_date,
                    "candidates": [
                        candidate.as_response()
                        for candidate in candidates
                    ],
                    "horizon_results": horizon_results,
                }
            )

        latest_trade_date = self.cache.latest_trade_date(adjustment) or end_date
        return SelectionBacktestResult(
            selection_dates=selection_dates,
            selection_results=selection_results,
            summary_metrics={
                str(horizon): _summarize_horizon(observations[horizon])
                for horizon in horizons
            },
            market_data_snapshot_ref=(
                f"market-data:{adjustment}:{start_date}:{latest_trade_date}"
            ),
        )


def _group_bars(bars: list[DailyBar]) -> dict[str, list[DailyBar]]:
    grouped: dict[str, list[DailyBar]] = {}
    for bar in bars:
        grouped.setdefault(bar.instrument_id, []).append(bar)
    return {
        instrument_id: sorted(instrument_bars, key=lambda bar: bar.trade_date)
        for instrument_id, instrument_bars in grouped.items()
    }


def _bar_index(bars: list[DailyBar], trade_date: str) -> int | None:
    for index, bar in enumerate(bars):
        if bar.trade_date == trade_date:
            return index
    return None


def _measure_horizon(
    candidate: Candidate,
    instrument_bars: list[DailyBar],
    entry_index: int,
    horizon: int,
    benchmark_bars: list[DailyBar],
) -> dict[str, Any] | None:
    exit_index = entry_index + horizon
    if exit_index >= len(instrument_bars):
        return None

    entry_bar = instrument_bars[entry_index]
    exit_bar = instrument_bars[exit_index]
    if entry_bar.close == 0:
        return None

    future_return = (exit_bar.close - entry_bar.close) / entry_bar.close
    close_window = instrument_bars[entry_index : exit_index + 1]
    max_drawdown = (
        min(bar.close for bar in close_window) - entry_bar.close
    ) / entry_bar.close
    benchmark_return = _benchmark_return(
        benchmark_bars=benchmark_bars,
        entry_date=entry_bar.trade_date,
        horizon=horizon,
    )
    excess_return = (
        future_return - benchmark_return
        if benchmark_return is not None
        else None
    )

    return {
        "instrument_id": candidate.instrument_id,
        "entry_date": entry_bar.trade_date,
        "exit_date": exit_bar.trade_date,
        "entry_close": float(entry_bar.close),
        "exit_close": float(exit_bar.close),
        "future_return": future_return,
        "max_drawdown": max_drawdown,
        "benchmark_return": benchmark_return,
        "excess_return": excess_return,
    }


def _benchmark_return(
    benchmark_bars: list[DailyBar],
    entry_date: str,
    horizon: int,
) -> float | None:
    entry_index = _bar_index(benchmark_bars, entry_date)
    if entry_index is None:
        return None
    exit_index = entry_index + horizon
    if exit_index >= len(benchmark_bars):
        return None
    entry_bar = benchmark_bars[entry_index]
    exit_bar = benchmark_bars[exit_index]
    if entry_bar.close == 0:
        return None
    return (exit_bar.close - entry_bar.close) / entry_bar.close


def _summarize_horizon(
    observations: list[dict[str, Any]],
) -> dict[str, float | int | None]:
    observation_count = len(observations)
    if observation_count == 0:
        return {
            "observation_count": 0,
            "average_return": None,
            "win_rate": None,
            "max_drawdown": None,
            "average_benchmark_return": None,
            "average_excess_return": None,
        }

    benchmark_returns = [
        observation["benchmark_return"]
        for observation in observations
        if observation["benchmark_return"] is not None
    ]
    excess_returns = [
        observation["excess_return"]
        for observation in observations
        if observation["excess_return"] is not None
    ]
    return {
        "observation_count": observation_count,
        "average_return": _average(
            [observation["future_return"] for observation in observations]
        ),
        "win_rate": sum(
            1 for observation in observations if observation["future_return"] > 0
        )
        / observation_count,
        "max_drawdown": min(
            observation["max_drawdown"] for observation in observations
        ),
        "average_benchmark_return": _average(benchmark_returns)
        if benchmark_returns
        else None,
        "average_excess_return": _average(excess_returns)
        if excess_returns
        else None,
    }


def _average(values: list[float]) -> float:
    return sum(values) / len(values)
