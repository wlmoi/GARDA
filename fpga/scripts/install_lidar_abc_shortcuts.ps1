$ErrorActionPreference = 'Stop'
$fpgaDirectory = Split-Path $PSScriptRoot -Parent
$desktopDirectory = [Environment]::GetFolderPath('Desktop')
$shellObject = New-Object -ComObject WScript.Shell
foreach ($item in @(
    @{Name='IGOR - FPGA Test Dashboard'; Target='bitstreams\OPEN_MOCK_DASHBOARD.bat'},
    @{Name='IGOR - Mock AI Surge Cargo'; Target='bitstreams\MOCK_AI_SURGE_CARGO.bat'},
    @{Name='IGOR - Mock Worker dan Liquid'; Target='bitstreams\MOCK_WORKER_LIQUID.bat'},
    @{Name='IGOR - Program FPGA dan Test'; Target='bitstreams\PROGRAM_AND_TEST.bat'},
    @{Name='IGOR - LiDAR AI Live'; Target='bitstreams\OPEN_LIDAR_AI.bat'},
    @{Name='IGOR - Testing ABC'; Target='bitstreams\RUN_LAPTOP_ABC.bat'},
    @{Name='IGOR - LiDAR AI Logs'; Target='evidence\lidar_ai'}
)) {
    $targetPath = Join-Path $fpgaDirectory $item.Target
    if ($item.Target -eq 'evidence\lidar_ai') { New-Item -ItemType Directory -Force -Path $targetPath | Out-Null }
    if (!(Test-Path -LiteralPath $targetPath)) { throw "Missing target: $targetPath" }
    $shortcut = $shellObject.CreateShortcut((Join-Path $desktopDirectory ($item.Name + '.lnk')))
    $shortcut.TargetPath = $targetPath
    $shortcut.WorkingDirectory = Split-Path $fpgaDirectory -Parent
    $shortcut.WindowStyle = 1
    $shortcut.Description = 'IGOR real LiDAR and laptop verification; timestamped evidence'
    $shortcut.Save()
    Write-Host "Created: $($item.Name) -> $targetPath"
}
