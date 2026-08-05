"""Always-on-top floating miniplayer window (CustomTkinter)."""

from __future__ import annotations

import ctypes
import logging
import tkinter as tk
from collections.abc import Callable
from ctypes import wintypes
from io import BytesIO

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from core.lyrics import current_line_index
from core.models import (
    DEFAULT_WINDOW_SIZE,
    WINDOW_SIZES,
    AppSettings,
    LyricLine,
    LyricsResult,
    NowPlaying,
)

log = logging.getLogger(__name__)

# The window is borderless, so it has no resize border and the height presets
# below are the only way to change its size. Width is deliberately one constant
# for every preset: it keeps the title row, its 232px marquee clip and the whole
# Tier 1/2 interior spacing identical at every size, so changing size only ever
# adds or removes lyric lines.
WINDOW_WIDTH = 420
WINDOW_PRESET_HEIGHTS: dict[str, int] = {
    "compact": 360,
    "standard": 500,
    "tall": 680,
}
_SIZE_LABELS: dict[str, str] = {
    "compact": "Compact",
    "standard": "Standard",
    "tall": "Tall",
}
_SIZE_BY_LABEL = {label: name for name, label in _SIZE_LABELS.items()}
# CTk.geometry() clamps WxH against minsize, so this has to leave room for the
# shortest preset or that preset would silently not apply.
WINDOW_MIN_HEIGHT = min(WINDOW_PRESET_HEIGHTS.values())
# Radius of the window itself. Windows 10 has no DWM rounded-corner attribute
# (that needs build 22000+), so the shape is clipped by hand in _round_corners.
WINDOW_RADIUS = 12
ART_SIZE = 72
ART_RADIUS = 6
# Overlay bounds in logical px. The displayed size tracks the source resolution
# between these so large art is not downscaled and small art is not blown up as
# far. With 1200px iTunes art the overlay reaches the 600 maximum; smaller
# sources clamp up to ART_ZOOM_MIN.
ART_ZOOM_MAX = 600
ART_ZOOM_MIN = 480
ART_ZOOM_INSET = 8
# Counteract the softness of an unavoidable upscale beyond this factor.
ART_SHARPEN_ABOVE = 1.5
ART_HOVER_BRIGHTNESS = 1.12
# Gap between the window and the work-area edges for the first-launch position.
EDGE_MARGIN = 16
# Ignore sub-threshold pointer movement so a plain click is not treated as a drag.
DRAG_THRESHOLD_PX = 3
# Glide the lyric scroll instead of jumping. Only normal line advances are eased;
# seeks and track changes still snap.
SCROLL_ANIM_MS = 180
SCROLL_ANIM_FRAMES = 6
# Title marquee: one pass per track change when the title overflows its clip,
# then it returns to the start and stops. Replayed on hover, never looping.
MARQUEE_DWELL_MS = 2000
MARQUEE_REST_MS = 1500
# Hover means the user is trying to read the title now, so only debounce a
# pointer passing through rather than making them wait out the full dwell.
MARQUEE_HOVER_DWELL_MS = 250
MARQUEE_SPEED_PX_S = 30
# Returning at reading speed would read as a second pass; faster reads as rewind.
MARQUEE_RETURN_SPEED_PX_S = 60
MARQUEE_FRAME_MS = 33
# Stop with the tail inset rather than flush against the clip edge.
MARQUEE_TAIL_PAD = 8
# Overflow below this is measurement noise, not a title that needs scrolling.
MARQUEE_MIN_OVERFLOW = 4
# Tk applies -alpha to the whole window including text, so below ~0.5 the lyrics
# stop being readable. Keep the slider out of the range where the app fails.
OPACITY_MIN = 0.55
FONT_FAMILY = "Segoe UI"

