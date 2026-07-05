# ADR 0005: Selection Backtest First

## Status

Accepted

## Context

TradeMiner needs historical evaluation for Strategies. One option is a Selection Backtest that measures how selected Candidates perform after each historical selection date. Another option is a full Portfolio Backtest that simulates orders, fills, cash, positions, rebalancing, fees, slippage, stop rules, and an equity curve.

The first Strategy boundary is screening and ranking, not trade execution or portfolio management. A full Portfolio Backtest would pull the project toward a trading system before the opportunity discovery workflow is proven.

## Decision

The first version will support Selection Backtests.

For each historical selection date, TradeMiner runs the Strategy, takes top-ranked Candidates, and measures future return, win rate, drawdown, and benchmark-relative behavior over fixed horizons such as 1, 5, 10, and 20 trading days.

Full Portfolio Backtests are deferred.

## Consequences

The first Backtest model does not need to simulate order placement, fills, cash, position sizing, fees, slippage, stop rules, or rebalancing.

Selection Backtest results should be presented as evidence about Strategy selection quality, not as a promise of executable portfolio returns.
