# AI Writing Coach - one-click local dev startup (Windows PowerShell 5.1+).
#
# Starts the infrastructure containers (db, languagetool) and the app
# processes (FastAPI :8000, Next.js :3500) using ONLY project-local
# toolchains (backend\.venv Python, .tools portable Node 22).
#
# Guarantees:
# - Never modifies system PATH, registry or the global Python environment
#   (PATH is prepended in this process only, inherited by child processes).
# - Never prints secrets or environment variable values.
# - Idempotent: already-running services are detected and left alone.
# - Docker Desktop must be started manually by the user; this script only
#   checks it and never changes Docker/WSL/system configuration.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\start-dev.ps1 [-NoBrowser]
#
# Logs: .dev\logs\start-dev.log, backend.out.log, backend.err.log,
#       frontend.out.log, frontend.err.log   (process PIDs: .dev\state.json)

param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$DevDir = Join-Path $Root '.dev'
$LogDir = Join-Path $DevDir 'logs'
$StateFile = Join-Path $DevDir 'state.json'
$NodeDir = Join-Path $Root '.tools\node-v22.23.5-win-x64'
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$NextBin = Join-Path $Root 'frontend\node_modules\next\dist\bin\next'
$BackendPort = 8000
$FrontendPort = 3500

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$script:LogFile = Join-Path $LogDir 'start-dev.log'

function Write-Log {
    param([string]$Message, [ValidateSet('INFO', 'OK', 'WARN', 'ERROR')][string]$Level = 'INFO')
    $line = '[{0}] [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    $color = switch ($Level) { 'OK' { 'Green' } 'WARN' { 'Yellow' } 'ERROR' { 'Red' } default { 'Gray' } }
    Write-Host $line -ForegroundColor $color
    Add-Content -Path $script:LogFile -Value $line -Encoding UTF8
}

# PS 5.1 turns native-command stderr into terminating errors under
# $ErrorActionPreference='Stop' (docker writes progress to stderr). Run
# native tools with 'Continue' and check $LASTEXITCODE explicitly instead.
function Invoke-NativeQuiet {
    param([scriptblock]$Command)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command } finally { $ErrorActionPreference = $prev }
}

function Test-TcpPort {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $client.ConnectAsync('127.0.0.1', $Port)
        if ($task.Wait(1500) -and $client.Connected) { return $true }
        return $false
    } catch { return $false } finally { $client.Close() }
}

function Test-DockerRunning {
    Invoke-NativeQuiet { $null = docker info --format '{{.ServerVersion}}' 2>$null }
    return ($LASTEXITCODE -eq 0)
}

function Wait-ContainerHealthy {
    param([string]$Name, [int]$TimeoutSec)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $status = 'unknown'
    while ((Get-Date) -lt $deadline) {
        $status = Invoke-NativeQuiet { docker inspect -f '{{.State.Health.Status}}' $Name 2>$null }
        if ($LASTEXITCODE -ne 0) { return 'missing' }
        if ($status -eq 'healthy') { return 'healthy' }
        Start-Sleep -Seconds 2
    }
    return $status
}

function Test-BackendHealthy {
    try {
        $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 5
        return ($resp.data.status -eq 'ok')
    } catch { return $false }
}

function Test-FrontendHealthy {
    try {
        $resp = Invoke-WebRequest -Uri 'http://127.0.0.1:3500/' -TimeoutSec 10 -UseBasicParsing
        return ($resp.StatusCode -eq 200)
    } catch { return $false }
}

function Wait-Healthy {
    param([scriptblock]$Probe, [int]$TimeoutSec)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (& $Probe) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

# Identify THIS project's app processes by command-line signature. The E2E
# stack (backend :8001, frontend :3600) is explicitly excluded.
function Get-ProjectAppProcesses {
    $all = Get-CimInstance Win32_Process -Filter "name='python.exe' or name='uvicorn.exe' or name='node.exe'"
    $backend = @($all | Where-Object {
        $_.CommandLine -and $_.CommandLine -like '*ai-writing-coach*' -and
        $_.CommandLine -like '*app.main:app*' -and $_.CommandLine -notlike '*--port 8001*'
    })
    $frontend = @($all | Where-Object {
        $_.CommandLine -and $_.CommandLine -like '*ai-writing-coach\frontend*' -and
        ($_.CommandLine -like '*next*dev*' -or $_.CommandLine -like '*next\dist\server*') -and
        $_.CommandLine -notlike '*-p 3600*'
    })
    return @{ Backend = $backend; Frontend = $frontend }
}

Write-Log '=== start-dev: AI Writing Coach local development stack ==='
$startedSomething = $false

# --- Preflight: project-local toolchains -----------------------------------
if (-not (Test-Path $Python)) {
    Write-Log "Python venv not found: $Python. Create it per README (backend\.venv, Python 3.13)." 'ERROR'
    exit 1
}
if (-not (Test-Path (Join-Path $NodeDir 'node.exe'))) {
    Write-Log "Portable Node not found: $NodeDir. See README environment requirements." 'ERROR'
    exit 1
}
if (-not (Test-Path $NextBin)) {
    Write-Log 'frontend\node_modules missing. Run npm install in frontend/ first (see README).' 'ERROR'
    exit 1
}
Invoke-NativeQuiet { & $Python -c 'import uvicorn, fastapi' 2>$null } | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Log 'Backend dependencies missing in venv. Run: backend\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -e "backend[dev]"' 'ERROR'
    exit 1
}
if (-not (Test-Path (Join-Path $Root 'frontend\.env.local'))) {
    Write-Log 'frontend\.env.local not found; frontend falls back to http://localhost:8000/api/v1.' 'WARN'
}

