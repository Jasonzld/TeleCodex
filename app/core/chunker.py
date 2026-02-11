"""Text chunker — split long output for Telegram's 4096-char limit."""

from __future__ import annotations

# Telegram max message length
MAX_CHUNK = 4096
# Reserve space for [n/N] prefix
PREFIX_RESERVE = 20


def chunk_text(text: str, max_len: int = MAX_CHUNK - PREFIX_RESERVE) -> list[str]:
    """Split text into chunks that fit within Telegram's message limit.

    Tries to split on newlines first, then on spaces, then hard-cuts.
    """
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        # Try to find a good split point
        split_at = max_len
        # Prefer splitting at newline
        nl_pos = remaining.rfind("\n", 0, max_len)
        if nl_pos > max_len // 2:
            split_at = nl_pos + 1
        else:
            # Try splitting at space
            sp_pos = remaining.rfind(" ", 0, max_len)
            if sp_pos > max_len // 2:
                split_at = sp_pos + 1

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    return chunks
