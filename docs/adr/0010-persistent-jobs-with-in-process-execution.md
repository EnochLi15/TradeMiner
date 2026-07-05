# ADR 0010: Persistent Jobs With In-Process Execution

## Status

Accepted

## Context

TradeMiner has long-running operations: Market Data synchronization, Strategy execution, and Selection Backtests. These operations need to be visible from the Web UI and CLI, including progress, failure details, and result references.

A dedicated worker and queue such as Celery, RQ, Redis, or a database-backed queue would provide stronger concurrency, retries, cancellation, and crash recovery. Starting there adds operational parts before the first single-user workflow needs them.

## Decision

TradeMiner will model long-running operations as persistent Jobs.

A Job records at least its id, type, status, parameters, progress, timing, error details, and result reference.

The first executor may run Jobs in process inside the server.

## Consequences

The Web UI and CLI can show durable Job status even though execution starts simple.

The domain model stays compatible with a future dedicated worker and queue because Jobs already exist as persistent records.

In-process execution is acceptable for the first version, but crash recovery, concurrent workload isolation, robust cancellation, and distributed execution are deferred.
