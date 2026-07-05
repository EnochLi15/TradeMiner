# Architecture

This directory is the durable architecture memory for TradeMiner. Codex and contributors must read this documentation before architecture-related work and update it whenever architecture context changes.

## Current State

TradeMiner has an MVP application shell in progress. The implemented slices include a FastAPI backend, React/Vite/TypeScript Web UI shell, Typer CLI, configurable TradeMiner data directory, SQLite application metadata store, DuckDB and Parquet analytical store locations, persistent Job records, the first Market Data synchronization loop, repository-owned source Strategy synchronization with source versioning, current Strategy Runs with persisted Candidate snapshots, Selection Backtests with persisted summary/result snapshots, Result Snapshot browsing and comparison, scheduled Market Data synchronization plus runtime diagnostics, and Playwright Web UI E2E tests for the core research loop.

## Product Direction

TradeMiner is being explored as a trading opportunity mining assistant. The initial product direction is to help a user define code-based selection strategies, execute those strategies to identify promising instruments, and backtest strategy behavior before use.

The initial market scope is A-share stocks and ETFs. Futures and digital assets are possible future extensions, but they are not part of the first architecture scope until explicitly accepted.

## Current Architecture Constraints

- A Strategy is code-defined screening and ranking logic. It can select candidate instruments from market data and explain the selection, but the first version does not include order placement, position management, portfolio rebalancing, or live trade execution.
- First-version Strategy code is written as a Python function. TradeMiner provides a read-only strategy context, and the Strategy returns Candidates with ranking and explanation fields.
- First-version Market Data is limited to daily adjusted bars, basic Instrument metadata, and commonly used technical indicators. Minute data, order book data, tick data, news, research reports, capital flow data, financial factors, announcements, and sentiment are outside the first architecture scope.
- Current screening and historical Backtests use the same Strategy Runtime. The Strategy is evaluated through a dated read-only data context, where current screening uses the latest eligible trading date and Backtests iterate across historical trading dates.
- The first version defines "best" through each Strategy's own score. TradeMiner sorts, displays, compares, and backtests Candidates, but it does not add a separate platform-level black-box ranking model.
- The first version is a single-user server application that can run on the user's machine or on a user-controlled server. It runs trusted Strategy files and does not expose a multi-tenant SaaS surface for arbitrary Python code execution.
- First-version Backtests are Selection Backtests. They run a Strategy on historical selection dates, take top-ranked Candidates, and measure future return, win rate, drawdown, and benchmark-relative behavior over fixed horizons.
- AkShare is the default first-version Data Provider for A-share and ETF Market Data. Strategy and Backtest code must depend on TradeMiner's Market Data interface rather than calling AkShare directly.
- Strategies and Backtests read Market Data through a server-owned shared Market Data Cache. Data Providers update the cache incrementally; they are not called directly during Strategy execution.
- The first-version Market Data Cache supports incremental updates, overlapping refresh windows, and idempotent upserts keyed by Instrument, date, data type, and adjustment mode.
- The first-version user experience is Web UI first and CLI second. The Web UI is the primary place to select or edit Strategies, run screening, inspect Candidates, and review Backtest results. The CLI supports cache updates, batch runs, debugging, and automation.
- First-version Strategy code editing happens in local files and external editors or IDEs. Repository-owned first-version Strategies live under `src/trademiner/strategies` and are synchronized from source into the metadata store. The Web UI can synchronize source Strategies, list, inspect, select, parameterize, run, and show Strategy source snapshots, but it does not need an in-browser code editor in the first version.
- The first-version backend is Python with FastAPI. The frontend is React, Vite, and TypeScript. The Market Data Cache uses DuckDB and Parquet. The CLI uses Typer. Background work starts with in-process server jobs and can later move to a dedicated worker system if durability or concurrency requires it.
- Browser-level Web UI regression testing uses Playwright. E2E tests start isolated FastAPI and Vite servers and map the `akshare` provider name to a deterministic fake provider so page workflows do not depend on external Market Data providers.
- First-version storage is split by workload: SQLite stores application metadata and transactional state, while DuckDB and Parquet store Market Data, indicator data, and large analytical Result Snapshot payloads.
- Market Data synchronization, Strategy execution, and Backtest execution are represented as persistent Jobs with status, parameters, progress, error details, timing, and result references. The first executor can run these Jobs in process.
- Strategy Runs and Backtests persist immutable Result Snapshots. Each snapshot records the Strategy version, parameters, relevant dates, Candidate outputs, metrics, and a Market Data snapshot reference so results can be compared and reproduced after Strategy code or Market Data changes.
- Strategy Versions are identified by Strategy id, file path, name, source hash, source snapshot, creation time, and optional Git commit and dirty-worktree metadata.
- Market Data synchronization can be triggered manually or by a configurable schedule. Synchronization uses Sync Cursors and overlapping refresh windows to incrementally update the Market Data Cache.
- The MVP Strategy API uses a Python `select(ctx, params)` function with optional `STRATEGY` metadata. `StrategyContext` is read-only and as-of-date bound. Strategies return Candidates with required `instrument_id`, `score`, and `explanation` fields plus optional `rank_basis`, `tags`, and `metrics`.
- The first PRD build slice is the minimum research loop: synchronize Market Data, discover or register a Strategy, run current screening, inspect Candidates, run a Selection Backtest, and inspect the saved Result Snapshot.
- The default first-version Market Data freshness policy is manual synchronization plus a configurable scheduled synchronization, defaulting to 16:30 Asia/Shanghai on trading days for A-share and ETF data.

