from fastapi.testclient import TestClient

from trademiner.api.app import create_app


def test_system_status_initializes_persistence_foundation(tmp_path):
    data_dir = tmp_path / "trademiner-data"
    client = TestClient(create_app(data_dir=data_dir))

    response = client.get("/api/system/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "data_dir": str(data_dir),
        "metadata_store": {
            "kind": "sqlite",
            "path": str(data_dir / "trademiner.sqlite"),
            "initialized": True,
        },
        "analytical_store": {
            "kind": "duckdb_parquet",
            "duckdb_path": str(data_dir / "market" / "trademiner.duckdb"),
            "parquet_dir": str(data_dir / "market" / "parquet"),
            "initialized": True,
        },
    }

    assert (data_dir / "trademiner.sqlite").is_file()
    assert (data_dir / "market" / "trademiner.duckdb").is_file()
    assert (data_dir / "market" / "parquet").is_dir()
