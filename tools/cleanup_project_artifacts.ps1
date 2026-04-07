[CmdletBinding()]
param(
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

function Remove-Target {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath
    )

    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return
    }

    if ($DryRun) {
        Write-Host "[DRY-RUN] remove $LiteralPath"
        return
    }

    try {
        Remove-Item -LiteralPath $LiteralPath -Recurse -Force
        Write-Host "[REMOVED] $LiteralPath"
    }
    catch {
        Write-Warning "Skipped locked path: $LiteralPath"
    }
}

$directTargets = @(
    (Join-Path $repoRoot "tmp_docx.docx"),
    (Join-Path $repoRoot "backend\data\havfs.db"),
    (Join-Path $repoRoot "backend\data\havfs.db-shm"),
    (Join-Path $repoRoot "backend\data\havfs.db-wal")
)

foreach ($target in $directTargets) {
    Remove-Target -LiteralPath $target
}

$experimentsRoot = Join-Path $repoRoot "experiments"
if (-not (Test-Path -LiteralPath $experimentsRoot)) {
    exit 0
}

$artifactDirs = @(
    (Join-Path $experimentsRoot "acceptance"),
    (Join-Path $experimentsRoot "extended_smoke"),
    (Join-Path $experimentsRoot "uploader_smoke"),
    (Join-Path $experimentsRoot "midterm_check")
)

foreach ($dirPath in $artifactDirs) {
    Remove-Target -LiteralPath $dirPath
}

$rootArtifactPatterns = @("*.csv", "*.db", "*.txt")
foreach ($pattern in $rootArtifactPatterns) {
    Get-ChildItem -LiteralPath $experimentsRoot -File -Filter $pattern -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Target -LiteralPath $_.FullName }
}

$evaluationLatest = Join-Path $experimentsRoot "evaluation\latest"
if (Test-Path -LiteralPath $evaluationLatest) {
    Get-ChildItem -LiteralPath $evaluationLatest -Force -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Target -LiteralPath $_.FullName }
}

Write-Host "Cleanup completed."