BG = "#0A0A0A"
SURFACE = "#181818"
PANEL = "#141414"
FG = "#FFFFFF"
MUTED = "#B3B3B3"
# Sung / upcoming lyric tiers; both clear 4.5:1 against PANEL.
LYRIC_PAST = "#808080"
LYRIC_NEXT = "#A0A0A0"
DIM = "#6A6A6A"
ACCENT = "#1DB954"
WARN = "#E8A33D"
HAIRLINE = "#2A2A2A"
HOVER = "#252525"
ART_PLACEHOLDER_BG = "#242424"

_SLIDER_STYLE = {
    "fg_color": "#3A3A3A",
    "progress_color": ACCENT,
    "button_color": FG,
    "button_hover_color": "#E8E8E8",
    "height": 14,
    "button_length": 10,
}
_SEGMENTED_STYLE = {
    "height": 26,
    "corner_radius": 6,
    "border_width": 2,
    "fg_color": HAIRLINE,
    # The selected segment is distinguished by brightness rather than accent
    # green: CustomTkinter shares one text color across all segments, and white
    # on #1DB954 is only 3:1, which would miss the 4.5:1 bar the rest of the
    # text clears.
    "selected_color": "#565656",
    "selected_hover_color": "#626262",
    "unselected_color": "#1E1E1E",
    "unselected_hover_color": "#2C2C2C",
    "text_color": FG,
}
_SWITCH_STYLE = {
    "fg_color": "#3A3A3A",
    "progress_color": ACCENT,
    "button_color": FG,
    "text_color": MUTED,
}

# The lyrics panel and the state panel share this slot, one packed at a time.
_PANEL_PACK = {"fill": "both", "expand": True, "padx": 12, "pady": (0, 12)}

# glyph, headline, default subline, glyph+headline color, subline color
_STATES: dict[str, tuple[str, str, str, str, str]] = {
    "idle": ("♪", "Nothing playing", "Start a track in Spotify", MUTED, LYRIC_PAST),
    "loading": ("", "Finding lyrics…", "", MUTED, LYRIC_PAST),
    "notfound": (
        "○",
        "No lyrics found",
        "LRCLIB doesn't have this track yet",
        MUTED,
        LYRIC_PAST,
    ),
    "instrumental": ("♫", "Instrumental", "No lyrics for this track", ACCENT, LYRIC_PAST),
    "error": ("⚠", "Can't reach lyrics service", "", WARN, MUTED),
    "ratelimited": ("⚠", "Too many requests", "Retrying shortly", WARN, MUTED),
}


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def _display_work_area() -> tuple[int, int, int, int]:
    """Return the usable desktop work area as (left, top, width, height).

    Uses the Windows work area (excludes taskbar) so visual centering matches
    what the user perceives as the display area.
    """
    rect = _RECT()
    spi_getworkarea = 0x0030
    ok = ctypes.windll.user32.SystemParametersInfoW(
        spi_getworkarea,
        0,
        ctypes.byref(rect),
        0,
    )
    if ok:
        return (
            int(rect.left),
            int(rect.top),
            int(rect.right - rect.left),
            int(rect.bottom - rect.top),
        )
    # Fallback: full primary screen.
    width = int(ctypes.windll.user32.GetSystemMetrics(0))
    height = int(ctypes.windll.user32.GetSystemMetrics(1))
    return 0, 0, width, height


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def _point_on_a_monitor(x: int, y: int) -> bool:
    """True when (x, y) falls on a currently connected display.

    Used to detect saved positions left behind by a disconnected monitor. A
    borderless window has no taskbar or Alt-Tab entry, so an off-screen restore
    would otherwise be unrecoverable without editing settings.json by hand.
    """
    monitor_defaulttonull = 0
    try:
        user32 = ctypes.windll.user32
        user32.MonitorFromPoint.argtypes = [_POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = wintypes.HANDLE
        return bool(user32.MonitorFromPoint(_POINT(int(x), int(y)), monitor_defaulttonull))
    except Exception:
        log.exception("MonitorFromPoint failed; assuming position is valid")
        return True


def _round_window_corners(window: tk.Misc, radius: int, scaling: float) -> bool:
    """Clip a window to a rounded rectangle. True when the clip was applied.

    A borderless Tk window paints every pixel of its rectangle, so a rounded
    panel drawn inside it still ends up framed by hard square corners. Windows
    10 has no DWM rounded-corner attribute to ask for instead, so the window
    region is set directly. The clip is binary, so the curve is not
    antialiased — the alternative, a transparent colour key, would turn any
    matching pixel of the album art transparent.
    """
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
        rect = _RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 1 or height <= 1:
            return False
        # CreateRoundRectRgn takes the ellipse size, which is twice the radius,
        # and treats the bounding box as exclusive.
        diameter = max(2, round(radius * scaling) * 2)
        region = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, diameter, diameter)
        if not region:
            return False
        # Windows takes ownership of the region here, so it must not be deleted.
        return bool(user32.SetWindowRgn(hwnd, region, True))
    except Exception:
        log.exception("Could not round the window corners; leaving it square")
        return False


