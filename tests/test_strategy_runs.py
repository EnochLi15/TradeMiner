from fastapi.testclient import TestClient
import pytest

from trademiner.api.app import create_app
from trademiner.market_data.fake import FakeMarketDataProvider
from trademiner.market_data.models import DailyBar, Instrument


def test_current_strategy_run_uses_as_of_context_sorts_candidates_and_persists_snapshot(
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
        ],
        daily_bars={
            "stock:000001": [
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-01",
                    adjustment="hfq",
                    open=10,
                    high=11,
                    low=9,
                    close=10,
                    volume=1000,
                    amount=10000,
                ),
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-02",
                    adjustment="hfq",
                    open=10,
                    high=12,
                    low=10,
                    close=12,
                    volume=1200,
                    amount=14400,
                ),
            ],
            "stock:000002": [
                DailyBar(
                    instrument_id="stock:000002",
                    trade_date="2024-01-01",
                    adjustment="hfq",
                    open=10,
                    high=11,
                    low=9,
                    close=10,
                    volume=1000,
                    amount=10000,
                ),
                DailyBar(
                    instrument_id="stock:000002",
                    trade_date="2024-01-02",
                    adjustment="hfq",
                    open=10,
                    high=11,
                    low=9,
                    close=11,
                    volume=1100,
                    amount=12100,
                ),
                DailyBar(
                    instrument_id="stock:000002",
                    trade_date="2024-01-03",
                    adjustment="hfq",
                    open=11,
                    high=20,
                    low=10,
                    close=20,
                    volume=5000,
                    amount=100000,
                ),
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
            "instrument_types": ["stock"],
            "adjustment": "hfq",
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "overlap_days": 1,
        },
    )

    strategy_source = '''\
from trademiner.strategy import Candidate

STRATEGY = {
    "id": "rank_by_as_of_close",
    "name": "Rank by As-Of Close",
    "description": "Verifies StrategyContext date bounds.",
    "params": {
        "top_n": {"type": "int", "default": 2, "min": 1, "max": 10},
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
        candidates.append(
            Candidate(
                instrument_id=instrument.instrument_id,
                score=last_bar["close"],
                explanation=f"close at {ctx.as_of}: {last_bar['close']}",
                rank_basis="as_of_close",
                tags=["as-of"],
                metrics={"close": last_bar["close"]},
            )
        )
    return candidates[: params["top_n"]]
'''
    strategy_file = tmp_path / "strategies" / "rank_close.py"
    strategy_file.parent.mkdir()
    strategy_file.write_text(strategy_source)
    client.post("/api/strategies/discover", json={"paths": [str(strategy_file)]})

    created = client.post(
        "/api/strategy-runs",
        json={
            "strategy_id": "rank_by_as_of_close",
            "params": {"top_n": 2},
            "as_of_date": "2024-01-02",
        },
    )

    assert created.status_code == 201
    created_body = created.json()
    assert created_body["job"]["type"] == "run_strategy"
    assert created_body["job"]["status"] == "succeeded"
    strategy_run = created_body["strategy_run"]
    assert strategy_run["strategy_id"] == "rank_by_as_of_close"
    assert strategy_run["as_of_date"] == "2024-01-02"
    assert strategy_run["params"] == {"top_n": 2}
    assert strategy_run["market_data_snapshot_ref"] == "market-data:hfq:2024-01-02"
    assert [candidate["instrument_id"] for candidate in strategy_run["candidates"]] == [
        "stock:000001",
        "stock:000002",
    ]
    assert [candidate["score"] for candidate in strategy_run["candidates"]] == [12, 11]
    assert strategy_run["candidates"][0]["explanation"] == "close at 2024-01-02: 12.0"
    assert strategy_run["candidates"][0]["rank_basis"] == "as_of_close"
    assert strategy_run["candidates"][0]["tags"] == ["as-of"]
    assert strategy_run["candidates"][0]["metrics"] == {"close": 12}
    assert strategy_run["strategy_version"]["source_snapshot"] == strategy_source

    fetched = client.get(f"/api/strategy-runs/{strategy_run['id']}")

    assert fetched.status_code == 200
    assert fetched.json() == strategy_run


def test_current_strategy_run_failure_is_visible_on_the_job(tmp_path):
    strategy_source = '''\
STRATEGY = {
    "id": "raising_strategy",
    "name": "Raising Strategy",
    "params": {},
}

def select(ctx, params):
    raise RuntimeError("strategy exploded")
'''
    strategy_file = tmp_path / "strategies" / "raising.py"
    strategy_file.parent.mkdir()
    strategy_file.write_text(strategy_source)
    client = TestClient(create_app(data_dir=tmp_path / "trademiner-data"))
    client.post("/api/strategies/discover", json={"paths": [str(strategy_file)]})

    failed = client.post(
        "/api/strategy-runs",
        json={
            "strategy_id": "raising_strategy",
            "params": {},
            "as_of_date": "2024-01-02",
        },
    )

    assert failed.status_code == 500
    failed_job = failed.json()["detail"]
    assert failed_job["type"] == "run_strategy"
    assert failed_job["status"] == "failed"
    assert failed_job["error"] == "strategy exploded"
    assert failed_job["started_at"] is not None
    assert failed_job["finished_at"] is not None

    fetched = client.get(f"/api/jobs/{failed_job['id']}")

    assert fetched.status_code == 200
    assert fetched.json() == failed_job


def test_source_strategy_can_be_selected_and_run(tmp_path):
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
        ],
        daily_bars={
            "stock:000001": [
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-01",
                    adjustment="hfq",
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    volume=1000,
                ),
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-02",
                    adjustment="hfq",
                    open=12,
                    high=12,
                    low=12,
                    close=12,
                    volume=1200,
                ),
            ],
            "stock:000002": [
                DailyBar(
                    instrument_id="stock:000002",
                    trade_date="2024-01-01",
                    adjustment="hfq",
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    volume=1000,
                ),
                DailyBar(
                    instrument_id="stock:000002",
                    trade_date="2024-01-02",
                    adjustment="hfq",
                    open=11,
                    high=11,
                    low=11,
                    close=11,
                    volume=1100,
                ),
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
            "instrument_types": ["stock"],
            "adjustment": "hfq",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "overlap_days": 1,
        },
    )
    client.post("/api/strategies/sync-source")

    created = client.post(
        "/api/strategy-runs",
        json={
            "strategy_id": "daily_momentum_v1",
            "params": {
                "lookback_days": 2,
                "top_n": 1,
                "include_etfs": False,
            },
            "as_of_date": "2024-01-02",
        },
    )

    assert created.status_code == 201
    strategy_run = created.json()["strategy_run"]
    assert strategy_run["strategy_id"] == "daily_momentum_v1"
    assert strategy_run["params"] == {
        "lookback_days": 2,
        "top_n": 1,
        "include_etfs": False,
    }
    assert [candidate["instrument_id"] for candidate in strategy_run["candidates"]] == [
        "stock:000001"
    ]
    assert strategy_run["candidates"][0]["rank_basis"] == "adjusted_close_momentum"
    assert strategy_run["candidates"][0]["metrics"]["momentum"] == pytest.approx(0.2)
