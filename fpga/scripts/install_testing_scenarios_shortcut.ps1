$ErrorActionPreference = 'Stop'
$fpgaDirectory = Split-Path $PSScriptRoot -Parent
$desktopDirectory = [Environment]::GetFolderPath('Desktop')
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut((Join-Path $desktopDirectory 'IGOR - Testing Scenarios.lnk'))
$shortcut.TargetPath = Join-Path $fpgaDirectory 'bitstreams/RUN_TESTING_SCENARIOS.bat'
$shortcut.WorkingDirectory = Split-Path $fpgaDirectory -Parent
$shortcut.Description = 'Auto-detect sensor COM ports and run LiDAR, STM, software, RTL and FPGA checks with logs'
$shortcut.Save()
Write-Host "Created: $(Join-Path $desktopDirectory 'IGOR - Testing Scenarios.lnk')"
$sensorShortcut = $shellObject.CreateShortcut((Join-Path $desktopDirectory 'IGOR - Cek LiDAR dan STM32.lnk'))
$sensorShortcut.TargetPath = Join-Path $fpgaDirectory 'bitstreams/CHECK_LIDAR_STM.bat'
$sensorShortcut.WorkingDirectory = Split-Path $fpgaDirectory -Parent
$sensorShortcut.Description = 'Detect current COM ports and check RPLIDAR A1 scans and STM32 IMU without driving wheels'
$sensorShortcut.Save()
$logDirectory = Join-Path $fpgaDirectory 'evidence/testing_scenarios'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$folderShortcut = $shellObject.CreateShortcut((Join-Path $desktopDirectory 'IGOR - Testing Scenario Logs.lnk'))
$folderShortcut.TargetPath = $logDirectory
$folderShortcut.Description = 'Open scenario logs and JSON summaries'
$folderShortcut.Save()
Write-Host 'Created: IGOR - Cek LiDAR dan STM32; IGOR - Testing Scenario Logs'