# Process-scoped PATH prepend only (never touches system/user PATH).
$env:PATH = "$NodeDir;$env:PATH"

# --- Infrastructure ---------------------------------------------------------
if (-not (Test-DockerRunning)) {
    Write-Log 'Docker Desktop is not running. Start it manually, then re-run this script.' 'ERROR'
    Write-Log '(This script never starts or reconfigures Docker/WSL/system services.)' 'ERROR'
    exit 1
}
Write-Log 'Docker Desktop is running.' 'OK'

Write-Log 'Starting infrastructure containers (db, languagetool)...'
$composeOut = Invoke-NativeQuiet { docker compose -f (Join-Path $Root 'docker-compose.yml') up -d db languagetool 2>&1 }
if ($LASTEXITCODE -ne 0) {
    Write-Log "docker compose up failed: $composeOut" 'ERROR'
    exit 1
}
foreach ($line in $composeOut) { Write-Log "  $line" }

$dbHealth = Wait-ContainerHealthy -Name 'awc-db' -TimeoutSec 60
if ($dbHealth -ne 'healthy') {
    Write-Log "awc-db not healthy (status: $dbHealth). Check: docker compose logs db" 'ERROR'
    exit 1
}
Write-Log 'awc-db is healthy.' 'OK'

$ltHealth = Wait-ContainerHealthy -Name 'awc-languagetool' -TimeoutSec 150
if ($ltHealth -ne 'healthy') {
    Write-Log "awc-languagetool not healthy (status: $ltHealth). Check: docker compose logs languagetool" 'ERROR'
    exit 1
}
Write-Log 'awc-languagetool is healthy.' 'OK'

# --- Backend (FastAPI :8000) ------------------------------------------------
$procs = Get-ProjectAppProcesses
$backendPid = $null
if (Test-TcpPort $BackendPort) {
    if (Test-BackendHealthy) {
        if ($procs.Backend.Count -gt 0) { $backendPid = $procs.Backend[0].ProcessId }
        Write-Log "Backend already running and healthy on :$BackendPort (PID: $backendPid). Skipping." 'OK'
    } else {
        Write-Log "Port $BackendPort is occupied but the backend health check fails. Investigate before starting another instance." 'ERROR'
        exit 1
    }
} else {
    Write-Log 'Starting backend (venv python -m uvicorn, :8000, --reload)...'
    $p = Start-Process -FilePath $Python `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload') `
        -WorkingDirectory (Join-Path $Root 'backend') `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir 'backend.out.log') `
        -RedirectStandardError (Join-Path $LogDir 'backend.err.log')
    $backendPid = $p.Id
    Write-Log "Backend process started (PID: $backendPid). Waiting for health..."
    if (-not (Wait-Healthy -Probe { Test-BackendHealthy } -TimeoutSec 60)) {
        Write-Log 'Backend failed to become healthy within 60s. See .dev\logs\backend.err.log' 'ERROR'
        exit 1
    }
    Write-Log 'Backend is healthy (database connected).' 'OK'
    $startedSomething = $true
}

# --- Frontend (Next.js :3500) -----------------------------------------------
$procs = Get-ProjectAppProcesses
$frontendPid = $null
if (Test-TcpPort $FrontendPort) {
    if (Test-FrontendHealthy) {
        if ($procs.Frontend.Count -gt 0) { $frontendPid = $procs.Frontend[0].ProcessId }
        Write-Log "Frontend already running and healthy on :$FrontendPort (PID: $frontendPid). Skipping." 'OK'
    } else {
        Write-Log "Port $FrontendPort is occupied but the frontend does not respond. Investigate before starting another instance." 'ERROR'
        exit 1
    }
} else {
    Write-Log 'Starting frontend (portable Node 22, next dev, :3500)...'
    $p = Start-Process -FilePath (Join-Path $NodeDir 'node.exe') `
        -ArgumentList @($NextBin, 'dev', '-p', '3500') `
        -WorkingDirectory (Join-Path $Root 'frontend') `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir 'frontend.out.log') `
        -RedirectStandardError (Join-Path $LogDir 'frontend.err.log')
    $frontendPid = $p.Id
    Write-Log "Frontend process started (PID: $frontendPid). Waiting for health (first compile can take a while)..."
    if (-not (Wait-Healthy -Probe { Test-FrontendHealthy } -TimeoutSec 120)) {
        Write-Log 'Frontend failed to become healthy within 120s. See .dev\logs\frontend.err.log' 'ERROR'
        exit 1
    }
    Write-Log 'Frontend is healthy.' 'OK'
    $startedSomething = $true
}

# --- State + summary ---------------------------------------------------------
$state = @{
    backendPid  = $backendPid
    frontendPid = $frontendPid
    startedAt   = (Get-Date).ToString('o')
    ports       = @{ backend = $BackendPort; frontend = $FrontendPort }
}
$state | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8

Write-Log '=== Stack ready ===' 'OK'
Write-Log "  Frontend: http://localhost:$FrontendPort"
Write-Log "  Backend:  http://127.0.0.1:$BackendPort/api/v1/health"
Write-Log "  Logs:     $LogDir"

if ($startedSomething -and -not $NoBrowser) {
    Write-Log 'Opening browser...'
    Start-Process "http://localhost:$FrontendPort"
}
exit 0
