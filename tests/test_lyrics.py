"""Tests for LRC parsing, lyric-line indexing, and plain-lyrics ingest."""

from core.lyrics import (
    _is_degenerate_plain,
    _normalize_newlines,
    _result_from_payload,
    _safe_str,
    current_line_index,
    parse_lrc,
)
from core.models import LyricLine


def test_parse_lrc_basic_timestamps():
    synced = """
[00:12.00]First line
[00:15.50]Second line
[01:02.123]Third line
"""
    lines = parse_lrc(synced)
    assert [(line.time_ms, line.text) for line in lines] == [
        (12_000, "First line"),
        (15_500, "Second line"),
        (62_123, "Third line"),
    ]


def test_parse_lrc_applies_offset():
    # Parser collects every [offset:] tag first; the last value applies to all lines.
    synced = """
[offset: 500]
[00:10.00]Hello
[offset: -250]
[00:20.00]World
"""
    lines = parse_lrc(synced)
    assert lines[0].time_ms == 10_000 - 250
    assert lines[1].time_ms == 20_000 - 250
    assert lines[0].text == "Hello"
    assert lines[1].text == "World"


def test_parse_lrc_negative_offset_clamps_to_zero():
    synced = "[offset: -5000]\n[00:01.00]Early"
    lines = parse_lrc(synced)
    assert lines == [LyricLine(time_ms=0, text="Early")]


def test_parse_lrc_skips_metadata_and_blank():
    synced = """
[ar:Artist]
[ti:Title]
[00:01.00]Keep me

[al:Album]
[00:02.00]And me
"""
    lines = parse_lrc(synced)
    assert [line.text for line in lines] == ["Keep me", "And me"]


def test_parse_lrc_multi_stamp_same_text():
    synced = "[00:01.00][00:05.00]Shared"
    lines = parse_lrc(synced)
    assert [(line.time_ms, line.text) for line in lines] == [
        (1_000, "Shared"),
        (5_000, "Shared"),
    ]


def test_parse_lrc_empty_and_non_string():
    assert parse_lrc("") == []
    assert parse_lrc("   ") == []
    assert parse_lrc(None) == []  # type: ignore[arg-type]


def test_parse_lrc_sorts_out_of_order():
    synced = "[00:30.00]Later\n[00:10.00]Earlier"
    lines = parse_lrc(synced)
    assert [line.text for line in lines] == ["Earlier", "Later"]


def test_current_line_index_edges():
    lines = [
        LyricLine(time_ms=1_000, text="a"),
        LyricLine(time_ms=2_000, text="b"),
        LyricLine(time_ms=3_000, text="c"),
    ]
    assert current_line_index([], 500) == -1
    assert current_line_index(lines, 0) == -1
    assert current_line_index(lines, 999) == -1
    assert current_line_index(lines, 1_000) == 0
    assert current_line_index(lines, 1_500) == 0
    assert current_line_index(lines, 2_000) == 1
    assert current_line_index(lines, 9_999) == 2


def test_normalize_newlines_canonicalizes_crlf_and_cr():
    assert _normalize_newlines("a\r\nb\rc\n") == "a\nb\nc\n"
    assert _safe_str("line1\r\nline2\rline3") == "line1\nline2\nline3"


def test_is_degenerate_plain_detects_run_on_blob():
    short = "A short single line chorus"
    assert not _is_degenerate_plain(short)
    assert not _is_degenerate_plain("Line one\nLine two")
    blob = "Deserted throne Radioactive Hum is gone Cold alone Lifeless time Lifelong crime."
    assert len(blob) >= 80
    assert _is_degenerate_plain(blob)


def test_result_from_payload_rejects_degenerate_plain_only():
    # Mirrors LRCLIB Moon / The Congregation: long plain, zero line breaks, no sync.
    blob = (
        '""Deserted throne Radioactive Hum is gone Cold alone Lifeless time '
        "Lifelong crime Witness the unstated A moon Without light of its own Alone"
    )
    result = _result_from_payload(
        {"plainLyrics": blob, "syncedLyrics": None, "instrumental": False},
        source="test",
    )
    assert result.error == "No usable lyrics in response"
    assert result.plain_lyrics is None
    assert result.timed_lines is None


def test_result_from_payload_keeps_multiline_plain():
    plain = "Deserted throne\nRadioactive\nHum is gone\nCold alone"
    result = _result_from_payload(
        {"plainLyrics": plain, "syncedLyrics": None, "instrumental": False},
        source="test",
    )
    assert result.error is None
    assert result.plain_lyrics == plain
    assert result.timed_lines is None


def test_result_from_payload_keeps_timed_when_plain_is_degenerate():
    blob = "x" * 100
    synced = "[00:01.00]First\n[00:02.00]Second"
    result = _result_from_payload(
        {"plainLyrics": blob, "syncedLyrics": synced, "instrumental": False},
        source="test",
    )
    assert result.error is None
    assert result.timed_lines is not None
    assert [line.text for line in result.timed_lines] == ["First", "Second"]


def test_result_from_payload_normalizes_plain_crlf():
    result = _result_from_payload(
        {
            "plainLyrics": "Line one\r\nLine two\rLine three",
            "syncedLyrics": None,
            "instrumental": False,
        },
        source="test",
    )
    assert result.error is None
    assert result.plain_lyrics == "Line one\nLine two\nLine three"
