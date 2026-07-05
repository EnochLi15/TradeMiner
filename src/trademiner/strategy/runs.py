from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from trademiner.strategy.repository import StrategyRepository, StrategyVersionRecord
from trademiner.strategy.runtime import Candidate


@dataclass(frozen=True)
class StrategyRunRecord:
    id: str
    strategy_id: str
    job_id: str
    strategy_version: StrategyVersionRecord
    params: dict[str, Any]
    as_of_date: str
    adjustment: str
    market_data_snapshot_ref: str
    candidates: list[dict[str, Any]]
    created_at: str

    def as_response(self) -> dict[str, object]:
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "job_id": self.job_id,
            "strategy_version": self.strategy_version.as_response(),
            "params": self.params,
            "as_of_date": self.as_of_date,
            "adjustment": self.adjustment,
            "market_data_snapshot_ref": self.market_data_snapshot_ref,
            "candidates": self.candidates,
            "created_at": self.created_at,
        }


class StrategyRunRepository:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.strategies = StrategyRepository(sqlite_path)

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_runs (
                    id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    strategy_version_id TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    adjustment TEXT NOT NULL,
                    market_data_snapshot_ref TEXT NOT NULL,
                    candidates_json TEXT NOT NULL,
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
        as_of_date: str,
        adjustment: str,
        market_data_snapshot_ref: str,
        candidates: list[Candidate],
    ) -> StrategyRunRecord:
        self.initialize()
        run_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO strategy_runs
                    (
                        id,
                        strategy_id,
                        job_id,
                        strategy_version_id,
                        params_json,
                        as_of_date,
                        adjustment,
                        market_data_snapshot_ref,
                        candidates_json
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    strategy_id,
                    job_id,
                    strategy_version.id,
                    json.dumps(params, sort_keys=True),
                    as_of_date,
                    adjustment,
                    market_data_snapshot_ref,
                    json.dumps(
                        [candidate.as_response() for candidate in candidates],
                        sort_keys=True,
                    ),
                ),
            )
        return self.get(run_id)

    def get(self, run_id: str) -> StrategyRunRecord:
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
                    as_of_date,
                    adjustment,
                    market_data_snapshot_ref,
                    candidates_json,
                    created_at
                FROM strategy_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(run_id)

        return self._record_from_row(row)

    def list(
        self,
        strategy_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StrategyRunRecord]:
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
                    as_of_date,
                    adjustment,
                    market_data_snapshot_ref,
                    candidates_json,
                    created_at
                FROM strategy_runs
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
                FROM strategy_runs
                {where}
                """,
                params,
            ).fetchone()
        return int(row[0])

    def _record_from_row(self, row: sqlite3.Row) -> StrategyRunRecord:
        version = self.strategies.get_version(row["strategy_version_id"])
        return StrategyRunRecord(
            id=row["id"],
            strategy_id=row["strategy_id"],
            job_id=row["job_id"],
            strategy_version=version,
            params=json.loads(row["params_json"]),
            as_of_date=row["as_of_date"],
            adjustment=row["adjustment"],
            market_data_snapshot_ref=row["market_data_snapshot_ref"],
            candidates=json.loads(row["candidates_json"]),
            created_at=row["created_at"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection
