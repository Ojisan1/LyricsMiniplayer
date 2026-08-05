"""Tests for LRC parsing and lyric-line indexing."""

from core.lyrics import current_line_index, parse_lrc
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
