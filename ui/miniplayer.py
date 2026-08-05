"""Always-on-top floating miniplayer window (CustomTkinter)."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from core.models import (
    DEFAULT_WINDOW_SIZE,
    WINDOW_SIZES,
    AppSettings,
    LyricLine,
    NowPlaying,
)
from ui.album_art import AlbumArtMixin
from ui.lyrics_panel import LyricsPanelMixin
from ui.settings_panel import SettingsPanelMixin
from ui.theme import (
    ART_PLACEHOLDER_BG,
    ART_RADIUS,
    ART_SIZE,
    DRAG_THRESHOLD_PX,
    EDGE_MARGIN,
    FG,
    FONT_FAMILY,
    HAIRLINE,
    HOVER,
    LYRIC_NEXT,
    MUTED,
    OPACITY_MIN,
    PANEL,
    SURFACE,
    WINDOW_MIN_HEIGHT,
    WINDOW_PRESET_HEIGHTS,
    WINDOW_RADIUS,
    WINDOW_WIDTH,
    _PANEL_PACK,
    _SEGMENTED_STYLE,
    _SIZE_LABELS,
    _SLIDER_STYLE,
    _SWITCH_STYLE,
)
from ui.title_marquee import TitleMarqueeMixin
from ui.tooltip import _Tooltip
from ui.win32_geom import (
    _animations_enabled,
    _display_work_area,
    _point_on_a_monitor,
    _round_window_corners,
    _window_scaling,
)

log = logging.getLogger(__name__)


def _format_ms(ms: int) -> str:
    total_s = max(0, ms) // 1000
    return f"{total_s // 60}:{total_s % 60:02d}"


class MiniplayerWindow(
    TitleMarqueeMixin,
    AlbumArtMixin,
    SettingsPanelMixin,
    LyricsPanelMixin,
):
    """Floating now-playing + synced lyrics window."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        on_hide_request: Callable[[], None] | None = None,
        on_quit_request: Callable[[], None] | None = None,
        on_settings_changed: Callable[[AppSettings], None] | None = None,
    ) -> None:
        self._on_hide_request = on_hide_request
        self._on_quit_request = on_quit_request
        self._on_settings_changed = on_settings_changed
        self._settings = settings or AppSettings()
        self._drag_offset: tuple[int, int] | None = None
        self._drag_origin: tuple[int, int] | None = None
        self._drag_moved = False
        self._position_is_user_set = False
        self._visible = True
        self._timed_lines: list[LyricLine] = []
        self._current_line_index = -2
        self._art_image: ctk.CTkImage | None = None
        self._art_hover_image: ctk.CTkImage | None = None
        self._art_bytes: bytes | None = None
        self._art_zoom_window: ctk.CTkToplevel | None = None
        self._art_zoom_image: ctk.CTkImage | None = None
        self._art_zoom_label: ctk.CTkLabel | None = None
        self._settings_open = False
        self._last_meta: tuple[str, str, str] | None = None
        self._lyrics_kind: str | None = None
        self._state_visible = False
        self._scroll_anim_id: str | None = None
        self._animate_scrolling = _animations_enabled()
        self._marquee_after_id: str | None = None
        self._marquee_offset = 0.0
        self._recenter_after_id: str | None = None

        ctk.set_appearance_mode("dark")

        self.root = ctk.CTk()
        self.root.title("Lyrics Miniplayer")
        self.root.geometry(self._initial_geometry())
        self.root.minsize(WINDOW_WIDTH, WINDOW_MIN_HEIGHT)
        # Matches the panel so the padding around it stops reading as a border.
        # The window used to sit on BG, which showed through as a black square
        # frame outside the panel's rounded corners.
        self.root.configure(fg_color=SURFACE)
        self.root.overrideredirect(True)
        self.root.protocol("WM_DELETE_WINDOW", self._request_hide)

        self._build()
        self.apply_settings(self._settings, persist=False)
        self._configure_lyric_tags()
        self._bind_drag(self.root)
        self._bind_drag(self._frame)
        self._bind_drag(self._title_label)
        self._bind_drag(self._artist_label)
        self._bind_drag(self._status_label)
        # Album art uses click-to-zoom instead of drag.
        self._round_corners()

    def _round_corners(self) -> None:
        """Clip the window to WINDOW_RADIUS once its real size is known.

        A region is expressed in window-relative pixels, so this survives moving,
        hiding and opacity changes. It does not survive a resize: the region keeps
        the dimensions it was cut for, so a size preset has to recut it or the
        square corners come back.
        """
        self.root.update_idletasks()
        if not _round_window_corners(
            self.root,
            WINDOW_RADIUS,
            _window_scaling(self.root),
        ):
            log.info("Window corners left square; rounded region unavailable")

    def _preset_size(self) -> tuple[int, int]:
        """The selected preset in logical px. Only the height varies."""
        height = WINDOW_PRESET_HEIGHTS.get(
            self._settings.window_size,
            WINDOW_PRESET_HEIGHTS[DEFAULT_WINDOW_SIZE],
        )
        return WINDOW_WIDTH, height

    def _initial_geometry(self) -> str:
        width, height = self._preset_size()
        saved = self._settings.window_position
        if saved and self._position_is_reachable(int(saved[0]), int(saved[1])):
            self._position_is_user_set = True
            x, y = int(saved[0]), int(saved[1])
        else:
            if saved:
                log.info("Saved window position %s is off-screen; using default", tuple(saved))
            x, y = self._default_position()
        return f"{width}x{height}+{x}+{y}"

    def _default_position(self) -> tuple[int, int]:
        """Bottom-right of the work area, near the tray, inset by EDGE_MARGIN.

        The work area already excludes the taskbar, so the inset reads as a gap
        above it rather than an overlap.
        """
        left, top, area_w, area_h = _display_work_area()
        width, height = self._preset_size()
        scaling = _window_scaling(self.root)
        margin = round(EDGE_MARGIN * scaling)
        x = left + area_w - round(width * scaling) - margin
        y = top + area_h - round(height * scaling) - margin
        return max(left, int(x)), max(top, int(y))

    def _apply_window_size(self) -> None:
        """Resize to the selected preset and return to the default tray corner.

        A size change always re-snaps to the corner rather than keeping a dragged
        position, so it also drops that position: leaving it unset is what keeps
        the corner recomputed on later launches.
        """
        width, height = self._preset_size()
        self._position_is_user_set = False
        x, y = self._default_position()
        # CustomTkinter scales WxH but not +x+y, so the corner is computed from
        # work-area pixels against the scaled size.
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.update_idletasks()
        # The region keeps the dimensions it was cut for, so it has to be recut
        # or the square corners come back.
        self._round_corners()
        # The title row is untouched: every preset shares WINDOW_WIDTH, so the
        # marquee clip and its measured travel are unchanged and a running pass
        # is left to finish rather than being snapped back to the start.
        self._schedule_recenter()
        self._sync_position_into_settings()

    def _schedule_recenter(self) -> None:
        """Re-center the active lyric once the resize has actually landed.

        A geometry() request is granted through a Configure event, which is a
        normal event and not an idle task, so update_idletasks() does not wait
        for it. Measuring immediately reads the panel's previous height and
        scrolls the active line clean off screen; after_idle runs once the new
        height is real.
        """
        self._cancel_recenter()
        self._recenter_after_id = self.root.after_idle(self._recenter_active_line)

    def _cancel_recenter(self) -> None:
        if self._recenter_after_id is None:
            return
        try:
            self.root.after_cancel(self._recenter_after_id)
        except (ValueError, tk.TclError):
            pass
        self._recenter_after_id = None

    def _recenter_active_line(self) -> None:
        """Re-center the active lyric after the panel's height changes."""
        self._recenter_after_id = None
        if not self._timed_lines or self._current_line_index < 0:
            return
        self._cancel_scroll_animation()
        # Snap rather than glide: a resize is not a line advance.
        self._scroll_for_active_line(self._current_line_index, reposition=True)

    def _position_is_reachable(self, x: int, y: int) -> bool:
        """Whether a saved position still lands on a connected display."""
        # Probe inside the drag strip: that is the part the user must be able to grab.
        scaling = _window_scaling(self.root)
        return _point_on_a_monitor(x + round(60 * scaling), y + round(16 * scaling))

    def _sync_position_into_settings(self) -> None:
        """Persist the position only once the user has chosen one.

        Leaving it as None keeps the tray-corner default recomputed on every
        launch, so it stays correct across resolution and taskbar changes.
        """
        self._settings.window_position = (
            self.window_position() if self._position_is_user_set else None
        )

    def _ghost_button(
        self,
        parent: ctk.CTkFrame,
        glyph: str,
        command: Callable[[], None],
    ) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text=glyph,
            width=26,
            height=26,
            # CustomTkinter adds ~2x corner_radius to a button's minimum width to
            # keep the glyph clear of the rounding, so a full circle (13) would
            # cost 19 logical px of title space per button. 6 matches ART_RADIUS.
            corner_radius=6,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            command=command,
        )
        # CTkButton has no text_hover_color, so brighten the glyph by hand.
        button.bind("<Enter>", lambda _e: button.configure(text_color=FG))
        button.bind("<Leave>", lambda _e: button.configure(text_color=MUTED))
        return button

    def _build(self) -> None:
        # The visible rounding comes from the window region, not from this frame,
        # which now sits on a matching background. The padding is kept because
        # the interior spacing was tuned against it.
        self._frame = ctk.CTkFrame(self.root, fg_color=SURFACE, corner_radius=WINDOW_RADIUS)
        self._frame.pack(fill="both", expand=True, padx=6, pady=6)

        meta_row = ctk.CTkFrame(self._frame, fg_color="transparent")
        meta_row.pack(fill="x", padx=14, pady=(12, 0))
        self._bind_drag(meta_row)

        self._art_label = ctk.CTkLabel(
            meta_row,
            text="",
            width=ART_SIZE,
            height=ART_SIZE,
            fg_color=ART_PLACEHOLDER_BG,
            corner_radius=ART_RADIUS,
            cursor="hand2",
        )
        self._art_label.pack(side="left", padx=(0, 14))
        self._art_label.bind("<Button-1>", self._on_art_clicked)
        self._art_label.bind("<Enter>", self._on_art_enter)
        self._art_label.bind("<Leave>", self._on_art_leave)
        self._set_placeholder_art()

        meta = ctk.CTkFrame(meta_row, fg_color="transparent")
        meta.pack(side="left", fill="both", expand=True)
        self._bind_drag(meta)

        # Controls sit inline with the title, so only the title row gives up width
        # and the artist / status lines below keep the full metadata column.
        title_row = ctk.CTkFrame(meta, fg_color="transparent")
        title_row.pack(fill="x")
        self._bind_drag(title_row)

        controls = ctk.CTkFrame(title_row, fg_color="transparent")
        # Packed before the title so the right slice is reserved ahead of expand.
        controls.pack(side="right")
        self._bind_drag(controls)

        hide_btn = self._ghost_button(controls, "—", self._request_hide)
        hide_btn.pack(side="right")

        settings_btn = self._ghost_button(controls, "⚙", self._toggle_settings)
        settings_btn.pack(side="right", padx=(0, 4))

        self._tooltips = [
            _Tooltip(hide_btn, "Hide to tray", self.root),
            _Tooltip(settings_btn, "Settings", self.root),
            _Tooltip(
                self._art_label,
                "Click to enlarge",
                self.root,
                enabled=lambda: self._art_bytes is not None,
            ),
        ]

        # The marquee slides the title inside this frame with place(), whose x/y
        # CustomTkinter scales from logical px. A raw tk.Canvas would not
        # participate in that scaling. Tk clips children to the frame, so the
        # frame edge is what hides the overflow.
        self._title_clip = ctk.CTkFrame(title_row, fg_color="transparent")
        self._title_clip.pack(side="left", fill="x", expand=True)
        self._bind_drag(self._title_clip)

        self._title_label = ctk.CTkLabel(
            self._title_clip,
            text="Waiting for Spotify...",
            text_color=FG,
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            anchor="w",
            justify="left",
        )
        self._title_label.place(x=0, y=0)
        self._title_label.bind("<Enter>", self._on_title_enter)
        self._sync_title_clip_height()

        self._artist_label = ctk.CTkLabel(
            meta,
            text="Start playing a track to begin",
            text_color=MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            anchor="w",
            justify="left",
        )
        self._artist_label.pack(fill="x", pady=(2, 0))

        self._status_label = ctk.CTkLabel(
            meta,
            text="No active session",
            text_color=MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            anchor="w",
            justify="left",
        )
        self._status_label.pack(fill="x", pady=(6, 0))

        self._settings_frame = ctk.CTkFrame(self._frame, fg_color=PANEL, corner_radius=8)

        self._size_value_label = self._settings_row("Window size", "")
        self._size_button = ctk.CTkSegmentedButton(
            self._settings_frame,
            values=[_SIZE_LABELS[name] for name in WINDOW_SIZES],
            command=self._on_size_preset,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            **_SEGMENTED_STYLE,
        )
        self._size_button.pack(fill="x", padx=14, pady=(0, 10))

        # Lyrics size next: it is the control that actually gets used.
        self._font_value_label = self._settings_row("Lyrics size", "")
        self._font_slider = ctk.CTkSlider(
            self._settings_frame,
            from_=11,
            to=22,
            number_of_steps=11,
            command=self._on_font_slide,
            **_SLIDER_STYLE,
        )
        self._font_slider.pack(fill="x", padx=14, pady=(0, 10))

        self._opacity_value_label = self._settings_row("Opacity", "")
        self._opacity_slider = ctk.CTkSlider(
            self._settings_frame,
            from_=OPACITY_MIN,
            to=1.0,
            number_of_steps=9,
            command=self._on_opacity_slide,
            **_SLIDER_STYLE,
        )
        self._opacity_slider.pack(fill="x", padx=14, pady=(0, 10))

        self._topmost_switch = ctk.CTkSwitch(
            self._settings_frame,
            text="Always on top",
            command=self._on_topmost_toggle,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            **_SWITCH_STYLE,
        )
        self._topmost_switch.pack(fill="x", padx=14, pady=(2, 14))

        self._divider = ctk.CTkFrame(self._frame, fg_color=HAIRLINE, height=1)
        self._divider.pack(fill="x", padx=14, pady=(10, 6))

        self._lyrics_box = ctk.CTkTextbox(
            self._frame,
            fg_color=PANEL,
            text_color=LYRIC_NEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=self._settings.font_size),
            wrap="word",
            activate_scrollbars=True,
            corner_radius=8,
            border_width=0,
            # The theme default (gray41) is brighter than the sung lyric tier and
            # pulls the eye to the edge of the panel.
            scrollbar_button_color="#2E2E2E",
            scrollbar_button_hover_color="#3F3F3F",
        )
        self._lyrics_box.pack(**_PANEL_PACK)

        self._build_state_panel()
        self.show_state("idle")

    def _bind_drag(self, widget: tk.Misc) -> None:
        widget.bind("<ButtonPress-1>", self._on_drag_start)
        widget.bind("<B1-Motion>", self._on_drag_motion)
        widget.bind("<ButtonRelease-1>", self._on_drag_end)

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )
        self._drag_origin = (event.x_root, event.y_root)
        self._drag_moved = False

    def _on_drag_motion(self, event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        if not self._drag_moved:
            if self._drag_origin is None:
                return
            travel = abs(event.x_root - self._drag_origin[0]) + abs(
                event.y_root - self._drag_origin[1]
            )
            if travel < DRAG_THRESHOLD_PX:
                return
            self._drag_moved = True
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _on_drag_end(self, _event: tk.Event) -> None:
        moved = self._drag_moved
        self._drag_offset = None
        self._drag_origin = None
        self._drag_moved = False
        # A click that never moved is not a position choice, and writing settings
        # on every click would mean a disk write per click.
        if not moved:
            return
        self._position_is_user_set = True
        self._sync_position_into_settings()
        self._emit_settings()

    def _request_hide(self) -> None:
        if self._on_hide_request:
            self._on_hide_request()
        else:
            self.hide()

    def show(self) -> None:
        self.root.deiconify()
        if self._settings.always_on_top:
            self.root.attributes("-topmost", True)
        self._visible = True

    def hide(self) -> None:
        self.close_art_zoom()
        self._hide_tooltips()
        self._cancel_marquee()
        self._sync_position_into_settings()
        self._emit_settings()
        self.root.withdraw()
        self._visible = False

    @property
    def is_visible(self) -> bool:
        return self._visible

    def update_track(self, track: NowPlaying | None) -> None:
        if track is None:
            self._set_meta(
                "Waiting for Spotify...",
                "Start playing a track to begin",
                "No active session",
            )
            self._set_placeholder_art()
            return

        self._set_meta(
            track.title or "Unknown title",
            track.artist or "Unknown artist",
            self._status_text(track),
        )
        # Album art is set only via set_album_art() from the iTunes fetch path.
        # SMTC thumbnails are intentionally not used for display.

    def _status_text(self, track: NowPlaying) -> str:
        """Elapsed / total, plus whether the highlight is real timing data."""
        if track.duration_ms > 0:
            clock = f"{_format_ms(track.position_ms)} / {_format_ms(track.duration_ms)}"
        else:
            clock = _format_ms(track.position_ms)
        badge = {"synced": " · Synced", "plain": " · Plain"}.get(self._lyrics_kind or "", "")
        if not track.is_playing:
            return f"Paused · {clock}{badge}"
        return f"{clock}{badge}"

    def _set_meta(self, title: str, artist: str, status: str) -> None:
        """Write the metadata labels, skipping the common unchanged poll."""
        meta = (title, artist, status)
        if meta == self._last_meta:
            return
        # The status clock changes every second, so the marquee has to react to
        # the title alone or it would restart on every poll.
        title_changed = self._last_meta is None or self._last_meta[0] != title
        self._last_meta = meta
        self._title_label.configure(text=title)
        self._artist_label.configure(text=artist)
        self._status_label.configure(text=status)
        if title_changed:
            self._start_marquee()

    def schedule(self, callback: Callable[[], None], delay_ms: int = 0) -> None:
        self.root.after(delay_ms, callback)

    def mainloop(self) -> None:
        self.root.mainloop()

    def _hide_tooltips(self) -> None:
        for tooltip in getattr(self, "_tooltips", ()):
            tooltip.hide()

    def destroy(self) -> None:
        self._cancel_scroll_animation()
        self._cancel_marquee(reset=False)
        self._cancel_recenter()
        self.close_art_zoom()
        self._hide_tooltips()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
