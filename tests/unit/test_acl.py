"""Tests for app.core.acl."""

import os
from unittest.mock import patch

from app.core.acl import is_allowed


def test_empty_whitelist_allows_all():
    with patch("app.core.acl.settings") as mock_settings:
        mock_settings.allowed_user_ids = set()
        assert is_allowed(123) is True
        assert is_allowed(999) is True


def test_whitelist_allows_listed_user():
    with patch("app.core.acl.settings") as mock_settings:
        mock_settings.allowed_user_ids = {100, 200, 300}
        assert is_allowed(100) is True
        assert is_allowed(200) is True


def test_whitelist_blocks_unlisted_user():
    with patch("app.core.acl.settings") as mock_settings:
        mock_settings.allowed_user_ids = {100, 200}
        assert is_allowed(999) is False
        assert is_allowed(0) is False
