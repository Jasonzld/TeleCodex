"""RQ job definitions."""

from __future__ import annotations

import logging

from app.bot.telegram_client import send_message_sync
from app.worker.codex_exec import run_codex

logger = logging.getLogger(__name__)


def execute_codex_task(chat_id: int, user_id: int, prompt: str) -> None:
    """RQ job: run codex and send the result back to Telegram."""
    logger.info("job_start user_id=%s chat_id=%s prompt_len=%d", user_id, chat_id, len(prompt))

    try:
        output = run_codex(prompt)
    except RuntimeError as exc:
        error_msg = str(exc)
        if "timed out" in error_msg:
            send_message_sync(chat_id, "⏰ 执行超时，请缩短问题或稍后重试。")
        elif "not found" in error_msg:
            send_message_sync(chat_id, "❌ Codex 服务不可用，请联系管理员。")
        else:
            send_message_sync(chat_id, "❌ 执行出错，请稍后重试。")
        logger.error("job_failed user_id=%s error=%s", user_id, error_msg)
        return
    except Exception:
        send_message_sync(chat_id, "❌ 系统异常，请稍后重试。")
        logger.exception("job_unexpected_error user_id=%s", user_id)
        return

    send_message_sync(chat_id, output)
    logger.info("job_done user_id=%s chat_id=%s output_len=%d", user_id, chat_id, len(output))
