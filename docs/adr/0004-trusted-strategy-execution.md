# ADR 0004: Trusted Strategy Execution

## Status

Accepted

## Context

TradeMiner executes Python Strategy code. The first product could either run trusted local Strategy files for a single user, or expose a multi-user web surface where users submit arbitrary Python code.

Running arbitrary Python for multiple users would require strong sandboxing, filesystem isolation, network controls, resource limits, dependency controls, and careful secret handling. That work is important for a hosted product, but it is not necessary to prove the first research workflow.

## Decision

The first version will run trusted Strategy files for a single user. It may run on the user's machine or on a user-controlled server.

It will not expose a multi-tenant web interface for arbitrary Python code execution.

## Consequences

The first runtime can assume the user trusts the Strategy files they execute. Basic guardrails and clear execution boundaries are still useful, but strong hostile-code sandboxing is deferred.

A future hosted or collaborative version must revisit this decision before accepting untrusted Strategy code or strategies from multiple users.
