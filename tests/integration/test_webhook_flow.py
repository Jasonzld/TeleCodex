"""Integration test — webhook endpoint flow."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with patch("app.api.webhook.settings") as mock_settings, \
         patch("app.api.webhook._redis"), \
         patch("app.api.webhook._queue") as mock_queue:
        mock_settings.telegram_webhook_secret = ""
        mock_settings.telegram_bot_token = "test-token"
        mock_settings.telegram_allowed_user_ids = ""
        mock_settings.allowed_user_ids = set()
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.queue_name = "telecodex"
        mock_settings.codex_timeout_sec = 90
        mock_settings.codex_bin = "codex"
        mock_settings.codex_max_output_chars = 12000

        from app.main import app
        yield TestClient(app)


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_no_message(client):
    resp = client.post("/telegram/webhook", json={"update_id": 1})
    assert resp.status_code == 200
    assert resp.json()["detail"] == "no_message"


def test_webhook_empty_text(client):
    body = {
        "update_id": 2,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 1},
            "text": "",
        },
    }
    resp = client.post("/telegram/webhook", json=body)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "no_text"


@patch("app.bot.telegram_client.send_message", new_callable=AsyncMock)
def test_webhook_start_command(mock_send, client):
    body = {
        "update_id": 3,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 1},
            "text": "/start",
        },
    }
    resp = client.post("/telegram/webhook", json=body)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "start"


@patch("app.bot.telegram_client.send_message", new_callable=AsyncMock)
def test_webhook_ask_empty(mock_send, client):
    body = {
        "update_id": 4,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 1},
            "text": "/ask",
        },
    }
    resp = client.post("/telegram/webhook", json=body)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "empty_ask"
