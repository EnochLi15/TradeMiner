# ADR 0012: Strategy Source Versioning

## Status

Accepted

## Context

TradeMiner persists Strategy Runs and Backtests as Result Snapshots. To make those snapshots reproducible, each run must know exactly which Strategy source was executed.

Using only a file path or Strategy name would be ambiguous because the file can change after a run. Requiring a full Git platform from the first version would add workflow complexity that is not necessary for a single-user server application.

## Decision

TradeMiner will create a Strategy Version record whenever a Strategy is executed.

The Strategy Version records the Strategy id, Strategy file path, Strategy name, source hash, source snapshot, and creation time.

If the Strategy is inside a Git worktree, TradeMiner also records the Git commit and whether the worktree was dirty.

## Consequences

Historical Result Snapshots can identify the exact Strategy source used even if the file later changes.

The first version does not need a full Git hosting or experiment-management system.

Storage grows with saved Strategy source snapshots, but first-version traceability is more important than minimizing metadata size.
