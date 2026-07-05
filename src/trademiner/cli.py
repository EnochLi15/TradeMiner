from __future__ import annotations

import json
from pathlib import Path

import typer

from trademiner.backtest.repository import SelectionBacktestRepository
from trademiner.backtest.selection import SelectionBacktestService
from trademiner.jobs import JobRepository
from trademiner.market_data.cache import MarketDataCache
from trademiner.market_data.providers import MarketDataProvider, default_data_providers
from trademiner.market_data.schedule import (
    MarketDataSyncDiagnosticsService,
    MarketDataSyncScheduleRepository,
)
from trademiner.market_data.sync import MarketDataSyncRequest, MarketDataSyncService
from trademiner.storage import initialize_storage
from trademiner.strategy.discovery import discover_strategy_sources, read_strategy_source
from trademiner.strategy.params import validate_strategy_params
from trademiner.strategy.repository import StrategyRepository
from trademiner.strategy.runtime import StrategyRuntime
from trademiner.strategy.runs import StrategyRunRepository


def create_cli(data_providers: dict[str, MarketDataProvider] | None = None) -> typer.Typer:
    app = typer.Typer(help="TradeMiner command line tools.")

    @app.callback()
    def root() -> None:
        """TradeMiner command line tools."""

    @app.command()
    def status(
        data_dir: Path | None = typer.Option(
            None,
            "--data-dir",
            help="TradeMiner server data directory.",
        ),
    ) -> None:
        """Show system status and initialize storage if needed."""
        storage_status = initialize_storage(data_dir)
        typer.echo(f"status: {storage_status.status}")
        typer.echo(f"data_dir: {storage_status.data_dir}")
        typer.echo(f"metadata_store: {storage_status.metadata_store.path}")
        typer.echo(f"analytical_store: {storage_status.analytical_store.duckdb_path}")

    @app.command("sync-market-data")
    def sync_market_data(
        data_dir: Path | None = typer.Option(
            None,
            "--data-dir",
            help="TradeMiner server data directory.",
        ),
        provider: str = typer.Option("akshare", "--provider"),
        instrument_type: list[str] = typer.Option(["stock", "etf"], "--instrument-type"),
        adjustment: str = typer.Option("hfq", "--adjustment"),
        start_date: str = typer.Option(..., "--start-date"),
        end_date: str = typer.Option(..., "--end-date"),
        overlap_days: int = typer.Option(5, "--overlap-days", min=1),
    ) -> None:
        """Synchronize Market Data into the shared cache."""
        storage_status = initialize_storage(data_dir)
        jobs = JobRepository(storage_status.metadata_store.path)
        cache = MarketDataCache(
            duckdb_path=storage_status.analytical_store.duckdb_path,
            sqlite_path=storage_status.metadata_store.path,
        )
        service = MarketDataSyncService(
            cache=cache,
            jobs=jobs,
            providers=data_providers or default_data_providers(),
        )
        job = service.sync(
            MarketDataSyncRequest(
                provider=provider,
                instrument_types=list(instrument_type),
                adjustment=adjustment,
                start_date=start_date,
                end_date=end_date,
                overlap_days=overlap_days,
            )
        )
        typer.echo(f"job_id: {job.id}")
        typer.echo(f"status: {job.status}")
        if job.error:
            typer.echo(f"error: {job.error}")
            raise typer.Exit(code=1)

    @app.command("sync-status")
    def sync_status(
        data_dir: Path | None = typer.Option(
            None,
            "--data-dir",
            help="TradeMiner server data directory.",
        ),
    ) -> None:
        """Show Market Data synchronization schedule and diagnostics."""
        storage_status = initialize_storage(data_dir)
        jobs = JobRepository(storage_status.metadata_store.path)
        schedules = MarketDataSyncScheduleRepository(storage_status.metadata_store.path)
        diagnostics = MarketDataSyncDiagnosticsService(
            schedules=schedules,
            jobs=jobs,
        ).status()
        schedule = diagnostics["schedule"]
        typer.echo(f"enabled: {schedule['enabled']}")
        typer.echo(f"provider: {schedule['provider']}")
        typer.echo(f"instrument_types: {','.join(schedule['instrument_types'])}")
        typer.echo(f"schedule_time: {schedule['schedule_time']}")
        typer.echo(f"timezone: {schedule['timezone']}")
        typer.echo(
            f"last_successful_sync_time: {diagnostics['last_successful_sync_time']}"
        )
        typer.echo(f"running_jobs: {len(diagnostics['running_jobs'])}")
        typer.echo(f"recent_jobs: {len(diagnostics['recent_jobs'])}")
        typer.echo(f"recent_failures: {len(diagnostics['recent_failures'])}")
        for failure in diagnostics["recent_failures"]:
            typer.echo(f"failure: {failure['id']} {failure['error']}")

    @app.command("discover-strategies")
    def discover_strategies(
        data_dir: Path | None = typer.Option(
            None,
            "--data-dir",
            help="TradeMiner server data directory.",
        ),
        path: list[Path] = typer.Option(..., "--path"),
    ) -> None:
        """Discover trusted Python Strategy files."""
        storage_status = initialize_storage(data_dir)
        repository = StrategyRepository(storage_status.metadata_store.path)
        strategies = [
            repository.upsert_source(source)
            for source in discover_strategy_sources(list(path))
        ]
        for strategy in strategies:
            typer.echo(f"strategy_id: {strategy.strategy_id}")
            typer.echo(f"name: {strategy.name}")

    @app.command("run-strategy")
    def run_strategy(
        data_dir: Path | None = typer.Option(
            None,
            "--data-dir",
            help="TradeMiner server data directory.",
        ),
        strategy_id: str = typer.Option(..., "--strategy-id"),
        params_json: str = typer.Option("{}", "--params-json"),
        as_of_date: str | None = typer.Option(None, "--as-of-date"),
        adjustment: str = typer.Option("hfq", "--adjustment"),
    ) -> None:
        """Run current screening for a discovered Strategy."""
        storage_status = initialize_storage(data_dir)
        jobs = JobRepository(storage_status.metadata_store.path)
        cache = MarketDataCache(
            duckdb_path=storage_status.analytical_store.duckdb_path,
            sqlite_path=storage_status.metadata_store.path,
        )
        strategies = StrategyRepository(storage_status.metadata_store.path)
        runs = StrategyRunRepository(storage_status.metadata_store.path)
        runtime = StrategyRuntime(cache)

        try:
            discovered_strategy = strategies.get(strategy_id)
            refreshed_source = read_strategy_source(Path(discovered_strategy.file_path))
            strategy = strategies.upsert_source(refreshed_source)
            params = validate_strategy_params(strategy.params, json.loads(params_json))
            resolved_as_of_date = as_of_date or cache.latest_trade_date(adjustment)
            if resolved_as_of_date is None:
                raise ValueError("No Market Data is available")

            job = jobs.create_pending(
                "run_strategy",
                {
                    "strategy_id": strategy.strategy_id,
                    "params": params,
                    "as_of_date": resolved_as_of_date,
                    "adjustment": adjustment,
                },
            )
            jobs.start(job.id)
            candidates = runtime.run(
                strategy=strategy,
                params=params,
                as_of_date=resolved_as_of_date,
                adjustment=adjustment,
            )
            strategy_run = runs.create(
                strategy_id=strategy.strategy_id,
                job_id=job.id,
                strategy_version=strategy.latest_version,
                params=params,
                as_of_date=resolved_as_of_date,
                adjustment=adjustment,
                market_data_snapshot_ref=(
                    f"market-data:{adjustment}:{resolved_as_of_date}"
                ),
                candidates=candidates,
            )
            job = jobs.succeed(
                job.id,
                progress={
                    "candidate_count": len(candidates),
                    "as_of_date": resolved_as_of_date,
                },
                result_ref=f"strategy-run:{strategy_run.id}",
            )
        except Exception as error:
            typer.echo(f"error: {error}")
            raise typer.Exit(code=1) from error

        typer.echo(f"job_id: {job.id}")
        typer.echo(f"status: {job.status}")
        typer.echo(f"strategy_run_id: {strategy_run.id}")
        typer.echo(f"candidate_count: {len(candidates)}")

    @app.command("run-selection-backtest")
    def run_selection_backtest(
        data_dir: Path | None = typer.Option(
            None,
            "--data-dir",
            help="TradeMiner server data directory.",
        ),
        strategy_id: str = typer.Option(..., "--strategy-id"),
        params_json: str = typer.Option("{}", "--params-json"),
        start_date: str = typer.Option(..., "--start-date"),
        end_date: str = typer.Option(..., "--end-date"),
        top_n: int = typer.Option(20, "--top-n", min=1),
        horizon: list[int] = typer.Option([1, 5, 10, 20], "--horizon"),
        adjustment: str = typer.Option("hfq", "--adjustment"),
        benchmark_instrument_id: str | None = typer.Option(
            None,
            "--benchmark-instrument-id",
        ),
    ) -> None:
        """Run a Selection Backtest for a discovered Strategy."""
        storage_status = initialize_storage(data_dir)
        jobs = JobRepository(storage_status.metadata_store.path)
        cache = MarketDataCache(
            duckdb_path=storage_status.analytical_store.duckdb_path,
            sqlite_path=storage_status.metadata_store.path,
        )
        strategies = StrategyRepository(storage_status.metadata_store.path)
        backtests = SelectionBacktestRepository(storage_status.metadata_store.path)
        runtime = StrategyRuntime(cache)
        service = SelectionBacktestService(cache=cache, runtime=runtime)
        benchmark = (
            {"instrument_id": benchmark_instrument_id}
            if benchmark_instrument_id is not None
            else None
        )

        try:
            discovered_strategy = strategies.get(strategy_id)
            refreshed_source = read_strategy_source(Path(discovered_strategy.file_path))
            strategy = strategies.upsert_source(refreshed_source)
            params = validate_strategy_params(strategy.params, json.loads(params_json))
            horizons = list(horizon)
            if not horizons or any(value <= 0 for value in horizons):
                raise ValueError("Horizons must be positive")

            job = jobs.create_pending(
                "run_selection_backtest",
                {
                    "strategy_id": strategy.strategy_id,
                    "params": params,
                    "start_date": start_date,
                    "end_date": end_date,
                    "top_n": top_n,
                    "horizons": horizons,
                    "adjustment": adjustment,
                    "benchmark": benchmark,
                },
            )
            jobs.start(job.id)
            result = service.run(
                strategy=strategy,
                params=params,
                start_date=start_date,
                end_date=end_date,
                top_n=top_n,
                horizons=horizons,
                adjustment=adjustment,
                benchmark=benchmark,
            )
            selection_backtest = backtests.create(
                strategy_id=strategy.strategy_id,
                job_id=job.id,
                strategy_version=strategy.latest_version,
                params=params,
                start_date=start_date,
                end_date=end_date,
                selection_dates=result.selection_dates,
                top_n=top_n,
                horizons=horizons,
                adjustment=adjustment,
                benchmark=benchmark,
                market_data_snapshot_ref=result.market_data_snapshot_ref,
                selection_results=result.selection_results,
                summary_metrics=result.summary_metrics,
            )
            job = jobs.succeed(
                job.id,
                progress={
                    "selection_date_count": len(result.selection_dates),
                    "observation_count": result.observation_count,
                },
                result_ref=f"selection-backtest:{selection_backtest.id}",
            )
        except Exception as error:
            typer.echo(f"error: {error}")
            raise typer.Exit(code=1) from error

        typer.echo(f"job_id: {job.id}")
        typer.echo(f"status: {job.status}")
        typer.echo(f"selection_backtest_id: {selection_backtest.id}")
        typer.echo(f"selection_date_count: {len(result.selection_dates)}")
        typer.echo(f"observation_count: {result.observation_count}")

    return app


cli = create_cli()


def main() -> None:
    cli()
