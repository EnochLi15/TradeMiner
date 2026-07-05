# ADR 0006: AkShare Default Data Provider

## Status

Accepted

## Context

TradeMiner needs a first Data Provider for A-share stocks and ETFs. The first-version Market Data scope is daily adjusted bars, basic Instrument metadata, and common technical indicators.

AkShare provides documented interfaces for A-share daily historical data and ETF daily historical data, including adjustment options. It is quick to adopt for a local MVP, but it should not become part of the Strategy or Backtest contract because future versions may use Tushare, JoinQuant, Ricequant, Wind, exchange data, or local analytical files.

References:

- AkShare A-share stock data: https://akshare.akfamily.xyz/data/stock/stock.html
- AkShare public fund and ETF data: https://akshare.akfamily.xyz/data/fund/fund_public.html

## Decision

AkShare will be the default first-version Data Provider.

TradeMiner will access AkShare behind a replaceable Market Data adapter. Strategies and Backtests must depend on TradeMiner's Market Data interface rather than importing or calling AkShare directly.

## Consequences

The first implementation can move quickly with public A-share and ETF data.

The Market Data interface must normalize AkShare responses into TradeMiner's own Instrument and Daily Bar concepts.

Provider reliability, rate limits, schema drift, and data quality issues must be treated as adapter concerns rather than leaking into Strategy code.
