from typer.testing import CliRunner

from trademiner.cli import cli, create_cli
from trademiner.market_data.fake import FakeMarketDataProvider
from trademiner.market_data.models import DailyBar, Instrument


def test_cli_status_initializes_and_reports_storage(tmp_path):
    data_dir = tmp_path / "trademiner-data"
    result = CliRunner().invoke(cli, ["status", "--data-dir", str(data_dir)])

    assert result.exit_code == 0
    assert "status: ok" in result.stdout
    assert f"data_dir: {data_dir}" in result.stdout
    assert f"metadata_store: {data_dir / 'trademiner.sqlite'}" in result.stdout
    assert f"analytical_store: {data_dir / 'market' / 'trademiner.duckdb'}" in result.stdout


def test_cli_sync_market_data_uses_application_sync_workflow(tmp_path):
    data_dir = tmp_path / "trademiner-data"
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
                )
            ]
        },
    )
    app = create_cli(data_providers={"fake": provider})

    result = CliRunner().invoke(
        app,
        [
            "sync-market-data",
            "--data-dir",
            str(data_dir),
            "--provider",
            "fake",
            "--instrument-type",
            "stock",
            "--adjustment",
            "hfq",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2024-01-01",
        ],
    )

    assert result.exit_code == 0
    assert "status: succeeded" in result.stdout
    assert provider.daily_bar_requests == [
        {
            "instrument_id": "stock:000001",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
            "adjustment": "hfq",
        }
    ]


def test_cli_can_discover_and_run_current_strategy(tmp_path):
    data_dir = tmp_path / "trademiner-data"
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
                )
            ]
        },
    )
    strategy_source = '''\
from trademiner.strategy import Candidate

STRATEGY = {
    "id": "cli_strategy",
    "name": "CLI Strategy",
    "params": {},
}

def select(ctx, params):
    instrument = ctx.universe(types=["stock"])[0]
    return [
        Candidate(
            instrument_id=instrument.instrument_id,
            score=1,
            explanation="selected from CLI",
        )
    ]
'''
    strategy_file = tmp_path / "strategies" / "cli_strategy.py"
    strategy_file.parent.mkdir()
    strategy_file.write_text(strategy_source)
    app = create_cli(data_providers={"fake": provider})
    runner = CliRunner()

    sync = runner.invoke(
        app,
        [
            "sync-market-data",
            "--data-dir",
            str(data_dir),
            "--provider",
            "fake",
            "--instrument-type",
            "stock",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2024-01-01",
        ],
    )
    discover = runner.invoke(
        app,
        ["discover-strategies", "--data-dir", str(data_dir), "--path", str(strategy_file)],
    )
    run = runner.invoke(
        app,
        [
            "run-strategy",
            "--data-dir",
            str(data_dir),
            "--strategy-id",
            "cli_strategy",
            "--as-of-date",
            "2024-01-01",
        ],
    )

    assert sync.exit_code == 0
    assert discover.exit_code == 0
    assert "strategy_id: cli_strategy" in discover.stdout
    assert run.exit_code == 0
    assert "status: succeeded" in run.stdout
    assert "candidate_count: 1" in run.stdout
    assert "strategy_run_id:" in run.stdout


def test_cli_can_run_selection_backtest_for_discovered_strategy(tmp_path):
    data_dir = tmp_path / "trademiner-data"
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
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-01",
                    adjustment="hfq",
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    volume=1000,
                    amount=10000,
                ),
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-02",
                    adjustment="hfq",
                    open=11,
                    high=11,
                    low=11,
                    close=11,
                    volume=1100,
                    amount=12100,
                ),
            ]
        },
    )
    strategy_source = '''\
from trademiner.strategy import Candidate

STRATEGY = {
    "id": "cli_backtest_strategy",
    "name": "CLI Backtest Strategy",
    "params": {},
}

def select(ctx, params):
    instrument = ctx.universe(types=["stock"])[0]
    return [
        Candidate(
            instrument_id=instrument.instrument_id,
            score=1,
            explanation=f"selected at {ctx.as_of}",
        )
    ]
'''
    strategy_file = tmp_path / "strategies" / "cli_backtest_strategy.py"
    strategy_file.parent.mkdir()
    strategy_file.write_text(strategy_source)
    app = create_cli(data_providers={"fake": provider})
    runner = CliRunner()

    sync = runner.invoke(
        app,
        [
            "sync-market-data",
            "--data-dir",
            str(data_dir),
            "--provider",
            "fake",
            "--instrument-type",
            "stock",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2024-01-02",
        ],
    )
    discover = runner.invoke(
        app,
        ["discover-strategies", "--data-dir", str(data_dir), "--path", str(strategy_file)],
    )
    backtest = runner.invoke(
        app,
        [
            "run-selection-backtest",
            "--data-dir",
            str(data_dir),
            "--strategy-id",
            "cli_backtest_strategy",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2024-01-01",
            "--top-n",
            "1",
            "--horizon",
            "1",
        ],
    )

    assert sync.exit_code == 0
    assert discover.exit_code == 0
    assert backtest.exit_code == 0
    assert "status: succeeded" in backtest.stdout
    assert "selection_backtest_id:" in backtest.stdout
    assert "selection_date_count: 1" in backtest.stdout
    assert "observation_count: 1" in backtest.stdout


def test_cli_sync_status_reports_schedule_and_recent_diagnostics(tmp_path):
    data_dir = tmp_path / "trademiner-data"
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
                DailyBar(
                    instrument_id="stock:000001",
                    trade_date="2024-01-01",
                    adjustment="hfq",
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    volume=1000,
                    amount=10000,
                )
            ]
        },
    )
    app = create_cli(data_providers={"fake": provider})
    runner = CliRunner()

    sync = runner.invoke(
        app,
        [
            "sync-market-data",
            "--data-dir",
            str(data_dir),
            "--provider",
            "fake",
            "--instrument-type",
            "stock",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2024-01-01",
        ],
    )
    status = runner.invoke(app, ["sync-status", "--data-dir", str(data_dir)])

    assert sync.exit_code == 0
    assert status.exit_code == 0
    assert "schedule_time: 16:30" in status.stdout
    assert "timezone: Asia/Shanghai" in status.stdout
    assert "last_successful_sync_time:" in status.stdout
    assert "recent_jobs: 1" in status.stdout
    assert "recent_failures: 0" in status.stdout
