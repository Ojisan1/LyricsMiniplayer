"""Shared colors, fonts, and layout constants for the miniplayer UI."""

from __future__ import annotations

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
