"""Spotify Lyrics Miniplayer - application entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import threading
import time

from core.artwork import fetch_album_art
from core.lyrics import LyricsService, current_line_index
from core.models import AppSettings, LyricsResult, NowPlaying
from core.settings import load_settings, save_settings
from core.smtc import SMTCReader
from ui.miniplayer import MiniplayerWindow
from ui.tray import TrayIcon

log = logging.getLogger("lyricsminiplayer")

POLL_INTERVAL_S = 0.5
POLL_INTERVAL_MS = int(POLL_INTERVAL_S * 1000)
SYNC_TICK_MS = 100
# Discontinuities larger than this vs the last SMTC sample count as seeks.
SEEK_THRESHOLD_MS = 1500
# Require this many consecutive paused SMTC readings before trusting pause.
PAUSE_CONFIRM_READINGS = 2
# Lead the lyric playhead slightly to offset SMTC timeline lag.
PLAYHEAD_LEAD_MS = 550


def _format_ms(ms: int) -> str:
    total_s = max(0, ms) // 1000
    return f"{total_s // 60}:{total_s % 60:02d}"


def _format_line(track: NowPlaying | None) -> str:
    if track is None:
        return "No Spotify session (play something in Spotify, or leave this running)"
    state = "PLAYING" if track.is_playing else "PAUSED"
    album = f" | {track.album}" if track.album else ""
    return (
        f"[{state}] {track.artist} - {track.title}{album} "
        f"({_format_ms(track.position_ms)} / {_format_ms(track.duration_ms)})"
    )


def _track_identity(track: NowPlaying | None) -> tuple:
    if track is None:
        return (None, None, None)
    return (track.title, track.artist, track.album)


async def run_live_monitor(interval: float = POLL_INTERVAL_S) -> int:
    """Poll SMTC and print live now-playing updates to the console."""
    reader = SMTCReader()
    last_identity: object = object()
    last_state: bool | None = None
    last_print = 0.0

    log.info("Console SMTC monitor started (Ctrl+C to quit)")
    print("Listening for Spotify via Windows SMTC...")
    print("Play, pause, or change tracks in Spotify to verify updates.\n")

    while True:
        track = await reader.get_now_playing_async()
        identity = _track_identity(track)
        state = track.is_playing if track else None
        now = time.monotonic()

        changed = identity != last_identity or state != last_state
        heartbeat = track is not None and (now - last_print) >= 2.0

        if changed or heartbeat:
            print(_format_line(track), flush=True)
            last_identity = identity
            last_state = state
            last_print = now

        await asyncio.sleep(interval)


class MiniplayerApp:
    """Owns the floating window, tray icon, SMTC polling, and lyric sync."""

    def __init__(self) -> None:
        self._reader = SMTCReader()
        self._lyrics = LyricsService()
        self._settings = load_settings()
        self._stopping = False
        self._current_identity: tuple | None = None
        self._fetch_generation = 0
        self._pos_anchor_ms = 0
        self._pos_anchor_mono = time.monotonic()
        self._pos_playing = False
        self._last_smtc_pos_ms = 0
        self._last_smtc_mono = time.monotonic()
        self._has_smtc_sample = False
        self._pause_streak = 0
        self._allow_highlight_backward = False
        self._window = MiniplayerWindow(
            settings=self._settings,
            on_hide_request=self.hide_window,
            on_quit_request=self.quit,
            on_settings_changed=self._on_settings_changed,
        )
        self._tray = TrayIcon(
            on_show=lambda: self._window.schedule(self.show_window),
            on_hide=lambda: self._window.schedule(self.hide_window),
            on_quit=lambda: self._window.schedule(self.quit),
            is_visible=lambda: self._window.is_visible,
        )

    def run(self) -> int:
        log.info("Starting floating miniplayer + system tray")
        self._tray.start()
        self._window.schedule(self._poll_smtc)
        self._window.schedule(self._sync_tick)
        self._window.mainloop()
        return 0

    def show_window(self) -> None:
        self._window.show()

    def hide_window(self) -> None:
        self._persist_settings()
        self._window.hide()
        log.info("Window hidden to tray")

    def quit(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        log.info("Quit requested")
        self._persist_settings()
        self._tray.stop()
        self._window.destroy()

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = settings
        save_settings(settings)

    def _persist_settings(self) -> None:
        self._settings = self._window.current_settings()
        save_settings(self._settings)

    def _poll_smtc(self) -> None:
        if self._stopping:
            return
        try:
            track = self._reader.get_now_playing()
            seeked = self._update_position_anchor(track)
            self._handle_track_change(track)
            if track is None:
                self._window.update_track(None)
            else:
                # Status uses confirmed playhead state (pause flicker filtered).
                self._window.update_track(
                    NowPlaying(
                        title=track.title,
                        artist=track.artist,
                        album=track.album,
                        duration_ms=track.duration_ms,
                        position_ms=self._effective_position_ms(),
                        is_playing=self._pos_playing,
                        thumbnail_bytes=track.thumbnail_bytes,
                    )
                )
            if track is not None and self._window.has_timed_lyrics:
                # Backward highlight only on scrub-back / track change / load.
                allow_backward = seeked or self._allow_highlight_backward
                self._window.update_sync_position(
                    self._sync_position_ms(),
                    allow_backward=allow_backward,
                )
                if allow_backward:
                    self._allow_highlight_backward = False
        except Exception:
            log.exception("SMTC poll failed")
        finally:
            if not self._stopping:
                self._window.schedule(self._poll_smtc, POLL_INTERVAL_MS)

    def _sync_tick(self) -> None:
        """Advance highlight between SMTC polls using interpolated position."""
        if self._stopping:
            return
        try:
            if self._window.has_timed_lyrics:
                self._window.update_sync_position(
                    self._sync_position_ms(),
                    allow_backward=False,
                )
        except Exception:
            log.exception("Lyric sync tick failed")
        finally:
            if not self._stopping:
                self._window.schedule(self._sync_tick, SYNC_TICK_MS)

    def _reset_playhead(self, position_ms: int = 0, *, playing: bool = False) -> None:
        now = time.monotonic()
        self._pos_anchor_ms = max(0, position_ms)
        self._pos_anchor_mono = now
        self._pos_playing = playing
        self._last_smtc_pos_ms = max(0, position_ms)
        self._last_smtc_mono = now
        self._has_smtc_sample = False
        self._pause_streak = 0

    def _update_position_anchor(self, track: NowPlaying | None) -> bool:
        """Update one-way playhead.

        Returns True only when the lyric highlight may move backward
        (confirmed scrub-back / session reset). Forward seeks and SMTC
        catch-ups never enable allow_backward.
        """
        now = time.monotonic()
        if track is None:
            self._reset_playhead(0, playing=False)
            return True

        smtc_pos = max(0, track.position_ms)
        reported_playing = track.is_playing

        # --- Pause flicker guard -------------------------------------------------
        if not reported_playing:
            self._pause_streak += 1
            if self._pause_streak < PAUSE_CONFIRM_READINGS and self._pos_playing:
                # Ignore a single flaky paused reading; keep interpolating.
                return False

            seeked_back = False
            if self._has_smtc_sample and (self._last_smtc_pos_ms - smtc_pos) > SEEK_THRESHOLD_MS:
                seeked_back = True
            elif (self._effective_position_ms() - smtc_pos) > SEEK_THRESHOLD_MS:
                seeked_back = True

            self._pos_anchor_ms = smtc_pos
            self._pos_anchor_mono = now
            self._pos_playing = False
            self._last_smtc_pos_ms = smtc_pos
            self._last_smtc_mono = now
            self._has_smtc_sample = True
            return seeked_back

        self._pause_streak = 0

        # --- First sample after start / track load ------------------------------
        if not self._has_smtc_sample:
            self._pos_anchor_ms = smtc_pos
            self._pos_anchor_mono = now
            self._pos_playing = True
            self._last_smtc_pos_ms = smtc_pos
            self._last_smtc_mono = now
            self._has_smtc_sample = True
            return False

        wall_elapsed_ms = max(0, int((now - self._last_smtc_mono) * 1000))
        smtc_delta = smtc_pos - self._last_smtc_pos_ms

        # Seek detection vs last *changed* SMTC sample (mono only updates on change).
        seeked_back = smtc_delta < -SEEK_THRESHOLD_MS
        seeked_forward = smtc_delta > wall_elapsed_ms + SEEK_THRESHOLD_MS

        if seeked_back:
            self._pos_anchor_ms = smtc_pos
            self._pos_anchor_mono = now
            self._pos_playing = True
            self._last_smtc_pos_ms = smtc_pos
            self._last_smtc_mono = now
            return True

        if seeked_forward:
            # Real scrub-forward OR a large SMTC catch-up after a stall.
            self._last_smtc_pos_ms = smtc_pos
            self._last_smtc_mono = now
            effective = self._effective_position_ms()
            if smtc_pos > effective + SEEK_THRESHOLD_MS:
                # Clearly ahead of our clock — adopt; sticky highlight advances.
                self._pos_anchor_ms = smtc_pos
                self._pos_anchor_mono = now
            elif smtc_pos >= effective:
                self._pos_anchor_ms = smtc_pos
                self._pos_anchor_mono = now
            else:
                # Catch-up still behind interpolated clock — never snap backward.
                self._pos_anchor_ms = effective
                self._pos_anchor_mono = now
            self._pos_playing = True
            return False

        # Normal / stalled samples.
        if smtc_pos > self._last_smtc_pos_ms:
            # Position advanced — refresh SMTC sample timestamp.
            self._last_smtc_pos_ms = smtc_pos
            self._last_smtc_mono = now
            effective = self._effective_position_ms()
            if smtc_pos >= effective:
                self._pos_anchor_ms = smtc_pos
                self._pos_anchor_mono = now
            else:
                self._pos_anchor_ms = effective
                self._pos_anchor_mono = now
            self._pos_playing = True
            return False

        if smtc_pos == self._last_smtc_pos_ms:
            # Stalled SMTC reading: do NOT refresh last_smtc_mono (avoids false
            # seek-forward on the next catch-up). Keep one-way interpolation.
            effective = self._effective_position_ms()
            self._pos_anchor_ms = effective
            self._pos_anchor_mono = now
            self._pos_playing = True
            return False

        # Small backward SMTC jitter (< seek threshold): ignore.
        self._pos_playing = True
        return False

    def _effective_position_ms(self) -> int:
        if not self._pos_playing:
            return self._pos_anchor_ms
        elapsed_ms = int((time.monotonic() - self._pos_anchor_mono) * 1000)
        return max(0, self._pos_anchor_ms + elapsed_ms)

    def _sync_position_ms(self) -> int:
        """Playhead used for lyric sync (adds a small lead while playing)."""
        position = self._effective_position_ms()
        if self._pos_playing:
            return position + PLAYHEAD_LEAD_MS
        return position

    def _handle_track_change(self, track: NowPlaying | None) -> None:
        identity = _track_identity(track)
        if identity == self._current_identity:
            return

        self._current_identity = identity
        self._fetch_generation += 1
        generation = self._fetch_generation
        self._allow_highlight_backward = True
        if track is None:
            self._tray.set_track()
        else:
            self._tray.set_track(track.title, track.artist)
        if track is not None:
            self._reset_playhead(track.position_ms, playing=track.is_playing)
            self._has_smtc_sample = True
            self._last_smtc_pos_ms = max(0, track.position_ms)
            self._last_smtc_mono = time.monotonic()
        else:
            self._reset_playhead(0, playing=False)

        if track is None:
            self._window.show_state("idle")
            return

        self._window.show_state("loading", detail=track.title)
        worker = threading.Thread(
            target=self._fetch_lyrics_worker,
            args=(track, generation),
            daemon=True,
            name="lyrics-fetch",
        )
        worker.start()

    def _fetch_lyrics_worker(self, track: NowPlaying, generation: int) -> None:
        # Art first so it can paint as soon as iTunes returns, without waiting
        # on LRCLIB. Never clear existing art on failure — previous cover stays.
        try:
            thumb_bytes = fetch_album_art(
                track.title, track.artist, track.album
            )
        except Exception:
            log.exception("Album art fetch failed")
            thumb_bytes = None
        if thumb_bytes and not self._stopping:
            self._window.schedule(
                lambda data=thumb_bytes: self._apply_album_art(data, generation)
            )

        result = self._lyrics.fetch(track)
        if self._stopping:
            return
        self._window.schedule(
            lambda: self._apply_lyrics_result(result, generation)
        )

    def _apply_album_art(self, thumb_bytes: bytes, generation: int) -> None:
        if self._stopping or generation != self._fetch_generation:
            return
        if thumb_bytes:
            self._window.set_album_art(thumb_bytes)

    def _apply_lyrics_result(
        self,
        result: LyricsResult,
        generation: int,
    ) -> None:
        if self._stopping or generation != self._fetch_generation:
            return
        self._window.update_lyrics(result)
        if result.timed_lines:
            self._window.update_sync_position(
                self._sync_position_ms(),
                allow_backward=True,
            )
            log.info(
                "Timed lyrics loaded (%d lines) from %s",
                len(result.timed_lines),
                result.source or "lrclib",
            )
        elif result.error:
            log.info("Lyrics unavailable: %s", result.error)
        elif result.is_instrumental:
            log.info("Track marked instrumental")
        else:
            log.info("Plain lyrics loaded from %s", result.source or "lrclib")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spotify Lyrics Miniplayer")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print a single SMTC snapshot and exit",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Phase 1-style console monitor instead of the floating window",
    )
    parser.add_argument(
        "--lyrics-test",
        action="store_true",
        help="Fetch lyrics for the current Spotify track and print them",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.once:
        track = SMTCReader().get_now_playing()
        print(_format_line(track))
        return 0

    if args.lyrics_test:
        track = SMTCReader().get_now_playing()
        print(_format_line(track))
        if track is None:
            return 1
        service = LyricsService()
        first = service.fetch(track)
        second = service.fetch(track)
        timed_count = len(first.timed_lines or [])
        print(f"source={first.source!r} instrumental={first.is_instrumental} error={first.error!r}")
        print(f"timed_lines={timed_count} cache_same_object={first is second}")
        if first.timed_lines:
            idx = current_line_index(first.timed_lines, track.position_ms)
            print(f"position_ms={track.position_ms} current_line_index={idx}")
            if 0 <= idx < len(first.timed_lines):
                line = first.timed_lines[idx]
                print(f"current: [{_format_ms(line.time_ms)}] {line.text}")
        elif first.plain_lyrics:
            preview = "\n".join(first.plain_lyrics.splitlines()[:8])
            print("--- lyrics preview ---")
            print(preview)
        return 0 if first.error is None or first.is_instrumental else 2

    if args.console:
        try:
            return asyncio.run(run_live_monitor())
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

    return MiniplayerApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
