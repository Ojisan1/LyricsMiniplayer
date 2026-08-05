"""Win32 geometry, DPI scaling, and window-region helpers."""

from __future__ import annotations

import ctypes
import logging
import tkinter as tk
from ctypes import wintypes

import customtkinter as ctk

log = logging.getLogger(__name__)


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
