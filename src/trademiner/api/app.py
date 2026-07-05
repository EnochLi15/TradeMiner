from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from trademiner.backtest.repository import SelectionBacktestRepository
from trademiner.backtest.selection import SelectionBacktestService
from trademiner.jobs import JobRepository
from trademiner.market_data.cache import MarketDataCache
from trademiner.market_data.providers import MarketDataProvider, default_data_providers
from trademiner.market_data.schedule import (
    MarketDataScheduledSyncService,
    MarketDataSyncDiagnosticsService,
    MarketDataSyncScheduleRepository,
)
from trademiner.market_data.sync import MarketDataSyncRequest, MarketDataSyncService
from trademiner.results import ResultSnapshotComparisonService
from trademiner.storage import StorageStatus, initialize_storage
from trademiner.strategy.discovery import (
    default_source_strategy_dir,
    discover_default_source_strategies,
    discover_strategy_sources,
    read_strategy_source,
)
from trademiner.strategy.params import validate_strategy_params
from trademiner.strategy.repository import StrategyRepository
from trademiner.strategy.runtime import StrategyRuntime
from trademiner.strategy.runs import StrategyRunRepository


class CreateJobRequest(BaseModel):
    type: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class SyncMarketDataRequest(BaseModel):
    provider: str = "akshare"
    instrument_types: list[str] = Field(default_factory=lambda: ["stock", "etf"])
    adjustment: str = "hfq"
    start_date: str
    end_date: str
    overlap_days: int = Field(default=5, ge=1)


class UpdateSyncScheduleRequest(BaseModel):
    enabled: bool | None = None
    provider: str | None = None
    instrument_types: list[str] | None = None
    adjustment: str | None = None
    start_date: str | None = None
    overlap_days: int | None = Field(default=None, ge=1)
    schedule_time: str | None = None
    timezone: str | None = None
    trading_days_only: bool | None = None


class RunScheduledSyncRequest(BaseModel):
    run_date: str | None = None


class DiscoverStrategiesRequest(BaseModel):
    paths: list[str] = Field(min_length=1)


class ValidateStrategyParamsRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class CreateStrategyRunRequest(BaseModel):
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    as_of_date: str | None = None
    adjustment: str = "hfq"


class BenchmarkConfig(BaseModel):
    instrument_id: str = Field(min_length=1)


class CreateSelectionBacktestRequest(BaseModel):
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    start_date: str
    end_date: str
    top_n: int = Field(default=20, ge=1)
    horizons: list[int] = Field(default_factory=lambda: [1, 5, 10, 20])
    adjustment: str = "hfq"
    benchmark: BenchmarkConfig | None = None


class CompareResultSnapshotsRequest(BaseModel):
    snapshot_type: str
    snapshot_ids: list[str] = Field(min_length=2)


