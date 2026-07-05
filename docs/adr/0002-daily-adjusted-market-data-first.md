# ADR 0002: Daily Adjusted Market Data First

## Status

Accepted

## Context

TradeMiner needs a first market data scope for screening and backtesting A-share stocks and ETFs. Possible scopes include daily bars, minute bars, order book data, tick data, fundamentals, news, research reports, capital flow data, announcements, and sentiment.

Daily adjusted bars are enough to support an initial research loop around momentum, trend, volatility, volume, breakout, and drawdown strategies. Starting with a larger data surface would add ingestion, storage, alignment, latency, and backtest correctness work before the first selection workflow is proven.

## Decision

The first version will use daily adjusted bars, basic Instrument metadata, and commonly used technical indicators as the Market Data available to Strategies.

Minute data, order book data, tick data, news, research reports, capital flow data, financial factors, announcements, and sentiment are deferred.

## Consequences

The first Strategy and backtesting interfaces should be designed around daily trading dates rather than intraday timestamps.

The data layer should leave room for future data families, but it does not need to ingest or model them in the first version.
