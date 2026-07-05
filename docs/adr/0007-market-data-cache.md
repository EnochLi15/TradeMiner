# ADR 0007: Market Data Cache

## Status

Accepted

## Context

TradeMiner uses AkShare as the first Data Provider, but Strategies and Backtests need reproducible, fast, and stable Market Data access. Running Strategies directly against AkShare would make results depend on network availability, provider response time, provider schema drift, and request limits.

## Decision

TradeMiner will use a normalized Market Data Cache owned by the TradeMiner runtime.

Data Providers update the Market Data Cache. Strategies, current screening, and Backtests read through TradeMiner's Market Data interface backed by that cache rather than calling a provider directly.

## Consequences

Backtests can run against a stable data snapshot and avoid repeated network calls.

The Market Data layer must include update, normalization, freshness, and cache invalidation behavior. It must support incremental updates, overlapping refresh windows, and idempotent upserts keyed by Instrument, date, data type, and adjustment mode.

ADR 0009 chooses DuckDB and Parquet as the first-version Market Data Cache storage model.
