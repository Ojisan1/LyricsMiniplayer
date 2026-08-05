"""Lyrics panel, state screens, highlight, and scroll animation."""

from __future__ import annotations

import logging
import tkinter as tk

import customtkinter as ctk

from core.lyrics import current_line_index
from core.models import LyricsResult
from ui.theme import (
    ACCENT,
    FG,
    FONT_FAMILY,
    HAIRLINE,
    LYRIC_NEXT,
    LYRIC_PAST,
    MUTED,
    PANEL,
    SCROLL_ANIM_FRAMES,
    SCROLL_ANIM_MS,
    _PANEL_PACK,
    _STATES,
)

log = logging.getLogger(__name__)


class LyricsPanelMixin:
    """Mixin owning lyrics textbox, empty states, and sync scrolling."""

    def _build_state_panel(self) -> None:
        """Centered glyph + headline + subline shown instead of the lyrics panel."""
        self._state_frame = ctk.CTkFrame(self._frame, fg_color=PANEL, corner_radius=8)
        self._bind_drag(self._state_frame)

        inner = ctk.CTkFrame(self._state_frame, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        self._bind_drag(inner)

        self._state_glyph = ctk.CTkLabel(
            inner,
            text="",
            text_color=MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=30),
        )
        self._state_progress = ctk.CTkProgressBar(
            inner,
            mode="indeterminate",
            width=120,
            height=2,
            corner_radius=1,
            fg_color=HAIRLINE,
            progress_color=ACCENT,
        )
        self._state_headline = ctk.CTkLabel(
            inner,
            text="",
            text_color=MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
        )
        self._state_sub = ctk.CTkLabel(
            inner,
            text="",
            text_color=LYRIC_PAST,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            wraplength=280,
            justify="center",
        )
        for widget in (self._state_glyph, self._state_headline, self._state_sub):
            self._bind_drag(widget)
    def _configure_lyric_tags(self) -> None:
        text = self._lyrics_box._textbox  # noqa: SLF001
        size = self._settings.font_size
        # Leading scales with the font so 22pt lyrics are not as cramped as 11pt.
        lead = max(4, round(size * 0.55))
        spacing = {"spacing1": lead, "spacing3": lead}
        text.configure(**spacing)
        # The active line changes weight but never size: a size change would
        # reflow every line height on each tick, which is what reads as jumpy.
        text.tag_configure("past", foreground=LYRIC_PAST, font=(FONT_FAMILY, size), **spacing)
        text.tag_configure("next", foreground=LYRIC_NEXT, font=(FONT_FAMILY, size), **spacing)
        text.tag_configure(
            "current",
            foreground=FG,
            font=(FONT_FAMILY, size, "bold"),
            **spacing,
        )
        text.tag_configure("plain", foreground=FG, font=(FONT_FAMILY, size), **spacing)
        text.tag_configure("muted_msg", foreground=MUTED, font=(FONT_FAMILY, size), **spacing)
    @property
    def has_timed_lyrics(self) -> bool:
        return bool(self._timed_lines)

    def show_state(self, kind: str, detail: str | None = None) -> None:
        """Show a typed empty / loading / error panel instead of the lyrics."""
        glyph, headline, default_sub, accent, sub_color = _STATES.get(kind, _STATES["idle"])
        self._cancel_scroll_animation()
        self._timed_lines = []
        self._current_line_index = -2
        self._lyrics_kind = None

        self._state_progress.stop()
        for widget in (self._state_glyph, self._state_progress, self._state_headline):
            widget.pack_forget()
        self._state_sub.pack_forget()

        if kind == "loading":
            self._state_glyph.configure(text="")
            self._state_progress.pack(pady=(6, 16))
            self._state_progress.start()
        else:
            self._state_glyph.configure(text=glyph, text_color=accent)
            self._state_glyph.pack(pady=(0, 8))

        self._state_headline.configure(text=headline, text_color=accent)
        self._state_headline.pack()

        sub = detail if detail else default_sub
        self._state_sub.configure(text=sub, text_color=sub_color)
        if sub:
            self._state_sub.pack(pady=(4, 0))

        if not self._state_visible:
            self._lyrics_box.pack_forget()
            self._state_frame.pack(**_PANEL_PACK)
            self._state_visible = True

    def _hide_state(self) -> None:
        if not self._state_visible:
            return
        self._state_progress.stop()
        self._state_frame.pack_forget()
        self._lyrics_box.pack(**_PANEL_PACK)
        self._state_visible = False

    @staticmethod
    def _state_for_error(error: str) -> tuple[str, str | None]:
        """Map a LyricsResult error onto a state.

        Messages come from core/lyrics.py; anything unrecognised falls through to
        the generic error panel showing the original text.
        """
        lowered = error.lower()
        if "rate limited" in lowered:
            return "ratelimited", None
        if "no lyrics" in lowered:
            return "notfound", None
        if "timed out" in lowered or "network error" in lowered:
            return "error", "No connection to LRCLIB. The next track will retry."
        return "error", error

    def update_lyrics(self, result: LyricsResult) -> None:
        self._timed_lines = []
        self._current_line_index = -2
        self._lyrics_kind = None

        if result.is_instrumental:
            self.show_state("instrumental")
            return
        if result.error:
            kind, detail = self._state_for_error(result.error)
            self.show_state(kind, detail=detail)
            return
        if result.timed_lines:
            self._lyrics_kind = "synced"
            self._timed_lines = list(result.timed_lines)
            self._hide_state()
            self._render_timed_lyrics()
            return
        if result.plain_lyrics:
            self._lyrics_kind = "plain"
            self._hide_state()
            self._set_plain_text(result.plain_lyrics)
            return
        self.show_state("notfound")

    def update_sync_position(
        self,
        position_ms: int,
        *,
        allow_backward: bool = False,
    ) -> None:
        if not self._timed_lines:
            return

        index = current_line_index(self._timed_lines, position_ms)
        if index == self._current_line_index:
            return
        if index < self._current_line_index and not allow_backward:
            return

        previous = self._current_line_index
        self._current_line_index = index
        self._apply_highlight(previous, index, reposition=allow_backward)

    def _render_timed_lyrics(self) -> None:
        self._cancel_scroll_animation()
        box = self._lyrics_box
        text = box._textbox  # noqa: SLF001
        box.configure(state="normal")
        box.delete("1.0", "end")

        for index, line in enumerate(self._timed_lines):
            content = line.text if line.text else " "
            if index > 0:
                box.insert("end", "\n")
            start = box.index("end-1c")
            box.insert("end", content)
            end = box.index("end-1c")
            text.tag_add("next", start, end)

        box.configure(state="disabled")
        try:
            text.yview_moveto(0.0)
        except tk.TclError:
            box.see("1.0")

    def _apply_highlight(
        self,
        previous: int,
        current: int,
        *,
        reposition: bool = False,
    ) -> None:
        box = self._lyrics_box
        text = box._textbox  # noqa: SLF001
        box.configure(state="normal")

        if previous >= 0:
            text.tag_remove("current", f"{previous + 1}.0", f"{previous + 1}.end")

        # Retag the span we crossed as one range, so a large seek costs the same
        # as a single-line advance.
        if current > previous:
            first_past = max(0, previous)
            if current > first_past:
                text.tag_remove("next", f"{first_past + 1}.0", f"{current}.end")
                text.tag_add("past", f"{first_past + 1}.0", f"{current}.end")
        elif current < previous and previous >= 0:
            # Scrubbed back: lines ahead of the playhead return to upcoming.
            first_next = max(0, current + 1)
            text.tag_remove("past", f"{first_next + 1}.0", f"{previous + 1}.end")
            text.tag_add("next", f"{first_next + 1}.0", f"{previous + 1}.end")

        if current >= 0:
            start = f"{current + 1}.0"
            end = f"{current + 1}.end"
            text.tag_remove("next", start, end)
            text.tag_remove("past", start, end)
            text.tag_add("current", start, end)
            self._scroll_for_active_line(current, reposition=reposition)

        box.configure(state="disabled")

    def _scroll_for_active_line(
        self,
        line_index: int,
        *,
        reposition: bool = False,
    ) -> None:
        box = self._lyrics_box
        text = box._textbox  # noqa: SLF001
        target = f"{line_index + 1}.0"

        try:
            text.update_idletasks()
            widget_h = text.winfo_height()
            if widget_h <= 1:
                return

            bbox = text.bbox(target)
            if bbox is None:
                text.see(target)
                text.update_idletasks()
                bbox = text.bbox(target)
                if bbox is None:
                    return

            _, y, _, line_h = bbox
            middle = widget_h / 2.0
            line_center = y + (line_h / 2.0)
            delta = int(line_center - middle)
            slack = max(2, line_h // 3)

            top_frac, bottom_frac = text.yview()
            at_bottom = bottom_frac >= 0.999
            at_top = top_frac <= 0.001

            if delta > slack:
                if at_bottom:
                    return
                if not reposition:
                    # Normal line advance: glide.
                    self._animate_scroll(delta)
                    return
                # Seek / track change / first load: snap, and keep the existing
                # second pass, which depends on the scroll having already landed.
                self._cancel_scroll_animation()
                text.yview_scroll(delta, "pixels")
                text.update_idletasks()
                bbox = text.bbox(target)
                if bbox is not None:
                    _, y2, _, h2 = bbox
                    delta2 = int((y2 + h2 / 2.0) - middle)
                    _top2, bottom2 = text.yview()
                    if delta2 > slack and bottom2 < 0.999:
                        text.yview_scroll(delta2, "pixels")
                return

            if delta < -slack and reposition and not at_top:
                self._cancel_scroll_animation()
                text.yview_scroll(delta, "pixels")
                return
        except tk.TclError:
            try:
                box.see(target)
            except tk.TclError:
                pass

    def _animate_scroll(self, delta: int) -> None:
        """Ease the approved delta over SCROLL_ANIM_MS instead of jumping it.

        The decision to scroll, and by how much, is unchanged; only the delivery
        is spread out. A newer line change cancels this and re-measures, so no
        travel is lost.
        """
        self._cancel_scroll_animation()
        if delta <= 0:
            return
        text = self._lyrics_box._textbox  # noqa: SLF001
        if not self._animate_scrolling or delta <= SCROLL_ANIM_FRAMES:
            text.yview_scroll(delta, "pixels")
            return

        step_ms = max(1, SCROLL_ANIM_MS // SCROLL_ANIM_FRAMES)
        # Quadratic ease-out: cumulative travel after each frame.
        marks = [
            round(delta * (1 - (1 - (frame + 1) / SCROLL_ANIM_FRAMES) ** 2))
            for frame in range(SCROLL_ANIM_FRAMES)
        ]

        def advance(frame: int, applied: int) -> None:
            self._scroll_anim_id = None
            try:
                step = marks[frame] - applied
                if step:
                    text.yview_scroll(step, "pixels")
            except tk.TclError:
                return
            if frame + 1 < len(marks):
                self._scroll_anim_id = self.root.after(
                    step_ms, advance, frame + 1, marks[frame]
                )

        advance(0, 0)

    def _cancel_scroll_animation(self) -> None:
        if self._scroll_anim_id is None:
            return
        try:
            self.root.after_cancel(self._scroll_anim_id)
        except (ValueError, tk.TclError):
            pass
        self._scroll_anim_id = None

    def _set_plain_text(self, content: str, *, muted: bool = False) -> None:
        self._cancel_scroll_animation()
        box = self._lyrics_box
        text = box._textbox  # noqa: SLF001
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", content)
        text.tag_add("muted_msg" if muted else "plain", "1.0", "end")
        box.configure(state="disabled")
        box.see("1.0")
