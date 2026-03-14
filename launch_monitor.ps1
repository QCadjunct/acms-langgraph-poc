# launch_monitor.ps1
# ACMS Monitor launcher — edit or run mode.
# Architecture Standard: Mind Over Metadata LLC — Peter Heller
#
# Usage:
#   .\launch_monitor.ps1          # default: run mode (demo / production)
#   .\launch_monitor.ps1 -Mode edit   # edit mode (development)
#   .\launch_monitor.ps1 -Mode run    # explicit run mode
#   .\launch_monitor.ps1 -Port 2719   # override port (e.g. if 2718 is taken)
#
# PYTHONPATH is set automatically to the repo root.
# No manual $env:PYTHONPATH required.

param(
    [ValidateSet("run", "edit")]
    [string]$Mode = "run",

    [int]$Port = 2718
)

$RepoRoot  = $PSScriptRoot
$MonitorPy = Join-Path $RepoRoot "ui\acms_monitor.py"
$Venv      = Join-Path $RepoRoot ".venv\Scripts\marimo"

# ── Validate environment ──────────────────────────────────────────────────────

if (-not (Test-Path $MonitorPy)) {
    Write-Error "acms_monitor.py not found at: $MonitorPy"
    exit 1
}

if (-not (Test-Path $Venv)) {
    Write-Error "Marimo not found at: $Venv — run: uv sync"
    exit 1
}

# ── Set PYTHONPATH ────────────────────────────────────────────────────────────

$env:PYTHONPATH = $RepoRoot

# ── Launch ────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  ACMS Monitor" -ForegroundColor Cyan
Write-Host "  Mind Over Metadata LLC -- Peter Heller" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Mode       : $Mode" -ForegroundColor White
Write-Host "  Port       : $Port" -ForegroundColor White
Write-Host "  PYTHONPATH : $RepoRoot" -ForegroundColor DarkGray
Write-Host "  Monitor    : $MonitorPy" -ForegroundColor DarkGray
Write-Host ""

if ($Mode -eq "edit") {
    Write-Host "  Starting in EDIT mode (development)..." -ForegroundColor Yellow
    Write-Host "  URL: http://127.0.0.1:$Port" -ForegroundColor Green
    Write-Host ""
    & $Venv edit $MonitorPy --port $Port
} else {
    Write-Host "  Starting in RUN mode (demo / production)..." -ForegroundColor Green
    Write-Host "  URL: http://127.0.0.1:$Port" -ForegroundColor Green
    Write-Host ""
    & $Venv run $MonitorPy --port $Port
}
