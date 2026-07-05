# TradeMiner

TradeMiner is a trading research context focused on discovering and evaluating market opportunities before trade execution.

## Language

**Strategy**:
A code-defined screening and ranking rule that selects candidate instruments from market data and explains why they were selected. In the first version, a Strategy does not place orders, manage positions, or execute live trades.
_Avoid_: Trading bot, signal, execution rule

**Candidate**:
An Instrument selected by a Strategy, with a Strategy-defined score, rank basis, tags, and explanation fields that describe why it was selected.
_Avoid_: Pick, recommendation, trade target

**Instrument**:
A tradable market object that TradeMiner can evaluate, such as an A-share stock or ETF in the first version.
_Avoid_: Asset, symbol, product

**Market Data**:
Historical and current data about Instruments that a Strategy can read. In the first version, Market Data means daily adjusted bars, basic Instrument metadata, and derived technical indicators.
_Avoid_: Data feed, quote data, raw ticks

**Market Data Cache**:
A server-owned shared normalized store of Market Data that Strategies and Backtests read from. Data Providers update the Market Data Cache, but Strategies do not call Data Providers directly.
_Avoid_: Raw download folder, provider cache

**Data Provider**:
An external source from which TradeMiner obtains Market Data.
_Avoid_: Vendor, data source, feed

**Daily Bar**:
One trading day's open, high, low, close, volume, and related adjusted price fields for an Instrument.
_Avoid_: Candle, K-line

**Strategy Runtime**:
The execution environment that runs a Strategy against a read-only dated view of Market Data. The same Strategy Runtime is used for current screening and historical Backtests.
_Avoid_: Engine, executor, runner

**Backtest**:
A historical evaluation of a Strategy by running it across prior trading dates and measuring the behavior of the Candidates it selected.
_Avoid_: Simulation, replay, paper trading

**Selection Backtest**:
A Backtest that measures the future performance of Strategy-selected Candidates across historical selection dates. It evaluates selection quality, not full portfolio trading behavior.
_Avoid_: Portfolio backtest, trading simulation

**Strategy Run**:
A durable record of running a Strategy for a specific as-of date, including the Candidate snapshot and references to the Strategy version and Market Data snapshot used.
_Avoid_: Scan, screen, execution result

**Strategy Version**:
An immutable identity for the Strategy source used by a Strategy Run or Backtest, based on the Strategy file path, source hash, source snapshot, and optional Git metadata.
_Avoid_: Latest strategy, file version

**Result Snapshot**:
An immutable stored output of a Strategy Run or Backtest, used to compare and reproduce past research results.
_Avoid_: Report, output file, latest result

**Job**:
A persistent record of a long-running TradeMiner operation such as Market Data synchronization, Strategy execution, or Backtest execution.
_Avoid_: Task, process, run

**Sync Cursor**:
A persistent marker that records how far a Market Data dataset has been synchronized for a provider, data type, adjustment mode, and Instrument or Instrument universe.
_Avoid_: Checkpoint, offset, latest date
