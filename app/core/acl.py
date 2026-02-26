"""Access control — whitelist by user_id."""

from __future__ import annotations

from app.config import settings


def is_allowed(user_id: int) -> bool:
    """Check if a user is in the allowed whitelist.

    If no whitelist is configured (empty), all users are allowed.
    """
    allowed = settings.allowed_user_ids
    if not allowed:
        return True
    return user_id in allowed
