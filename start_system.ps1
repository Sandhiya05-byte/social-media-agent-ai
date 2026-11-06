#Requires -Version 5.1
<#
.SYNOPSIS
    Unified startup script for the Social Media AI Agent platform.
.DESCRIPTION
    Starts all services in correct order:
      1. Ollama           (if not already running)
      2. Browser Service  port 8002
      3. FastAPI backend  port 8001
      4. React frontend   port 5173

    Health checks are performed for every service after launch.
    Processes already listening on a required port are detected and
    skipped rather than killed, so the user's existing work is preserved.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Configuration ─────────────────────────────────────────────────────────────
$ROOT           = $PSScriptRoot
$BACKEND_DIR    = Join-Path $ROOT 'backend'
$BROWSER_DIR    = Join-Path $ROOT 'browser_service'
$FRONTEND_DIR   = Join-Path $ROOT 'frontend'

$BACKEND_PORT   = 8001
$BROWSER_PORT   = 8002
$FRONTEND_PORT  = 5173
$OLLAMA_PORT    = 11434
$OLLAMA_MODEL   = 'qwen2.5:3b'

$HEALTH_TIMEOUT = 60   # seconds to wait per service

# ── Helpers ───────────────────────────────────────────────────────────────────

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "--- $Text ---" -ForegroundColor Cyan
}

function Write-Ok   { param([string]$Text); Write-Host "  [OK]   $Text" -ForegroundColor Green }
function Write-Warn { param([string]$Text); Write-Host "  [WARN] $Text" -ForegroundColor Yellow }
function Write-Fail { param([string]$Text); Write-Host "  [FAIL] $Text" -ForegroundColor Red }
function Write-Info { param([string]$Text); Write-Host "  [INFO] $Text" -ForegroundColor Gray }

function Test-PortListening {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return ($null -ne $conn)
}

function Wait-ForHealth {
    param(
        [string]$Url,
        [string]$Name,
        [int]$TimeoutSec = $HEALTH_TIMEOUT
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-RestMethod -Uri $Url -TimeoutSec 3 -ErrorAction Stop
            # A 2xx response is success; some endpoints (e.g. Ollama /api/tags)
            # return no `status` field at all.
            if ($null -ne $resp) {
                Write-Ok "$Name is healthy ($Url)"
                return $true
            }
        } catch { }
        Start-Sleep -Seconds 2
    }
    Write-Fail "$Name did not respond at $Url within ${TimeoutSec}s"
    return $false
}

function Test-OllamaModel {
    param([string]$Model)
    try {
        $resp  = Invoke-RestMethod -Uri "http://127.0.0.1:${OLLAMA_PORT}/api/tags" -TimeoutSec 5 -ErrorAction Stop
        $names = $resp.models | ForEach-Object { $_.name }
        return ($names -contains $Model)
    } catch {
        return $false
    }
}

function Start-ServiceWindow {
    param(
        [string]$Name,
        [string]$WorkDir,
        [string]$Command
    )
    Write-Info "Launching '$Name' in a new terminal window..."
    $escaped = $Command -replace '"', '\"'
    $argsStr = "-NoExit -Command Set-Location '$WorkDir'; $escaped"
    Start-Process powershell.exe -ArgumentList $argsStr -WorkingDirectory $WorkDir
}

# ── 1. Ollama ─────────────────────────────────────────────────────────────────
Write-Header "Ollama"

if (Test-PortListening -Port $OLLAMA_PORT) {
    Write-Ok "Ollama is already running on port $OLLAMA_PORT"
} else {
    Write-Info "Starting Ollama serve..."
    Start-ServiceWindow -Name 'Ollama' -WorkDir $ROOT -Command 'ollama serve'
    Start-Sleep -Seconds 4
}

$ollamaHealthy = Wait-ForHealth -Url "http://127.0.0.1:${OLLAMA_PORT}/api/tags" -Name 'Ollama' -TimeoutSec 30
if (-not $ollamaHealthy) {
    Write-Warn "Ollama is not responding. The backend will fall back to template generation."
}

if ($ollamaHealthy) {
    if (Test-OllamaModel -Model $OLLAMA_MODEL) {
        Write-Ok "Model '$OLLAMA_MODEL' is installed and ready"
    } else {
        Write-Fail "Model '$OLLAMA_MODEL' is NOT installed."
        Write-Warn "Run:  ollama pull $OLLAMA_MODEL"
        Write-Warn "Continuing -- backend will use template fallback until model is available."
    }
}

