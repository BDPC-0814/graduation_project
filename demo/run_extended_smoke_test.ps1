[CmdletBinding()]
param(
    [string[]]$Devices = @("cpu", "gpu", "npu"),
    [int]$Duration = 3,
    [string]$Vendor = "auto",
    [string]$OutputRoot = "experiments\extended_smoke"
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

$deviceFieldChecks = @{
    cpu = @("utilization", "power_w", "freq_mhz", "threads", "ctx_switch_rate", "duty_cycle_percent")
    gpu = @("utilization", "chip_temp_c", "power_w", "mem_util_percent", "nv_graphics_clock_mhz", "pstate")
    npu = @("utilization", "chip_temp_c", "power_w", "mem_util_percent", "device_uptime_s")
}

$commonRequiredColumns = @(
    "device_id",
    "utilization",
    "chip_temp_c",
    "power_w",
    "freq_mhz",
    "mem_util_percent",
    "duty_cycle_percent",
    "collect_ts",
    "status",
    "error"
)

$results = New-Object System.Collections.Generic.List[object]

function Test-NonEmptyField {
    param(
        [pscustomobject]$Row,
        [string]$FieldName
    )

    if (-not ($Row.PSObject.Properties.Name -contains $FieldName)) {
        return $false
    }

    $value = $Row.$FieldName
    return -not [string]::IsNullOrWhiteSpace([string]$value)
}

foreach ($device in $Devices) {
    $metricsPath = Join-Path $runDir "${device}_metrics.csv"
    $eventsPath = Join-Path $runDir "${device}_events.csv"
    $outboxPath = Join-Path $runDir "${device}_outbox.db"

    Write-Host ""
    Write-Host "=== Running smoke test for $device ==="

    $cmd = @(
        "demo\havfs_experiment.py",
        "--mode", "fixed",
        "--device", $device,
        "--vendor", $Vendor,
        "--duration", $Duration,
        "--output", $metricsPath,
        "--event-output", $eventsPath,
        "--outbox-db", $outboxPath
    )

    & $pythonCmd.Source @cmd
    if ($LASTEXITCODE -ne 0) {
        $results.Add([pscustomobject]@{
            device = $device
            status = "failed"
            detail = "experiment command failed"
        }) | Out-Null
        continue
    }

    if (-not (Test-Path $metricsPath)) {
        $results.Add([pscustomobject]@{
            device = $device
            status = "failed"
            detail = "metrics CSV was not generated"
        }) | Out-Null
        continue
    }

    $rows = @(Import-Csv $metricsPath)
    if (-not $rows -or $rows.Count -eq 0) {
        $results.Add([pscustomobject]@{
            device = $device
            status = "failed"
            detail = "metrics CSV is empty"
        }) | Out-Null
        continue
    }

    $lastRow = $rows[-1]
    $missingColumns = @($commonRequiredColumns | Where-Object { -not ($lastRow.PSObject.Properties.Name -contains $_) })
    if ($missingColumns.Count -gt 0) {
        $results.Add([pscustomobject]@{
            device = $device
            status = "failed"
            detail = "missing columns: $($missingColumns -join ', ')"
        }) | Out-Null
        continue
    }

    if ($lastRow.status -ne "ok") {
        $results.Add([pscustomobject]@{
            device = $device
            status = "unavailable"
            detail = "device unavailable, error=$($lastRow.error)"
        }) | Out-Null
        continue
    }

    $deviceChecks = $deviceFieldChecks[$device]
    $hitFields = @($deviceChecks | Where-Object { Test-NonEmptyField -Row $lastRow -FieldName $_ })
    $missingValues = @($deviceChecks | Where-Object { -not (Test-NonEmptyField -Row $lastRow -FieldName $_) })

    if ($hitFields.Count -eq 0) {
        $results.Add([pscustomobject]@{
            device = $device
            status = "failed"
            detail = "device is available but all extended fields are empty: $($deviceChecks -join ', ')"
        }) | Out-Null
        continue
    }

    $results.Add([pscustomobject]@{
        device = $device
        status = "passed"
        detail = "populated fields: $($hitFields -join ', '); empty fields: $($missingValues -join ', ')"
    }) | Out-Null
}

Write-Host ""
Write-Host "=== Extended Smoke Test Summary ==="
$results | Format-Table -AutoSize

$summaryPath = Join-Path $runDir "summary.txt"
$results | Out-String | Set-Content -Path $summaryPath -Encoding UTF8

$failedCount = @($results | Where-Object { $_.status -eq "failed" }).Count
$passedCount = @($results | Where-Object { $_.status -eq "passed" }).Count
$unavailableCount = @($results | Where-Object { $_.status -eq "unavailable" }).Count

Write-Host ""
Write-Host "Output directory: $runDir"
Write-Host "Passed: $passedCount  Unavailable: $unavailableCount  Failed: $failedCount"

if ($failedCount -gt 0) {
    exit 1
}

exit 0