## Working Module Map

- Strategy Runtime: loads trusted Python Strategy files, records Strategy Versions, and executes saved source snapshots against a dated, read-only Market Data context. Discovery currently parses `STRATEGY` metadata from trusted Python files, including repository-owned source Strategies under `src/trademiner/strategies`, stores source hashes and source snapshots, and records optional Git commit and dirty-worktree metadata. Current Strategy Runs validate parameters, create persistent Jobs, execute `select(ctx, params)`, sort returned Candidates by Strategy score, and persist the immutable run snapshot.
- Market Data: exposes the stable data interface used by Strategies and Backtests, backed by a server-owned shared Market Data Cache that is updated through replaceable Data Provider adapters. The first implemented sync loop supports AkShare as the default provider, fake provider tests, Sync Cursors, incremental updates, overlapping refresh windows, idempotent upserts, a configurable scheduled sync plan, and runtime diagnostics over recent sync Jobs.
- Backtest: runs Selection Backtests by iterating historical selection dates through the shared Strategy Runtime and measuring Candidate outcomes. The implemented Selection Backtest takes a date range, top N, horizons, Strategy parameters, adjustment mode, and optional benchmark instrument, then computes future return, win rate, max drawdown, benchmark return, and excess return by horizon.
- Results: stores immutable Result Snapshots, sorts and displays Strategy-defined Candidate scores, and compares Backtest metrics. The implemented Strategy Run snapshot stores Strategy Version metadata, validated parameters, as-of date, adjustment mode, Market Data snapshot reference, and Candidate JSON. The implemented Selection Backtest snapshot stores Strategy Version metadata, date range, selection dates, top N, horizons, optional benchmark config, per-date Candidates, per-horizon observations, summary metrics, and Market Data snapshot reference. Result Snapshot browsing reads persisted snapshots without recomputing Strategy code, and comparison computes Strategy Run score deltas or Backtest metric deltas across saved snapshots of the same type.
- Application Metadata Store: SQLite database for Strategies, Strategy Versions, Jobs, run indexes, settings, sync cursors, and lightweight Result Snapshot metadata. The implemented schema includes persistent Jobs, Strategies, Strategy Versions, Sync Cursors, Strategy Runs, Selection Backtests, and Sync Schedules.
- Analytical Store: DuckDB and Parquet storage for Market Data, indicators, large Candidate tables, Backtest detail rows, and analytical Result Snapshot payloads.
- Web UI: primary interactive surface for source Strategy synchronization, Strategy listing, inspection, parameterization, selection, screening results, Candidate explanation, and Backtest review.
- CLI: operational and automation surface for cache synchronization, Strategy runs, Backtests, and diagnostics.
- API Server: FastAPI application exposing Strategy, Market Data, screening, Backtest, and result workflows to the Web UI and CLI.
- Job Execution: persistent Job records with an in-process first executor for cache synchronization, scheduled synchronization triggers, screening runs, and Selection Backtests. The scheduled sync service is a thin orchestrator over the manual Market Data sync service so a future worker or queue can replace the trigger without changing sync semantics.
- E2E Testing: Playwright browser tests launch a deterministic FastAPI test server and Vite frontend, exercise the full Web UI research loop, and verify mobile layout constraints for Strategy management and Result Snapshot browsing.

## Implemented Entry Points