def _animations_enabled() -> bool:
    """Honour the Windows "show animations" accessibility preference."""
    spi_getclientareaanimation = 0x1042
    try:
        enabled = wintypes.BOOL()
        ok = ctypes.windll.user32.SystemParametersInfoW(
            spi_getclientareaanimation,
            0,
            ctypes.byref(enabled),
            0,
        )
        return bool(enabled) if ok else True
    except Exception:
        log.exception("Could not read animation preference; assuming enabled")
        return True


def _format_ms(ms: int) -> str:
    total_s = max(0, ms) // 1000
    return f"{total_s // 60}:{total_s % 60:02d}"


def _window_scaling(window: tk.Misc) -> float:
    """Physical pixels per logical pixel for this window.

    Geometry strings mix coordinate spaces: CustomTkinter scales the WxH part by
    this factor, but passes the +x+y part through untouched, so any position
    computed from Win32 work-area pixels must use the scaled size.
    """
    try:
        return float(ctk.ScalingTracker.get_window_scaling(window))
    except Exception:
        log.exception("Could not read window scaling; assuming 1.0")
        return 1.0


def _widget_scaling(widget: tk.Misc) -> float:
    """Physical pixels per logical pixel for widget geometry.

    Distinct from _window_scaling: CustomTkinter tracks widget and window
    scaling separately. winfo_* reports physical pixels while place() x/y are
    scaled up from logical, so any measurement that drives an offset has to be
    converted down first.
    """
    try:
        return float(ctk.ScalingTracker.get_widget_scaling(widget))
    except Exception:
        log.exception("Could not read widget scaling; assuming 1.0")
        return 1.0


def _centre_crop_square(image: Image.Image) -> Image.Image:
    """Centre-crop to square so later square resizes do not squash the art."""
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    if width == height:
        return image
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _rounded_thumbnail(image: Image.Image, size: int, radius: int) -> Image.Image:
    """Square thumbnail with rounded corners.

    The art label's corner_radius is invisible on its own because the image
    covers it, so the rounding has to live in the image itself.
    """
    square = _centre_crop_square(image)
    thumb = square.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=radius,
        fill=255,
    )
    thumb.putalpha(mask)
    return thumb


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


