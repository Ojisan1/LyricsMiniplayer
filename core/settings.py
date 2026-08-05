"""Persistent application settings (JSON in %%APPDATA%%)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from core.models import DEFAULT_WINDOW_SIZE, WINDOW_SIZES, AppSettings

log = logging.getLogger(__name__)

_APP_DIR_NAME = "LyricsMiniplayer"
_SETTINGS_FILE = "settings.json"


def settings_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / _APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return settings_dir() / _SETTINGS_FILE


def load_settings() -> AppSettings:
    path = settings_path()
    if not path.exists():
        return AppSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return AppSettings()
        pos = raw.get("window_position")
        window_position = None
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            window_position = (int(pos[0]), int(pos[1]))
        # An unknown or missing preset name falls back to the default, so a file
        # written by an older build still loads.
        window_size = str(raw.get("window_size", DEFAULT_WINDOW_SIZE)).strip().lower()
        if window_size not in WINDOW_SIZES:
            window_size = DEFAULT_WINDOW_SIZE
        opacity = float(raw.get("opacity", 1.0))
        # Floor matches the UI slider: -alpha dims text too, so lower values make
        # the lyrics unreadable. Older saved values clamp up harmlessly.
        opacity = min(1.0, max(0.55, opacity))
        font_size = int(raw.get("font_size", 14))
        font_size = min(22, max(11, font_size))
        always_on_top = bool(raw.get("always_on_top", True))
        return AppSettings(
            window_position=window_position,
            window_size=window_size,
            opacity=opacity,
            font_size=font_size,
            always_on_top=always_on_top,
        )
    except Exception:
        log.exception("Failed to load settings from %s", path)
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    path = settings_path()
    payload = {
        "window_position": list(settings.window_position)
        if settings.window_position
        else None,
        "window_size": settings.window_size,
        "opacity": settings.opacity,
        "font_size": settings.font_size,
        "always_on_top": settings.always_on_top,
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        log.exception("Failed to save settings to %s", path)
