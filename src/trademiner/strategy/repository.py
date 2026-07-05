from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from trademiner.strategy.discovery import StrategySource


@dataclass(frozen=True)
class StrategyVersionRecord:
    id: str
    strategy_id: str
    file_path: str
    name: str
    source_hash: str
    source_snapshot: str
    git_commit: str | None
    git_dirty: bool | None
    created_at: str

    def as_response(self) -> dict[str, object]:
        return {
            "source_hash": self.source_hash,
            "source_snapshot": self.source_snapshot,
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class StrategyRecord:
    strategy_id: str
    name: str
    description: str
    file_path: str
    params: dict[str, Any]
    latest_version: StrategyVersionRecord

    def as_response(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "file_path": self.file_path,
            "params": self.params,
            "latest_version": self.latest_version.as_response(),
        }


class StrategyRepository:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path

    def initialize(self) -> None:
        with self._connect() as connection:
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

    def upsert_source(self, source: StrategySource) -> StrategyRecord:
        self.initialize()
        metadata = source.metadata
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO strategies
                    (strategy_id, name, description, file_path, params_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(strategy_id)
                DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    file_path = excluded.file_path,
                    params_json = excluded.params_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    metadata.strategy_id,
                    metadata.name,
                    metadata.description,
                    str(source.file_path),
                    json.dumps(metadata.params, sort_keys=True),
                ),
            )
            existing_version = connection.execute(
                """
                SELECT id
                FROM strategy_versions
                WHERE strategy_id = ?
                  AND source_hash = ?
                """,
                (metadata.strategy_id, source.source_hash),
            ).fetchone()
            if existing_version is None:
                connection.execute(
                    """
                    INSERT INTO strategy_versions
                        (
                            id,
                            strategy_id,
                            file_path,
                            name,
                            source_hash,
                            source_snapshot,
                            git_commit,
                            git_dirty
                        )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        metadata.strategy_id,
                        str(source.file_path),
                        metadata.name,
                        source.source_hash,
                        source.source_snapshot,
                        source.git_commit,
                        _bool_to_int(source.git_dirty),
                    ),
                )
        return self.get(metadata.strategy_id)

    def list(self) -> list[StrategyRecord]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT strategy_id
                FROM strategies
                ORDER BY strategy_id
                """
            ).fetchall()
        return [self.get(row["strategy_id"]) for row in rows]

    def get(self, strategy_id: str) -> StrategyRecord:
        self.initialize()
        with self._connect() as connection:
            strategy_row = connection.execute(
                """
                SELECT strategy_id, name, description, file_path, params_json
                FROM strategies
                WHERE strategy_id = ?
                """,
                (strategy_id,),
            ).fetchone()
            if strategy_row is None:
                raise KeyError(strategy_id)
            version_row = connection.execute(
                """
                SELECT
                    id,
                    strategy_id,
                    file_path,
                    name,
                    source_hash,
                    source_snapshot,
                    git_commit,
                    git_dirty,
                    created_at
                FROM strategy_versions
                WHERE strategy_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (strategy_id,),
            ).fetchone()
        if version_row is None:
            raise KeyError(strategy_id)

        return StrategyRecord(
            strategy_id=strategy_row["strategy_id"],
            name=strategy_row["name"],
            description=strategy_row["description"],
            file_path=strategy_row["file_path"],
            params=json.loads(strategy_row["params_json"]),
            latest_version=StrategyVersionRecord(
                id=version_row["id"],
                strategy_id=version_row["strategy_id"],
                file_path=version_row["file_path"],
                name=version_row["name"],
                source_hash=version_row["source_hash"],
                source_snapshot=version_row["source_snapshot"],
                git_commit=version_row["git_commit"],
                git_dirty=_int_to_bool(version_row["git_dirty"]),
                created_at=version_row["created_at"],
            ),
        )

    def get_version(self, version_id: str) -> StrategyVersionRecord:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    strategy_id,
                    file_path,
                    name,
                    source_hash,
                    source_snapshot,
                    git_commit,
                    git_dirty,
                    created_at
                FROM strategy_versions
                WHERE id = ?
                """,
                (version_id,),
            ).fetchone()
        if row is None:
            raise KeyError(version_id)

        return StrategyVersionRecord(
            id=row["id"],
            strategy_id=row["strategy_id"],
            file_path=row["file_path"],
            name=row["name"],
            source_hash=row["source_hash"],
            source_snapshot=row["source_snapshot"],
            git_commit=row["git_commit"],
            git_dirty=_int_to_bool(row["git_dirty"]),
            created_at=row["created_at"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _int_to_bool(value: int | None) -> bool | None:
    if value is None:
        return None
    return bool(value)
