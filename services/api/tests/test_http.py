"""G005 and G007: request id on every response, and CORS only for CORS_ORIGINS."""

import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_request_id_header_and_log(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="recontact.access"):
        response = client.get("/api/health", headers={"X-Request-Id": "req-test-1"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-test-1"
    assert "req-test-1" in caplog.text


def test_generated_request_id() -> None:
    response = client.get("/api/health")
    assert response.headers["x-request-id"]


def test_evil_origin_has_no_cors_headers() -> None:
    response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    names = {key.lower() for key in response.headers}
    assert "access-control-allow-origin" not in names


def test_allowed_origin_gets_cors_header() -> None:
    response = client.get("/api/health", headers={"Origin": "http://localhost:3001"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3001"
