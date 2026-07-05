# ADR 0016: Source Strategy Library

## Status

Accepted

## Context

TradeMiner Strategies are code-defined and versioned from source snapshots. The first Web UI already supports listing, inspecting, selecting, and running discovered Strategy files, but requiring a user-entered filesystem path makes Strategy management easy to miss and weakens the expectation that shared first-version Strategies live with the application source.

The main alternatives are to keep only manual path discovery, store Strategy definitions in the application data directory, add an in-browser Strategy editor, or keep a repository-owned Strategy source library that the API can sync into the metadata store.

## Decision

TradeMiner will keep repository-owned first-version Strategy source files under `src/trademiner/strategies`.

The API exposes a source Strategy synchronization endpoint that reads that directory, parses Strategy metadata, snapshots the source, and upserts the Strategy records into SQLite using the same Strategy Version model as manually discovered files.

The Web UI treats this source Strategy library as the primary Strategy management entry point. Manual path discovery remains available for local research Strategies outside the repository.

## Consequences

Users can open the Web UI and immediately synchronize, inspect, select, parameterize, and run Strategies that are co-developed with the application source.

Built-in and manually discovered Strategies share one Strategy Runtime, parameter validation path, source snapshot model, and Result Snapshot lineage.

Repository-owned Strategies should stay small, explicit, and coupled only to the public `StrategyContext` API. They must not call provider-specific APIs, SQLite, DuckDB, or AkShare directly.

Moving to a collaborative or hosted Strategy authoring model would require a new architecture decision for permissions, review, sandboxing, and source ownership.
