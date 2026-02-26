"""Tests for app.core.chunker."""

from app.core.chunker import chunk_text


def test_short_text_no_split():
    text = "hello world"
    result = chunk_text(text)
    assert result == [text]


def test_empty_text():
    result = chunk_text("")
    assert result == [""]


def test_exact_limit():
    text = "a" * 4076  # MAX_CHUNK - PREFIX_RESERVE
    result = chunk_text(text)
    assert len(result) == 1


def test_long_text_splits():
    text = "word " * 2000  # ~10000 chars
    result = chunk_text(text)
    assert len(result) > 1
    for chunk in result:
        assert len(chunk) <= 4076


def test_split_prefers_newline():
    line = "x" * 3000
    text = line + "\n" + line
    result = chunk_text(text)
    assert len(result) == 2
    assert result[0] == line + "\n"


def test_split_prefers_space_over_hard_cut():
    # Build text with spaces but no newlines
    word = "abcdefghij "  # 11 chars
    text = word * 500  # 5500 chars
    result = chunk_text(text)
    assert len(result) >= 2
    # Each chunk should end at a space boundary (except possibly the last)
    for chunk in result[:-1]:
        assert chunk.endswith(" ") or chunk.endswith("\n")


def test_hard_cut_no_separators():
    text = "x" * 10000  # no spaces or newlines
    result = chunk_text(text)
    assert len(result) >= 3
    for chunk in result:
        assert len(chunk) <= 4076
    assert "".join(result) == text
