# AI Writing Coach - one-click local dev shutdown (Windows PowerShell 5.1+).
#
# Stops ONLY this project's app processes (FastAPI :8000, Next.js :3500),
# identified by command-line signature (repo path + uvicorn app.main:app /
# next dev). Other projects' processes are never touched, and the isolated
# E2E stack (:8001 / :3600) is excluded.
#
# Infrastructure policy:
# - Default: containers (awc-db, awc-languagetool) keep running.
# - -Infrastructure: also stops the containers via `docker compose stop`.
#   Containers and the pgdata volume are PRESERVED. This script never runs
#   `docker compose down -v` and never deletes data volumes.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\stop-dev.ps1 [-Infrastructure]
#
# Logs: .dev\logs\stop-dev.log

param([switch]$Infrastructure)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$DevDir = Join-Path $Root '.dev'
$LogDir = Join-Path $DevDir 'logs'
$StateFile = Join-Path $DevDir 'state.json'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$script:LogFile = Join-Path $LogDir 'stop-dev.log'

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

# Same signature as start-dev.ps1 / status-dev.ps1: repo path + app marker,
# excluding the E2E stack. Command lines are re-checked immediately before
# killing to guard against PID reuse.
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

function Stop-ProjectProcessTree {
    param($Proc, [string]$Label)
    $targetPid = $Proc.ProcessId
    # Re-verify the PID still belongs to a matching project process (PID reuse
    # guard) before killing the tree.
    $fresh = Get-CimInstance Win32_Process -Filter "ProcessId=$targetPid" -ErrorAction SilentlyContinue
    if (-not $fresh) {
        Write-Log "$Label PID $targetPid already exited (stopped with its process tree)."
        return
    }
    if (-not $fresh.CommandLine -or $fresh.CommandLine -notlike '*ai-writing-coach*') {
        Write-Log "$Label PID $targetPid no longer matches a project process (PID reuse?); skipping." 'WARN'
        return
    }
    Invoke-NativeQuiet { & taskkill.exe /PID $targetPid /T /F 2>&1 } | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Log "$Label stopped (PID: $targetPid, process tree)." 'OK'
    } else {
        Write-Log "$Label PID $targetPid could not be stopped (taskkill exit $LASTEXITCODE)." 'WARN'
    }
}

Write-Log '=== stop-dev: AI Writing Coach local development stack ==='

$procs = Get-ProjectAppProcesses
$stopped = 0

foreach ($p in $procs.Frontend) {
    Stop-ProjectProcessTree -Proc $p -Label 'Frontend (Next.js)'
    $stopped++
}
foreach ($p in $procs.Backend) {
    Stop-ProjectProcessTree -Proc $p -Label 'Backend (FastAPI)'
    $stopped++
}
if ($stopped -eq 0) {
    Write-Log 'No project app processes found (already stopped).' 'INFO'
}

if (Test-Path $StateFile) {
    Remove-Item $StateFile -Force
    Write-Log 'Removed .dev\state.json'
}

# Give processes a moment to release their ports, then verify.
Start-Sleep -Seconds 2
foreach ($port in @(8000, 3500)) {
    if (Test-TcpPort $port) {
        Write-Log "Port $port is still occupied. Another program may own it; this script will not kill unidentifiable processes." 'WARN'
    } else {
        Write-Log "Port $port is free." 'OK'
    }
}

if ($Infrastructure) {
    Invoke-NativeQuiet { $null = docker info --format '{{.ServerVersion}}' 2>$null }
    if ($LASTEXITCODE -ne 0) {
        Write-Log 'Docker is not running; cannot stop containers (they are already down).' 'WARN'
    } else {
        Write-Log 'Stopping infrastructure containers (compose stop; containers and pgdata volume preserved)...'
        $out = Invoke-NativeQuiet { docker compose -f (Join-Path $Root 'docker-compose.yml') stop db languagetool 2>&1 }
        if ($LASTEXITCODE -eq 0) {
            foreach ($line in $out) { Write-Log "  $line" }
            Write-Log 'Containers stopped. Data volumes were NOT removed.' 'OK'
        } else {
            Write-Log "docker compose stop failed: $out" 'ERROR'
            exit 1
        }
    }
} else {
    Write-Log 'Containers left running (use -Infrastructure to stop them; data volumes are never deleted).'
}

Write-Log '=== stop-dev complete ===' 'OK'
exit 0
