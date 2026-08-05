"""Album art thumbnail, hover state, and click-to-zoom overlay."""

from __future__ import annotations

import logging
import tkinter as tk
from io import BytesIO

import customtkinter as ctk
from PIL import Image, ImageEnhance, ImageFilter

from ui.art_images import _centre_crop_square, _rounded_thumbnail
from ui.theme import (
    ART_HOVER_BRIGHTNESS,
    ART_RADIUS,
    ART_SHARPEN_ABOVE,
    ART_SIZE,
    ART_ZOOM_INSET,
    ART_ZOOM_MAX,
    ART_ZOOM_MIN,
    BG,
    DIM,
    FONT_FAMILY,
    HAIRLINE,
)
from ui.win32_geom import _display_work_area, _window_scaling

log = logging.getLogger(__name__)


class AlbumArtMixin:
    """Mixin owning thumbnail display and the art zoom overlay."""

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
