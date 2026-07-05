# ADR 0014: Manual and Scheduled Market Data Sync

## Status

Accepted

## Context

TradeMiner's Market Data Cache must stay fresh without making Strategies or Backtests call Data Providers directly. Users need explicit control during research, and a server deployment should also be able to refresh data automatically after the market close.

## Decision

The first version will support both manual and configurable scheduled Market Data synchronization.

Manual synchronization can be triggered from the Web UI or CLI.

Scheduled synchronization can run after the relevant market close time, such as a configurable post-close schedule for A-share and ETF data.

Synchronization uses Sync Cursors, overlapping refresh windows, and idempotent upserts into the Market Data Cache.

## Consequences

Users can force-refresh data before a Strategy Run or Backtest.

The server can keep shared Market Data reasonably fresh without requiring manual action every day.

The first scheduler can remain lightweight, but synchronization must still be represented as persistent Jobs with progress, errors, and result references.
