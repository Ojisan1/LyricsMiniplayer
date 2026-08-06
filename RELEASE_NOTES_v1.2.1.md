## Spotify Lyrics Miniplayer v1.2.1

Floating always-on-top Windows miniplayer for Spotify with time-synced lyrics. No Spotify API keys or account linking.

### What's new
- **Plain lyrics line breaks** — reject LRCLIB plain-only uploads that store an entire song as one space-separated blob with no line breaks. The client then falls through to search, which usually finds a proper multiline copy.
- **Better timed coverage as a side effect** — for some previously broken tracks (e.g. Leprous *Moon*, *Illuminate*), that search hit includes synced LRC, so they now highlight and scroll like other timed songs.
- **Line-ending normalization** — canonicalize `\r\n` / `\r` to `\n` when ingesting lyric text (Windows/Tk-friendly).

### Installation
1. Download `LyricsMiniplayer-v1.2.1.zip` from this release.
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
Get-FileHash -Algorithm SHA256 .\LyricsMiniplayer-v1.2.1.zip
Get-Content .\SHA256SUMS
```

Confirm the hash matches the corresponding line in `SHA256SUMS`.

### Requirements
- Windows 10 / 11
- Spotify desktop app
- Internet for lyrics (LRCLIB) and album art (iTunes Search)

MIT licensed. Not affiliated with Spotify, Apple, or LRCLIB.
