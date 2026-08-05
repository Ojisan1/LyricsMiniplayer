# Contributing

Thanks for taking an interest in Spotify Lyrics Miniplayer. This is a small Windows-only project; keep changes focused and reviewable.

## Development setup

Requirements: Windows 10/11, Python 3.11+, Spotify desktop app (for manual UI checks).

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --require-hashes -r requirements.txt
pip install -r requirements-dev.txt
python main.py
```

`requirements.txt` is the hashed release lockfile (used by `build.ps1`). Edit `requirements.in` and recompile when upgrading runtime deps:

```powershell
pip install uv
uv pip compile --generate-hashes -o requirements.txt requirements.in
```

### Optional CLI helpers

- `python main.py --once` — single SMTC snapshot
- `python main.py --console` — console-only now-playing monitor
- `python main.py --lyrics-test` — fetch lyrics for the current track

## Tests

Unit tests cover pure `core/` helpers and do not need Spotify:

```powershell
python -m pytest
```

CI (`.github/workflows/ci.yml`) runs the same suite on `windows-latest` with the hashed lockfile, then `pip check`, `pip-audit`, and `compileall`. It does not launch the CustomTkinter UI.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Produces `dist\LyricsMiniplayer.exe`, the release zip, `SHA256SUMS`, SBOM, and provenance under `dist\`.

## Pre-release security check

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\security-check.ps1
```

## Pull requests

- Prefer small, reviewable commits.
- Do not commit `dist/`, `build/`, `.venv/`, or secrets.
- Match existing code style; avoid drive-by refactors.
- UI/CustomTkinter changes should stay Windows-focused; unit-test pure logic where possible.
