import pytest
from fastapi.testclient import TestClient

from trademiner.api.app import create_app
from trademiner.market_data.fake import FakeMarketDataProvider
from trademiner.market_data.models import DailyBar, Instrument


def test_selection_backtest_runs_shared_runtime_computes_metrics_and_persists_snapshot(
    tmp_path,
):
    provider = FakeMarketDataProvider(
        instruments=[
            Instrument(
                instrument_id="stock:000001",
                symbol="000001",
                name="Ping An Bank",
                instrument_type="stock",
                exchange="SZSE",
            ),
            Instrument(
                instrument_id="stock:000002",
                symbol="000002",
                name="Vanke",
                instrument_type="stock",
                exchange="SZSE",
            ),
            Instrument(
                instrument_id="etf:510300",
                symbol="510300",
                name="CSI 300 ETF",
                instrument_type="etf",
                exchange="SSE",
            ),
        ],
        daily_bars={
            "stock:000001": [
                DailyBar("stock:000001", "2024-01-01", "hfq", 10, 10, 10, 10, 1000, 10000),
                DailyBar("stock:000001", "2024-01-02", "hfq", 12, 12, 12, 12, 1200, 14400),
                DailyBar("stock:000001", "2024-01-03", "hfq", 11, 11, 11, 11, 1100, 12100),
                DailyBar("stock:000001", "2024-01-04", "hfq", 15, 15, 15, 15, 1500, 22500),
            ],
            "stock:000002": [
                DailyBar("stock:000002", "2024-01-01", "hfq", 10, 10, 10, 10, 1000, 10000),
                DailyBar("stock:000002", "2024-01-02", "hfq", 9, 9, 9, 9, 900, 8100),
                DailyBar("stock:000002", "2024-01-03", "hfq", 8, 8, 8, 8, 800, 6400),
                DailyBar("stock:000002", "2024-01-04", "hfq", 8, 8, 8, 8, 800, 6400),
            ],
            "etf:510300": [
                DailyBar("etf:510300", "2024-01-01", "hfq", 100, 100, 100, 100, 1000, 100000),
                DailyBar("etf:510300", "2024-01-02", "hfq", 105, 105, 105, 105, 1000, 105000),
                DailyBar("etf:510300", "2024-01-03", "hfq", 110, 110, 110, 110, 1000, 110000),
                DailyBar("etf:510300", "2024-01-04", "hfq", 100, 100, 100, 100, 1000, 100000),
            ],
        },
    )
    client = TestClient(
        create_app(
            data_dir=tmp_path / "trademiner-data",
            data_providers={"fake": provider},
        )
    )
    client.post(
        "/api/market-data/sync",
        json={
            "provider": "fake",
            "instrument_types": ["stock", "etf"],
            "adjustment": "hfq",
            "start_date": "2024-01-01",
            "end_date": "2024-01-04",
            "overlap_days": 1,
        },
    )

    strategy_source = '''\
from trademiner.strategy import Candidate

STRATEGY = {
    "id": "backtest_rank_close",
    "name": "Backtest Rank Close",
    "params": {
        "minimum_score": {"type": "float", "default": 0, "min": 0, "max": 100},
    },
}

def select(ctx, params):
    candidates = []
    for instrument in ctx.universe(types=["stock"]):
        bars = ctx.daily_bars(
            instruments=[instrument.instrument_id],
            lookback=5,
            fields=["trade_date", "close"],
        )
        if any(bar["trade_date"] > ctx.as_of for bar in bars):
            raise AssertionError("future data leaked")
        last_bar = bars[-1]
        if last_bar["close"] < params["minimum_score"]:
            continue
        candidates.append(
            Candidate(
                instrument_id=instrument.instrument_id,
                score=last_bar["close"],
                explanation=f"close at {ctx.as_of}: {last_bar['close']}",
                rank_basis="as_of_close",
                tags=["backtest"],
                metrics={"close": last_bar["close"]},
            )
        )
    return candidates
'''
    strategy_file = tmp_path / "strategies" / "backtest_rank_close.py"
    strategy_file.parent.mkdir()
    strategy_file.write_text(strategy_source)
    client.post("/api/strategies/discover", json={"paths": [str(strategy_file)]})

    created = client.post(
        "/api/selection-backtests",
        json={
            "strategy_id": "backtest_rank_close",
            "params": {"minimum_score": 0},
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "top_n": 1,
            "horizons": [1, 2],
            "benchmark": {"instrument_id": "etf:510300"},
        },
    )

    assert created.status_code == 201
    created_body = created.json()
    assert created_body["job"]["type"] == "run_selection_backtest"
    assert created_body["job"]["status"] == "succeeded"
    assert created_body["job"]["progress"] == {
        "selection_date_count": 2,
        "observation_count": 4,
    }
    backtest = created_body["selection_backtest"]
    assert backtest["strategy_id"] == "backtest_rank_close"
    assert backtest["params"] == {"minimum_score": 0.0}
    assert backtest["start_date"] == "2024-01-01"
    assert backtest["end_date"] == "2024-01-02"
    assert backtest["selection_dates"] == ["2024-01-01", "2024-01-02"]
    assert backtest["top_n"] == 1
    assert backtest["horizons"] == [1, 2]
    assert backtest["benchmark"] == {"instrument_id": "etf:510300"}
    assert backtest["market_data_snapshot_ref"] == "market-data:hfq:2024-01-01:2024-01-04"
    assert backtest["strategy_version"]["source_snapshot"] == strategy_source

    first_selection = backtest["selection_results"][0]
    assert first_selection["selection_date"] == "2024-01-01"
    assert first_selection["candidates"][0]["instrument_id"] == "stock:000001"
    assert first_selection["candidates"][0]["explanation"] == "close at 2024-01-01: 10.0"
    assert first_selection["horizon_results"]["1"][0] == {
        "instrument_id": "stock:000001",
        "entry_date": "2024-01-01",
        "exit_date": "2024-01-02",
        "entry_close": 10.0,
        "exit_close": 12.0,
        "future_return": 0.2,
        "max_drawdown": 0.0,
        "benchmark_return": 0.05,
        "excess_return": 0.15000000000000002,
    }

    metrics = backtest["summary_metrics"]
    assert metrics["1"]["observation_count"] == 2
    assert metrics["1"]["average_return"] == pytest.approx(0.0583333333)
    assert metrics["1"]["win_rate"] == 0.5
    assert metrics["1"]["max_drawdown"] == pytest.approx(-0.0833333333)
    assert metrics["1"]["average_benchmark_return"] == pytest.approx(0.0488095238)
    assert metrics["1"]["average_excess_return"] == pytest.approx(0.0095238095)
    assert metrics["2"]["observation_count"] == 2
    assert metrics["2"]["average_return"] == pytest.approx(0.175)
    assert metrics["2"]["win_rate"] == 1.0
    assert metrics["2"]["max_drawdown"] == pytest.approx(-0.0833333333)
    assert metrics["2"]["average_benchmark_return"] == pytest.approx(0.0261904762)
    assert metrics["2"]["average_excess_return"] == pytest.approx(0.1488095238)

    fetched = client.get(f"/api/selection-backtests/{backtest['id']}")

    assert fetched.status_code == 200
    assert fetched.json() == backtest


