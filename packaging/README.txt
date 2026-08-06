Spotify Lyrics Miniplayer v1.2.1
================================

A floating Windows miniplayer that shows the current Spotify track and
time-synced lyrics. No Spotify API keys or account linking required.

Installation
------------
1. Unzip this folder anywhere you like (Desktop, Documents, etc.).
   There is no installer.
2. Start the Spotify desktop app and play a track.
3. Double-click LyricsMiniplayer.exe.

Settings are saved under:
  %APPDATA%\LyricsMiniplayer\settings.json
You can move or delete this unzipped folder without losing preferences.

Windows security warning (first launch)
---------------------------------------
This .exe is not code-signed with a paid publisher certificate, so Windows
may show a blue "Windows protected your PC" (SmartScreen) dialog the first
time you run it. That is normal for small unsigned open-source apps and does
not mean the file was changed after you downloaded it from this project's
GitHub Releases page.

If you trust that download:
  1. Click "More info" on the SmartScreen dialog.
  2. Click "Run anyway".

Windows usually only asks once. If antivirus quarantines the file, restore
or allow it the same way you would for other tools you chose to install.

Verifying the download
----------------------
Each GitHub Release also includes SHA256SUMS, sbom.cdx.json, and
PROVENANCE.md. Compare the zip/exe hash to SHA256SUMS before running.
See the project README for PowerShell verification commands.

How to use
----------
The floating window (always on top by default):
  - Album art (left) — cover for the current track; hover brightens it.
  - Title / artist — song info. Long titles scroll once, then stop; hover
    the title to replay the scroll.
  - Status line — e.g. "1:42 / 2:38 · Synced". Shows "Paused ·" when
    paused, and "· Plain" when lyrics are not time-synced.
  - Lyrics area — timed lines follow the music; the current line is bold.
  - Gear (⚙) — opens settings.
  - Dash (—) — hides the window to the system tray. Does NOT quit.

Move the window by clicking and dragging anywhere on it.

Album art zoom:
  Click the art thumbnail for a larger centered overlay. Close it by
  clicking the overlay (or the art again) or pressing Escape.

Settings (gear):
  - Window size — Compact / Standard / Tall (more or fewer lyric lines).
  - Lyrics size — font size for the lyrics panel.
  - Opacity — how translucent the window is.
  - Always on top — keep the miniplayer above other windows.
  Changing window size returns the window to the tray corner.

System tray (icon near the clock):
  - Hover — shows the current track.
  - Right-click → Show lyrics — show or hide the floating window.
  - Right-click → Quit — fully exit the app.
  Hiding with — only closes the window; use Quit to stop the program.

Requirements
------------
- Windows 10 or 11
- Spotify desktop app
- Internet connection for lyrics (LRCLIB) and album art (iTunes Search)

License
-------
MIT — see LICENSE in this folder.

This app is not affiliated with Spotify, Apple, or LRCLIB. Those services
have their own terms of use.
