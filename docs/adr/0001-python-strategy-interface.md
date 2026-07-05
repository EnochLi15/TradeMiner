# ADR 0001: Python Strategy Interface

## Status

Accepted

## Context

TradeMiner needs a first strategy authoring model for screening and ranking A-share stocks and ETFs. The main alternatives are a Python strategy interface, a custom domain-specific language, or a visual strategy builder.

Python fits the expected research workflow and keeps the first version close to the data analysis and backtesting ecosystem. A custom language or visual builder could become useful later, but would add language design, compilation, validation, and UI complexity before the core research loop is proven.

## Decision

The first version will support code-defined Strategies written as Python functions. TradeMiner will provide a read-only strategy context, and a Strategy will return Candidates containing selected Instruments, ranking data, and explanation fields.

## Consequences

TradeMiner's initial runtime, sandboxing, test harness, and backtesting engine must support executing Python strategy code safely and reproducibly.

This decision defers a custom DSL and visual strategy builder. They may be revisited after the Python strategy model proves the core workflow.
