# Local pre-release security checks (no GitHub Actions required).
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\security-check.ps1
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Create a venv first: python -m venv .venv"
}

Write-Host "==> Ensuring pip-audit is available"
& $Python -m pip install --quiet pip-audit
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install pip-audit."
}

Write-Host "==> pip check"
& $Python -m pip check
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip check failed."
}

Write-Host "==> pip-audit (requirements.txt)"
& $Python -m pip_audit -r (Join-Path $RepoRoot "requirements.txt") --progress-spinner off
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip-audit reported vulnerabilities."
}

Write-Host "==> Compile check"
& $Python -m compileall -q main.py core ui
if ($LASTEXITCODE -ne 0) {
    Write-Error "compileall failed."
}

Write-Host "Security check passed."
