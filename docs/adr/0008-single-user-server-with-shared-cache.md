# ADR 0008: Single-User Server With Shared Cache

## Status

Accepted

## Context

TradeMiner needs a deployment shape for its first version. One option is a purely local desktop or CLI tool where each invocation owns its own cache. Another option is a hosted multi-tenant service. A middle path is a single-user server application that can run on the user's machine or on a user-controlled server, with all clients sharing the server's Market Data Cache.

A shared cache avoids duplicated provider calls, aligns Backtests and current screening on the same data snapshot, and allows future web, CLI, and notebook clients to reuse one data service. A full SaaS architecture would add tenant isolation, account management, hostile-code sandboxing, data SLAs, and larger operational requirements before the core research workflow is proven.

## Decision

The first version will be designed as a single-user server application with a server-owned shared Market Data Cache.

The server can run locally on the user's machine or on a user-controlled server. The first version will not be a multi-tenant SaaS service.

## Consequences

Market Data synchronization, Strategy execution, Backtests, and result storage should be modeled as server-side capabilities rather than one-off client actions.

Clients can be added incrementally, such as CLI, local web UI, or notebooks, without changing the core cache ownership model.

Hosted multi-user operation remains a future architecture decision and must revisit tenant isolation, strategy sandboxing, user permissions, and operational reliability.
