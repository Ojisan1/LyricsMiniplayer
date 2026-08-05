# Spotify Lyrics Miniplayer

**Version 1.0.0**

A lightweight, always-on-top Windows floating miniplayer that shows the currently playing Spotify track and time-synced lyrics — with zero Spotify API keys or account linking.

## Download (Windows)

Grab the latest zip from this repository’s **Releases** page:

1. Download `LyricsMiniplayer-v1.0.0.zip`
2. Unzip anywhere
3. Start Spotify and play a track
4. Run `LyricsMiniplayer.exe`

No installer. Settings are stored under `%APPDATA%\LyricsMiniplayer\`.

Windows SmartScreen may warn on first launch (unsigned personal build). Use **More info → Run anyway** if you trust the release you downloaded.

## Status

**v1.0.0** — functional miniplayer with timed lyrics, UX polish (Tiers 1–3 core items), and clean high-resolution album art from iTunes. See `PHASE_STATUS.md` for history and `Spotify-Lyrics-Miniplayer-Product-Handoff.md` for the product spec.

## Requirements

- Windows 10 / 11
- Spotify desktop app
- Internet connection for lyrics ([LRCLIB](https://lrclib.net)) and album art (iTunes Search API)
- Python 3.11+ only if running from source (developed/tested on 3.14)

## Quick start (development)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Optional CLI helpers

- `python main.py --once` — single SMTC snapshot
- `python main.py --console` — console-only now-playing monitor
- `python main.py --lyrics-test` — fetch lyrics for the current track

## Usage

1. Start Spotify and play a track.
2. Run `python main.py` (or the packaged `.exe`).
3. The floating window stays on top and shows title, artist, album art, and synced lyrics.
   The status line reads `1:42 / 2:38 · Synced`, with a `Plain` badge when only untimed
   lyrics exist and a `Paused ·` prefix when playback is paused.
4. A title too long for its row scrolls once on track change, then returns to the start and
   stops. Hover the title to replay it.
5. Click the album art to enlarge it to a centered overlay; click it again, click the
   overlay, or press **Escape** to close.
6. Drag anywhere on the window to move it. Use **—** to hide to the system tray (this does
   not quit the app).
7. Tray menu: a checked **Show lyrics** toggle plus **Quit**. The current track appears above
   them and as the icon's hover tooltip.
8. Use **⚙** for window size, lyrics size, opacity, and always-on-top.

The window has no resize border, so **Window size** in the settings panel is how you resize it.
Three presets are available, all 420 logical px wide and differing only in height — Compact
(420 × 360, about 7 lyric lines), Standard (420 × 500, about 11) and Tall (420 × 680, about 17),
measured at the default 14pt. Because the width never changes, a size change only adds or removes
lyric lines and leaves the rest of the layout alone. Lyrics size stays on its own slider and is
not affected by the preset. Changing size returns the window to the tray corner.

Settings (window position, window size, opacity, font size, always-on-top) are saved under
`%APPDATA%\LyricsMiniplayer\settings.json`. The window position is only written once you
actually drag the window; until then, and again after any size change, it opens near the tray in
the bottom-right corner of the work area, recomputed each launch so it survives resolution and
taskbar changes.

Lyric scrolling and the title marquee both honour the Windows "show animations"
accessibility setting.

## Build a redistributable zip

```bash
.venv\Scripts\activate
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

This produces:

- `dist\LyricsMiniplayer.exe` — windowed, no console
- `dist\LyricsMiniplayer-v1.0.0.zip` — exe + `README.txt` + `LICENSE` for GitHub Releases

## How it works

- **Now playing:** Windows System Media Transport Controls (SMTC) via PyWinRT
- **Lyrics:** [LRCLIB](https://lrclib.net) (free, no API key)
- **Album art:** [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/) (no API key; prefers 1200×1200)
- **UI:** CustomTkinter floating window + system tray (`pystray`)

## Project layout

| Path | Role |
|------|------|
| `main.py` | App entry, SMTC poll, lyric sync |
| `core/smtc.py` | Spotify now-playing via SMTC |
| `core/lyrics.py` | LRCLIB client + LRC parse |
| `core/artwork.py` | iTunes album art fetch |
| `core/settings.py` | Persistent settings |
| `ui/miniplayer.py` | Floating window, size presets, state screens, art zoom, title marquee |
| `ui/tray.py` | System tray |
| `packaging/README.txt` | Short readme bundled in the release zip |
| `PHASE_STATUS.md` | Phase checklist and UX notes |
| `Spotify-Lyrics-Miniplayer-Product-Handoff.md` | Product spec (source of truth) |

## Dependencies note

SMTC access uses PyWinRT (`winrt-Windows.Media.Control`) rather than the older `winsdk` package, which does not install cleanly on Python 3.14 without a C++ build toolchain.

## License

[MIT](LICENSE). This project is not affiliated with Spotify, Apple, or LRCLIB; those services have their own terms.
