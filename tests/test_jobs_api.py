from fastapi.testclient import TestClient

from trademiner.api.app import create_app


def test_job_records_can_be_created_and_read_back(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "trademiner-data"))

    created = client.post(
        "/api/jobs",
        json={
            "type": "sync_market_data",
            "parameters": {"universe": "a_share", "adjustment": "hfq"},
        },
    )

    assert created.status_code == 201
    created_body = created.json()
    assert created_body["type"] == "sync_market_data"
    assert created_body["status"] == "pending"
    assert created_body["parameters"] == {"universe": "a_share", "adjustment": "hfq"}
    assert created_body["progress"] == {}
    assert created_body["error"] is None
    assert created_body["result_ref"] is None
    assert created_body["created_at"]

    fetched = client.get(f"/api/jobs/{created_body['id']}")

    assert fetched.status_code == 200
    assert fetched.json() == created_body
