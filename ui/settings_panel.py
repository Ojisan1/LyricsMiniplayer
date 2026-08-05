"""Settings panel widgets and handlers for the miniplayer."""

from __future__ import annotations

import customtkinter as ctk

from core.models import AppSettings
from ui.theme import (
    FG,
    FONT_FAMILY,
    MUTED,
    OPACITY_MIN,
    _SEGMENTED_STYLE,
    _SIZE_BY_LABEL,
    _SIZE_LABELS,
    _SLIDER_STYLE,
    _SWITCH_STYLE,
)


class SettingsPanelMixin:
    """Mixin owning settings rows, toggles, and apply/current_settings."""

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
