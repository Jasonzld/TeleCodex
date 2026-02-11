"""Telegram Bot API client — send messages with chunking support."""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.core.chunker import chunk_text

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}"


def _url(method: str) -> str:
    return f"{_API_BASE.format(token=settings.telegram_bot_token)}/{method}"


async def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown",
) -> None:
    """Send a message to a Telegram chat, auto-chunking if needed."""
    chunks = chunk_text(text)
    total = len(chunks)
    async with httpx.AsyncClient(timeout=30) as client:
        for i, chunk in enumerate(chunks, 1):
            body = chunk
            if total > 1:
                body = f"[{i}/{total}]\n{chunk}"
            try:
                resp = await client.post(
                    _url("sendMessage"),
                    json={
                        "chat_id": chat_id,
                        "text": body,
                        "parse_mode": parse_mode,
                    },
                )
                if resp.status_code != 200:
                    logger.warning(
                        "telegram_send_failed chat_id=%s status=%s body=%s",
                        chat_id,
                        resp.status_code,
                        resp.text[:200],
                    )
            except Exception:
                logger.exception("telegram_send_error chat_id=%s chunk=%d/%d", chat_id, i, total)


def send_message_sync(
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown",
) -> None:
    """Synchronous version for use inside RQ workers."""
    chunks = chunk_text(text)
    total = len(chunks)
    with httpx.Client(timeout=30) as client:
        for i, chunk in enumerate(chunks, 1):
            body = chunk
            if total > 1:
                body = f"[{i}/{total}]\n{chunk}"
            try:
                resp = client.post(
                    _url("sendMessage"),
                    json={
                        "chat_id": chat_id,
                        "text": body,
                        "parse_mode": parse_mode,
                    },
                )
                if resp.status_code != 200:
                    logger.warning(
                        "telegram_send_failed chat_id=%s status=%s",
                        chat_id,
                        resp.status_code,
                    )
            except Exception:
                logger.exception("telegram_send_error chat_id=%s chunk=%d/%d", chat_id, i, total)
