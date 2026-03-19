param(
    [switch]$DumpSensors
)

$ErrorActionPreference = "Stop"

function Get-VendorAssemblyPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PackageName,
        [Parameter(Mandatory = $true)]
        [string]$AssemblyName
    )

    $packageDir = Get-ChildItem (Join-Path $PSScriptRoot "vendor") -Directory |
        Where-Object { $_.Name -like "$PackageName.*" } |
        Select-Object -First 1

    if (-not $packageDir) {
        return $null
    }

    $candidates = @(
        (Join-Path $packageDir.FullName "runtimes\win-x64\lib\net481\$AssemblyName.dll"),
        (Join-Path $packageDir.FullName "runtimes\win-x64\lib\net472\$AssemblyName.dll"),
        (Join-Path $packageDir.FullName "runtimes\win-x64\lib\net462\$AssemblyName.dll"),
        (Join-Path $packageDir.FullName "lib\net481\$AssemblyName.dll"),
        (Join-Path $packageDir.FullName "lib\net472\$AssemblyName.dll"),
        (Join-Path $packageDir.FullName "lib\net462\$AssemblyName.dll"),
        (Join-Path $packageDir.FullName "lib\netstandard2.0\$AssemblyName.dll"),
        (Join-Path $packageDir.FullName "ref\net472\$AssemblyName.dll"),
        (Join-Path $packageDir.FullName "ref\netstandard2.0\$AssemblyName.dll")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-LibreHardwareMonitorDllPath {
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString().ToLowerInvariant()
    $rid = switch ($arch) {
        "arm64" { "win-arm64" }
        "x86" { "win-x86" }
        default { "win-x64" }
    }

    $candidates = @(
        (Join-Path $PSScriptRoot "vendor\LibreHardwareMonitorLib.0.9.6-pre625\runtimes\$rid\lib\net472\LibreHardwareMonitorLib.dll"),
        (Join-Path $PSScriptRoot "vendor\LibreHardwareMonitorLib.0.9.6-pre625\ref\net472\LibreHardwareMonitorLib.dll")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "LibreHardwareMonitorLib.dll not found."
}

[System.AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($sender, $args)

    if (-not $args.Name) {
        return $null
    }

    $simpleName = ([System.Reflection.AssemblyName]::new($args.Name)).Name
    $path = switch ($simpleName) {
        "DiskInfoToolkit" { Get-VendorAssemblyPath -PackageName "DiskInfoToolkit" -AssemblyName "DiskInfoToolkit" }
        "HidSharp" { Get-VendorAssemblyPath -PackageName "HidSharp" -AssemblyName "HidSharp" }
        "RAMSPDToolkit-NDD" { Get-VendorAssemblyPath -PackageName "RAMSPDToolkit-NDD" -AssemblyName "RAMSPDToolkit-NDD" }
        "System.Management" { Get-VendorAssemblyPath -PackageName "System.Management" -AssemblyName "System.Management" }
        "System.Memory" { Get-VendorAssemblyPath -PackageName "System.Memory" -AssemblyName "System.Memory" }
        "System.Buffers" { Get-VendorAssemblyPath -PackageName "System.Buffers" -AssemblyName "System.Buffers" }
        "System.Numerics.Vectors" { Get-VendorAssemblyPath -PackageName "System.Numerics.Vectors" -AssemblyName "System.Numerics.Vectors" }
        "System.Runtime.CompilerServices.Unsafe" { Get-VendorAssemblyPath -PackageName "System.Runtime.CompilerServices.Unsafe" -AssemblyName "System.Runtime.CompilerServices.Unsafe" }
        "System.Threading.AccessControl" { Get-VendorAssemblyPath -PackageName "System.Threading.AccessControl" -AssemblyName "System.Threading.AccessControl" }
        default { $null }
    }

    if ($path) {
        return [System.Reflection.Assembly]::LoadFrom($path)
    }

    return $null
})

$dependencyPackages = @(
    @{ Package = "System.Memory"; Assembly = "System.Memory" },
    @{ Package = "System.Buffers"; Assembly = "System.Buffers" },
    @{ Package = "System.Numerics.Vectors"; Assembly = "System.Numerics.Vectors" },
    @{ Package = "System.Runtime.CompilerServices.Unsafe"; Assembly = "System.Runtime.CompilerServices.Unsafe" },
    @{ Package = "DiskInfoToolkit"; Assembly = "DiskInfoToolkit" },
    @{ Package = "HidSharp"; Assembly = "HidSharp" },
    @{ Package = "RAMSPDToolkit-NDD"; Assembly = "RAMSPDToolkit-NDD" },
    @{ Package = "System.Management"; Assembly = "System.Management" },
    @{ Package = "System.Threading.AccessControl"; Assembly = "System.Threading.AccessControl" }
)

foreach ($dependency in $dependencyPackages) {
    $path = Get-VendorAssemblyPath -PackageName $dependency.Package -AssemblyName $dependency.Assembly
    if ($path) {
        [Reflection.Assembly]::LoadFrom($path) | Out-Null
    }
}

$dllPath = Get-LibreHardwareMonitorDllPath
[Reflection.Assembly]::LoadFrom($dllPath) | Out-Null

$visitorSource = @"
using LibreHardwareMonitor.Hardware;

public sealed class UpdateVisitor : IVisitor
{
    public void VisitComputer(IComputer computer)
    {
        computer.Traverse(this);
    }

    public void VisitHardware(IHardware hardware)
    {
        hardware.Update();
        foreach (IHardware subHardware in hardware.SubHardware)
        {
            subHardware.Accept(this);
        }
    }

    public void VisitSensor(ISensor sensor) { }
    public void VisitParameter(IParameter parameter) { }
}
"@

if (-not ([System.Management.Automation.PSTypeName]"UpdateVisitor").Type) {
    Add-Type -TypeDefinition $visitorSource -ReferencedAssemblies $dllPath | Out-Null
}

function Get-PreferredSensorValue {
    param(
        [AllowNull()]
        [array]$Candidates
    )

    if (-not $Candidates -or $Candidates.Count -eq 0) {
        return $null
    }

    $preferredKeywords = @(
        "cpu package",
        "package",
        "gpu core",
        "package power",
        "board power draw",
        "hot spot",
        "junction",
        "core (tdie)",
        "cpu core"
    )

    foreach ($keyword in $preferredKeywords) {
        $match = $Candidates | Where-Object { $_.Name -and $_.Name.ToLowerInvariant().Contains($keyword) } | Select-Object -First 1
        if ($match) {
            return $match.Value
        }
    }

    return ($Candidates | Select-Object -First 1).Value
}

function New-SensorRecord {
    param(
        [string]$HardwareName,
        [string]$HardwareType,
        $Sensor
    )

    [pscustomobject]@{
        HardwareName = $HardwareName
        HardwareType = $HardwareType
        Name = $Sensor.Name
        SensorType = $Sensor.SensorType.ToString()
        Value = $Sensor.Value
    }
}

function Collect-HardwareSensors {
    param(
        [Parameter(Mandatory = $true)]
        [LibreHardwareMonitor.Hardware.IHardware]$Hardware
    )

    $records = @()
    foreach ($sensor in $Hardware.Sensors) {
        if ($null -ne $sensor.Value) {
            $records += New-SensorRecord -HardwareName $Hardware.Name -HardwareType $Hardware.HardwareType.ToString() -Sensor $sensor
        }
    }

    foreach ($subHardware in $Hardware.SubHardware) {
        $records += Collect-HardwareSensors -Hardware $subHardware
    }

    return $records
}

$computer = New-Object LibreHardwareMonitor.Hardware.Computer
$computer.IsCpuEnabled = $true
$computer.IsGpuEnabled = $true
$computer.IsMemoryEnabled = $true
$computer.IsMotherboardEnabled = $true
$computer.IsControllerEnabled = $true
$computer.IsNetworkEnabled = $false
$computer.IsStorageEnabled = $false
$computer.IsBatteryEnabled = $false
$computer.IsPsuEnabled = $false
$computer.Open()

try {
    $visitor = New-Object UpdateVisitor
    $computer.Accept($visitor)

    $records = @()
    foreach ($hardware in $computer.Hardware) {
        $records += Collect-HardwareSensors -Hardware $hardware
    }

    if ($DumpSensors) {
        $records | ConvertTo-Json -Compress -Depth 4
        return
    }

    $cpuTempCandidates = $records | Where-Object {
        $_.HardwareType -eq "Cpu" -and $_.SensorType -eq "Temperature"
    }
    $cpuPowerCandidates = $records | Where-Object {
        $_.HardwareType -eq "Cpu" -and $_.SensorType -eq "Power"
    }
    $cpuBoardTempCandidates = $records | Where-Object {
        ($_.HardwareType -eq "Motherboard" -or $_.HardwareType -eq "SuperIO" -or $_.HardwareType -eq "EmbeddedController") -and $_.SensorType -eq "Temperature"
    }
    $gpuTempCandidates = $records | Where-Object {
        $_.HardwareType -like "Gpu*" -and $_.SensorType -eq "Temperature"
    }
    $gpuPowerCandidates = $records | Where-Object {
        $_.HardwareType -like "Gpu*" -and $_.SensorType -eq "Power"
    }

    [pscustomobject]@{
        cpu_temp_c = Get-PreferredSensorValue -Candidates $cpuTempCandidates
        cpu_power_w = Get-PreferredSensorValue -Candidates $cpuPowerCandidates
        cpu_board_temp_c = Get-PreferredSensorValue -Candidates $cpuBoardTempCandidates
        gpu_temp_c = Get-PreferredSensorValue -Candidates $gpuTempCandidates
        gpu_power_w = Get-PreferredSensorValue -Candidates $gpuPowerCandidates
        sensor_count = $records.Count
    } | ConvertTo-Json -Compress
}
finally {
    $computer.Close()
}
