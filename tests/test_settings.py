"""Tests for settings load, clamp, and defaults."""

from core.models import AppSettings, DEFAULT_WINDOW_SIZE
from core import settings as settings_mod


def test_load_settings_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    loaded = settings_mod.load_settings()
    assert loaded == AppSettings()
    assert loaded.window_size == DEFAULT_WINDOW_SIZE
    assert loaded.opacity == 1.0
    assert loaded.font_size == 14
    assert loaded.always_on_top is True
    assert loaded.window_position is None


def test_load_settings_clamps_opacity_and_font(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = settings_mod.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"opacity": 0.1, "font_size": 99, "window_size": "tall", "always_on_top": false}',
        encoding="utf-8",
    )
    loaded = settings_mod.load_settings()
    assert loaded.opacity == 0.55
    assert loaded.font_size == 22
    assert loaded.window_size == "tall"
    assert loaded.always_on_top is False


def test_load_settings_unknown_window_size_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = settings_mod.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"window_size": "huge"}', encoding="utf-8")
    loaded = settings_mod.load_settings()
    assert loaded.window_size == DEFAULT_WINDOW_SIZE


def test_load_settings_parses_window_position(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = settings_mod.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"window_position": [120, 340]}', encoding="utf-8")
    loaded = settings_mod.load_settings()
    assert loaded.window_position == (120, 340)


def test_load_settings_invalid_json_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = settings_mod.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    assert settings_mod.load_settings() == AppSettings()


def test_save_and_reload_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    original = AppSettings(
        window_position=(10, 20),
        window_size="compact",
        opacity=0.8,
        font_size=16,
        always_on_top=False,
    )
    settings_mod.save_settings(original)
    loaded = settings_mod.load_settings()
    assert loaded == original
