"""TeleCodex one-click launcher.

Usage:
    python launcher.py              # polling mode (default, no Redis needed)
    python launcher.py --webhook    # webhook mode (needs Redis + public URL)
"""

from __future__ import annotations

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    webhook = "--webhook" in sys.argv

    if webhook:
        _start_webhook_mode()
    else:
        _start_polling_mode()


def _start_polling_mode() -> None:
    """Single-process polling — no Redis, no public URL."""
    import logging
    from app.config import settings

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not settings.telegram_bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN is empty.")
        print("Edit .env and set your bot token, then retry.")
        sys.exit(1)

    print("=" * 50)
    print("  TeleCodex — Local Polling Mode")
    print("=" * 50)
    print()
    print(f"  Bot token : ...{settings.telegram_bot_token[-6:]}")
    print(f"  Codex bin : {settings.codex_bin}")
    print(f"  Timeout   : {settings.codex_timeout_sec}s")
    wl = settings.allowed_user_ids
    print(f"  Whitelist : {wl if wl else '(all users allowed)'}")
    print()
    print("  No Redis needed. No public URL needed.")
    print("  Messages are processed in-process.")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 50)
    print()

    from app.bot.polling import run_polling
    run_polling()


def _start_webhook_mode() -> None:
    """Start Redis check + API + Worker via subprocess."""
    import subprocess
    import time
    from app.config import settings

    if not settings.telegram_bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN is empty.")
        sys.exit(1)

    print("=" * 50)
    print("  TeleCodex — Webhook Mode")
    print("=" * 50)
    print()

    # Check Redis
    print("[1/3] Checking Redis...")
    try:
        from redis import Redis
        r = Redis.from_url(settings.redis_url, socket_connect_timeout=3)
        r.ping()
        print(f"  Redis OK ({settings.redis_url})")
    except Exception as e:
        print(f"  Redis FAILED: {e}")
        print()
        print("  Redis is required for webhook mode.")
        print("  Options:")
        print("    - Install Redis and start it")
        print("    - Use Docker: docker run -d -p 6379:6379 redis:7-alpine")
        print("    - Or use polling mode: python launcher.py")
        sys.exit(1)

    processes: list[tuple[str, subprocess.Popen]] = []  # type: ignore[type-arg]

    try:
        # Start API
        print("[2/3] Starting API server...")
        api_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", settings.app_host, "--port", str(settings.app_port)],
        )
        processes.append(("API", api_proc))
        time.sleep(1)

        # Start Worker
        print("[3/3] Starting Worker...")
        worker_proc = subprocess.Popen(
            [sys.executable, "-m", "app.worker.runner"],
        )
        processes.append(("Worker", worker_proc))

        print()
        print(f"  API     : http://{settings.app_host}:{settings.app_port}")
        print(f"  Webhook : http://{settings.app_host}:{settings.app_port}/telegram/webhook")
        print(f"  Health  : http://{settings.app_host}:{settings.app_port}/healthz")
        print()
        print("  Set webhook with:")
        print(f"  curl \"https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://YOUR_URL/telegram/webhook\"")
        print()
        print("  Press Ctrl+C to stop all services.")
        print("=" * 50)

        # Wait for any process to exit
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"\n  {name} exited with code {ret}")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n  Stopping all services...")
        for name, proc in processes:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            print(f"  {name} stopped.")
        print("  Done.")


if __name__ == "__main__":
    main()
