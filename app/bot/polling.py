"""Telegram polling mode — local dev without public URL or Redis."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.core.acl import is_allowed
from app.core.chunker import chunk_text
from app.worker.codex_exec import run_codex

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}"


def _url(method: str) -> str:
    return f"{_API_BASE.format(token=settings.telegram_bot_token)}/{method}"


def _extract_command(text: str) -> tuple[str, str]:
    text = text.strip()
    if not text.startswith("/"):
        return ("", text)
    parts = text.split(None, 1)
    cmd = parts[0].lower().split("@")[0]
    arg = parts[1] if len(parts) > 1 else ""
    return (cmd, arg)


def _send_sync(chat_id: int, text: str) -> None:
    chunks = chunk_text(text)
    total = len(chunks)
    with httpx.Client(timeout=30) as client:
        for i, chunk in enumerate(chunks, 1):
            body = chunk
            if total > 1:
                body = f"[{i}/{total}]\n{chunk}"
            try:
                client.post(
                    _url("sendMessage"),
                    json={"chat_id": chat_id, "text": body, "parse_mode": "Markdown"},
                )
            except Exception:
                logger.exception("send_error chat_id=%s chunk=%d/%d", chat_id, i, total)


def _handle_message(message: dict[str, Any]) -> None:
    chat_id: int = message["chat"]["id"]
    user_id: int = message.get("from", {}).get("id", 0)
    text: str = message.get("text", "")

    if not text:
        return

    cmd, arg = _extract_command(text)

    if cmd == "/start":
        _send_sync(
            chat_id,
            "Welcome to TeleCodex!\n\n"
            "Send `/ask <question>` to query Codex.\n"
            "Example: `/ask How to read CSV in Python?`\n\n"
            "Send `/help` for more info.",
        )
        return

    if cmd == "/help":
        _send_sync(
            chat_id,
            "*TeleCodex Help*\n\n"
            "- `/ask <question>` -- Ask Codex\n"
            "- `/start` -- Welcome message\n"
            "- `/help` -- This help\n\n"
            "*Examples:*\n"
            "`/ask write a quicksort function`\n"
            "`/ask explain Python GIL`",
        )
        return

    if cmd == "/ask":
        if not is_allowed(user_id):
            _send_sync(chat_id, "Access denied. Contact the admin.")
            return

        if not arg.strip():
            _send_sync(chat_id, "Please provide a question, e.g.: `/ask how to sort a list?`")
            return

        _send_sync(chat_id, "Accepted, processing...")
        logger.info("ask user_id=%s chat_id=%s prompt_len=%d", user_id, chat_id, len(arg))

        try:
            output = run_codex(arg.strip())
        except RuntimeError as exc:
            error_msg = str(exc)
            if "timed out" in error_msg:
                _send_sync(chat_id, "Timed out. Try a shorter question or retry later.")
            elif "not found" in error_msg:
                _send_sync(chat_id, "Codex binary not found. Check CODEX_BIN config.")
            else:
                _send_sync(chat_id, f"Execution error: {error_msg}")
            return
        except Exception:
            logger.exception("unexpected_error user_id=%s", user_id)
            _send_sync(chat_id, "System error. Please retry later.")
            return

        _send_sync(chat_id, output)
        logger.info("done user_id=%s output_len=%d", user_id, len(output))
        return

    # Unknown command or plain text — ignore silently
    return


def run_polling() -> None:
    """Long-polling loop — no Redis, no webhook, no public URL needed."""
    token = settings.telegram_bot_token
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set. Check your .env file.")
        return

    # Delete any existing webhook so polling works
    with httpx.Client(timeout=10) as client:
        client.post(_url("deleteWebhook"))

    print(f"TeleCodex polling started (bot token ...{token[-6:]})")
    print("Press Ctrl+C to stop.\n")

    offset = 0
    while True:
        try:
            with httpx.Client(timeout=35) as client:
                resp = client.post(
                    _url("getUpdates"),
                    json={"offset": offset, "timeout": 30},
                )
                data = resp.json()

            if not data.get("ok"):
                logger.warning("getUpdates failed: %s", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    try:
                        _handle_message(message)
                    except Exception:
                        logger.exception("handle_error update_id=%s", update.get("update_id"))

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception:
            logger.exception("polling_error")
            time.sleep(5)