def create_app(
    data_dir: Path | str | None = None,
    data_providers: dict[str, MarketDataProvider] | None = None,
) -> FastAPI:
    storage_status = initialize_storage(data_dir)
    job_repository = JobRepository(storage_status.metadata_store.path)
    providers = data_providers if data_providers is not None else default_data_providers()
    market_data_cache = MarketDataCache(
        duckdb_path=storage_status.analytical_store.duckdb_path,
        sqlite_path=storage_status.metadata_store.path,
    )
    market_data_sync = MarketDataSyncService(
        cache=market_data_cache,
        jobs=job_repository,
        providers=providers,
    )
    sync_schedule_repository = MarketDataSyncScheduleRepository(
        storage_status.metadata_store.path
    )
    scheduled_sync = MarketDataScheduledSyncService(
        schedules=sync_schedule_repository,
        sync_service=market_data_sync,
    )
    sync_diagnostics = MarketDataSyncDiagnosticsService(
        schedules=sync_schedule_repository,
        jobs=job_repository,
    )
    strategy_repository = StrategyRepository(storage_status.metadata_store.path)
    strategy_run_repository = StrategyRunRepository(storage_status.metadata_store.path)
    selection_backtest_repository = SelectionBacktestRepository(
        storage_status.metadata_store.path
    )
    strategy_runtime = StrategyRuntime(market_data_cache)
    selection_backtest_service = SelectionBacktestService(
        cache=market_data_cache,
        runtime=strategy_runtime,
    )
    result_snapshot_comparison = ResultSnapshotComparisonService(
        strategy_runs=strategy_run_repository,
        selection_backtests=selection_backtest_repository,
    )
    app = FastAPI(title="TradeMiner")
    app.state.storage_status = storage_status
    app.state.job_repository = job_repository
    app.state.market_data_cache = market_data_cache
    app.state.market_data_sync = market_data_sync
    app.state.sync_schedule_repository = sync_schedule_repository
    app.state.scheduled_sync = scheduled_sync
    app.state.sync_diagnostics = sync_diagnostics
    app.state.strategy_repository = strategy_repository
    app.state.strategy_run_repository = strategy_run_repository
    app.state.selection_backtest_repository = selection_backtest_repository
    app.state.strategy_runtime = strategy_runtime
    app.state.selection_backtest_service = selection_backtest_service
    app.state.result_snapshot_comparison = result_snapshot_comparison

    @app.get("/api/system/status")
    def system_status() -> dict[str, object]:
        status: StorageStatus = app.state.storage_status
        return status.as_response()

    @app.post("/api/jobs", status_code=201)
    def create_job(request: CreateJobRequest) -> dict[str, object]:
        repository: JobRepository = app.state.job_repository
        return repository.create_pending(request.type, request.parameters).as_response()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, object]:
        repository: JobRepository = app.state.job_repository
        try:
            return repository.get(job_id).as_response()
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error

    @app.post("/api/market-data/sync", status_code=201)
    def sync_market_data(request: SyncMarketDataRequest) -> dict[str, object]:
        service: MarketDataSyncService = app.state.market_data_sync
        job = service.sync(
            MarketDataSyncRequest(
                provider=request.provider,
                instrument_types=request.instrument_types,
                adjustment=request.adjustment,
                start_date=request.start_date,
                end_date=request.end_date,
                overlap_days=request.overlap_days,
            )
        )
        if job.status == "failed":
            raise HTTPException(status_code=500, detail=job.as_response())
        return {"job": job.as_response()}

    @app.get("/api/market-data/sync-schedule")
    def get_sync_schedule() -> dict[str, object]:
        repository: MarketDataSyncScheduleRepository = (
            app.state.sync_schedule_repository
        )
        return repository.get().as_response()

    @app.put("/api/market-data/sync-schedule")
    def update_sync_schedule(
        request: UpdateSyncScheduleRequest,
    ) -> dict[str, object]:
        repository: MarketDataSyncScheduleRepository = (
            app.state.sync_schedule_repository
        )
        return repository.update(request.model_dump(exclude_none=True)).as_response()

    @app.post("/api/market-data/sync-schedule/run", status_code=201)
    def run_scheduled_sync(request: RunScheduledSyncRequest) -> dict[str, object]:
        service: MarketDataScheduledSyncService = app.state.scheduled_sync
        job = service.run(run_date=request.run_date)
        if job.status == "failed":
            raise HTTPException(status_code=500, detail=job.as_response())
        return {"job": job.as_response()}

    @app.get("/api/market-data/sync-diagnostics")
    def get_sync_diagnostics() -> dict[str, object]:
        service: MarketDataSyncDiagnosticsService = app.state.sync_diagnostics
        return service.status()

    @app.get("/api/market-data/instruments")
    def list_instruments() -> list[dict[str, object]]:
        cache: MarketDataCache = app.state.market_data_cache
        return [instrument.as_response() for instrument in cache.list_instruments()]

    @app.get("/api/market-data/daily-bars")
    def list_daily_bars(
        instrument_id: str | None = None,
        adjustment: str | None = None,
    ) -> list[dict[str, object]]:
        cache: MarketDataCache = app.state.market_data_cache
        return [
            bar.as_response()
            for bar in cache.list_daily_bars(
                instrument_id=instrument_id,
                adjustment=adjustment,
            )
        ]

    @app.get("/api/market-data/sync-cursors")
    def list_sync_cursors() -> list[dict[str, object]]:
        cache: MarketDataCache = app.state.market_data_cache
        return [cursor.as_response() for cursor in cache.list_cursors()]

    @app.post("/api/strategies/discover", status_code=201)
    def discover_strategies(request: DiscoverStrategiesRequest) -> dict[str, object]:
        repository: StrategyRepository = app.state.strategy_repository
        strategy_sources = discover_strategy_sources(
            [Path(path) for path in request.paths]
        )
        strategies = [repository.upsert_source(source) for source in strategy_sources]
        return {"strategies": [strategy.as_response() for strategy in strategies]}

    @app.post("/api/strategies/sync-source", status_code=201)
    def sync_source_strategies() -> dict[str, object]:
        repository: StrategyRepository = app.state.strategy_repository
        strategies = [
            repository.upsert_source(source)
            for source in discover_default_source_strategies()
        ]
        return {
            "source_path": str(default_source_strategy_dir()),
            "strategies": [strategy.as_response() for strategy in strategies],
        }

    @app.get("/api/strategies")
    def list_strategies() -> list[dict[str, object]]:
        repository: StrategyRepository = app.state.strategy_repository
        return [strategy.as_response() for strategy in repository.list()]

    @app.get("/api/strategies/{strategy_id}")
    def get_strategy(strategy_id: str) -> dict[str, object]:
        repository: StrategyRepository = app.state.strategy_repository
        try:
            return repository.get(strategy_id).as_response()
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Strategy not found") from error

    @app.post("/api/strategies/{strategy_id}/validate-parameters")
    def validate_strategy_parameters(
        strategy_id: str,
        request: ValidateStrategyParamsRequest,
    ) -> dict[str, object]:
        repository: StrategyRepository = app.state.strategy_repository
        try:
            strategy = repository.get(strategy_id)
            return {
                "params": validate_strategy_params(
                    definitions=strategy.params,
                    provided=request.params,
                )
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Strategy not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/strategy-runs", status_code=201)
    def create_strategy_run(request: CreateStrategyRunRequest) -> dict[str, object]:
        repository: StrategyRepository = app.state.strategy_repository
        run_repository: StrategyRunRepository = app.state.strategy_run_repository
        runtime: StrategyRuntime = app.state.strategy_runtime
        cache: MarketDataCache = app.state.market_data_cache
        jobs: JobRepository = app.state.job_repository

        try:
            discovered_strategy = repository.get(request.strategy_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Strategy not found") from error

        refreshed_source = read_strategy_source(Path(discovered_strategy.file_path))
        strategy = repository.upsert_source(refreshed_source)
        try:
            validated_params = validate_strategy_params(strategy.params, request.params)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        as_of_date = request.as_of_date or cache.latest_trade_date(request.adjustment)
        if as_of_date is None:
            raise HTTPException(status_code=422, detail="No Market Data is available")

        job = jobs.create_pending(
            "run_strategy",
            {
                "strategy_id": strategy.strategy_id,
                "params": validated_params,
                "as_of_date": as_of_date,
                "adjustment": request.adjustment,
            },
        )
        jobs.start(job.id)
        try:
            candidates = runtime.run(
                strategy=strategy,
                params=validated_params,
                as_of_date=as_of_date,
                adjustment=request.adjustment,
            )
            market_data_snapshot_ref = f"market-data:{request.adjustment}:{as_of_date}"
            strategy_run = run_repository.create(
                strategy_id=strategy.strategy_id,
                job_id=job.id,
                strategy_version=strategy.latest_version,
                params=validated_params,
                as_of_date=as_of_date,
                adjustment=request.adjustment,
                market_data_snapshot_ref=market_data_snapshot_ref,
                candidates=candidates,
            )
            job = jobs.succeed(
                job.id,
                progress={
                    "candidate_count": len(candidates),
                    "as_of_date": as_of_date,
                },
                result_ref=f"strategy-run:{strategy_run.id}",
            )
            return {
                "job": job.as_response(),
                "strategy_run": strategy_run.as_response(),
            }
        except Exception as error:
            job = jobs.fail(job.id, str(error))
            raise HTTPException(status_code=500, detail=job.as_response()) from error

    @app.get("/api/strategy-runs")
    def list_strategy_runs(
        strategy_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        if limit < 1 or offset < 0:
            raise HTTPException(status_code=422, detail="Invalid pagination")
        repository: StrategyRunRepository = app.state.strategy_run_repository
        return {
            "items": [
                strategy_run.as_response()
                for strategy_run in repository.list(
                    strategy_id=strategy_id,
                    limit=limit,
                    offset=offset,
                )
            ],
            "total": repository.count(strategy_id=strategy_id),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/strategy-runs/{strategy_run_id}")
    def get_strategy_run(strategy_run_id: str) -> dict[str, object]:
        repository: StrategyRunRepository = app.state.strategy_run_repository
        try:
            return repository.get(strategy_run_id).as_response()
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Strategy Run not found") from error

    @app.post("/api/selection-backtests", status_code=201)
    def create_selection_backtest(
        request: CreateSelectionBacktestRequest,
    ) -> dict[str, object]:
        if not request.horizons or any(horizon <= 0 for horizon in request.horizons):
            raise HTTPException(status_code=422, detail="Horizons must be positive")

        repository: StrategyRepository = app.state.strategy_repository
        backtests: SelectionBacktestRepository = (
            app.state.selection_backtest_repository
        )
        service: SelectionBacktestService = app.state.selection_backtest_service
        jobs: JobRepository = app.state.job_repository

        try:
            discovered_strategy = repository.get(request.strategy_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Strategy not found") from error

        refreshed_source = read_strategy_source(Path(discovered_strategy.file_path))
        strategy = repository.upsert_source(refreshed_source)
        try:
            validated_params = validate_strategy_params(strategy.params, request.params)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        benchmark = (
            request.benchmark.model_dump()
            if request.benchmark is not None
            else None
        )
        job = jobs.create_pending(
            "run_selection_backtest",
            {
                "strategy_id": strategy.strategy_id,
                "params": validated_params,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "top_n": request.top_n,
                "horizons": request.horizons,
                "adjustment": request.adjustment,
                "benchmark": benchmark,
            },
        )
        jobs.start(job.id)
        try:
            result = service.run(
                strategy=strategy,
                params=validated_params,
                start_date=request.start_date,
                end_date=request.end_date,
                top_n=request.top_n,
                horizons=request.horizons,
                adjustment=request.adjustment,
                benchmark=benchmark,
            )
            selection_backtest = backtests.create(
                strategy_id=strategy.strategy_id,
                job_id=job.id,
                strategy_version=strategy.latest_version,
                params=validated_params,
                start_date=request.start_date,
                end_date=request.end_date,
                selection_dates=result.selection_dates,
                top_n=request.top_n,
                horizons=request.horizons,
                adjustment=request.adjustment,
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
            return {
                "job": job.as_response(),
                "selection_backtest": selection_backtest.as_response(),
            }
        except Exception as error:
            job = jobs.fail(job.id, str(error))
            raise HTTPException(status_code=500, detail=job.as_response()) from error

    @app.get("/api/selection-backtests")
    def list_selection_backtests(
        strategy_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        if limit < 1 or offset < 0:
            raise HTTPException(status_code=422, detail="Invalid pagination")
        repository: SelectionBacktestRepository = (
            app.state.selection_backtest_repository
        )
        return {
            "items": [
                backtest.as_response()
                for backtest in repository.list(
                    strategy_id=strategy_id,
                    limit=limit,
                    offset=offset,
                )
            ],
            "total": repository.count(strategy_id=strategy_id),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/selection-backtests/{selection_backtest_id}")
    def get_selection_backtest(selection_backtest_id: str) -> dict[str, object]:
        repository: SelectionBacktestRepository = (
            app.state.selection_backtest_repository
        )
        try:
            return repository.get(selection_backtest_id).as_response()
        except KeyError as error:
            raise HTTPException(
                status_code=404,
                detail="Selection Backtest not found",
            ) from error

    @app.post("/api/result-snapshots/compare")
    def compare_result_snapshots(
        request: CompareResultSnapshotsRequest,
    ) -> dict[str, object]:
        service: ResultSnapshotComparisonService = (
            app.state.result_snapshot_comparison
        )
        try:
            return service.compare(
                snapshot_type=request.snapshot_type,
                snapshot_ids=request.snapshot_ids,
            )
        except KeyError as error:
            raise HTTPException(
                status_code=404,
                detail="Result Snapshot not found",
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return app


app = create_app()
