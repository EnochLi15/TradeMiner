from fastapi.testclient import TestClient

from trademiner.api.app import create_app
from trademiner.market_data.fake import FakeMarketDataProvider
from trademiner.market_data.models import DailyBar, Instrument


def test_result_snapshot_lists_details_and_comparisons_do_not_recompute(tmp_path):
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
                DailyBar("stock:000001", "2024-01-01", "hfq", 10, 10, 10, 10, 1000, 10000),
                DailyBar("stock:000001", "2024-01-02", "hfq", 12, 12, 12, 12, 1200, 14400),
                DailyBar("stock:000001", "2024-01-03", "hfq", 13, 13, 13, 13, 1300, 16900),
            ],
            "stock:000002": [
                DailyBar("stock:000002", "2024-01-01", "hfq", 8, 8, 8, 8, 800, 6400),
                DailyBar("stock:000002", "2024-01-02", "hfq", 9, 9, 9, 9, 900, 8100),
                DailyBar("stock:000002", "2024-01-03", "hfq", 7, 7, 7, 7, 700, 4900),
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
    "id": "snapshot_rank_close",
    "name": "Snapshot Rank Close",
    "params": {},
}

def select(ctx, params):
    candidates = []
    for instrument in ctx.universe(types=["stock"]):
        bars = ctx.daily_bars(
            instruments=[instrument.instrument_id],
            lookback=1,
            fields=["trade_date", "close"],
        )
        last_bar = bars[-1]
        candidates.append(
            Candidate(
                instrument_id=instrument.instrument_id,
                score=last_bar["close"],
                explanation=f"saved close at {ctx.as_of}: {last_bar['close']}",
                rank_basis="close",
                tags=["snapshot"],
                metrics={"close": last_bar["close"]},
            )
        )
    return candidates
'''
    strategy_file = tmp_path / "strategies" / "snapshot_rank_close.py"
    strategy_file.parent.mkdir()
    strategy_file.write_text(strategy_source)
    client.post("/api/strategies/discover", json={"paths": [str(strategy_file)]})

    first_run = client.post(
        "/api/strategy-runs",
        json={
            "strategy_id": "snapshot_rank_close",
            "as_of_date": "2024-01-01",
        },
    ).json()["strategy_run"]
    second_run = client.post(
        "/api/strategy-runs",
        json={
            "strategy_id": "snapshot_rank_close",
            "as_of_date": "2024-01-02",
        },
    ).json()["strategy_run"]
    first_backtest = client.post(
        "/api/selection-backtests",
        json={
            "strategy_id": "snapshot_rank_close",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
            "top_n": 1,
            "horizons": [1],
        },
    ).json()["selection_backtest"]
    second_backtest = client.post(
        "/api/selection-backtests",
        json={
            "strategy_id": "snapshot_rank_close",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "top_n": 1,
            "horizons": [1],
        },
    ).json()["selection_backtest"]

    strategy_file.write_text(
        strategy_source + "\ndef select(ctx, params):\n    raise RuntimeError('do not recompute')\n"
    )

    run_list = client.get(
        "/api/strategy-runs",
        params={"strategy_id": "snapshot_rank_close", "limit": 10},
    )
    backtest_list = client.get(
        "/api/selection-backtests",
        params={"strategy_id": "snapshot_rank_close", "limit": 10},
    )
    run_detail = client.get(f"/api/strategy-runs/{first_run['id']}")
    backtest_detail = client.get(f"/api/selection-backtests/{first_backtest['id']}")
    run_comparison = client.post(
        "/api/result-snapshots/compare",
        json={
            "snapshot_type": "strategy_run",
            "snapshot_ids": [first_run["id"], second_run["id"]],
        },
    )
    backtest_comparison = client.post(
        "/api/result-snapshots/compare",
        json={
            "snapshot_type": "selection_backtest",
            "snapshot_ids": [first_backtest["id"], second_backtest["id"]],
        },
    )

    assert run_list.status_code == 200
    assert {snapshot["id"] for snapshot in run_list.json()["items"]} == {
        first_run["id"],
        second_run["id"],
    }
    assert run_list.json()["total"] == 2
    assert backtest_list.status_code == 200
    assert {snapshot["id"] for snapshot in backtest_list.json()["items"]} == {
        first_backtest["id"],
        second_backtest["id"],
    }
    assert backtest_list.json()["total"] == 2

    assert run_detail.status_code == 200
    assert run_detail.json()["candidates"][0]["explanation"] == (
        "saved close at 2024-01-01: 10.0"
    )
    assert backtest_detail.status_code == 200
    assert backtest_detail.json()["selection_results"][0]["selection_date"] == (
        "2024-01-01"
    )

    assert run_comparison.status_code == 200
    run_comparison_body = run_comparison.json()
    assert run_comparison_body["snapshot_type"] == "strategy_run"
    assert run_comparison_body["candidate_score_deltas"]["stock:000001"] == {
        "values": {
            first_run["id"]: 10.0,
            second_run["id"]: 12.0,
        },
        "delta": 2.0,
    }
    assert backtest_comparison.status_code == 200
    backtest_comparison_body = backtest_comparison.json()
    assert backtest_comparison_body["snapshot_type"] == "selection_backtest"
    assert backtest_comparison_body["metric_deltas"]["1"]["observation_count"] == {
        "values": {
            first_backtest["id"]: 1,
            second_backtest["id"]: 2,
        },
        "delta": 1,
    }
    assert (
        backtest_comparison_body["metric_deltas"]["1"]["average_return"]["values"][
            first_backtest["id"]
        ]
        == 0.2
    )
