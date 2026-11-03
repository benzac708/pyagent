"""Tests for FastAPI server endpoints."""

from fastapi.testclient import TestClient

from api.server import app


def test_root():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "pyagent"
        assert body["version"] == "0.7.0"


def test_health_ok():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "db_path" in body
        assert "timestamp" in body


def test_run_endpoint():
    from unittest.mock import patch

    from tests.helpers import make_response

    with TestClient(app) as client:
        with patch("agent.loop.chain") as mock_chain:
            mock_chain.chat.return_value = (make_response(content="api reply", total_tokens=5), "primary")
            r = client.post("/run", json={"prompt": "hello"})
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "completed"
            assert body["response"] == "api reply"
