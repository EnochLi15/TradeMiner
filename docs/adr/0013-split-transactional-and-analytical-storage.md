# ADR 0013: Split Transactional and Analytical Storage

## Status

Accepted

## Context

TradeMiner stores two different kinds of data.

Application metadata and operational state are small, transactional records such as Strategies, Strategy Versions, Jobs, sync cursors, settings, and Result Snapshot indexes.

Market Data, indicators, Candidate tables, and Backtest detail rows are analytical data. They are usually scanned by date and Instrument, read by column, aggregated, sorted, and appended or refreshed in batches.

Using one storage engine for both workloads would force either analytical scans into a row-oriented transactional database or operational state into a file-based analytical layout.

## Decision

TradeMiner will split first-version storage by workload.

SQLite stores application metadata and transactional state.

DuckDB and Parquet store Market Data, indicator data, large Candidate tables, Backtest detail rows, and analytical Result Snapshot payloads.

## Consequences

SQLite can provide simple durable state for the single-user server without requiring a separate database server.

DuckDB and Parquet can provide efficient local analytical reads for daily bars, indicators, and Backtest outputs.

The application must maintain references between SQLite metadata rows and analytical artifacts stored in DuckDB and Parquet.

Backups and migrations must account for both stores.
