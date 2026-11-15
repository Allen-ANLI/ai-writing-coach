# AI Writing Coach - local dev stack status (Windows PowerShell 5.1+).
#
# Read-only: shows Docker Desktop, container health, app processes (PIDs),
# endpoint health and log locations. Never prints secrets or env values.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\status-dev.ps1
#
# Logs: .dev\logs\status-dev.log

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$DevDir = Join-Path $Root '.dev'
$LogDir = Join-Path $DevDir 'logs'
$StateFile = Join-Path $DevDir 'state.json'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$script:LogFile = Join-Path $LogDir 'status-dev.log'

function Write-Log {
    param([string]$Message, [ValidateSet('INFO', 'OK', 'WARN', 'ERROR')][string]$Level = 'INFO')
    $line = '[{0}] [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    $color = switch ($Level) { 'OK' { 'Green' } 'WARN' { 'Yellow' } 'ERROR' { 'Red' } default { 'Gray' } }
    Write-Host $line -ForegroundColor $color
    Add-Content -Path $script:LogFile -Value $line -Encoding UTF8
}

# PS 5.1 turns native-command stderr into terminating errors under
# $ErrorActionPreference='Stop'; run native tools with 'Continue' and check
# $LASTEXITCODE explicitly instead.
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

Write-Log '=== status-dev: AI Writing Coach local development stack ==='

# --- Docker Desktop ----------------------------------------------------------
$dockerVersion = Invoke-NativeQuiet { docker info --format '{{.ServerVersion}}' 2>$null }
if ($LASTEXITCODE -eq 0) {
    Write-Log "Docker Desktop: running (server $dockerVersion)" 'OK'
    $dockerUp = $true
} else {
    Write-Log 'Docker Desktop: NOT running (start it manually)' 'WARN'
    $dockerUp = $false
}

# --- Containers ---------------------------------------------------------------
if ($dockerUp) {
    foreach ($name in @('awc-db', 'awc-languagetool')) {
        $info = Invoke-NativeQuiet { docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' $name 2>$null }
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Container ${name}: not created (run start-dev.ps1)" 'WARN'
            continue
        }
        $parts = "$info".Split('|')
        $state = $parts[0]
        $health = $parts[1]
        if ($state -eq 'running' -and $health -eq 'healthy') {
            Write-Log "Container ${name}: running / healthy" 'OK'
        } else {
            Write-Log "Container ${name}: $state / $health" 'WARN'
        }
    }
}

# --- App processes -------------------------------------------------------------
$procs = Get-ProjectAppProcesses
if ($procs.Backend.Count -gt 0) {
    $ids = ($procs.Backend | ForEach-Object { $_.ProcessId }) -join ', '
    Write-Log "Backend process(es): PID $ids" 'OK'
} else {
    Write-Log 'Backend process: not running' 'WARN'
}
if ($procs.Frontend.Count -gt 0) {
    $ids = ($procs.Frontend | ForEach-Object { $_.ProcessId }) -join ', '
    Write-Log "Frontend process(es): PID $ids" 'OK'
} else {
    Write-Log 'Frontend process: not running' 'WARN'
}

# --- Endpoint health -------------------------------------------------------------
if (Test-TcpPort 8000) {
    try {
        $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 5
        if ($resp.data.status -eq 'ok') {
            Write-Log "Backend :8000 health: ok (database: $($resp.data.database))" 'OK'
        } else {
            Write-Log 'Backend :8000 health: unexpected response' 'WARN'
        }
    } catch {
        Write-Log 'Backend :8000: port open but health request failed' 'WARN'
    }
} else {
    Write-Log 'Backend :8000: not listening' 'WARN'
}

if (Test-TcpPort 3500) {
    try {
        $resp = Invoke-WebRequest -Uri 'http://127.0.0.1:3500/' -TimeoutSec 10 -UseBasicParsing
        Write-Log "Frontend :3500: HTTP $($resp.StatusCode)" 'OK'
    } catch {
        Write-Log 'Frontend :3500: port open but page request failed' 'WARN'
    }
} else {
    Write-Log 'Frontend :3500: not listening' 'WARN'
}

# --- State + logs ------------------------------------------------------------------
if (Test-Path $StateFile) {
    try {
        $state = Get-Content $StateFile -Raw | ConvertFrom-Json
        Write-Log "State file: backend PID $($state.backendPid), frontend PID $($state.frontendPid), started $($state.startedAt)"
    } catch {
        Write-Log 'State file present but unreadable.' 'WARN'
    }
} else {
    Write-Log 'State file: none (stack not started via start-dev.ps1, or stopped)'
}
Write-Log "Logs: $LogDir (backend.err.log holds uvicorn output; frontend.out.log holds next dev output)"
Write-Log '=== status-dev complete ==='
exit 0
