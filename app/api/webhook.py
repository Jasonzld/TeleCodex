"""Telegram webhook endpoint."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from redis import Redis
from rq import Queue

from app.config import settings
from app.core.acl import is_allowed
from app.worker.jobs import execute_codex_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])

_redis = Redis.from_url(settings.redis_url)
_queue = Queue(settings.queue_name, connection=_redis)

# Simple dedup cache (update_id -> True), short-lived in-memory
_seen_updates: dict[int, bool] = {}
_SEEN_MAX = 10000


def _verify_secret(secret_token: str | None) -> None:
    """Verify Telegram webhook secret token."""
    expected = settings.telegram_webhook_secret
    if not expected:
        return  # no secret configured, skip
    if not secret_token or not hmac.compare_digest(secret_token, expected):
        raise HTTPException(status_code=403, detail="Invalid secret token")


def _extract_command(text: str) -> tuple[str, str]:
    """Extract command and argument from message text.

    Returns (command, argument). command includes the leading slash.
    """
    text = text.strip()
    if not text.startswith("/"):
        return ("", text)
    parts = text.split(None, 1)
    cmd = parts[0].lower().split("@")[0]  # strip @botname
    arg = parts[1] if len(parts) > 1 else ""
    return (cmd, arg)


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> dict[str, Any]:
    _verify_secret(x_telegram_bot_api_secret_token)
    body: dict[str, Any] = await request.json()

    update_id = body.get("update_id")
    if update_id and update_id in _seen_updates:
        return {"ok": True, "detail": "duplicate"}
    if update_id:
        _seen_updates[update_id] = True
        if len(_seen_updates) > _SEEN_MAX:
            oldest = list(_seen_updates.keys())[: _SEEN_MAX // 2]
            for k in oldest:
                _seen_updates.pop(k, None)

    message = body.get("message")
    if not message:
        return {"ok": True, "detail": "no_message"}

    chat_id: int = message["chat"]["id"]
    user_id: int = message.get("from", {}).get("id", 0)
    text: str = message.get("text", "")

    if not text:
        return {"ok": True, "detail": "no_text"}

    cmd, arg = _extract_command(text)

    if cmd == "/start":
        from app.bot.telegram_client import send_message
        await send_message(
            chat_id,
            "👋 欢迎使用 TeleCodex！\n\n"
            "发送 `/ask <问题>` 即可获取 Codex 的回答。\n"
            "例如：`/ask 如何用 Python 读取 CSV？`\n\n"
            "发送 `/help` 查看更多信息。",
        )
        return {"ok": True, "detail": "start"}

    if cmd == "/help":
        from app.bot.telegram_client import send_message
        await send_message(
            chat_id,
            "📖 *TeleCodex 使用帮助*\n\n"
            "• `/ask <问题>` — 向 Codex 提问\n"
            "• `/start` — 查看欢迎信息\n"
            "• `/help` — 查看本帮助\n\n"
            "*示例：*\n"
            "`/ask 写一个快速排序函数`\n"
            "`/ask 解释 Python 的 GIL`",
        )
        return {"ok": True, "detail": "help"}

    if cmd == "/ask":
        if not is_allowed(user_id):
            from app.bot.telegram_client import send_message
            await send_message(chat_id, "🚫 你没有使用权限，请联系管理员。")
            return {"ok": True, "detail": "unauthorized"}

        if not arg.strip():
            from app.bot.telegram_client import send_message
            await send_message(
                chat_id,
                "请提供问题内容，例如：`/ask 如何排序列表？`",
            )
            return {"ok": True, "detail": "empty_ask"}

        # Enqueue task
        _queue.enqueue(
            execute_codex_task,
            chat_id=chat_id,
            user_id=user_id,
            prompt=arg.strip(),
            job_timeout=settings.codex_timeout_sec + 30,
        )

        from app.bot.telegram_client import send_message
        await send_message(chat_id, "✅ 已受理，正在处理...")

        logger.info("task_enqueued user_id=%s chat_id=%s prompt_len=%d", user_id, chat_id, len(arg))
        return {"ok": True, "detail": "enqueued"}

    return {"ok": True, "detail": "unknown_command"}
