from __future__ import annotations

from typing import Any

from trademiner.backtest.repository import (
    SelectionBacktestRecord,
    SelectionBacktestRepository,
)
from trademiner.strategy.runs import StrategyRunRecord, StrategyRunRepository


class ResultSnapshotComparisonService:
    def __init__(
        self,
        strategy_runs: StrategyRunRepository,
        selection_backtests: SelectionBacktestRepository,
    ):
        self.strategy_runs = strategy_runs
        self.selection_backtests = selection_backtests

    def compare(self, snapshot_type: str, snapshot_ids: list[str]) -> dict[str, Any]:
        if len(snapshot_ids) < 2:
            raise ValueError("At least two snapshots are required")
        if snapshot_type == "strategy_run":
            return self.compare_strategy_runs(snapshot_ids)
        if snapshot_type == "selection_backtest":
            return self.compare_selection_backtests(snapshot_ids)
        raise ValueError("Unsupported Result Snapshot type")

    def compare_strategy_runs(self, snapshot_ids: list[str]) -> dict[str, Any]:
        snapshots = [self.strategy_runs.get(snapshot_id) for snapshot_id in snapshot_ids]
        return {
            "snapshot_type": "strategy_run",
            "snapshots": [_strategy_run_summary(snapshot) for snapshot in snapshots],
            "candidate_score_deltas": _candidate_score_deltas(snapshots),
        }

    def compare_selection_backtests(self, snapshot_ids: list[str]) -> dict[str, Any]:
        snapshots = [
            self.selection_backtests.get(snapshot_id) for snapshot_id in snapshot_ids
        ]
        return {
            "snapshot_type": "selection_backtest",
            "snapshots": [
                _selection_backtest_summary(snapshot) for snapshot in snapshots
            ],
            "metric_deltas": _metric_deltas(snapshots),
        }


def _strategy_run_summary(snapshot: StrategyRunRecord) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "strategy_id": snapshot.strategy_id,
        "as_of_date": snapshot.as_of_date,
        "candidate_count": len(snapshot.candidates),
        "market_data_snapshot_ref": snapshot.market_data_snapshot_ref,
        "created_at": snapshot.created_at,
    }


def _selection_backtest_summary(snapshot: SelectionBacktestRecord) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "strategy_id": snapshot.strategy_id,
        "start_date": snapshot.start_date,
        "end_date": snapshot.end_date,
        "selection_date_count": len(snapshot.selection_dates),
        "market_data_snapshot_ref": snapshot.market_data_snapshot_ref,
        "created_at": snapshot.created_at,
    }


def _candidate_score_deltas(
    snapshots: list[StrategyRunRecord],
) -> dict[str, dict[str, Any]]:
    instrument_ids = sorted(
        {
            candidate["instrument_id"]
            for snapshot in snapshots
            for candidate in snapshot.candidates
        }
    )
    deltas: dict[str, dict[str, Any]] = {}
    for instrument_id in instrument_ids:
        values: dict[str, float] = {}
        for snapshot in snapshots:
            candidate = next(
                (
                    candidate
                    for candidate in snapshot.candidates
                    if candidate["instrument_id"] == instrument_id
                ),
                None,
            )
            if candidate is not None:
                values[snapshot.id] = float(candidate["score"])
        deltas[instrument_id] = {
            "values": values,
            "delta": _first_last_delta(values, [snapshot.id for snapshot in snapshots]),
        }
    return deltas


def _metric_deltas(
    snapshots: list[SelectionBacktestRecord],
) -> dict[str, dict[str, dict[str, Any]]]:
    horizons = sorted(
        {
            horizon
            for snapshot in snapshots
            for horizon in snapshot.summary_metrics.keys()
        },
        key=lambda value: int(value),
    )
    metrics = [
        "observation_count",
        "average_return",
        "win_rate",
        "max_drawdown",
        "average_benchmark_return",
        "average_excess_return",
    ]
    deltas: dict[str, dict[str, dict[str, Any]]] = {}
    for horizon in horizons:
        deltas[horizon] = {}
        for metric in metrics:
            values = {
                snapshot.id: snapshot.summary_metrics[horizon][metric]
                for snapshot in snapshots
                if horizon in snapshot.summary_metrics
                and snapshot.summary_metrics[horizon][metric] is not None
            }
            deltas[horizon][metric] = {
                "values": values,
                "delta": _first_last_delta(
                    values,
                    [snapshot.id for snapshot in snapshots],
                ),
            }
    return deltas


def _first_last_delta(values: dict[str, Any], snapshot_ids: list[str]) -> float | None:
    first_id = snapshot_ids[0]
    last_id = snapshot_ids[-1]
    first = values.get(first_id)
    last = values.get(last_id)
    if isinstance(first, (int, float)) and isinstance(last, (int, float)):
        return last - first
    return None
