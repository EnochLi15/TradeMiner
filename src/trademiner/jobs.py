from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class JobRecord:
    id: str
    type: str
    status: str
    parameters: dict[str, Any]
    progress: dict[str, Any]
    error: str | None
    result_ref: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None

    def as_response(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "parameters": self.parameters,
            "progress": self.progress,
            "error": self.error,
            "result_ref": self.result_ref,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class JobRepository:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path

    def create_pending(self, job_type: str, parameters: dict[str, Any]) -> JobRecord:
        job_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, type, status, parameters_json, progress_json)
                VALUES (?, ?, 'pending', ?, '{}')
                """,
                (job_id, job_type, json.dumps(parameters, sort_keys=True)),
            )
        return self.get(job_id)

    def start(self, job_id: str) -> JobRecord:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    started_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (job_id,),
            )
        return self.get(job_id)

    def succeed(
        self,
        job_id: str,
        progress: dict[str, Any] | None = None,
        result_ref: str | None = None,
    ) -> JobRecord:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'succeeded',
                    progress_json = ?,
                    result_ref = ?,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(progress or {}, sort_keys=True), result_ref, job_id),
            )
        return self.get(job_id)

    def fail(self, job_id: str, error_message: str) -> JobRecord:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    error_message = ?,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (error_message, job_id),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    type,
                    status,
                    parameters_json,
                    progress_json,
                    error_message,
                    result_ref,
                    created_at,
                    started_at,
                    finished_at
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            raise KeyError(job_id)

        return self._record_from_row(row)

    def list(
        self,
        job_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[JobRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if job_type is not None:
            clauses.append("type = ?")
            params.append(job_type)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    type,
                    status,
                    parameters_json,
                    progress_json,
                    error_message,
                    result_ref,
                    created_at,
                    started_at,
                    finished_at
                FROM jobs
                {where}
                ORDER BY created_at DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def last_successful(self, job_type: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    type,
                    status,
                    parameters_json,
                    progress_json,
                    error_message,
                    result_ref,
                    created_at,
                    started_at,
                    finished_at
                FROM jobs
                WHERE type = ?
                  AND status = 'succeeded'
                ORDER BY finished_at DESC, rowid DESC
                LIMIT 1
                """,
                (job_type,),
            ).fetchone()
        if row is None:
            return None
        return self._record_from_row(row)

    def _record_from_row(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            type=row["type"],
            status=row["status"],
            parameters=json.loads(row["parameters_json"]),
            progress=json.loads(row["progress_json"]),
            error=row["error_message"],
            result_ref=row["result_ref"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection
