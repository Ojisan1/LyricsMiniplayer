"""Lightweight import / compile smoke checks (no UI startup)."""

import py_compile
from pathlib import Path


def test_import_core_helpers():
    import core.artwork
    import core.cache
    import core.http_limits
    import core.lyrics
    import core.models
    import core.settings

    assert core.lyrics.USER_AGENT.endswith("Ojisan1/LyricsMiniplayer)")
    assert core.artwork.USER_AGENT.endswith("Ojisan1/LyricsMiniplayer)")


def test_compile_main_and_core():
    root = Path(__file__).resolve().parents[1]
    targets = [root / "main.py", *sorted((root / "core").glob("*.py"))]
    for path in targets:
        py_compile.compile(str(path), doraise=True)
