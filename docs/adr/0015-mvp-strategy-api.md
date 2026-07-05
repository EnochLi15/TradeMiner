# ADR 0015: MVP Strategy API

## Status

Accepted

## Context

TradeMiner needs a concrete Python Strategy API for the MVP. The API must support current screening and Selection Backtests through the shared Strategy Runtime, allow the Web UI and CLI to pass parameters, prevent provider-specific coupling, and keep future data from leaking into Backtests.

A large framework-style API would add complexity before the first research loop is proven. A completely unstructured function would make UI generation, validation, persistence, and reproducibility harder.

## Decision

The MVP Strategy API uses a Python function:

```python
def select(ctx: StrategyContext, params: dict) -> list[Candidate]:
    ...
```

A Strategy file may define `STRATEGY` metadata with id, name, description, and parameter definitions.

`StrategyContext` is read-only and bound to an as-of trading date. It exposes Instrument universe access, Daily Bar access, derived indicator access, and validated parameters. Data access defaults to data available on or before the as-of date.

`Candidate` requires `instrument_id`, `score`, and `explanation`. It may include `rank_basis`, `tags`, and `metrics`.

Strategies must not call AkShare, DuckDB, SQLite, or provider-specific APIs directly.

## Consequences

The Web UI can generate parameter forms and display Candidate explanations and metrics.

The Strategy Runtime can use the same API for current screening and historical Selection Backtests.

The first API stays small while preserving a path to richer metadata, parameter types, and result fields later.
