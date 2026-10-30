$ErrorActionPreference = 'Stop'
$fpgaDirectory = Split-Path $PSScriptRoot -Parent
$desktopDirectory = [Environment]::GetFolderPath('Desktop')
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut((Join-Path $desktopDirectory 'IGOR - LIVE Input Output Auto Check.lnk'))
$shortcut.TargetPath = Join-Path $fpgaDirectory 'bitstreams/OPEN_LIVE_IO_CHECK.bat'
$shortcut.WorkingDirectory = Split-Path $fpgaDirectory -Parent
$shortcut.Description = 'Automatically send inputs, display real FPGA outputs and verify calculations every second'
$shortcut.Save()
Write-Host "Created: $(Join-Path $desktopDirectory 'IGOR - LIVE Input Output Auto Check.lnk')"
$logDirectory = Join-Path $fpgaDirectory 'evidence/live_io'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$folderShortcut = $shellObject.CreateShortcut((Join-Path $desktopDirectory 'IGOR - LIVE Input Output Logs.lnk'))
$folderShortcut.TargetPath = $logDirectory
$folderShortcut.Description = 'Open logged inputs, real FPGA outputs, timestamps and communication results'
$folderShortcut.Save()
Write-Host "Created: $(Join-Path $desktopDirectory 'IGOR - LIVE Input Output Logs.lnk')"
