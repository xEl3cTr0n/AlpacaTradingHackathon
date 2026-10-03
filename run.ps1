# ==============================================================================
# RegimeShift AI - Windows (PowerShell) development runner. Mirrors run.sh.
# Starts the FastAPI backend (port 8000) and Next.js frontend (port 3000).
#
#   powershell -ExecutionPolicy Bypass -File .\run.ps1          # Alpaca keys from .env
#   powershell -ExecutionPolicy Bypass -File .\run.ps1 -Demo    # no keys: demo data
# ==============================================================================
param([switch]$Demo)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Uvicorn = Join-Path $Backend ".venv\Scripts\uvicorn.exe"

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js (npm) not found. Install it, then open a NEW PowerShell window:" -ForegroundColor Red
    Write-Host "  winget install -e --id OpenJS.NodeJS.LTS"
    exit 1
}
if (-not (Test-Path $Uvicorn)) {
    Write-Host "Backend virtualenv not found. Create it once (Python 3.11+):" -ForegroundColor Red
    Write-Host "  winget install -e --id Python.Python.3.12   # if Python is not installed"
    Write-Host "  cd backend; py -3.12 -m venv .venv; .\.venv\Scripts\python -m pip install -e '.[dev]'"
    exit 1
}
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "Frontend dependencies not found. Install them once:" -ForegroundColor Red
    Write-Host "  cd frontend; npm.cmd install"
    exit 1
}

Write-Host "Checking for existing instances on ports 8000 and 3000..."
foreach ($port in 8000, 3000) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

# Remember the caller's values: a script started as .\run.ps1 shares the
# shell's environment, and demo mode must not leak into the next live run.
$savedMode = $env:MARKET_DATA_MODE
$savedAllowDemo = $env:REGIMESHIFT_ALLOW_DEMO_DATA
if ($Demo) {
    # Child processes inherit these; they override values in .env.
    $env:MARKET_DATA_MODE = "demo"
    $env:REGIMESHIFT_ALLOW_DEMO_DATA = "true"
    Write-Host "Demo mode: deterministic synthetic data, clearly labelled in the UI." -ForegroundColor Yellow
}

Write-Host "Starting backend on http://127.0.0.1:8000 ..."
$backendProcess = Start-Process -FilePath $Uvicorn -WorkingDirectory $Backend -NoNewWindow -PassThru `
    -ArgumentList "regimeshift.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"

Write-Host ""
Write-Host "======================================================================"
Write-Host "  RegimeShift AI terminal: http://localhost:3000"
Write-Host "  Backend API:             http://127.0.0.1:8000  (docs at /docs)"
Write-Host "  Press Ctrl+C to stop both servers."
Write-Host "======================================================================"
Write-Host ""

try {
    Push-Location $Frontend
    # npm.cmd sidesteps the npm.ps1 shim that execution policy often blocks.
    npm.cmd run dev
}
finally {
    # Windows PowerShell 5.1 turns redirected native stderr into errors under
    # "Stop", which would abort cleanup if the backend already exited.
    $ErrorActionPreference = "Continue"
    Pop-Location
    Write-Host "Shutting down backend..."
    # /T also stops the uvicorn reload worker that holds port 8000.
    & taskkill /PID $backendProcess.Id /T /F *> $null
    $env:MARKET_DATA_MODE = $savedMode
    $env:REGIMESHIFT_ALLOW_DEMO_DATA = $savedAllowDemo
}
