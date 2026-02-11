"""Telegram polling mode — local dev without public URL or Redis."""

from __future__ import annotations

import logging
import threading
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


def _send_typing(chat_id: int, stop_event: threading.Event) -> None:
    """Send 'typing...' indicator every 4s until stop_event is set."""
    while not stop_event.is_set():
        try:
            with httpx.Client(timeout=10) as client:
                client.post(
                    _url("sendChatAction"),
                    json={"chat_id": chat_id, "action": "typing"},
                )
        except Exception:
            pass
        stop_event.wait(4)


def _send_sync(chat_id: int, text: str, parse_mode: str | None = "Markdown") -> None:
    chunks = chunk_text(text)
    total = len(chunks)
    with httpx.Client(timeout=30) as client:
        for i, chunk in enumerate(chunks, 1):
            body = chunk
            if total > 1:
                body = f"[{i}/{total}]\n{chunk}"
            payload: dict[str, Any] = {"chat_id": chat_id, "text": body}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            try:
                resp = client.post(_url("sendMessage"), json=payload)
                if resp.status_code == 400 and parse_mode:
                    payload.pop("parse_mode", None)
                    client.post(_url("sendMessage"), json=payload)
            except Exception:
                logger.exception("send_error chat_id=%s chunk=%d/%d", chat_id, i, total)


def _do_ask(chat_id: int, user_id: int, prompt: str) -> None:
    """Execute codex and send the result, with typing indicator."""
    if not is_allowed(user_id):
        _send_sync(chat_id, "Access denied. Contact the admin.")
        return

    if not prompt.strip():
        _send_sync(chat_id, "Please provide a question, e.g.: `/ask how to sort a list?`")
        return

    # Start typing indicator
    stop_typing = threading.Event()
    typing_thread = threading.Thread(target=_send_typing, args=(chat_id, stop_typing), daemon=True)
    typing_thread.start()

    logger.info("ask user_id=%s chat_id=%s prompt_len=%d", user_id, chat_id, len(prompt))

    try:
        output = run_codex(prompt.strip())
    except RuntimeError as exc:
        stop_typing.set()
        error_msg = str(exc)
        if "timed out" in error_msg:
            _send_sync(chat_id, "Timed out. Try a shorter question or retry later.")
        elif "not found" in error_msg:
            _send_sync(chat_id, "Codex binary not found. Check CODEX_BIN config.")
        else:
            _send_sync(chat_id, f"Error: {error_msg}")
        return
    except Exception:
        stop_typing.set()
        logger.exception("unexpected_error user_id=%s", user_id)
        _send_sync(chat_id, "System error. Please retry later.")
        return

    stop_typing.set()
    _send_sync(chat_id, output)
    logger.info("done user_id=%s output_len=%d", user_id, len(output))


def _handle_message(message: dict[str, Any]) -> None:
    chat_id: int = message["chat"]["id"]
    user_id: int = message.get("from", {}).get("id", 0)
    text: str = message.get("text", "")

    if not text:
        return

    cmd, arg = _extract_command(text)

    if cmd == "/start":
        mode_hint = "Send any message directly" if settings.direct_chat else "Use `/ask <question>`"
        _send_sync(
            chat_id,
            f"Welcome to TeleCodex!\n\n"
            f"{mode_hint} to query Codex.\n"
            f"Example: `How to read CSV in Python?`\n\n"
            f"Send `/help` for more info.",
        )
        return

    if cmd == "/help":
        lines = [
            "*TeleCodex Help*\n",
            "- `/ask <question>` -- Ask Codex",
            "- `/start` -- Welcome message",
            "- `/help` -- This help\n",
        ]
        if settings.direct_chat:
            lines.insert(1, "You can also just type your question directly!\n")
        lines.extend([
            "*Examples:*",
            "`write a quicksort function`",
            "`explain Python GIL`",
        ])
        _send_sync(chat_id, "\n".join(lines))
        return

    if cmd == "/ask":
        _do_ask(chat_id, user_id, arg)
        return

    # Direct chat mode: treat any non-command text as a codex prompt
    if not cmd and settings.direct_chat:
        _do_ask(chat_id, user_id, text)
        return

    return


def run_polling() -> None:
    """Long-polling loop — no Redis, no webhook, no public URL needed."""
    token = settings.telegram_bot_token
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set. Check your .env file.")
        return

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
