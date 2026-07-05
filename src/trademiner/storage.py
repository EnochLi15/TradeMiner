from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb


def default_data_dir() -> Path:
    configured = os.environ.get("TRADEMINER_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".trademiner"


@dataclass(frozen=True)
class MetadataStoreStatus:
    path: Path
    initialized: bool

    def as_response(self) -> dict[str, Any]:
        return {
            "kind": "sqlite",
            "path": str(self.path),
            "initialized": self.initialized,
        }


@dataclass(frozen=True)
class AnalyticalStoreStatus:
    duckdb_path: Path
    parquet_dir: Path
    initialized: bool

    def as_response(self) -> dict[str, Any]:
        return {
            "kind": "duckdb_parquet",
            "duckdb_path": str(self.duckdb_path),
            "parquet_dir": str(self.parquet_dir),
            "initialized": self.initialized,
        }


@dataclass(frozen=True)
class StorageStatus:
    status: str
    data_dir: Path
    metadata_store: MetadataStoreStatus
    analytical_store: AnalyticalStoreStatus

    def as_response(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "data_dir": str(self.data_dir),
            "metadata_store": self.metadata_store.as_response(),
            "analytical_store": self.analytical_store.as_response(),
        }


def initialize_storage(data_dir: Path | str | None = None) -> StorageStatus:
    root = Path(data_dir).expanduser() if data_dir is not None else default_data_dir()
    root.mkdir(parents=True, exist_ok=True)

    sqlite_path = root / "trademiner.sqlite"
    _initialize_sqlite(sqlite_path)

    market_dir = root / "market"
    parquet_dir = market_dir / "parquet"
    market_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)

    duckdb_path = market_dir / "trademiner.duckdb"
    _initialize_duckdb(duckdb_path)

    return StorageStatus(
        status="ok",
        data_dir=root,
        metadata_store=MetadataStoreStatus(path=sqlite_path, initialized=True),
        analytical_store=AnalyticalStoreStatus(
            duckdb_path=duckdb_path,
            parquet_dir=parquet_dir,
            initialized=True,
        ),
    )


def _initialize_sqlite(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                parameters_json TEXT NOT NULL DEFAULT '{}',
                progress_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT,
                result_ref TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS strategies (
                strategy_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                file_path TEXT NOT NULL,
                params_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_versions (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                name TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                source_snapshot TEXT NOT NULL,
                git_commit TEXT,
                git_dirty INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(strategy_id) REFERENCES strategies(strategy_id)
            )
            """
        )
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_schedules (
                id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL,
                provider TEXT NOT NULL,
                instrument_types_json TEXT NOT NULL,
                adjustment TEXT NOT NULL,
                start_date TEXT NOT NULL,
                overlap_days INTEGER NOT NULL,
                schedule_time TEXT NOT NULL,
                timezone TEXT NOT NULL,
                trading_days_only INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _initialize_duckdb(path: Path) -> None:
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO storage_metadata (key, value)
            VALUES ('storage_model', 'duckdb_parquet')
            """
        )
