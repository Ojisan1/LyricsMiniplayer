# Build LyricsMiniplayer.exe with PyInstaller (windowed, no console)
# and pack a redistributable zip for GitHub Releases.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Version = "1.1.0"
$ReleaseName = "LyricsMiniplayer-v$Version"

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Error "Create and activate a venv first (python -m venv .venv)."
}

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name LyricsMiniplayer `
    --collect-all customtkinter `
    --collect-all winrt `
    --hidden-import winrt.windows.media.control `
    --hidden-import winrt.windows.storage.streams `
    --hidden-import winrt.windows.foundation `
    --hidden-import winrt.windows.foundation.collections `
    --hidden-import PIL._tkinter_finder `
    main.py

if (-not (Test-Path .\dist\LyricsMiniplayer.exe)) {
    Write-Error "Build failed: dist\LyricsMiniplayer.exe not found."
}

$stage = Join-Path $PSScriptRoot "dist\$ReleaseName"
if (Test-Path $stage) {
    Remove-Item $stage -Recurse -Force
}
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item .\dist\LyricsMiniplayer.exe $stage
Copy-Item .\packaging\README.txt $stage
Copy-Item .\LICENSE $stage

$zipPath = Join-Path $PSScriptRoot "dist\$ReleaseName.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath

Write-Host "Built: dist\LyricsMiniplayer.exe"
Write-Host "Zip:   dist\$ReleaseName.zip"