- API: `/api/system/status` reports server status and storage initialization. `/api/jobs` creates a pending Job record, and `/api/jobs/{job_id}` reads it back. `/api/market-data/sync` runs manual Market Data synchronization, while `/api/market-data/sync-schedule`, `/api/market-data/sync-schedule/run`, and `/api/market-data/sync-diagnostics` expose schedule configuration, scheduled trigger execution, and sync diagnostics. `/api/market-data/instruments`, `/api/market-data/daily-bars`, and `/api/market-data/sync-cursors` expose cached Market Data and Sync Cursor state. `/api/strategy-runs` creates and lists current Strategy Run snapshots, and `/api/strategy-runs/{strategy_run_id}` reads the persisted run snapshot. `/api/selection-backtests` creates and lists Selection Backtest snapshots, and `/api/selection-backtests/{selection_backtest_id}` reads the persisted Backtest snapshot. `/api/result-snapshots/compare` compares saved snapshots of the same type without recomputing results.
- CLI: `trademiner status --data-dir <path>` initializes storage and reports system status. `trademiner sync-market-data` triggers Market Data synchronization, and `trademiner sync-status` reports schedule and recent sync diagnostics. `trademiner discover-strategies` records trusted Strategy files, `trademiner run-strategy` executes a current Strategy Run, and `trademiner run-selection-backtest` executes a Selection Backtest.
- E2E: `npm run test:e2e` runs Playwright against isolated test servers using `.tmp/e2e-data`.
- Strategy API: `/api/strategies/sync-source` synchronizes repository-owned Strategy source files from `src/trademiner/strategies`, `/api/strategies/discover` discovers trusted Python Strategy files from explicit paths, `/api/strategies` lists Strategy metadata, `/api/strategies/{strategy_id}` returns detail, and `/api/strategies/{strategy_id}/validate-parameters` validates run parameters against Strategy metadata.
- Web UI: the MVP shell fetches `/api/system/status`, displays the backend status and storage paths, provides a manual Market Data synchronization control plus sync diagnostics, synchronizes repository-owned source Strategies, lets the user discover additional local Strategies, inspect metadata, edit run parameters, choose a Strategy, inspect source hash, Git metadata, and source snapshots, runs the selected Strategy to display persisted Candidates with scores, rank basis, tags, metrics, and explanations, runs a Selection Backtest with the same Strategy parameters to display persisted summary metrics by horizon, and provides a Result Snapshot browser for saved Strategy Runs, Backtests, details, per-date Backtest rows, and same-type comparisons.

## Strategy API

The first Strategy API keeps Strategy files small and explicit:

```python
from trademiner.strategy import Candidate, StrategyContext

STRATEGY = {
    "id": "momentum_breakout_v1",
    "name": "Momentum Breakout",
    "description": "Ranks instruments by recent momentum and volume confirmation.",
    "params": {
        "lookback_days": {"type": "int", "default": 60, "min": 20, "max": 250},
        "top_n": {"type": "int", "default": 20, "min": 1, "max": 100},
    },
}

def select(ctx: StrategyContext, params: dict) -> list[Candidate]:
    ...
```

`StrategyContext` is read-only and date-bound. It exposes the Strategy's `as_of` trading date, validated parameters, Instrument universe access, Daily Bar access, and derived indicator access. Data access defaults to values available on or before `as_of` so Backtests do not leak future data into Strategy logic.

`Candidate` requires at least `instrument_id`, `score`, and `explanation`. It may also include `rank_basis`, `tags`, and a `metrics` dictionary for values the Web UI should show beside the Candidate.

Strategies should not call AkShare, DuckDB, SQLite, or provider-specific APIs directly. They should compute with data returned by `StrategyContext` and return Candidates.

Repository-owned first-version Strategies are stored as source files in `src/trademiner/strategies`. The source Strategy synchronization endpoint reads those files, snapshots their source, and persists Strategy metadata through the same Strategy Version records used for manually discovered Strategy files.

## Discovery Notes

The following architecture questions are still open:

- Job durability boundary: when in-process jobs should be replaced by a dedicated worker and queue.

## Required Updates

Update this document when any of the following become known or change:

- System responsibilities and boundaries
- Module or package structure
- Data model and data flow
- External integrations and APIs
- Runtime, deployment, or infrastructure topology
- Cross-cutting constraints such as security, observability, reliability, and performance

## Architecture Index

- MVP PRD: https://github.com/EnochLi15/TradeMiner/issues/1
- Architecture decisions: `../adr/`
- ADR 0001: `../adr/0001-python-strategy-interface.md`
- ADR 0002: `../adr/0002-daily-adjusted-market-data-first.md`
- ADR 0003: `../adr/0003-shared-strategy-runtime.md`
- ADR 0004: `../adr/0004-trusted-strategy-execution.md`
- ADR 0005: `../adr/0005-selection-backtest-first.md`
- ADR 0006: `../adr/0006-akshare-default-data-provider.md`
- ADR 0007: `../adr/0007-market-data-cache.md`
- ADR 0008: `../adr/0008-single-user-server-with-shared-cache.md`
- ADR 0009: `../adr/0009-first-version-application-stack.md`
- ADR 0010: `../adr/0010-persistent-jobs-with-in-process-execution.md`
- ADR 0011: `../adr/0011-persist-result-snapshots.md`
- ADR 0012: `../adr/0012-strategy-source-versioning.md`
- ADR 0013: `../adr/0013-split-transactional-and-analytical-storage.md`
- ADR 0014: `../adr/0014-manual-and-scheduled-market-data-sync.md`
- ADR 0015: `../adr/0015-mvp-strategy-api.md`
- ADR 0016: `../adr/0016-source-strategy-library.md`
- ADR 0017: `../adr/0017-playwright-web-e2e-tests.md`
