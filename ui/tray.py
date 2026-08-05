"""System tray icon and menu (now playing / show toggle / quit)."""

from __future__ import annotations

import logging
from collections.abc import Callable

import pystray
from PIL import Image, ImageDraw

log = logging.getLogger(__name__)

_ICON_DARK = (18, 18, 18, 255)
_ICON_ACCENT = (29, 185, 84, 255)
# Windows truncates the notification-area tooltip well before this.
_TOOLTIP_LIMIT = 120


def _make_icon_image(size: int = 64) -> Image.Image:
    """Dark rounded tile holding a Spotify-green record.

    Drawn large and downscaled by Windows, so the glyph fills most of the tile to
    stay legible at the 16px the notification area actually renders.
    """
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = max(1, size // 16)
    draw.rounded_rectangle(
        (margin, margin, size - margin - 1, size - margin - 1),
        radius=size // 5,
        fill=_ICON_DARK,
    )

    pad = size // 5
    draw.ellipse((pad, pad, size - pad - 1, size - pad - 1), fill=_ICON_ACCENT)

    hole = size // 2 - max(1, size // 14)
    draw.ellipse((hole, hole, size - hole - 1, size - hole - 1), fill=_ICON_DARK)
    return image


class TrayIcon:
    """System tray resident icon for the miniplayer."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_hide: Callable[[], None],
        on_quit: Callable[[], None],
        is_visible: Callable[[], bool] | None = None,
    ) -> None:
        self._on_show = on_show
        self._on_hide = on_hide
        self._on_quit = on_quit
        self._is_visible = is_visible
        self._icon: pystray.Icon | None = None
        self._track_text = ""

    def start(self) -> None:
        """Create and run the system tray icon on a background thread."""
        menu = pystray.Menu(
            pystray.MenuItem(self._now_playing_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            # One checked toggle rather than Show / Hide, where one of the two was
            # always a no-op.
            pystray.MenuItem(
                "Show lyrics",
                self._handle_toggle,
                checked=self._is_checked,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._handle_quit),
        )
        self._icon = pystray.Icon(
            name="lyrics_miniplayer",
            icon=_make_icon_image(),
            title=self._tooltip(),
            menu=menu,
        )
        self._icon.run_detached()
        log.info("System tray icon started")

    def set_track(self, title: str = "", artist: str = "") -> None:
        """Reflect the current track in the menu and the hover tooltip."""
        text = " — ".join(part for part in (artist.strip(), title.strip()) if part)
        if text == self._track_text:
            return
        self._track_text = text
        if self._icon is None:
            return
        try:
            self._icon.title = self._tooltip()
            self._icon.update_menu()
        except Exception:
            log.exception("Failed to update tray icon after track change")

    def stop(self) -> None:
        """Remove the tray icon and stop its loop."""
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            log.exception("Failed to stop tray icon")
        self._icon = None

    def _tooltip(self) -> str:
        if not self._track_text:
            return "Lyrics Miniplayer"
        return self._track_text[:_TOOLTIP_LIMIT]

    def _now_playing_text(self, _item: pystray.MenuItem) -> str:
        return self._track_text or "Nothing playing"

    def _is_checked(self, _item: pystray.MenuItem) -> bool:
        if self._is_visible is None:
            return False
        return bool(self._is_visible())

    def _handle_toggle(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self._is_visible is not None and self._is_visible():
            self._on_hide()
        else:
            self._on_show()

    def _handle_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._on_quit()
