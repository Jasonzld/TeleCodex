"""Codex CLI executor — runs codex as a subprocess."""

from __future__ import annotations

import logging
import subprocess

from app.config import settings

logger = logging.getLogger(__name__)


def run_codex(prompt: str) -> str:
    """Execute codex CLI with the given prompt and return stdout.

    Raises RuntimeError on failure or timeout.
    """
    cmd = [settings.codex_bin, prompt]
    logger.info("codex_exec prompt_len=%d timeout=%d", len(prompt), settings.codex_timeout_sec)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.codex_timeout_sec,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"codex timed out after {settings.codex_timeout_sec}s")
    except FileNotFoundError:
        raise RuntimeError(f"codex binary not found: {settings.codex_bin}")

    if result.returncode != 0:
        stderr = result.stderr.strip()[:500] if result.stderr else "(no stderr)"
        raise RuntimeError(f"codex exited with code {result.returncode}: {stderr}")

    output = result.stdout.strip()
    max_chars = settings.codex_max_output_chars
    if len(output) > max_chars:
        output = output[:max_chars] + f"\n\n⚠️ 输出已截断（超过 {max_chars} 字符）"

    return output
