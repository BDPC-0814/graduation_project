[CmdletBinding()]
param(
    [string]$Devices = "cpu",
    [ValidateSet("auto", "nvidia", "intel")]
    [string]$GpuVendor = "auto",
    [int]$Duration = 30,
    [double]$FixedInterval = 5.0,
    [double]$TMin = 0.5,
    [double]$TMax = 8.0,
    [string]$ReplayTrace = "",
    [string]$GroundTruthEvents = "",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$ServerHost = "127.0.0.1",
    [switch]$SkipInstall,
    [switch]$SkipCleanup,
    [switch]$ShutdownOnFinish
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "Python was not found in PATH and .venv\Scripts\python.exe does not exist."
    }
    $pythonPath = $pythonCmd.Source
}

$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    throw "npm.cmd was not found in PATH."
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [string]$WorkingDirectory = $repoRoot
    )

    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            $joined = $Arguments -join " "
            throw "Command failed: $FilePath $joined"
        }
    }
    finally {
        Pop-Location
    }
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 800
        }
    }

    throw "Timed out while waiting for $Uri"
}

function Get-ListeningProcessesByPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $results = @()

    try {
        $connections = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop
        foreach ($connection in $connections) {
            $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
            $results += [PSCustomObject]@{
                Port = $Port
                PID = $connection.OwningProcess
                ProcessName = if ($process) { $process.ProcessName } else { "unknown" }
            }
        }
    }
    catch {
        $netstatLines = netstat -ano | Select-String -Pattern "LISTENING\s+(\d+)$"
        foreach ($line in $netstatLines) {
            $text = $line.ToString().Trim()
            if ($text -match "[:\.]$Port\s+.*LISTENING\s+(\d+)$") {
                $pid = [int]$matches[1]
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
                $results += [PSCustomObject]@{
                    Port = $Port
                    PID = $pid
                    ProcessName = if ($process) { $process.ProcessName } else { "unknown" }
                }
            }
        }
    }

    return $results
}

function Assert-PortAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    $listeners = @(Get-ListeningProcessesByPort -Port $Port)
    if ($listeners.Count -eq 0) {
        return
    }

    $summary = ($listeners | ForEach-Object { "$($_.ProcessName)[$($_.PID)]" }) -join ", "
    throw "$ServiceName port $Port is already in use by: $summary. Stop those processes or rerun with a different port."
}

function Resolve-AvailablePort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$StartingPort,
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [int[]]$ReservedPorts = @(),
        [int]$MaxAttempts = 50
    )

    for ($offset = 0; $offset -lt $MaxAttempts; $offset++) {
        $candidatePort = $StartingPort + $offset
        if ($ReservedPorts -contains $candidatePort) {
            continue
        }

        $listeners = @(Get-ListeningProcessesByPort -Port $candidatePort)
        if ($listeners.Count -eq 0) {
            if ($candidatePort -ne $StartingPort) {
                Write-Host "$ServiceName port $StartingPort was unavailable. Using port $candidatePort instead."
            }
            return $candidatePort
        }
    }

    throw "Could not find an available port for $ServiceName starting from $StartingPort within $MaxAttempts attempts."
}

function Ensure-PythonDependencies {
    $modules = @("fastapi", "uvicorn", "pydantic", "numpy", "pandas", "matplotlib", "psutil")
    $checkScript = @'
import sys
missing = []
for name in sys.argv[1:]:
    try:
        __import__(name)
    except ModuleNotFoundError:
        missing.append(name)
print(chr(44).join(missing))
'@
    $missingOutput = & $pythonPath -c $checkScript @modules
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to inspect Python dependencies."
    }
    $missing = if ($null -eq $missingOutput) { "" } else { ($missingOutput | Out-String).Trim() }

    if ($missing) {
        Write-Host "Installing missing Python modules: $missing"
        Invoke-Checked -FilePath $pythonPath -Arguments @("-m", "pip", "install", "-r", "requirements.txt", "-r", "backend/requirements.txt")
    }
}

function Ensure-FrontendDependencies {
    $nodeModules = Join-Path $repoRoot "frontend\node_modules"
    if (-not (Test-Path -LiteralPath $nodeModules)) {
        Write-Host "Installing frontend dependencies"
        Invoke-Checked -FilePath $npmCmd.Source -Arguments @("install") -WorkingDirectory (Join-Path $repoRoot "frontend")
    }
}

if (-not $SkipInstall) {
    Ensure-PythonDependencies
    Ensure-FrontendDependencies
}

if (-not $SkipCleanup) {
    Invoke-Checked -FilePath "powershell" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "tools/cleanup_project_artifacts.ps1"
    )
}

$ResolvedBackendPort = Resolve-AvailablePort -StartingPort $BackendPort -ServiceName "Backend"
$ResolvedFrontendPort = Resolve-AvailablePort -StartingPort $FrontendPort -ServiceName "Frontend" -ReservedPorts @($ResolvedBackendPort)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runDir = Join-Path $repoRoot (Join-Path "experiments\midterm_check" $timestamp)
$logDir = Join-Path $runDir "logs"
$dataDir = Join-Path $runDir "data"
$snapshotDir = Join-Path $runDir "snapshots"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $repoRoot "experiments\evaluation\latest") -Force | Out-Null