def test_selection_backtest_failure_is_visible_on_the_job(tmp_path):
    provider = FakeMarketDataProvider(
        instruments=[
            Instrument(
                instrument_id="stock:000001",
                symbol="000001",
                name="Ping An Bank",
                instrument_type="stock",
                exchange="SZSE",
            )
        ],
        daily_bars={
            "stock:000001": [
                DailyBar("stock:000001", "2024-01-01", "hfq", 10, 10, 10, 10, 1000, 10000),
                DailyBar("stock:000001", "2024-01-02", "hfq", 11, 11, 11, 11, 1100, 12100),
            ]
        },
    )
    strategy_source = '''\
STRATEGY = {
    "id": "raising_backtest_strategy",
    "name": "Raising Backtest Strategy",
    "params": {},
}

def select(ctx, params):
    raise RuntimeError("backtest strategy exploded")
'''
    strategy_file = tmp_path / "strategies" / "raising.py"
    strategy_file.parent.mkdir()
    strategy_file.write_text(strategy_source)
    client = TestClient(
        create_app(
            data_dir=tmp_path / "trademiner-data",
            data_providers={"fake": provider},
        )
    )
    client.post(
        "/api/market-data/sync",
        json={
            "provider": "fake",
            "instrument_types": ["stock"],
            "adjustment": "hfq",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "overlap_days": 1,
        },
    )
    client.post("/api/strategies/discover", json={"paths": [str(strategy_file)]})

    failed = client.post(
        "/api/selection-backtests",
        json={
            "strategy_id": "raising_backtest_strategy",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
            "top_n": 1,
            "horizons": [1],
        },
    )

    assert failed.status_code == 500
    failed_job = failed.json()["detail"]
    assert failed_job["type"] == "run_selection_backtest"
    assert failed_job["status"] == "failed"
    assert failed_job["error"] == "backtest strategy exploded"
    assert failed_job["started_at"] is not None
    assert failed_job["finished_at"] is not None

    fetched = client.get(f"/api/jobs/{failed_job['id']}")

    assert fetched.status_code == 200
    assert fetched.json() == failed_job
