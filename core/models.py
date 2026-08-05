"""Shared data models for now-playing metadata and lyrics."""

from __future__ import annotations

from dataclasses import dataclass

# Selectable window sizes. Only the names live here, because a settings file has
# to be validated against them; the pixel dimensions belong to ui/miniplayer.py,
# which owns layout.
WINDOW_SIZES = ("compact", "standard", "tall")
DEFAULT_WINDOW_SIZE = "standard"


@dataclass
class NowPlaying:
    """Currently playing track metadata from Windows SMTC."""

    title: str = ""
    artist: str = ""
    album: str = ""
    duration_ms: int = 0
    position_ms: int = 0
    is_playing: bool = False
    thumbnail_bytes: bytes | None = None


@dataclass
class LyricLine:
    """A single timed lyric line."""

    time_ms: int
    text: str


@dataclass
class LyricsResult:
    """Result of a lyrics lookup from LRCLIB or cache."""

    plain_lyrics: str | None = None
    timed_lines: list[LyricLine] | None = None
    source: str = ""
    is_instrumental: bool = False
    error: str | None = None


@dataclass
class AppSettings:
    """User preferences."""

    window_position: tuple[int, int] | None = None
    window_size: str = DEFAULT_WINDOW_SIZE
    opacity: float = 1.0
    font_size: int = 14
    always_on_top: bool = True
