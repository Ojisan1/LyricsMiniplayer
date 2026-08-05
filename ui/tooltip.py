"""Hover tooltip helper for the miniplayer chrome."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable

from ui.theme import FONT_FAMILY, HAIRLINE, MUTED
from ui.win32_geom import _display_work_area, _window_scaling

log = logging.getLogger(__name__)


class _Tooltip:
    """Hover tooltip. CustomTkinter has none, and this must never take focus.

    Built from plain Tk widgets rather than CTkToplevel: these are created and
    destroyed constantly, and CTkToplevel schedules titlebar work that has no
    meaning for a borderless hint. Sizes are scaled by hand for the same reason.
    """

    DELAY_MS = 400

    def __init__(
        self,
        widget: tk.Misc,
        text: str,
        root: tk.Misc,
        enabled: Callable[[], bool] | None = None,
    ) -> None:
        self._widget = widget
        self._text = text
        self._root = root
        self._enabled = enabled
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._dismiss)
        widget.bind("<Button-1>", self._dismiss)

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self._dismiss()
        if self._enabled is not None and not self._enabled():
            return
        self._after_id = self._widget.after(self.DELAY_MS, self._show)

    def _dismiss(self, _event: tk.Event | None = None) -> None:
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except (ValueError, tk.TclError):
                pass
            self._after_id = None
        self.hide()

    def _show(self) -> None:
        self._after_id = None
        if self._window is not None:
            return
        try:
            scaling = _window_scaling(self._root)
            window = tk.Toplevel(self._root)
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.configure(bg=HAIRLINE)
            tk.Label(
                window,
                text=self._text,
                bg="#202020",
                fg=MUTED,
                font=(FONT_FAMILY, round(10 * scaling)),
                padx=round(7 * scaling),
                pady=round(4 * scaling),
            ).pack(padx=1, pady=1)
            window.update_idletasks()

            x = self._widget.winfo_rootx()
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + round(6 * scaling)
            left, _top, area_w, _area_h = _display_work_area()
            x = min(x, left + area_w - window.winfo_width() - round(8 * scaling))
            window.geometry(f"+{max(left, int(x))}+{int(y)}")
            self._window = window
        except tk.TclError:
            log.exception("Failed to show tooltip")

    def hide(self) -> None:
        if self._window is None:
            return
        try:
            self._window.destroy()
        except tk.TclError:
            pass
        self._window = None
