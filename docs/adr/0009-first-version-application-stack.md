# ADR 0009: First-Version Application Stack

## Status

Accepted

## Context

TradeMiner's first version is a single-user server application with a Web UI primary surface, a CLI secondary surface, Python Strategies, AkShare ingestion, a shared Market Data Cache, and Selection Backtests.

The stack should keep Strategy execution, data ingestion, indicators, and Backtests close to Python while still supporting a rich interactive UI for reviewing Candidates and Backtest results.

Alternatives include a notebook-only tool, a pure CLI tool, a Python-only web UI framework, a JavaScript backend, a PostgreSQL-based service stack, or a larger distributed job system from the start.

## Decision

The first-version stack is:

- Backend: Python and FastAPI.
- Frontend: React, Vite, and TypeScript.
- Application metadata store: SQLite.
- Market Data Cache: DuckDB and Parquet.
- CLI: Typer.
- Background jobs: in-process server jobs first.

## Consequences

Python remains the center of Strategy execution, AkShare integration, data normalization, indicators, and Backtests.

The Web UI can provide a richer product experience for Strategy selection, Candidate review, explanations, and Backtest visualizations than a CLI-only or notebook-only workflow.

DuckDB and Parquet provide a lightweight analytical storage model suitable for daily bars and local or self-hosted single-user operation without requiring a separate database server.

SQLite provides a lightweight transactional store for Jobs, Strategy Versions, settings, sync cursors, and Result Snapshot indexes.

In-process jobs keep the first implementation simple, but long-running cache updates and Backtests may later require a dedicated worker and queue if concurrency, cancellation, retry, or crash recovery becomes important.
