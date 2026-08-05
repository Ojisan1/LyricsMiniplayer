# Spotify Lyrics Miniplayer

**Version 1.2.0**

A lightweight, always-on-top Windows floating miniplayer that shows the currently playing Spotify track and time-synced lyrics with high resolution album art — with zero Spotify API keys or account linking.

## Installation

1. Open this repository’s **[Releases](https://github.com/Ojisan1/LyricsMiniplayer/releases)** page and download `LyricsMiniplayer-v1.2.0.zip`.
2. Right-click the zip → **Extract All…** (or unzip with your usual tool) into any folder you like — Desktop, Documents, a USB stick, etc. There is **no installer**.
3. Start the **Spotify desktop app** and play a track (the miniplayer reads what Windows reports as “now playing”).
4. Open the unzipped folder and double-click **`LyricsMiniplayer.exe`**.

Settings are saved under `%APPDATA%\LyricsMiniplayer\` so you can move or delete the unzipped folder without losing preferences.

### Windows security warning (first launch)

Because this is a small personal open-source app, the `.exe` is **not code-signed** with a paid publisher certificate. Windows may show a blue **Windows protected your PC** (SmartScreen) dialog the first time you run it. That is normal for unsigned software and does **not** mean the file was altered after you downloaded it from this repo’s Releases page.

If you downloaded the zip from **this project’s GitHub Releases** and trust that source:

1. On the SmartScreen dialog, click **More info**.
2. Click **Run anyway**.

Windows usually only asks once for that file. If your antivirus quarantines the exe, restore/allow it the same way you would for other small open-source tools you chose to install.

### Verifying the release

Each GitHub Release also publishes:

| Artifact | Purpose |
|----------|---------|
| `SHA256SUMS` | SHA-256 digests of `LyricsMiniplayer.exe` and the release zip |
| `sbom.cdx.json` | CycloneDX software bill of materials for the build environment |
| `PROVENANCE.md` | Python version, lockfile hash, host OS/arch, and exact build command |

**PowerShell** (from the folder that contains the downloaded files):

```powershell
Get-FileHash -Algorithm SHA256 .\LyricsMiniplayer-v1.2.0.zip
Get-Content .\SHA256SUMS
```

Confirm the hash matches the corresponding line in `SHA256SUMS`. Optionally open `PROVENANCE.md` and `sbom.cdx.json` to see how that binary was built and which packages it included.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and a summary of the August 2026 security review.

## How to use

### The floating window

Once running, a dark always-on-top panel appears (by default near the bottom-right of your screen, above the taskbar):

| Part | What it does |
|------|----------------|
| **Album art** (left) | Cover for the current track. Hover brightens it slightly. |
| **Title** | Song name. If it is too long for the row, it scrolls once, then returns to the start. Hover the title to replay the scroll. |
| **Artist** | Artist name. |
| **Status line** | Elapsed / duration, e.g. `1:42 / 2:38 · Synced`. Shows `Paused ·` when Spotify is paused, and `· Plain` when lyrics exist but are not time-synced. |
| **Lyrics area** | Timed lines scroll with the music; the current line is white and bold. |
| **⚙ (gear)** | Opens settings (see below). |
| **— (dash)** | Hides the window to the system tray. **This does not quit the app.** |

**Move the window:** click and drag anywhere on it.

**Album art zoom:** click the art thumbnail to open a larger centered overlay. Close it by clicking the overlay (or the art again) or pressing **Escape**.

### Settings (gear)

| Setting | Meaning |
|---------|---------|
| **Window size** | Compact / Standard / Tall — same width, different heights (more or fewer lyric lines). Changing size snaps the window back to the tray corner. |
| **Lyrics size** | Font size for the lyrics panel (independent of window size). |
| **Opacity** | How translucent the window is. |
| **Always on top** | Keep the miniplayer above other windows. |

There is no resize border on the window; use **Window size** to change dimensions.

### System tray

The app keeps a tray icon (notification area, near the clock) even when the floating window is hidden:

- **Hover** the icon to see the current track.
- **Right-click** for the menu:
  - Current track (informational)
  - **Show lyrics** — checked when the window is visible; click to show or hide
  - **Quit** — fully exits the app

Hiding with **—** only closes the floating window; use **Quit** in the tray menu when you want to stop the program.

Lyric scrolling and the title marquee both honour the Windows **“Show animations”** accessibility setting.

## Status

**v1.2.0** — security hardening: bounded remote content, constrained artwork fetch, hashed dependency lock, release checksums/SBOM/provenance. See [RELEASE_NOTES_v1.2.0.md](RELEASE_NOTES_v1.2.0.md).  
**v1.1.0** — album-aware iTunes art matching (prefers the album Spotify is playing over compilations/singles).  
**v1.0.0** — timed lyrics, UX polish, high-res iTunes art, redistributable zip.

See `PHASE_STATUS.md` for history and `Spotify-Lyrics-Miniplayer-Product-Handoff.md` for the product spec.

## Requirements

- Windows 10 / 11
- Spotify desktop app
- Internet connection for lyrics ([LRCLIB](https://lrclib.net)) and album art (iTunes Search API)
- Python 3.11+ only if running from source (developed/tested on 3.14)

## Quick start (development)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install --require-hashes -r requirements.txt
python main.py
```

`requirements.txt` is a fully pinned lockfile with hashes. Edit `requirements.in` and recompile when upgrading dependencies:

```bash
pip install uv
uv pip compile --generate-hashes -o requirements.txt requirements.in
```

### Optional CLI helpers

- `python main.py --once` — single SMTC snapshot
- `python main.py --console` — console-only now-playing monitor
- `python main.py --lyrics-test` — fetch lyrics for the current track

### Pre-release security check

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\security-check.ps1
```

Runs `pip check`, `pip-audit` against the lockfile, and a compile-all pass.

## Build a redistributable zip

```bash
.venv\Scripts\activate
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

This installs from the hashed lockfile and produces:

- `dist\LyricsMiniplayer.exe` — windowed, no console
- `dist\LyricsMiniplayer-v1.2.0.zip` — exe + `README.txt` + `LICENSE` for GitHub Releases
- `dist\SHA256SUMS` — checksums for the exe and zip
- `dist\sbom.cdx.json` — CycloneDX SBOM
- `dist\PROVENANCE.md` — build environment and command

## How it works

- **Now playing:** Windows System Media Transport Controls (SMTC) via PyWinRT
- **Lyrics:** [LRCLIB](https://lrclib.net) (free, no API key)
- **Album art:** [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/) (no API key; prefers 1200×1200; ranks by SMTC album when available)
- **UI:** CustomTkinter floating window + system tray (`pystray`)

## Project layout

| Path | Role |
|------|------|
| `main.py` | App entry, SMTC poll, lyric sync |
| `core/smtc.py` | Spotify now-playing via SMTC |
| `core/lyrics.py` | LRCLIB client + LRC parse |
| `core/artwork.py` | iTunes album art fetch |
| `core/limits.py` | Hard caps for untrusted remote content |
| `core/settings.py` | Persistent settings |
| `ui/miniplayer.py` | Floating window, size presets, state screens, art zoom, title marquee |
| `ui/tray.py` | System tray |
| `requirements.in` | Direct dependency constraints |
| `requirements.txt` | Pinned lockfile with hashes |
| `scripts/security-check.ps1` | Local pre-release dependency audit |
| `packaging/README.txt` | Short readme bundled in the release zip |
| `SECURITY.md` | Vulnerability reporting and review summary |
| `RELEASE_NOTES_v1.2.0.md` | v1.2.0 changelog |
| `PHASE_STATUS.md` | Phase checklist and UX notes |
| `Spotify-Lyrics-Miniplayer-Product-Handoff.md` | Product spec (source of truth) |

## Dependencies note

SMTC access uses PyWinRT (`winrt-Windows.Media.Control`) rather than the older `winsdk` package, which does not install cleanly on Python 3.14 without a C++ build toolchain.

## License

[MIT](LICENSE). This project is not affiliated with Spotify, Apple, or LRCLIB; those services have their own terms.
