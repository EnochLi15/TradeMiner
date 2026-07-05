from fastapi.testclient import TestClient

from trademiner.api.app import create_app
from trademiner.market_data.fake import FakeMarketDataProvider
from trademiner.market_data.models import DailyBar, Instrument


def test_market_data_sync_normalizes_caches_and_incrementally_refreshes(tmp_path):
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
                instrument_id="etf:510300",
                symbol="510300",
                name="CSI 300 ETF",
                instrument_type="etf",
                exchange="SSE",
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
                    close=10.5,
                    volume=1000,
                    amount=10500,
                ),
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-02",
                    adjustment="hfq",
                    open=10.5,
                    high=12,
                    low=10,
                    close=11.5,
                    volume=1200,
                    amount=13800,
                ),
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-03",
                    adjustment="hfq",
                    open=11.5,
                    high=13,
                    low=11,
                    close=12.5,
                    volume=1300,
                    amount=16250,
                ),
            ],
            "etf:510300": [
                DailyBar(
                    instrument_id="etf:510300",
                    trade_date="2024-01-01",
                    adjustment="hfq",
                    open=4,
                    high=4.2,
                    low=3.9,
                    close=4.1,
                    volume=2000,
                    amount=8200,
                ),
                DailyBar(
                    instrument_id="etf:510300",
                    trade_date="2024-01-02",
                    adjustment="hfq",
                    open=4.1,
                    high=4.3,
                    low=4.0,
                    close=4.2,
                    volume=2100,
                    amount=8820,
                ),
                DailyBar(
                    instrument_id="etf:510300",
                    trade_date="2024-01-03",
                    adjustment="hfq",
                    open=4.2,
                    high=4.4,
                    low=4.1,
                    close=4.3,
                    volume=2200,
                    amount=9460,
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

    created = client.post(
        "/api/market-data/sync",
        json={
            "provider": "fake",
            "instrument_types": ["stock", "etf"],
            "adjustment": "hfq",
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "overlap_days": 1,
        },
    )

    assert created.status_code == 201
    sync_job = created.json()["job"]
    assert sync_job["type"] == "sync_market_data"
    assert sync_job["status"] == "succeeded"
    assert sync_job["progress"] == {
        "instrument_count": 2,
        "daily_bar_count": 6,
        "synced_through": "2024-01-03",
    }

    instruments = client.get("/api/market-data/instruments")
    assert instruments.status_code == 200
    assert instruments.json() == [
        {
            "instrument_id": "etf:510300",
            "symbol": "510300",
            "name": "CSI 300 ETF",
            "instrument_type": "etf",
            "exchange": "SSE",
        },
        {
            "instrument_id": "stock:000001",
            "symbol": "000001",
            "name": "Ping An Bank",
            "instrument_type": "stock",
            "exchange": "SZSE",
        },
    ]

    bars = client.get(
        "/api/market-data/daily-bars",
        params={"instrument_id": "stock:000001", "adjustment": "hfq"},
    )
    assert bars.status_code == 200
    assert [bar["trade_date"] for bar in bars.json()] == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
    ]

    provider.replace_daily_bars(
        "stock:000001",
        [
            DailyBar(
                instrument_id="stock:000001",
                trade_date="2024-01-03",
                adjustment="hfq",
                open=11.5,
                high=13,
                low=11,
                close=12.75,
                volume=1400,
                amount=17850,
            ),
            DailyBar(
                instrument_id="stock:000001",
                trade_date="2024-01-04",
                adjustment="hfq",
                open=12.75,
                high=13.5,
                low=12.4,
                close=13.1,
                volume=1500,
                amount=19650,
            ),
        ],
    )

    refreshed = client.post(
        "/api/market-data/sync",
        json={
            "provider": "fake",
            "instrument_types": ["stock"],
            "adjustment": "hfq",
            "start_date": "2024-01-01",
            "end_date": "2024-01-04",
            "overlap_days": 1,
        },
    )

    assert refreshed.status_code == 201
    assert provider.daily_bar_requests[-1] == {
        "instrument_id": "stock:000001",
        "start_date": "2024-01-03",
        "end_date": "2024-01-04",
        "adjustment": "hfq",
    }

    refreshed_bars = client.get(
        "/api/market-data/daily-bars",
        params={"instrument_id": "stock:000001", "adjustment": "hfq"},
    ).json()
    assert [(bar["trade_date"], bar["close"]) for bar in refreshed_bars] == [
        ("2024-01-01", 10.5),
        ("2024-01-02", 11.5),
        ("2024-01-03", 12.75),
        ("2024-01-04", 13.1),
    ]

    cursors = client.get("/api/market-data/sync-cursors").json()
    assert {
        "provider": "fake",
        "data_type": "daily_bars",
        "adjustment": "hfq",
        "scope": "stock:000001",
        "last_synced_trade_date": "2024-01-04",
    } in cursors


def test_market_data_sync_failure_is_visible_on_the_job(tmp_path):
    provider = FakeMarketDataProvider(
        instruments=[],
        daily_bars={},
        fail_on_fetch=True,
    )
    client = TestClient(
        create_app(
            data_dir=tmp_path / "trademiner-data",
            data_providers={"fake": provider},
        )
    )

    failed = client.post(
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

    assert failed.status_code == 500
    failed_job = failed.json()["detail"]
    assert failed_job["status"] == "failed"
    assert failed_job["error"] == "fake provider failure"
    assert failed_job["started_at"] is not None
    assert failed_job["finished_at"] is not None

    fetched = client.get(f"/api/jobs/{failed_job['id']}")

    assert fetched.status_code == 200
    assert fetched.json() == failed_job