# ── 2. Browser Service ────────────────────────────────────────────────────────
Write-Header "Browser Service (port $BROWSER_PORT)"

if (Test-PortListening -Port $BROWSER_PORT) {
    Write-Ok "Browser Service already listening on port $BROWSER_PORT -- skipping start"
} else {
    $browserVenv = Join-Path $BROWSER_DIR '.venv\Scripts\python.exe'
    if (-not (Test-Path $browserVenv)) {
        Write-Fail "Browser Service venv not found at: $browserVenv"
        Write-Warn "Run:  cd browser_service; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    } else {
        Start-ServiceWindow `
            -Name 'BrowserService' `
            -WorkDir $BROWSER_DIR `
            -Command ".\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port $BROWSER_PORT"
    }
}

$browserHealthy = Wait-ForHealth `
    -Url "http://127.0.0.1:${BROWSER_PORT}/health" `
    -Name 'Browser Service' `
    -TimeoutSec 30

# ── 3. FastAPI Backend ────────────────────────────────────────────────────────
Write-Header "FastAPI Backend (port $BACKEND_PORT)"

if (Test-PortListening -Port $BACKEND_PORT) {
    Write-Ok "Backend already listening on port $BACKEND_PORT -- skipping start"
} else {
    $backendVenv = Join-Path $BACKEND_DIR '.venv\Scripts\python.exe'
    if (-not (Test-Path $backendVenv)) {
        Write-Fail "Backend venv not found at: $backendVenv"
        Write-Warn "Run:  cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    } else {
        Start-ServiceWindow `
            -Name 'Backend' `
            -WorkDir $BACKEND_DIR `
            -Command ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT --reload"
    }
}

$backendHealthy = Wait-ForHealth `
    -Url "http://127.0.0.1:${BACKEND_PORT}/api/health" `
    -Name 'Backend' `
    -TimeoutSec $HEALTH_TIMEOUT

# ── 4. React Frontend ─────────────────────────────────────────────────────────
Write-Header "React Frontend (port $FRONTEND_PORT)"

if (Test-PortListening -Port $FRONTEND_PORT) {
    Write-Ok "Frontend already listening on port $FRONTEND_PORT -- skipping start"
} else {
    if (-not (Test-Path (Join-Path $FRONTEND_DIR 'node_modules'))) {
        Write-Warn "node_modules not found -- running npm install first (this may take a minute)..."
        Start-ServiceWindow -Name 'FrontendInstall' -WorkDir $FRONTEND_DIR -Command 'npm install; npm run dev'
    } else {
        Start-ServiceWindow -Name 'Frontend' -WorkDir $FRONTEND_DIR -Command ("npm run dev -- --port ${FRONTEND_PORT} --strictPort")
    }
}

# Vite dev server: a plain HTTP 200 from the HTML page is enough
$deadline        = (Get-Date).AddSeconds($HEALTH_TIMEOUT)
$frontendHealthy = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:${FRONTEND_PORT}" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            Write-Ok "Frontend is healthy (http://localhost:${FRONTEND_PORT})"
            $frontendHealthy = $true
            break
        }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $frontendHealthy) {
    Write-Fail "Frontend did not respond within ${HEALTH_TIMEOUT}s"
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Header "Startup Summary"

function Write-StatusLine {
    param([string]$Label, [bool]$Ok)
    if ($Ok) { Write-Ok  $Label } else { Write-Fail $Label }
}

Write-StatusLine "Ollama          http://127.0.0.1:${OLLAMA_PORT}"  $ollamaHealthy
Write-StatusLine "Browser Service http://127.0.0.1:${BROWSER_PORT}" $browserHealthy
Write-StatusLine "Backend         http://127.0.0.1:${BACKEND_PORT}" $backendHealthy
Write-StatusLine "Frontend        http://localhost:${FRONTEND_PORT}" $frontendHealthy

Write-Host ""
if ($frontendHealthy) {
    Write-Host "  Open in browser: http://localhost:${FRONTEND_PORT}" -ForegroundColor Cyan
} else {
    Write-Warn "Frontend not ready. Check the terminal window for errors."
}
Write-Host ""
