"""Tests for app.config."""

from app.config import Settings


def test_default_settings():
    s = Settings(
        telegram_bot_token="test-token",
        telegram_webhook_secret="test-secret",
    )
    assert s.app_port == 8080
    assert s.codex_timeout_sec == 90
    assert s.queue_name == "telecodex"


def test_allowed_user_ids_parsing():
    s = Settings(
        telegram_bot_token="t",
        telegram_allowed_user_ids="111,222,333",
    )
    assert s.allowed_user_ids == {111, 222, 333}


def test_allowed_user_ids_empty():
    s = Settings(
        telegram_bot_token="t",
        telegram_allowed_user_ids="",
    )
    assert s.allowed_user_ids == set()


def test_allowed_user_ids_whitespace():
    s = Settings(
        telegram_bot_token="t",
        telegram_allowed_user_ids=" 111 , 222 , ",
    )
    assert s.allowed_user_ids == {111, 222}
