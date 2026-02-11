"""Configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    log_level: str = "INFO"

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_allowed_user_ids: str = ""  # comma-separated

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "telecodex"

    # Codex
    codex_bin: str = "codex"
    codex_timeout_sec: int = 90
    codex_max_output_chars: int = 12000
    codex_concurrency_per_user: int = 1
    codex_global_concurrency: int = 4

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def allowed_user_ids(self) -> set[int]:
        if not self.telegram_allowed_user_ids.strip():
            return set()
        return {int(uid.strip()) for uid in self.telegram_allowed_user_ids.split(",") if uid.strip()}


settings = Settings()
