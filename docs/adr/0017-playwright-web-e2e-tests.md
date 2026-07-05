# ADR 0017: Playwright Web E2E Tests

## Status

Accepted

## Context

TradeMiner's Web UI is the primary surface for the first research loop. Unit and API tests cover backend behavior, but they do not prove that the browser page can synchronize Market Data, synchronize source Strategies, discover local Strategy files, parameterize and run a Strategy, run Backtests, inspect Result Snapshots, compare snapshots, or stay usable on mobile layouts.

The main alternatives are to keep relying on manual browser checks, use component-only tests, or add browser-level E2E tests that launch the FastAPI backend and Vite frontend together.

## Decision

TradeMiner will use Playwright for Web UI E2E tests.

The E2E test server maps the `akshare` provider name to a deterministic `FakeMarketDataProvider`, so browser tests exercise the same UI and API requests without calling external Market Data providers.

The E2E suite runs through `npm run test:e2e`. It starts isolated FastAPI and Vite servers on test-only ports and stores temporary data under `.tmp/e2e-data`.

## Consequences

The Web UI has an automated browser-level regression path for the core research loop and responsive Strategy management layout.

E2E tests can safely verify the manual Market Data synchronization button while avoiding external network, provider reliability, and rate-limit variability.

The test suite now has a browser dependency that must be installed with Playwright before E2E tests can run on a new machine or CI worker.