if ($ReplayTrace) {
    $resolvedReplayTrace = if ([System.IO.Path]::IsPathRooted($ReplayTrace)) { $ReplayTrace } else { Join-Path $repoRoot $ReplayTrace }
    if (-not (Test-Path -LiteralPath $resolvedReplayTrace)) {
        throw "Replay trace not found: $resolvedReplayTrace. Generate one first with demo/generate_replay_trace.py."
    }
    $ReplayTrace = $resolvedReplayTrace

    if (-not $GroundTruthEvents) {
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($ReplayTrace)
        $candidateNames = @(
            ($baseName -replace "trace$", "events") + ".csv",
            ($baseName -replace "_trace$", "_events") + ".csv",
            ($baseName + "_events.csv")
        ) | Select-Object -Unique

        foreach ($candidateName in $candidateNames) {
            $candidatePath = Join-Path (Split-Path -Parent $ReplayTrace) $candidateName
            if (Test-Path -LiteralPath $candidatePath) {
                $GroundTruthEvents = $candidatePath
                break
            }
        }
    }
    elseif (-not [System.IO.Path]::IsPathRooted($GroundTruthEvents)) {
        $GroundTruthEvents = Join-Path $repoRoot $GroundTruthEvents
    }
}

$backendProcess = $null
$frontendProcess = $null

try {
    $backendStdout = Join-Path $logDir "backend.stdout.log"
    $backendStderr = Join-Path $logDir "backend.stderr.log"
    $backendArgs = @(
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host", $ServerHost,
        "--port", "$ResolvedBackendPort"
    )
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList $backendArgs -WorkingDirectory $repoRoot -PassThru -RedirectStandardOutput $backendStdout -RedirectStandardError $backendStderr
    Wait-HttpOk -Uri "http://$ServerHost`:$ResolvedBackendPort/health"

    $frontendStdout = Join-Path $logDir "frontend.stdout.log"
    $frontendStderr = Join-Path $logDir "frontend.stderr.log"
    $frontendArgs = @("run", "dev", "--", "--host", $ServerHost, "--port", "$ResolvedFrontendPort", "--strictPort")
    $frontendProcess = Start-Process -FilePath $npmCmd.Source -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $repoRoot "frontend") -PassThru -RedirectStandardOutput $frontendStdout -RedirectStandardError $frontendStderr
    Wait-HttpOk -Uri "http://$ServerHost`:$ResolvedFrontendPort"

    $sharedArgs = @(
        "demo/evolution_sampling_experiment.py",
        "--device", $Devices,
        "--vendor", $GpuVendor,
        "--remote-endpoint", "http://$ServerHost`:$ResolvedBackendPort/api/ingest"
    )
    if ($Duration -gt 0) {
        $sharedArgs += @("--duration", "$Duration")
    }
    if ($ReplayTrace) {
        $sharedArgs += @("--trace-file", $ReplayTrace)
    }

    Invoke-Checked -FilePath $pythonPath -Arguments @(
        $sharedArgs +
        @(
            "--mode", "fixed",
            "--fixed-interval", "$FixedInterval",
            "--output", (Join-Path $dataDir "fixed_metrics.csv"),
            "--event-output", (Join-Path $dataDir "fixed_events.csv"),
            "--outbox-db", (Join-Path $dataDir "fixed_outbox.db")
        )
    )

    Invoke-Checked -FilePath $pythonPath -Arguments @(
        $sharedArgs +
        @(
            "--mode", "evolution",
            "--t-min", "$TMin",
            "--t-max", "$TMax",
            "--output", (Join-Path $dataDir "evolution_metrics.csv"),
            "--event-output", (Join-Path $dataDir "evolution_events.csv"),
            "--outbox-db", (Join-Path $dataDir "evolution_outbox.db")
        )
    )

    $evaluateArgs = @(
        "demo/evaluate_metrics.py",
        "--fixed", (Join-Path $dataDir "fixed_metrics.csv"),
        "--evolution", (Join-Path $dataDir "evolution_metrics.csv"),
        "--output-dir", "experiments/evaluation/latest"
    )
    if ($GroundTruthEvents) {
        $evaluateArgs += @("--ground-truth-events", $GroundTruthEvents)
    }

    Invoke-Checked -FilePath $pythonPath -Arguments $evaluateArgs

    $overview = Invoke-RestMethod -Uri "http://$ServerHost`:$ResolvedBackendPort/api/dashboard/overview" -TimeoutSec 20
    $evaluation = Invoke-RestMethod -Uri "http://$ServerHost`:$ResolvedBackendPort/api/experiments/evaluation" -TimeoutSec 20

    $overview | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $snapshotDir "dashboard_overview.json") -Encoding UTF8
    $evaluation | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $snapshotDir "evaluation_report.json") -Encoding UTF8

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Midterm check completed."
    Write-Host "Backend URL: http://$ServerHost`:$ResolvedBackendPort"
    Write-Host "Frontend URL: http://$ServerHost`:$ResolvedFrontendPort"
    Write-Host "Run output: $runDir"
    Write-Host "Evaluation report: experiments/evaluation/latest/report.json"
    Write-Host "============================================================"

    if ($ShutdownOnFinish) {
        if ($frontendProcess -and -not $frontendProcess.HasExited) {
            Stop-Process -Id $frontendProcess.Id -Force
        }
        if ($backendProcess -and -not $backendProcess.HasExited) {
            Stop-Process -Id $backendProcess.Id -Force
        }
    }
    else {
        Write-Host "Servers are still running for the live demo."
        Write-Host "Backend PID: $($backendProcess.Id)"
        Write-Host "Frontend PID: $($frontendProcess.Id)"
    }
}
catch {
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        Stop-Process -Id $frontendProcess.Id -Force
    }
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force
    }
    throw
}
