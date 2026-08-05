"""Title marquee animation for overflowing track titles."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable

from ui.theme import (
    MARQUEE_DWELL_MS,
    MARQUEE_FRAME_MS,
    MARQUEE_HOVER_DWELL_MS,
    MARQUEE_MIN_OVERFLOW,
    MARQUEE_REST_MS,
    MARQUEE_RETURN_SPEED_PX_S,
    MARQUEE_SPEED_PX_S,
    MARQUEE_TAIL_PAD,
)
from ui.win32_geom import _widget_scaling

log = logging.getLogger(__name__)


class TitleMarqueeMixin:
    """Mixin owning title-clip height sync and one-pass marquee animation."""

    def _sync_title_clip_height(self) -> None:
        """Give the clip frame an explicit height.

        A place()d child contributes nothing to its parent's requested size, so
        without this the frame would keep CTkFrame's 200px default and push the
        lyrics panel down.
        """
        try:
            scaling = _widget_scaling(self._title_label)
            height = self._title_label.winfo_reqheight() / scaling
        except tk.TclError:
            log.debug("Could not measure title height; leaving clip frame default")
            return
        if height >= 1:
            self._title_clip.configure(height=round(height))

    def _marquee_travel(self) -> float:
        """Logical px the title must move for its tail to clear the frame.

        0 when the title fits, which is the common case and means no animation.
        """
        try:
            self.root.update_idletasks()
            scaling = _widget_scaling(self._title_label)
            text_width = self._title_label.winfo_reqwidth() / scaling
            clip_width = self._title_clip.winfo_width() / scaling
        except tk.TclError:
            return 0.0
        # Before the first layout pass the frame has no real width yet.
        if clip_width <= 1:
            return 0.0
        overflow = text_width - clip_width
        if overflow < MARQUEE_MIN_OVERFLOW:
            return 0.0
        return overflow + MARQUEE_TAIL_PAD

    def _start_marquee(self, *, dwell_ms: int = MARQUEE_DWELL_MS) -> None:
        """Run one pass over an overflowing title, then return to the start.

        Cancelling first means a new track never inherits the previous offset.
        """
        self._cancel_marquee()
        if not self._animate_scrolling:
            return
        travel = self._marquee_travel()
        if travel <= 0:
            return
        self._marquee_after_id = self.root.after(
            dwell_ms,
            self._marquee_glide,
            travel,
            MARQUEE_SPEED_PX_S,
            self._marquee_rest,
        )

    def _marquee_glide(
        self,
        target: float,
        speed_px_s: float,
        on_arrive: Callable[[], None],
    ) -> None:
        self._marquee_after_id = None
        step = speed_px_s * (MARQUEE_FRAME_MS / 1000.0)
        remaining = target - self._marquee_offset
        if abs(remaining) <= step:
            self._set_title_offset(target)
            on_arrive()
            return
        direction = 1.0 if remaining > 0 else -1.0
        self._set_title_offset(self._marquee_offset + direction * step)
        self._marquee_after_id = self.root.after(
            MARQUEE_FRAME_MS,
            self._marquee_glide,
            target,
            speed_px_s,
            on_arrive,
        )

    def _marquee_rest(self) -> None:
        self._marquee_after_id = self.root.after(MARQUEE_REST_MS, self._marquee_return)

    def _marquee_return(self) -> None:
        self._marquee_after_id = None
        self._marquee_glide(0.0, MARQUEE_RETURN_SPEED_PX_S, self._marquee_finish)

    def _marquee_finish(self) -> None:
        """One pass per track change: stop here rather than looping back out."""
        self._marquee_after_id = None

    def _set_title_offset(self, offset: float) -> None:
        self._marquee_offset = offset
        try:
            # place() is CustomTkinter's override, which scales x from logical.
            # place_configure() would bypass that and take physical px.
            self._title_label.place(x=-round(offset), y=0)
        except tk.TclError:
            log.debug("Could not move title label; stopping marquee")
            self._cancel_marquee(reset=False)

    def _cancel_marquee(self, *, reset: bool = True) -> None:
        if self._marquee_after_id is not None:
            try:
                self.root.after_cancel(self._marquee_after_id)
            except (ValueError, tk.TclError):
                pass
            self._marquee_after_id = None
        if reset and self._marquee_offset:
            self._set_title_offset(0.0)

    def _on_title_enter(self, _event: tk.Event | None = None) -> None:
        # Ignore hover while a pass is already running, so sweeping the pointer
        # across the title does not restart it mid-glide.
        if self._marquee_after_id is not None:
            return
        self._start_marquee(dwell_ms=MARQUEE_HOVER_DWELL_MS)
