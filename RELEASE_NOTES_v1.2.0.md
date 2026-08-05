## Spotify Lyrics Miniplayer v1.2.0

Floating always-on-top Windows miniplayer for Spotify with time-synced lyrics. No Spotify API keys or account linking.

### Installation
1. Download `LyricsMiniplayer-v1.2.0.zip` from this release.
2. Right-click the zip → **Extract All…** into any folder (Desktop, Documents, etc.). There is **no installer**.
3. Start the **Spotify desktop app** and play a track.
4. Open the unzipped folder and double-click **`LyricsMiniplayer.exe`**.

Settings are saved under `%APPDATA%\LyricsMiniplayer\`, so you can move or delete the unzipped folder without losing preferences.

### Windows security warning (first launch)
Because this is a small personal open-source app, the `.exe` is **not code-signed**. Windows may show a blue **Windows protected your PC** (SmartScreen) dialog the first time you run it. That is normal for unsigned software and does **not** mean the file was altered after you downloaded it from this Releases page.

If you trust this download:
1. Click **More info**.
2. Click **Run anyway**.

Windows usually only asks once. If antivirus quarantines the exe, restore/allow it the same way you would for other open-source tools you chose to install.

### Verifying the release
This release also includes `SHA256SUMS`, `sbom.cdx.json`, and `PROVENANCE.md`.

**PowerShell** (from the folder with the downloaded files):

```powershell
Get-FileHash -Algorithm SHA256 .\LyricsMiniplayer-v1.2.0.zip
Get-Content .\SHA256SUMS
```

Confirm the hash matches the corresponding line in `SHA256SUMS`.

### How to use

**Floating window**
- **Album art** — current cover; hover brightens it. **Click** to open a larger centered zoom overlay; close with another click or **Escape**.
- **Title / artist** — long titles scroll once, then stop; hover the title to replay.
- **Status line** — e.g. `1:42 / 2:38 · Synced`; `Paused ·` when paused; `· Plain` when lyrics are not timed.
- **Lyrics** — timed lines follow the music; the current line is white and bold.
- **Gear (⚙)** — settings.
- **Dash (—)** — hide to the system tray (**does not quit**).
- **Drag** anywhere on the window to move it.

**Settings (gear)**
- **Window size** — Compact / Standard / Tall (same width, more or fewer lyric lines).
- **Lyrics size** — font size for the lyrics panel.
- **Opacity** — window translucency.
- **Always on top** — keep the miniplayer above other windows.

**System tray** (icon near the clock)
- Hover for the current track.
- Right-click → **Show lyrics** to show/hide the window.
- Right-click → **Quit** to fully exit.
- Hiding with **—** only closes the window; use **Quit** to stop the app.

### Requirements
- Windows 10 / 11
- Spotify desktop app
- Internet for lyrics (LRCLIB) and album art (iTunes Search)

MIT licensed. Not affiliated with Spotify, Apple, or LRCLIB.

### What's new
- **Security hardening** — following an August 2026 review of the v1.1 release: bounded LRCLIB/iTunes responses, constrained HTTPS artwork fetch (Apple CDN hosts, redirects, JPEG/PNG checks), serialized lyric/art fetches, and hashed dependency lockfile.
- **Release verification** — each build publishes `SHA256SUMS`, a CycloneDX `sbom.cdx.json`, and `PROVENANCE.md` (no Authenticode signing).
- **Album-aware cover art** (from v1.1) — iTunes results are ranked using the album Spotify reports, so studio-album art wins over compilations/singles when the same song appears on multiple releases.
