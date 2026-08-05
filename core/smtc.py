"""Windows System Media Transport Controls (SMTC) now-playing reader.

Uses PyWinRT (winrt-Windows.Media.Control) to read Spotify session metadata.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus,
)
from winrt.windows.storage.streams import Buffer, InputStreamOptions

from core.models import NowPlaying

log = logging.getLogger(__name__)

# Spotify desktop and Microsoft Store package IDs both contain "spotify".
_SPOTIFY_HINT = "spotify"
_THUMB_MAX_BYTES = 5_000_000


def _timespan_to_ms(value: Any) -> int:
    """Convert a WinRT TimeSpan / timedelta-like value to milliseconds."""
    if value is None:
        return 0
    if hasattr(value, "total_seconds"):
        return max(0, int(value.total_seconds() * 1000))
    # Some projections expose duration in 100-ns ticks.
    if hasattr(value, "duration"):
        return max(0, int(value.duration / 10_000))
    return 0


def _is_spotify_session(session: Any) -> bool:
    app_id = (session.source_app_user_model_id or "").lower()
    return _SPOTIFY_HINT in app_id


async def _read_thumbnail_bytes(thumbnail_ref: Any) -> bytes | None:
    """Read an SMTC thumbnail stream into raw image bytes."""
    if thumbnail_ref is None:
        return None
    stream = None
    try:
        stream = await thumbnail_ref.open_read_async()
        size = int(getattr(stream, "size", 0) or 0)
        capacity = min(_THUMB_MAX_BYTES, max(size, 65_536))
        buffer = Buffer(capacity)
        await stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)
        if not buffer.length:
            return None
        return bytes(buffer)
    except Exception:
        log.exception("Failed to read SMTC thumbnail")
        return None
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass


class SMTCReader:
    """Reads now-playing information from Windows SMTC (Spotify preferred)."""

    def __init__(self) -> None:
        self._manager: GlobalSystemMediaTransportControlsSessionManager | None = None

    async def _ensure_manager(self) -> GlobalSystemMediaTransportControlsSessionManager:
        if self._manager is None:
            self._manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        return self._manager

    def _pick_spotify_session(self, manager: GlobalSystemMediaTransportControlsSessionManager):
        """Prefer an active Spotify session; otherwise None."""
        sessions = list(manager.get_sessions())
        spotify = [s for s in sessions if _is_spotify_session(s)]
        if not spotify:
            return None

        playing = GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
        for session in spotify:
            info = session.get_playback_info()
            if info and info.playback_status == playing:
                return session
        return spotify[0]

    async def get_now_playing_async(
        self,
        *,
        include_thumbnail: bool = False,
    ) -> NowPlaying | None:
        """Return the current Spotify track, or None if nothing is active."""
        try:
            manager = await self._ensure_manager()
            session = self._pick_spotify_session(manager)
            if session is None:
                return None

            props = await session.try_get_media_properties_async()
            if props is None:
                return None

            playback = session.get_playback_info()
            timeline = session.get_timeline_properties()

            is_playing = False
            if playback is not None:
                is_playing = (
                    playback.playback_status
                    == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
                )

            position_ms = 0
            duration_ms = 0
            if timeline is not None:
                position_ms = _timespan_to_ms(timeline.position)
                start_ms = _timespan_to_ms(timeline.start_time)
                end_ms = _timespan_to_ms(timeline.end_time)
                duration_ms = max(0, end_ms - start_ms)

            thumbnail_bytes = None
            if include_thumbnail:
                thumbnail_bytes = await _read_thumbnail_bytes(props.thumbnail)

            return NowPlaying(
                title=(props.title or "").strip(),
                artist=(props.artist or "").strip(),
                album=(props.album_title or "").strip(),
                duration_ms=duration_ms,
                position_ms=position_ms,
                is_playing=is_playing,
                thumbnail_bytes=thumbnail_bytes,
            )
        except Exception:
            log.exception("Failed to read SMTC now-playing state")
            self._manager = None
            return None

    def get_now_playing(self, *, include_thumbnail: bool = False) -> NowPlaying | None:
        """Synchronous wrapper around get_now_playing_async()."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            raise RuntimeError(
                "get_now_playing() cannot be called from a running event loop; "
                "use get_now_playing_async() instead"
            )
        return asyncio.run(self.get_now_playing_async(include_thumbnail=include_thumbnail))
