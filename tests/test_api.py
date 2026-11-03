"""Tests for FastAPI server endpoints."""

from fastapi.testclient import TestClient

from api.server import app


def test_root():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "pyagent"
    assert body["version"] == "0.6.0"


def test_health_ok():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "db_path" in body
    assert "timestamp" in body
