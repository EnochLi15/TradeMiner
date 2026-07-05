from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb

from trademiner.market_data.models import DailyBar, Instrument, SyncCursor


class MarketDataCache:
    def __init__(self, duckdb_path: Path, sqlite_path: Path):
        self.duckdb_path = duckdb_path
        self.sqlite_path = sqlite_path
        self.initialize()

    def initialize(self) -> None:
        with self._duckdb() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS instruments (
                    instrument_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    instrument_type TEXT NOT NULL,
                    exchange TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_bars (
                    instrument_id TEXT NOT NULL,
                    trade_date DATE NOT NULL,
                    adjustment TEXT NOT NULL,
                    open DOUBLE NOT NULL,
                    high DOUBLE NOT NULL,
                    low DOUBLE NOT NULL,
                    close DOUBLE NOT NULL,
                    volume DOUBLE NOT NULL,
                    amount DOUBLE,
                    PRIMARY KEY (instrument_id, trade_date, adjustment)
                )
                """
            )

        with self._sqlite() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_cursors (
                    provider TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    adjustment TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    last_synced_trade_date TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (provider, data_type, adjustment, scope)
                )
                """
            )

    def upsert_instruments(self, instruments: list[Instrument]) -> int:
        if not instruments:
            return 0
        with self._duckdb() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO instruments
                    (instrument_id, symbol, name, instrument_type, exchange)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        instrument.instrument_id,
                        instrument.symbol,
                        instrument.name,
                        instrument.instrument_type,
                        instrument.exchange,
                    )
                    for instrument in instruments
                ],
            )
        return len(instruments)

    def upsert_daily_bars(self, bars: list[DailyBar]) -> int:
        if not bars:
            return 0
        with self._duckdb() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO daily_bars
                    (
                        instrument_id,
                        trade_date,
                        adjustment,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        amount
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        bar.instrument_id,
                        bar.trade_date,
                        bar.adjustment,
                        bar.open,
                        bar.high,
                        bar.low,
                        bar.close,
                        bar.volume,
                        bar.amount,
                    )
                    for bar in bars
                ],
            )
        return len(bars)

    def list_instruments(self) -> list[Instrument]:
        with self._duckdb() as connection:
            rows = connection.execute(
                """
                SELECT instrument_id, symbol, name, instrument_type, exchange
                FROM instruments
                ORDER BY instrument_id
                """
            ).fetchall()
        return [
            Instrument(
                instrument_id=row[0],
                symbol=row[1],
                name=row[2],
                instrument_type=row[3],
                exchange=row[4],
            )
            for row in rows
        ]

    def list_daily_bars(
        self,
        instrument_id: str | None = None,
        adjustment: str | None = None,
    ) -> list[DailyBar]:
        clauses: list[str] = []
        params: list[str] = []
        if instrument_id is not None:
            clauses.append("instrument_id = ?")
            params.append(instrument_id)
        if adjustment is not None:
            clauses.append("adjustment = ?")
            params.append(adjustment)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._duckdb() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    instrument_id,
                    CAST(trade_date AS VARCHAR),
                    adjustment,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    amount
                FROM daily_bars
                {where}
                ORDER BY instrument_id, trade_date
                """,
                params,
            ).fetchall()
        return [
            DailyBar(
                instrument_id=row[0],
                trade_date=row[1],
                adjustment=row[2],
                open=row[3],
                high=row[4],
                low=row[5],
                close=row[6],
                volume=row[7],
                amount=row[8],
            )
            for row in rows
        ]

    def trade_dates(
        self,
        adjustment: str = "hfq",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        clauses = ["adjustment = ?"]
        params: list[str] = [adjustment]
        if start_date is not None:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date is not None:
            clauses.append("trade_date <= ?")
            params.append(end_date)

        with self._duckdb() as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT CAST(trade_date AS VARCHAR)
                FROM daily_bars
                WHERE {' AND '.join(clauses)}
                ORDER BY trade_date
                """,
                params,
            ).fetchall()
        return [row[0] for row in rows]

    def get_cursor(
        self,
        provider: str,
        data_type: str,
        adjustment: str,
        scope: str,
    ) -> SyncCursor | None:
        with self._sqlite() as connection:
            row = connection.execute(
                """
                SELECT provider, data_type, adjustment, scope, last_synced_trade_date
                FROM sync_cursors
                WHERE provider = ?
                  AND data_type = ?
                  AND adjustment = ?
                  AND scope = ?
                """,
                (provider, data_type, adjustment, scope),
            ).fetchone()
        if row is None:
            return None
        return SyncCursor(
            provider=row["provider"],
            data_type=row["data_type"],
            adjustment=row["adjustment"],
            scope=row["scope"],
            last_synced_trade_date=row["last_synced_trade_date"],
        )

    def upsert_cursor(self, cursor: SyncCursor) -> None:
        with self._sqlite() as connection:
            connection.execute(
                """
                INSERT INTO sync_cursors
                    (provider, data_type, adjustment, scope, last_synced_trade_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider, data_type, adjustment, scope)
                DO UPDATE SET
                    last_synced_trade_date = excluded.last_synced_trade_date,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    cursor.provider,
                    cursor.data_type,
                    cursor.adjustment,
                    cursor.scope,
                    cursor.last_synced_trade_date,
                ),
            )

    def list_cursors(self) -> list[SyncCursor]:
        with self._sqlite() as connection:
            rows = connection.execute(
                """
                SELECT provider, data_type, adjustment, scope, last_synced_trade_date
                FROM sync_cursors
                ORDER BY provider, data_type, adjustment, scope
                """
            ).fetchall()
        return [
            SyncCursor(
                provider=row["provider"],
                data_type=row["data_type"],
                adjustment=row["adjustment"],
                scope=row["scope"],
                last_synced_trade_date=row["last_synced_trade_date"],
            )
            for row in rows
        ]

    def incremental_start_date(
        self,
        provider: str,
        adjustment: str,
        instrument_id: str,
        requested_start_date: str,
        overlap_days: int,
    ) -> str:
        cursor = self.get_cursor(provider, "daily_bars", adjustment, instrument_id)
        if cursor is None:
            return requested_start_date

        overlap = max(overlap_days, 1)
        with self._duckdb() as connection:
            row = connection.execute(
                """
                SELECT CAST(trade_date AS VARCHAR)
                FROM daily_bars
                WHERE instrument_id = ?
                  AND adjustment = ?
                  AND trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT 1 OFFSET ?
                """,
                (
                    instrument_id,
                    adjustment,
                    cursor.last_synced_trade_date,
                    overlap - 1,
                ),
            ).fetchone()

        if row is None:
            return cursor.last_synced_trade_date
        return max(requested_start_date, str(row[0]))

    def latest_trade_date(self, adjustment: str = "hfq") -> str | None:
        with self._duckdb() as connection:
            row = connection.execute(
                """
                SELECT CAST(MAX(trade_date) AS VARCHAR)
                FROM daily_bars
                WHERE adjustment = ?
                """,
                (adjustment,),
            ).fetchone()
        if row is None:
            return None
        return row[0]

    def _duckdb(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.duckdb_path))

    def _sqlite(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection
