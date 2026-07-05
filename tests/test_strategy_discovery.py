from hashlib import sha256
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest

from trademiner.api.app import create_app
from trademiner.strategy.discovery import default_source_strategy_dir


def test_strategy_discovery_persists_metadata_source_snapshot_and_validates_params(
    tmp_path,
):
    strategy_source = '''\
STRATEGY = {
    "id": "momentum_breakout_v1",
    "name": "Momentum Breakout",
    "description": "Ranks instruments by recent momentum.",
    "params": {
        "lookback_days": {"type": "int", "default": 60, "min": 20, "max": 250},
        "top_n": {"type": "int", "default": 20, "min": 1, "max": 100},
        "include_etfs": {"type": "bool", "default": True},
    },
}

def select(ctx, params):
    return []
'''
    strategy_file = tmp_path / "strategies" / "momentum.py"
    strategy_file.parent.mkdir()
    strategy_file.write_text(strategy_source)
    client = TestClient(create_app(data_dir=tmp_path / "trademiner-data"))

    discovered = client.post(
        "/api/strategies/discover",
        json={"paths": [str(strategy_file.parent)]},
    )

    assert discovered.status_code == 201
    discovered_body = discovered.json()
    assert [strategy["strategy_id"] for strategy in discovered_body["strategies"]] == [
        "momentum_breakout_v1"
    ]

    strategies = client.get("/api/strategies")
    assert strategies.status_code == 200
    strategy = strategies.json()[0]
    assert strategy == {
        "strategy_id": "momentum_breakout_v1",
        "name": "Momentum Breakout",
        "description": "Ranks instruments by recent momentum.",
        "file_path": str(strategy_file),
        "params": {
            "lookback_days": {
                "type": "int",
                "default": 60,
                "min": 20,
                "max": 250,
            },
            "top_n": {"type": "int", "default": 20, "min": 1, "max": 100},
            "include_etfs": {"type": "bool", "default": True},
        },
        "latest_version": {
            "source_hash": sha256(strategy_source.encode()).hexdigest(),
            "source_snapshot": strategy_source,
            "git_commit": None,
            "git_dirty": None,
            "created_at": strategy["latest_version"]["created_at"],
        },
    }
    assert strategy["latest_version"]["created_at"]

    detail = client.get("/api/strategies/momentum_breakout_v1")
    assert detail.status_code == 200
    assert detail.json()["latest_version"]["source_snapshot"] == strategy_source

    validated = client.post(
        "/api/strategies/momentum_breakout_v1/validate-parameters",
        json={"params": {"lookback_days": 30}},
    )

    assert validated.status_code == 200
    assert validated.json() == {
        "params": {
            "lookback_days": 30,
            "top_n": 20,
            "include_etfs": True,
        }
    }

    invalid = client.post(
        "/api/strategies/momentum_breakout_v1/validate-parameters",
        json={"params": {"lookback_days": 10}},
    )

    assert invalid.status_code == 422
    assert "lookback_days" in invalid.json()["detail"]


def test_strategy_discovery_records_git_metadata_when_available(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    repo = tmp_path / "strategy-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)

    strategy_source = '''\
STRATEGY = {
    "id": "git_strategy",
    "name": "Git Strategy",
    "params": {},
}

def select(ctx, params):
    return []
'''
    strategy_file = repo / "git_strategy.py"
    strategy_file.write_text(strategy_source)
    subprocess.run(["git", "add", "git_strategy.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add strategy"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    client = TestClient(create_app(data_dir=tmp_path / "trademiner-data"))

    clean = client.post(
        "/api/strategies/discover",
        json={"paths": [str(strategy_file)]},
    )

    assert clean.status_code == 201
    clean_version = clean.json()["strategies"][0]["latest_version"]
    assert clean_version["git_commit"] == commit
    assert clean_version["git_dirty"] is False

    dirty_source = strategy_source + "\n# local research tweak\n"
    strategy_file.write_text(dirty_source)
    dirty = client.post(
        "/api/strategies/discover",
        json={"paths": [str(strategy_file)]},
    )

    assert dirty.status_code == 201
    dirty_version = dirty.json()["strategies"][0]["latest_version"]
    assert dirty_version["git_commit"] == commit
    assert dirty_version["git_dirty"] is True
    assert dirty_version["source_hash"] == sha256(dirty_source.encode()).hexdigest()
    assert dirty_version["source_snapshot"] == dirty_source


def test_source_strategies_sync_reads_repository_strategy_sources(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "trademiner-data"))

    synced = client.post("/api/strategies/sync-source")

    assert synced.status_code == 201
    body = synced.json()
    assert body["source_path"] == str(default_source_strategy_dir())
    strategy_ids = [strategy["strategy_id"] for strategy in body["strategies"]]
    assert "daily_momentum_v1" in strategy_ids
    assert "__init__" not in strategy_ids

    strategies = client.get("/api/strategies")

    assert strategies.status_code == 200
    listed_strategy_ids = [strategy["strategy_id"] for strategy in strategies.json()]
    assert "daily_momentum_v1" in listed_strategy_ids

    daily_momentum = next(
        strategy
        for strategy in strategies.json()
        if strategy["strategy_id"] == "daily_momentum_v1"
    )
    source_file = default_source_strategy_dir() / "daily_momentum.py"
    source_snapshot = source_file.read_text()
    assert daily_momentum["file_path"] == str(source_file)
    assert daily_momentum["latest_version"]["source_snapshot"] == source_snapshot
    assert daily_momentum["latest_version"]["source_hash"] == sha256(
        source_snapshot.encode()
    ).hexdigest()
