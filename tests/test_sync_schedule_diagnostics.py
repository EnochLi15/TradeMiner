from fastapi.testclient import TestClient

from trademiner.api.app import create_app
from trademiner.market_data.fake import FakeMarketDataProvider
from trademiner.market_data.models import DailyBar, Instrument


def test_scheduled_sync_configuration_and_run_reuse_manual_sync_path(tmp_path):
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
    client = TestClient(
        create_app(
            data_dir=tmp_path / "trademiner-data",
            data_providers={"fake": provider},
        )
    )

    default_schedule = client.get("/api/market-data/sync-schedule")

    assert default_schedule.status_code == 200
    assert default_schedule.json()["schedule_time"] == "16:30"
    assert default_schedule.json()["timezone"] == "Asia/Shanghai"
    assert default_schedule.json()["instrument_types"] == ["stock", "etf"]
    assert default_schedule.json()["trading_days_only"] is True

    updated_schedule = client.put(
        "/api/market-data/sync-schedule",
        json={
            "provider": "fake",
            "instrument_types": ["stock"],
            "start_date": "2024-01-01",
            "overlap_days": 1,
        },
    )
    first_run = client.post(
        "/api/market-data/sync-schedule/run",
        json={"run_date": "2024-01-02"},
    )

    assert updated_schedule.status_code == 200
    assert updated_schedule.json()["provider"] == "fake"
    assert first_run.status_code == 201
    first_job = first_run.json()["job"]
    assert first_job["type"] == "sync_market_data"
    assert first_job["status"] == "succeeded"
    assert first_job["parameters"]["trigger"] == "scheduled"
    assert provider.daily_bar_requests[-1] == {
        "instrument_id": "stock:000001",
        "start_date": "2024-01-01",
        "end_date": "2024-01-02",
        "adjustment": "hfq",
    }

    provider.replace_daily_bars(
        "stock:000001",
        [
            DailyBar("stock:000001", "2024-01-02", "hfq", 11, 11, 11, 11.5, 1150, 13225),
            DailyBar("stock:000001", "2024-01-03", "hfq", 12, 12, 12, 12, 1200, 14400),
        ],
    )
    second_run = client.post(
        "/api/market-data/sync-schedule/run",
        json={"run_date": "2024-01-03"},
    )

    assert second_run.status_code == 201
    assert provider.daily_bar_requests[-1] == {
        "instrument_id": "stock:000001",
        "start_date": "2024-01-02",
        "end_date": "2024-01-03",
        "adjustment": "hfq",
    }

    cursors = client.get("/api/market-data/sync-cursors").json()
    assert {
        "provider": "fake",
        "data_type": "daily_bars",
        "adjustment": "hfq",
        "scope": "stock:000001",
        "last_synced_trade_date": "2024-01-03",
    } in cursors

    diagnostics = client.get("/api/market-data/sync-diagnostics")

    assert diagnostics.status_code == 200
    assert diagnostics.json()["last_successful_job"]["id"] == second_run.json()["job"]["id"]
    assert diagnostics.json()["last_successful_sync_time"] is not None
    assert diagnostics.json()["running_jobs"] == []
    assert diagnostics.json()["recent_failures"] == []
    assert diagnostics.json()["recent_jobs"][0]["id"] == second_run.json()["job"]["id"]


def test_failed_scheduled_sync_preserves_job_error_in_diagnostics(tmp_path):
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
    client.put(
        "/api/market-data/sync-schedule",
        json={
            "provider": "fake",
            "instrument_types": ["stock"],
            "start_date": "2024-01-01",
            "overlap_days": 1,
        },
    )

    failed = client.post(
        "/api/market-data/sync-schedule/run",
        json={"run_date": "2024-01-02"},
    )
    diagnostics = client.get("/api/market-data/sync-diagnostics")

    assert failed.status_code == 500
    failed_job = failed.json()["detail"]
    assert failed_job["type"] == "sync_market_data"
    assert failed_job["status"] == "failed"
    assert failed_job["parameters"]["trigger"] == "scheduled"
    assert failed_job["error"] == "fake provider failure"
    assert diagnostics.status_code == 200
    assert diagnostics.json()["recent_failures"][0]["id"] == failed_job["id"]
    assert diagnostics.json()["recent_failures"][0]["error"] == "fake provider failure"
