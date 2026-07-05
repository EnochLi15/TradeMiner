from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from trademiner.jobs import JobRepository
from trademiner.market_data.sync import MarketDataSyncRequest, MarketDataSyncService


DEFAULT_SYNC_SCHEDULE_ID = "market_data_default"


@dataclass(frozen=True)
class MarketDataSyncSchedule:
    id: str
    enabled: bool
    provider: str
    instrument_types: list[str]
    adjustment: str
    start_date: str
    overlap_days: int
    schedule_time: str
    timezone: str
    trading_days_only: bool
    updated_at: str | None = None

    def as_response(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "enabled": self.enabled,
            "provider": self.provider,
            "instrument_types": self.instrument_types,
            "adjustment": self.adjustment,
            "start_date": self.start_date,
            "overlap_days": self.overlap_days,
            "schedule_time": self.schedule_time,
            "timezone": self.timezone,
            "trading_days_only": self.trading_days_only,
            "updated_at": self.updated_at,
        }


class MarketDataSyncScheduleRepository:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path

    def initialize(self) -> None:
        with self._connect() as connection:
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
            connection.execute(
                """
                INSERT OR IGNORE INTO sync_schedules
                    (
                        id,
                        enabled,
                        provider,
                        instrument_types_json,
                        adjustment,
                        start_date,
                        overlap_days,
                        schedule_time,
                        timezone,
                        trading_days_only
                    )
                VALUES (?, 1, 'akshare', ?, 'hfq', '2024-01-01', 5, '16:30', 'Asia/Shanghai', 1)
                """,
                (
                    DEFAULT_SYNC_SCHEDULE_ID,
                    json.dumps(["stock", "etf"], sort_keys=True),
                ),
            )

    def get(self) -> MarketDataSyncSchedule:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    enabled,
                    provider,
                    instrument_types_json,
                    adjustment,
                    start_date,
                    overlap_days,
                    schedule_time,
                    timezone,
                    trading_days_only,
                    updated_at
                FROM sync_schedules
                WHERE id = ?
                """,
                (DEFAULT_SYNC_SCHEDULE_ID,),
            ).fetchone()
        return _schedule_from_row(row)

    def update(self, changes: dict[str, Any]) -> MarketDataSyncSchedule:
        self.initialize()
        current = self.get()
        values = {
            "enabled": current.enabled,
            "provider": current.provider,
            "instrument_types": current.instrument_types,
            "adjustment": current.adjustment,
            "start_date": current.start_date,
            "overlap_days": current.overlap_days,
            "schedule_time": current.schedule_time,
            "timezone": current.timezone,
            "trading_days_only": current.trading_days_only,
        }
        values.update(changes)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE sync_schedules
                SET enabled = ?,
                    provider = ?,
                    instrument_types_json = ?,
                    adjustment = ?,
                    start_date = ?,
                    overlap_days = ?,
                    schedule_time = ?,
                    timezone = ?,
                    trading_days_only = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    1 if values["enabled"] else 0,
                    values["provider"],
                    json.dumps(values["instrument_types"], sort_keys=True),
                    values["adjustment"],
                    values["start_date"],
                    values["overlap_days"],
                    values["schedule_time"],
                    values["timezone"],
                    1 if values["trading_days_only"] else 0,
                    DEFAULT_SYNC_SCHEDULE_ID,
                ),
            )
        return self.get()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection


class MarketDataScheduledSyncService:
    def __init__(
        self,
        schedules: MarketDataSyncScheduleRepository,
        sync_service: MarketDataSyncService,
    ):
        self.schedules = schedules
        self.sync_service = sync_service

    def run(self, run_date: str | None = None):
        schedule = self.schedules.get()
        end_date = run_date or date.today().isoformat()
        return self.sync_service.sync(
            MarketDataSyncRequest(
                provider=schedule.provider,
                instrument_types=schedule.instrument_types,
                adjustment=schedule.adjustment,
                start_date=schedule.start_date,
                end_date=end_date,
                overlap_days=schedule.overlap_days,
                trigger="scheduled",
            )
        )


class MarketDataSyncDiagnosticsService:
    def __init__(
        self,
        schedules: MarketDataSyncScheduleRepository,
        jobs: JobRepository,
    ):
        self.schedules = schedules
        self.jobs = jobs

    def status(self) -> dict[str, Any]:
        last_successful = self.jobs.last_successful("sync_market_data")
        recent_jobs = self.jobs.list(job_type="sync_market_data", limit=10)
        running_jobs = self.jobs.list(
            job_type="sync_market_data",
            status="running",
            limit=10,
        )
        recent_failures = self.jobs.list(
            job_type="sync_market_data",
            status="failed",
            limit=5,
        )
        return {
            "schedule": self.schedules.get().as_response(),
            "last_successful_sync_time": (
                last_successful.finished_at if last_successful is not None else None
            ),
            "last_successful_job": (
                last_successful.as_response() if last_successful is not None else None
            ),
            "running_jobs": [job.as_response() for job in running_jobs],
            "recent_failures": [job.as_response() for job in recent_failures],
            "recent_jobs": [job.as_response() for job in recent_jobs],
        }


def _schedule_from_row(row: sqlite3.Row) -> MarketDataSyncSchedule:
    return MarketDataSyncSchedule(
        id=row["id"],
        enabled=bool(row["enabled"]),
        provider=row["provider"],
        instrument_types=json.loads(row["instrument_types_json"]),
        adjustment=row["adjustment"],
        start_date=row["start_date"],
        overlap_days=row["overlap_days"],
        schedule_time=row["schedule_time"],
        timezone=row["timezone"],
        trading_days_only=bool(row["trading_days_only"]),
        updated_at=row["updated_at"],
    )
