"""LRCLIB lyrics client, LRC parsing, and in-memory cache."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

from core.cache import media_cache
from core.http_limits import read_json_object
from core.limits import MAX_JSON_BYTES, MAX_LYRIC_LINES, MAX_LYRIC_TEXT_BYTES
from core.models import LyricLine, LyricsResult, NowPlaying

log = logging.getLogger(__name__)

LRCLIB_BASE = "https://lrclib.net/api"
USER_AGENT = "SpotifyLyricsMiniplayer/0.1 (https://github.com/local/LyricsMiniplayer)"
REQUEST_TIMEOUT_S = 8

# [mm:ss], [mm:ss.xx], or [mm:ss.xxx]
_LRC_TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\]")
_LRC_OFFSET = re.compile(r"\[offset\s*:\s*(-?\d+)\]", re.IGNORECASE)
_LRC_METADATA = re.compile(r"^\[\s*[a-zA-Z][a-zA-Z0-9_-]*\s*:")


def _cache_key(track: NowPlaying) -> tuple[str, str, str, str, int]:
    duration_s = max(0, track.duration_ms // 1000)
    return (
        "lyrics",
        track.title.strip().lower(),
        track.artist.strip().lower(),
        track.album.strip().lower(),
        duration_s,
    )


def _is_cacheable(result: LyricsResult) -> bool:
    """Cache definitive outcomes; allow retries after transient failures."""
    if result.plain_lyrics or result.timed_lines or result.is_instrumental:
        return True
    if result.error == "No lyrics found":
        return True
    return False


def _result_size_bytes(result: LyricsResult) -> int:
    size = 0
    if result.plain_lyrics:
        size += len(result.plain_lyrics.encode("utf-8", errors="replace"))
    if result.timed_lines:
        for line in result.timed_lines:
            size += len(line.text.encode("utf-8", errors="replace")) + 8
    if result.error:
        size += len(result.error.encode("utf-8", errors="replace"))
    return size


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def parse_lrc(synced: str) -> list[LyricLine]:
    """Parse LRC timed lyrics into LyricLine entries (sorted by time)."""
    if not isinstance(synced, str) or not synced.strip():
        return []

    offset_ms = 0
    for match in _LRC_OFFSET.finditer(synced):
        try:
            offset_ms = int(match.group(1))
        except ValueError:
            offset_ms = 0

    lines: list[LyricLine] = []
    for raw in synced.splitlines():
        if len(lines) >= MAX_LYRIC_LINES:
            log.warning("LRC exceeded %d lines; truncating parse", MAX_LYRIC_LINES)
            break
        line = raw.strip()
        if not line:
            continue
        if _LRC_METADATA.match(line) and not _LRC_TIMESTAMP.match(line):
            continue

        stamps = list(_LRC_TIMESTAMP.finditer(line))
        if not stamps:
            continue

        text = line[stamps[-1].end() :].strip()
        for stamp in stamps:
            if len(lines) >= MAX_LYRIC_LINES:
                break
            minutes = int(stamp.group(1))
            seconds = int(stamp.group(2))
            frac = stamp.group(3) or "0"
            frac_ms = int((frac + "000")[:3])
            time_ms = minutes * 60_000 + seconds * 1_000 + frac_ms + offset_ms
            lines.append(LyricLine(time_ms=max(0, time_ms), text=text))

    lines.sort(key=lambda item: item.time_ms)
    return lines


def current_line_index(lines: list[LyricLine], position_ms: int) -> int:
    """Return index of the active line for position_ms, or -1 before the first line."""
    if not lines:
        return -1
    active = -1
    for index, line in enumerate(lines):
        if line.time_ms <= position_ms:
            active = index
        else:
            break
    return active


def _strip_lrc_timestamps(synced: str) -> str:
    timed = parse_lrc(synced)
    if timed:
        return "\n".join(line.text for line in timed if line.text).strip()

    lines: list[str] = []
    for raw in synced.splitlines():
        if len(lines) >= MAX_LYRIC_LINES:
            break
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and "]" in line:
            line = line.split("]", 1)[1].strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _text_byte_len(text: str) -> int:
    return len(text.encode("utf-8", errors="replace"))


def _enforce_lyric_bounds(result: LyricsResult, source: str) -> LyricsResult:
    """Reject lyrics that exceed line or total-text caps."""
    if result.error and not result.plain_lyrics and not result.timed_lines:
        return result

    total_bytes = 0
    if result.plain_lyrics:
        total_bytes += _text_byte_len(result.plain_lyrics)
    if result.timed_lines:
        if len(result.timed_lines) > MAX_LYRIC_LINES:
            log.warning("Lyrics from %s exceeded %d lines; rejecting", source, MAX_LYRIC_LINES)
            return LyricsResult(error="Lyrics response too large", source=source)
        for line in result.timed_lines:
            total_bytes += _text_byte_len(line.text)

    if total_bytes > MAX_LYRIC_TEXT_BYTES:
        log.warning(
            "Lyrics from %s exceeded %d text bytes (%d); rejecting",
            source,
            MAX_LYRIC_TEXT_BYTES,
            total_bytes,
        )
        return LyricsResult(error="Lyrics response too large", source=source)

    if result.plain_lyrics:
        plain_lines = result.plain_lyrics.splitlines()
        if len(plain_lines) > MAX_LYRIC_LINES:
            log.warning("Plain lyrics from %s exceeded %d lines; rejecting", source, MAX_LYRIC_LINES)
            return LyricsResult(error="Lyrics response too large", source=source)

    return result


def _result_from_payload(payload: dict[str, Any], source: str) -> LyricsResult:
    """Build a LyricsResult from an LRCLIB JSON object (untrusted input)."""
    if not isinstance(payload, dict):
        return LyricsResult(error="Unexpected lyrics response", source=source)

    instrumental = bool(payload.get("instrumental"))
    plain = _safe_str(payload.get("plainLyrics"))
    synced = _safe_str(payload.get("syncedLyrics"))

    # Reject oversized raw fields before LRC parsing expands timestamps.
    raw_bytes = 0
    if plain is not None:
        raw_bytes += _text_byte_len(plain)
    if synced is not None:
        raw_bytes += _text_byte_len(synced)
    if raw_bytes > MAX_LYRIC_TEXT_BYTES:
        log.warning("LRCLIB payload text exceeded %d bytes (%s)", MAX_LYRIC_TEXT_BYTES, source)
        return LyricsResult(error="Lyrics response too large", source=source)

    if instrumental and not plain and not synced:
        return LyricsResult(
            plain_lyrics=None,
            timed_lines=None,
            source=source,
            is_instrumental=True,
            error=None,
        )

    if plain is None and synced is None:
        return LyricsResult(
            error="No lyrics text in response",
            source=source,
            is_instrumental=instrumental,
        )

    timed_lines = parse_lrc(synced) if synced else []
    if plain is None and synced is not None:
        plain = _strip_lrc_timestamps(synced)

    result = LyricsResult(
        plain_lyrics=plain,
        timed_lines=timed_lines or None,
        source=source,
        is_instrumental=instrumental,
        error=None,
    )
    return _enforce_lyric_bounds(result, source)


class LyricsService:
    """Fetches and caches lyrics from LRCLIB (https://lrclib.net)."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )

    def fetch(self, track: NowPlaying) -> LyricsResult:
        """Look up lyrics for the given track (cached in memory)."""
        title = track.title.strip()
        artist = track.artist.strip()
        if not title or not artist:
            return LyricsResult(error="Missing title or artist")

        key = _cache_key(track)
        cached = media_cache.get(key)
        if isinstance(cached, LyricsResult):
            log.debug("Lyrics cache hit for %s - %s", artist, title)
            return cached

        result = self._fetch_uncached(track)
        if _is_cacheable(result):
            media_cache.put(key, result, _result_size_bytes(result))
        return result

    def _fetch_uncached(self, track: NowPlaying) -> LyricsResult:
        title = track.title.strip()
        artist = track.artist.strip()
        album = track.album.strip()
        duration_s = track.duration_ms // 1000 if track.duration_ms > 0 else None

        params: dict[str, str | int] = {
            "track_name": title,
            "artist_name": artist,
        }
        if album:
            params["album_name"] = album
        if duration_s and 1 <= duration_s <= 3600:
            params["duration"] = duration_s

        result = self._get(params, source="lrclib:/api/get")
        if result.error is None or result.is_instrumental:
            return result

        if "duration" in params:
            params_no_dur = dict(params)
            del params_no_dur["duration"]
            result = self._get(params_no_dur, source="lrclib:/api/get(no-duration)")
            if result.error is None or result.is_instrumental:
                return result

        search = self._search(title, artist, album)
        if search is not None:
            return search

        return LyricsResult(error="No lyrics found", source="lrclib")

    def _get(self, params: dict[str, str | int], source: str) -> LyricsResult:
        try:
            response = self._session.get(
                f"{LRCLIB_BASE}/get",
                params=params,
                timeout=REQUEST_TIMEOUT_S,
                stream=True,
            )
        except requests.Timeout:
            log.warning("LRCLIB timed out (%s)", source)
            return LyricsResult(error="Lyrics request timed out", source=source)
        except requests.RequestException as exc:
            log.warning("LRCLIB network error (%s): %s", source, exc)
            return LyricsResult(error="Network error fetching lyrics", source=source)

        try:
            if response.status_code == 404:
                return LyricsResult(error="No lyrics found", source=source)
            if response.status_code == 429:
                retry = response.headers.get("Retry-After", "?")
                log.warning("LRCLIB rate limited; Retry-After=%s", retry)
                return LyricsResult(error="Lyrics rate limited — try again shortly", source=source)
            if response.status_code != 200:
                log.warning("LRCLIB HTTP %s (%s)", response.status_code, source)
                return LyricsResult(
                    error=f"Lyrics service error ({response.status_code})",
                    source=source,
                )

            payload = read_json_object(
                response,
                max_bytes=MAX_JSON_BYTES,
                label=f"LRCLIB {source}",
            )
        finally:
            response.close()

        if payload is None:
            return LyricsResult(error="Invalid lyrics response", source=source)

        return _result_from_payload(payload, source=source)

    def _search(
        self,
        title: str,
        artist: str,
        album: str,
    ) -> LyricsResult | None:
        params: dict[str, str] = {
            "track_name": title,
            "artist_name": artist,
        }
        if album:
            params["album_name"] = album

        try:
            response = self._session.get(
                f"{LRCLIB_BASE}/search",
                params=params,
                timeout=REQUEST_TIMEOUT_S,
                stream=True,
            )
        except requests.RequestException as exc:
            log.warning("LRCLIB search network error: %s", exc)
            return LyricsResult(error="Network error fetching lyrics", source="lrclib:/api/search")

        try:
            if response.status_code != 200:
                return None
            payload = read_json_object(
                response,
                max_bytes=MAX_JSON_BYTES,
                label="LRCLIB /api/search",
            )
        finally:
            response.close()

        if payload is None:
            return None

        if not isinstance(payload, list) or not payload:
            return None

        for item in payload:
            if not isinstance(item, dict):
                continue
            result = _result_from_payload(item, source="lrclib:/api/search")
            if result.error == "Lyrics response too large":
                continue
            if result.is_instrumental or result.plain_lyrics or result.timed_lines:
                return result

        return None
