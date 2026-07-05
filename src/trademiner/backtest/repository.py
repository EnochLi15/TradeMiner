from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from trademiner.strategy.repository import StrategyRepository, StrategyVersionRecord


@dataclass(frozen=True)
class SelectionBacktestRecord:
    id: str
    strategy_id: str
    job_id: str
    strategy_version: StrategyVersionRecord
    params: dict[str, Any]
    start_date: str
    end_date: str
    selection_dates: list[str]
    top_n: int
    horizons: list[int]
    adjustment: str
    benchmark: dict[str, Any] | None
    market_data_snapshot_ref: str
    selection_results: list[dict[str, Any]]
    summary_metrics: dict[str, Any]
    created_at: str

    def as_response(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "job_id": self.job_id,
            "strategy_version": self.strategy_version.as_response(),
            "params": self.params,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "selection_dates": self.selection_dates,
            "top_n": self.top_n,
            "horizons": self.horizons,
            "adjustment": self.adjustment,
            "benchmark": self.benchmark,
            "market_data_snapshot_ref": self.market_data_snapshot_ref,
            "selection_results": self.selection_results,
            "summary_metrics": self.summary_metrics,
            "created_at": self.created_at,
        }


class SelectionBacktestRepository:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.strategies = StrategyRepository(sqlite_path)

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS selection_backtests (
                    id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    strategy_version_id TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    selection_dates_json TEXT NOT NULL,
                    top_n INTEGER NOT NULL,
                    horizons_json TEXT NOT NULL,
                    adjustment TEXT NOT NULL,
                    benchmark_json TEXT,
                    market_data_snapshot_ref TEXT NOT NULL,
                    selection_results_json TEXT NOT NULL,
                    summary_metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def create(
        self,
        strategy_id: str,
        job_id: str,
        strategy_version: StrategyVersionRecord,
        params: dict[str, Any],
        start_date: str,
        end_date: str,
        selection_dates: list[str],
        top_n: int,
        horizons: list[int],
        adjustment: str,
        benchmark: dict[str, Any] | None,
        market_data_snapshot_ref: str,
        selection_results: list[dict[str, Any]],
        summary_metrics: dict[str, Any],
    ) -> SelectionBacktestRecord:
        self.initialize()
        backtest_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO selection_backtests
                    (
                        id,
                        strategy_id,
                        job_id,
                        strategy_version_id,
                        params_json,
                        start_date,
                        end_date,
                        selection_dates_json,
                        top_n,
                        horizons_json,
                        adjustment,
                        benchmark_json,
                        market_data_snapshot_ref,
                        selection_results_json,
                        summary_metrics_json
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    backtest_id,
                    strategy_id,
                    job_id,
                    strategy_version.id,
                    json.dumps(params, sort_keys=True),
                    start_date,
                    end_date,
                    json.dumps(selection_dates, sort_keys=True),
                    top_n,
                    json.dumps(horizons, sort_keys=True),
                    adjustment,
                    json.dumps(benchmark, sort_keys=True)
                    if benchmark is not None
                    else None,
                    market_data_snapshot_ref,
                    json.dumps(selection_results, sort_keys=True),
                    json.dumps(summary_metrics, sort_keys=True),
                ),
            )
        return self.get(backtest_id)

    def get(self, backtest_id: str) -> SelectionBacktestRecord:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    strategy_id,
                    job_id,
                    strategy_version_id,
                    params_json,
                    start_date,
                    end_date,
                    selection_dates_json,
                    top_n,
                    horizons_json,
                    adjustment,
                    benchmark_json,
                    market_data_snapshot_ref,
                    selection_results_json,
                    summary_metrics_json,
                    created_at
                FROM selection_backtests
                WHERE id = ?
                """,
                (backtest_id,),
            ).fetchone()
        if row is None:
            raise KeyError(backtest_id)

        return self._record_from_row(row)

    def list(
        self,
        strategy_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SelectionBacktestRecord]:
        self.initialize()
        clauses: list[str] = []
        params: list[Any] = []
        if strategy_id is not None:
            clauses.append("strategy_id = ?")
            params.append(strategy_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    strategy_id,
                    job_id,
                    strategy_version_id,
                    params_json,
                    start_date,
                    end_date,
                    selection_dates_json,
                    top_n,
                    horizons_json,
                    adjustment,
                    benchmark_json,
                    market_data_snapshot_ref,
                    selection_results_json,
                    summary_metrics_json,
                    created_at
                FROM selection_backtests
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def count(self, strategy_id: str | None = None) -> int:
        self.initialize()
        clauses: list[str] = []
        params: list[Any] = []
        if strategy_id is not None:
            clauses.append("strategy_id = ?")
            params.append(strategy_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*)
                FROM selection_backtests
                {where}
                """,
                params,
            ).fetchone()
        return int(row[0])

    def _record_from_row(self, row: sqlite3.Row) -> SelectionBacktestRecord:
        version = self.strategies.get_version(row["strategy_version_id"])
        benchmark = (
            json.loads(row["benchmark_json"])
            if row["benchmark_json"] is not None
            else None
        )
        return SelectionBacktestRecord(
            id=row["id"],
            strategy_id=row["strategy_id"],
            job_id=row["job_id"],
            strategy_version=version,
            params=json.loads(row["params_json"]),
            start_date=row["start_date"],
            end_date=row["end_date"],
            selection_dates=json.loads(row["selection_dates_json"]),
            top_n=row["top_n"],
            horizons=json.loads(row["horizons_json"]),
            adjustment=row["adjustment"],
            benchmark=benchmark,
            market_data_snapshot_ref=row["market_data_snapshot_ref"],
            selection_results=json.loads(row["selection_results_json"]),
            summary_metrics=json.loads(row["summary_metrics_json"]),
            created_at=row["created_at"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection
