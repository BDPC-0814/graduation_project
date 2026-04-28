[CmdletBinding()]
param(
    [int]$Port = 8001,
    [string]$BindHost = "127.0.0.1",
    [switch]$SkipInstall,
    [switch]$SkipBuild,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
Set-Location $repoRoot

function Resolve-PythonPath {
    $venvWindows = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $venvUnix = Join-Path $repoRoot ".venv/bin/python"

    if (Test-Path -LiteralPath $venvWindows) {
        return $venvWindows
    }
    if (Test-Path -LiteralPath $venvUnix) {
        return $venvUnix
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return $pythonCmd.Source
    }

    throw "Python was not found. Create .venv or add python to PATH first."
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
            throw "Command failed: $FilePath $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Ensure-PortAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [int]$TargetPort
    )

    $listener = Get-NetTCPConnection -State Listen -LocalPort $TargetPort -ErrorAction SilentlyContinue
    if ($listener) {
        $process = Get-Process -Id $listener[0].OwningProcess -ErrorAction SilentlyContinue
        $processName = if ($process) { $process.ProcessName } else { "unknown" }
        throw "Port $TargetPort is already in use by $processName[$($listener[0].OwningProcess)]."
    }
}

function Ensure-PythonDependencies {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonPath
    )

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
    $missingOutput = & $PythonPath -c $checkScript @modules
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to inspect Python dependencies."
    }

    $missing = if ($null -eq $missingOutput) { "" } else { ($missingOutput | Out-String).Trim() }
    if ($missing) {
        Write-Host "Installing missing Python packages: $missing"
        Invoke-Checked -FilePath $PythonPath -Arguments @("-m", "pip", "install", "-r", "requirements.txt", "-r", "backend/requirements.txt")
    }
}

function Ensure-FrontendDependencies {
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npmCmd) {
        throw "npm.cmd was not found. Install Node.js first."
    }

    $nodeModules = Join-Path $repoRoot "frontend\node_modules"
    if (-not (Test-Path -LiteralPath $nodeModules)) {
        Write-Host "Installing frontend dependencies..."
        Invoke-Checked -FilePath $npmCmd.Source -Arguments @("install") -WorkingDirectory (Join-Path $repoRoot "frontend")
    }

    return $npmCmd.Source
}

$pythonPath = Resolve-PythonPath
$distIndex = Join-Path $repoRoot "frontend\dist\index.html"

if (-not $SkipInstall) {
    Ensure-PythonDependencies -PythonPath $pythonPath
}

$npmPath = $null
if (-not $SkipBuild) {
    $npmPath = Ensure-FrontendDependencies
    Write-Host "Building frontend bundle..."
    Invoke-Checked -FilePath $npmPath -Arguments @("run", "build") -WorkingDirectory (Join-Path $repoRoot "frontend")
}
elseif (-not (Test-Path -LiteralPath $distIndex)) {
    throw "frontend/dist/index.html does not exist. Remove -SkipBuild or build the frontend first."
}

Ensure-PortAvailable -TargetPort $Port

$url = "http://$BindHost`:$Port"
if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        param($TargetUrl)
        Start-Sleep -Seconds 2
        Start-Process $TargetUrl
    } -ArgumentList $url | Out-Null
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Unified startup ready."
Write-Host "URL: $url"
Write-Host "This window keeps the backend running."
Write-Host "Press Ctrl+C to stop the system."
Write-Host "============================================================"
Write-Host ""

& $pythonPath -m uvicorn backend.app.main:app --host $BindHost --port "$Port"
