# ADR 0003: Shared Strategy Runtime

## Status

Accepted

## Context

TradeMiner supports current screening and historical Backtests. These workflows could use separate execution engines, or they could run the same Strategy through different dated data contexts.

Separate engines would make each workflow easier to optimize independently, but they risk behavioral drift: a Strategy could select Candidates one way during current screening and behave differently during Backtests.

## Decision

Current screening and historical Backtests will share one Strategy Runtime.

The Strategy Runtime executes a Strategy against a read-only dated Market Data context. Current screening uses the latest eligible trading date, while a Backtest iterates the same Strategy across historical trading dates.

## Consequences

The Strategy context must make time explicit, usually through an as-of trading date. Data access must prevent future leakage during Backtests.

Runtime correctness becomes a shared foundation for both product workflows, so tests should cover equivalent behavior between current screening and Backtest execution.