class MiniplayerWindow:
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

    def _settings_row(self, label: str, value: str) -> ctk.CTkLabel:
        """Label on the left, live value readout on the right."""
        row = ctk.CTkFrame(self._settings_frame, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            row,
            text=label,
            text_color=MUTED,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        ).pack(side="left")
        value_label = ctk.CTkLabel(
            row,
            text=value,
            text_color=FG,
            anchor="e",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        value_label.pack(side="right")
        return value_label

    def _refresh_setting_readouts(self) -> None:
        width, height = self._preset_size()
        self._size_value_label.configure(text=f"{width} × {height}")
        # set() only invokes the command for a real button press, so syncing the
        # widget from settings cannot trigger a resize.
        self._size_button.set(_SIZE_LABELS.get(self._settings.window_size, ""))
        self._font_value_label.configure(text=f"{self._settings.font_size} pt")
        self._opacity_value_label.configure(text=f"{round(self._settings.opacity * 100)}%")

    def _toggle_settings(self) -> None:
        if self._settings_open:
            self._settings_frame.pack_forget()
            self._settings_open = False
            return
        self._opacity_slider.set(self._settings.opacity)
        self._font_slider.set(self._settings.font_size)
        self._refresh_setting_readouts()
        if self._settings.always_on_top:
            self._topmost_switch.select()
        else:
            self._topmost_switch.deselect()
        self._settings_frame.pack(fill="x", padx=12, pady=(8, 0), after=self._divider)
        self._settings_open = True

    def _on_size_preset(self, label: str) -> None:
        name = _SIZE_BY_LABEL.get(label)
        if name is None or name == self._settings.window_size:
            return
        self._settings.window_size = name
        self._apply_window_size()
        self._refresh_setting_readouts()
        self._emit_settings()

    def _on_opacity_slide(self, value: float) -> None:
        self._settings.opacity = float(value)
        self.root.attributes("-alpha", self._settings.opacity)
        self._refresh_setting_readouts()
        self._emit_settings()

    def _on_font_slide(self, value: float) -> None:
        self._settings.font_size = int(round(float(value)))
        self._configure_lyric_tags()
        self._lyrics_box.configure(
            font=ctk.CTkFont(family=FONT_FAMILY, size=self._settings.font_size)
        )
        self._refresh_setting_readouts()
        self._emit_settings()

    def _on_topmost_toggle(self) -> None:
        self._settings.always_on_top = bool(self._topmost_switch.get())
        self.root.attributes("-topmost", self._settings.always_on_top)
        self._emit_settings()

    def _emit_settings(self) -> None:
        if self._on_settings_changed:
            self._on_settings_changed(self._settings)

    def apply_settings(self, settings: AppSettings, *, persist: bool = True) -> None:
        self._settings = settings
        self.root.attributes("-alpha", settings.opacity)
        self.root.attributes("-topmost", settings.always_on_top)
        self._configure_lyric_tags()
        self._lyrics_box.configure(
            font=ctk.CTkFont(family=FONT_FAMILY, size=settings.font_size)
        )
        self._refresh_setting_readouts()
        if persist and self._on_settings_changed:
            self._on_settings_changed(self._settings)

    def current_settings(self) -> AppSettings:
        self._sync_position_into_settings()
        return self._settings

    def window_position(self) -> tuple[int, int]:
        return (int(self.root.winfo_x()), int(self.root.winfo_y()))

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

    @property
    def has_timed_lyrics(self) -> bool:
        return bool(self._timed_lines)

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

    def set_album_art(self, image_bytes: bytes | None) -> None:
        if not image_bytes:
            self._set_placeholder_art()
            return
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGBA")
            thumb = _rounded_thumbnail(image, ART_SIZE, ART_RADIUS)
            hover = ImageEnhance.Brightness(thumb).enhance(ART_HOVER_BRIGHTNESS)
            self._art_bytes = image_bytes
            self._art_image = ctk.CTkImage(
                light_image=thumb,
                dark_image=thumb,
                size=(ART_SIZE, ART_SIZE),
            )
            self._art_hover_image = ctk.CTkImage(
                light_image=hover,
                dark_image=hover,
                size=(ART_SIZE, ART_SIZE),
            )
            self._art_label.configure(image=self._art_image, text="", cursor="hand2")
            # Keep zoom overlay in sync if it's already open for the previous track.
            if self._art_zoom_window is not None:
                self._refresh_zoom_overlay(image)
        except Exception:
            log.exception("Failed to display album art")
            self._set_placeholder_art()

    def _set_placeholder_art(self) -> None:
        self.close_art_zoom()
        self._art_bytes = None
        self._art_image = None
        self._art_hover_image = None
        self._art_label.configure(
            image=None,
            text="♪",
            text_color=DIM,
            font=ctk.CTkFont(family=FONT_FAMILY, size=26),
            cursor="",
        )

    def _on_art_enter(self, _event: tk.Event | None = None) -> None:
        if self._art_hover_image is not None:
            self._art_label.configure(image=self._art_hover_image)

    def _on_art_leave(self, _event: tk.Event | None = None) -> None:
        if self._art_image is not None:
            self._art_label.configure(image=self._art_image)

    def _on_art_clicked(self, _event: tk.Event | None = None) -> None:
        if self._art_zoom_window is not None:
            self.close_art_zoom()
            return
        if not self._art_bytes:
            return
        self._open_art_zoom()

    def _open_art_zoom(self) -> None:
        if not self._art_bytes or self._art_zoom_window is not None:
            return
        try:
            image = Image.open(BytesIO(self._art_bytes)).convert("RGBA")
        except Exception:
            log.exception("Failed to open album art for zoom")
            return

        zoom = ctk.CTkToplevel(self.root)
        zoom.title("Album art")
        zoom.overrideredirect(True)
        zoom.attributes("-topmost", True)
        # Hairline frame around a dark inset, so the overlay reads as a card
        # rather than a bare rectangle floating on the desktop.
        zoom.configure(fg_color=HAIRLINE)
        zoom.resizable(False, False)

        matte = ctk.CTkFrame(zoom, fg_color=BG, corner_radius=0)
        matte.pack(fill="both", expand=True, padx=1, pady=1)

        label = ctk.CTkLabel(matte, text="", cursor="hand2", fg_color=BG)
        label.pack(fill="both", expand=True, padx=ART_ZOOM_INSET, pady=ART_ZOOM_INSET)

        self._art_zoom_window = zoom
        self._art_zoom_label = label
        self._refresh_zoom_overlay(image)

        for widget in (zoom, matte, label):
            widget.bind("<Button-1>", lambda _e: self.close_art_zoom())
        zoom.bind("<Escape>", lambda _e: self.close_art_zoom())
        zoom.protocol("WM_DELETE_WINDOW", self.close_art_zoom)
        # Needed for Escape to reach us; the overlay only opens on a click, so the
        # app is already the active window at this point.
        try:
            zoom.focus_force()
        except tk.TclError:
            log.debug("Could not focus art overlay; Escape may not fire")

    def _refresh_zoom_overlay(self, image: Image.Image) -> None:
        if self._art_zoom_window is None or self._art_zoom_label is None:
            return
        zoom = self._art_zoom_window
        scaling = _window_scaling(self.root)

        # Show the art at its own resolution where possible: CTkImage renders a
        # logical size at `scaling` physical px, so the logical box that avoids
        # upscaling is native / scaling, bounded by the overlay min and max.
        square = _centre_crop_square(image)
        native = max(1, square.width)
        logical = int(min(ART_ZOOM_MAX, max(ART_ZOOM_MIN, native / scaling)))
        physical = round(logical * scaling)

        zoomed = square.resize((physical, physical), Image.Resampling.LANCZOS)
        if physical >= native * ART_SHARPEN_ABOVE:
            zoomed = zoomed.filter(ImageFilter.UnsharpMask(radius=1.5, percent=60, threshold=3))
        self._art_zoom_image = ctk.CTkImage(
            light_image=zoomed,
            dark_image=zoomed,
            size=(logical, logical),
        )
        self._art_zoom_label.configure(image=self._art_zoom_image, text="")

        # Frame + inset sit outside the art, so the window is larger than the image.
        chrome = 2 * (1 + ART_ZOOM_INSET)
        box_logical = logical + chrome
        box_physical = round(box_logical * scaling)
        left, top, area_w, area_h = _display_work_area()
        x = left + (area_w - box_physical) // 2
        y = top + (area_h - box_physical) // 2
        zoom.geometry(f"{box_logical}x{box_logical}+{x}+{y}")
        zoom.update_idletasks()

    def close_art_zoom(self) -> None:
        if self._art_zoom_window is None:
            return
        try:
            self._art_zoom_window.destroy()
        except tk.TclError:
            pass
        self._art_zoom_window = None
        self._art_zoom_image = None
        self._art_zoom_label = None

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
