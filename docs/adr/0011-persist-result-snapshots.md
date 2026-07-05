# ADR 0011: Persist Result Snapshots

## Status

Accepted

## Context

TradeMiner users need to compare Strategy Runs and Backtests over time. Results can change if Strategy code changes, Market Data is refreshed, adjustment behavior changes, or provider schemas drift.

Only storing run parameters and recomputing results later would make past research hard to audit and compare.

## Decision

TradeMiner will persist immutable Result Snapshots for Strategy Runs and Backtests.

A Strategy Run snapshot records the Strategy version, as-of date, parameters, Candidate outputs, score and explanation fields, and Market Data snapshot reference.

A Backtest snapshot records the Strategy version, date range, selection dates, top N, horizons, per-date Candidates, performance metrics, and Market Data snapshot reference.

## Consequences

Past research results can be compared and reproduced even after Strategy code or Market Data changes.

The system needs a Strategy versioning model and a way to reference the Market Data snapshot used by a run.

Storage growth must be managed over time, but first-version correctness and traceability take priority.
