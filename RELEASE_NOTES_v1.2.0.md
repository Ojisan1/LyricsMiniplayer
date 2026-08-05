# LyricsMiniplayer v1.2.0

Security hardening release following the August 2026 review of the v1.1.0 source and Windows package.

## Highlights

- Bound untrusted LRCLIB and iTunes responses (JSON size, lyric lines/text, image bytes and dimensions)
- Constrain artwork retrieval to HTTPS Apple CDN hosts with redirect, Content-Type, and JPEG/PNG checks
- Stop using SMTC thumbnails for display; album art continues to come from iTunes only
- Serialize lyric/artwork fetches on a single worker to avoid skip-track stampedes
- Pin dependencies with hashes (`requirements.txt` / `requirements.in`)
- Publish `SHA256SUMS`, CycloneDX `sbom.cdx.json`, and `PROVENANCE.md` with every release build
- Add local `scripts/security-check.ps1` (`pip check`, `pip-audit`, compile-all)
- Document verification steps in the README and add `SECURITY.md`

## Explicitly deferred

- Spotify AUMID allowlist / stricter local metadata hardening
- Atomic `settings.json` writes
- Authenticode code signing (checksums + SBOM + provenance used instead)

## Download

From the [GitHub Releases](https://github.com/Ojisan1/LyricsMiniplayer/releases) page, get `LyricsMiniplayer-v1.2.0.zip` plus `SHA256SUMS`, `sbom.cdx.json`, and `PROVENANCE.md`. Verify the zip hash before running.
