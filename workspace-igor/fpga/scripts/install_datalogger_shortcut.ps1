$ErrorActionPreference = 'Stop'
$fpgaDirectory = Split-Path $PSScriptRoot -Parent
$desktopDirectory = [Environment]::GetFolderPath('Desktop')
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut((Join-Path $desktopDirectory 'IGOR - FPGA Datalogger.lnk'))
$shortcut.TargetPath = Join-Path $fpgaDirectory 'bitstreams/OPEN_FPGA_DATALOGGER.bat'
$shortcut.WorkingDirectory = Split-Path $fpgaDirectory -Parent
$shortcut.Description = 'Read FPGA results via USB-Blaster JTAG with timestamps and a manual location label'
$shortcut.Save()
Write-Host "Created: $(Join-Path $desktopDirectory 'IGOR - FPGA Datalogger.lnk')"
$logDirectory = Join-Path $fpgaDirectory 'evidence/datalogger'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$folderShortcut = $shellObject.CreateShortcut((Join-Path $desktopDirectory 'IGOR - Folder Data Logging.lnk'))
$folderShortcut.TargetPath = $logDirectory
$folderShortcut.Description = 'Open timestamped FPGA CSV and JSONL datalogger sessions'
$folderShortcut.Save()
Write-Host "Created: $(Join-Path $desktopDirectory 'IGOR - Folder Data Logging.lnk')"
