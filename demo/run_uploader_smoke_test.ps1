[CmdletBinding()]
param(
    [int]$Port = 18080,
    [int]$Duration = 10,
    [int]$FailFirst = 2,
    [int]$RetryBatchSize = 10,
    [string]$OutputRoot = "experiments\uploader_smoke"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    throw "Python was not found in PATH."
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$runDir = Join-Path $repoRoot (Join-Path $OutputRoot $timestamp)
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$logPath = Join-Path $runDir "mock_server.jsonl"
$stdoutPath = Join-Path $runDir "mock_server_stdout.log"
$stderrPath = Join-Path $runDir "mock_server_stderr.log"
$metricsPath = Join-Path $runDir "metrics.csv"
$eventsPath = Join-Path $runDir "events.csv"
$outboxPath = Join-Path $runDir "outbox.db"
$endpoint = "http://127.0.0.1:$Port/ingest"

$serverArgs = @(
    "demo\mock_ingest_server.py",
    "--port", "$Port",
    "--fail-first", "$FailFirst",
    "--log-file", $logPath
)

Write-Host "Starting mock ingest server on $endpoint"
$serverProcess = Start-Process -FilePath $pythonCmd.Source -ArgumentList $serverArgs -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

try {
    Start-Sleep -Seconds 2

    Write-Host "Running edge experiment against mock server"
    & $pythonCmd.Source `
        demo\havfs_experiment.py `
        --mode fixed `
        --device cpu `
        --duration $Duration `
        --remote-endpoint $endpoint `
        --retry-batch-size $RetryBatchSize `
        --retry-max-attempts 6 `
        --output $metricsPath `
        --event-output $eventsPath `
        --outbox-db $outboxPath

    if ($LASTEXITCODE -ne 0) {
        throw "Experiment command failed."
    }

    Start-Sleep -Seconds 2
}
finally {
    if (-not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force
    }
}

Write-Host ""
Write-Host "=== Mock Server Log Summary ==="

$logRows = @()
if (Test-Path $logPath) {
    $logRows = @(Get-Content $logPath | Where-Object { $_.Trim() -ne "" } | ForEach-Object { $_ | ConvertFrom-Json })
}

if ($logRows.Count -eq 0) {
    Write-Host "No requests were captured."
}
else {
    $logRows | Select-Object request_id, status, content_encoding, record_count, sample_types | Format-Table -AutoSize
}

Write-Host ""
Write-Host "=== Outbox Summary ==="

$summaryJson = @'
import json
import sqlite3
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
rows = conn.execute("select status, count(*) from outbox group by status order by status").fetchall()
conn.close()
print(json.dumps(rows))
'@ | python - $outboxPath

Write-Host $summaryJson
Write-Host ""
Write-Host "Artifacts: $runDir"
