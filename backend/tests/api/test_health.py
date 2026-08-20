from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_returns_ok() -> None:
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint_exposes_prometheus_format() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
