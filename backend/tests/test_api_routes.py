"""Regressions for status routes, API errors, authentication and SPA fallback.

TestClient is intentionally used without the application lifespan: no monitor,
database, NUT connection or shutdown client is started.
"""
from types import SimpleNamespace

import main
import pytest
from api import status, websocket
from fastapi.testclient import TestClient
from models import UpsData, UpsStatus
from starlette.websockets import WebSocketDisconnect

TOKEN = "route-regression-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.auth_middleware, "skip_auth", False)
    monkeypatch.setattr(main.auth_middleware, "api_token", TOKEN)
    monkeypatch.setattr(type(main.settings), "get_or_generate_api_token", lambda self: TOKEN)
    return TestClient(main.app)


@pytest.fixture
def monitor():
    data = UpsData(status=UpsStatus.ONLINE, battery_charge=100)
    return SimpleNamespace(
        get_current_data=lambda: data,
        shutdown_manager=SimpleNamespace(get_status=lambda: {"shutting_down": False}),
    )


@pytest.mark.parametrize("path", ["/api", "/api/ups", "/api/missing", "/api/missing/nested"])
def test_unknown_api_get_returns_404(client, path):
    response = client.get(path, headers=HEADERS)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("path", ["/api/ups", "/api/missing", "/api/status"])
def test_api_authentication_precedes_routing(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_status_route_returns_live_data(client, monitor, monkeypatch):
    monkeypatch.setattr(status, "get_monitor", lambda: monitor)
    response = client.get("/api/status", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "ONLINE"
    assert response.json()["battery_charge"] == 100
    assert response.json()["shutdown"] == {"shutting_down": False}


@pytest.mark.parametrize("monitor", [None, SimpleNamespace(get_current_data=lambda: None)])
def test_status_without_data_remains_503(client, monitor, monkeypatch):
    monkeypatch.setattr(status, "get_monitor", lambda: monitor)
    assert client.get("/api/status", headers=HEADERS).status_code == 503


def test_status_wrong_method_remains_405(client):
    assert client.post("/api/status", headers=HEADERS).status_code == 405


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_spa_fallback_preserves_page_routes(client, tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>UPS Guard</html>")
    monkeypatch.setattr(main, "STATIC_DIR", tmp_path)
    for path in ("/", "/dashboard", "/apiary"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.text == "<html>UPS Guard</html>"
    assert client.get("/api/missing", headers=HEADERS).status_code == 404


def test_openapi_lists_real_status_route(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths["/api/status"]
    assert "/api/ups" not in paths
    assert "/{full_path}" not in paths


@pytest.mark.parametrize("token", ["", "invalid"])
def test_websocket_rejects_missing_or_invalid_token(client, token):
    with (
        pytest.raises(WebSocketDisconnect) as error,
        client.websocket_connect(f"/api/ws?token={token}"),
    ):
        pass
    assert error.value.code == 4001


def test_websocket_uses_api_prefix_and_status_update(client, monitor, monkeypatch):
    monkeypatch.setattr(websocket, "get_monitor", lambda: monitor)
    with client.websocket_connect(f"/api/ws?token={TOKEN}") as connection:
        message = connection.receive_json()
        assert message["type"] == "status_update"
        assert message["data"]["status"] == "ONLINE"
        assert message["data"]["shutdown"] == {"shutting_down": False}
