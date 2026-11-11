<#
.SYNOPSIS
  Programs the GARDA FPGA design over JTAG regardless of what the FPGA is currently doing.

.DESCRIPTION
  JTAG configuration does not depend on the current FPGA state (blank, running another design,
  stuck, or reset). What CAN get in the way is host-side: a hung jtagd/quartus_pgm, a stale cable
  list, or a transient USB error. This script handles those: it finds Quartus, detects the cable and
  the FPGA position in the JTAG chain, checks the .sof matches the detected device, clears stale
  Quartus JTAG processes, programs, and retries with escalating recovery.

  It cannot work if the board is unpowered, the USB cable/driver is missing, or the .sof targets a
  different device family than the board. The bundled igor.sof targets Cyclone V 5CSEBA6U23I7
  (DE10-Nano). A DE10-Lite is a MAX 10 board and needs a .sof compiled for it (use -Force to skip the check).

.EXAMPLE
  .\Program-FPGA.ps1
  .\Program-FPGA.ps1 -Sof C:\path\design.sof -Cable "DE-SoC [USB-1]"
  .\Program-FPGA.ps1 -DryRun        # detect only, do not program
  .\Program-FPGA.ps1 -Explorer      # start the UART Explorer afterwards
#>
[CmdletBinding()]
param(
  [string]$Sof,
  [string]$Cable,
  [string]$QuartusBin,
  [string]$DeviceRegex = '5C[SE]',
  [int]$Retries = 3,
  [int]$ToolTimeoutSec = 60,
  [switch]$DryRun,
  [switch]$Force,
  [switch]$Explorer
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogPath = Join-Path $Here 'program_fpga.log'
if (-not $Sof) { $Sof = Join-Path $Here '..\..\dashboard\dist\downloads\igor.sof' }

function Log([string]$m, [string]$c = 'Gray') {
  $line = "{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Write-Host $line -ForegroundColor $c
  Add-Content -Path $LogPath -Value $line
}
function Die([string]$m, [int]$code = 1) { Log "FAILED: $m" 'Red'; exit $code }

function Find-QuartusBin {
  $cands = @()
  if ($QuartusBin) { $cands += $QuartusBin }
  $cmd = Get-Command quartus_pgm.exe -ErrorAction SilentlyContinue
  if ($cmd) { $cands += (Split-Path -Parent $cmd.Source) }
  if ($env:QUARTUS_ROOTDIR) { $cands += (Join-Path $env:QUARTUS_ROOTDIR 'bin64'), (Join-Path $env:QUARTUS_ROOTDIR 'bin') }
  foreach ($root in 'C:\intelFPGA_lite', 'C:\intelFPGA', 'C:\altera', 'C:\altera_lite', 'C:\documents') {
    if (Test-Path $root) {
      Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $cands += (Join-Path $_.FullName 'quartus\bin64'), (Join-Path $_.FullName 'quartus\bin')
      }
      $cands += (Join-Path $root 'quartus\bin64'), (Join-Path $root 'quartus\bin')
    }
  }
  foreach ($c in $cands) { if ($c -and (Test-Path (Join-Path $c 'quartus_pgm.exe'))) { return (Resolve-Path $c).Path } }
  return $null
}

# Runs a tool with a hard timeout (a wedged jtagd makes quartus_pgm/jtagconfig hang forever).
function Invoke-Tool([string]$Exe, [string]$ToolArgs, [int]$TimeoutSec) {
  $o = [IO.Path]::GetTempFileName(); $e = [IO.Path]::GetTempFileName()
  $sp = @{ FilePath = $Exe; NoNewWindow = $true; PassThru = $true; RedirectStandardOutput = $o; RedirectStandardError = $e }
  if ($ToolArgs) { $sp.ArgumentList = $ToolArgs }
  $p = Start-Process @sp
  $timedOut = -not $p.WaitForExit($TimeoutSec * 1000)
  if ($timedOut) { try { $p.Kill() } catch {} }
  else { $p.WaitForExit() }
  $text = ((Get-Content $o -Raw -ErrorAction SilentlyContinue) + "`n" + (Get-Content $e -Raw -ErrorAction SilentlyContinue))
  Remove-Item $o, $e -Force -ErrorAction SilentlyContinue
  [pscustomobject]@{ Exit = $(if ($timedOut) { -1 } else { $p.ExitCode }); Out = $text; TimedOut = $timedOut }
}

# Clears host-side JTAG state. Only Quartus' own JTAG processes are touched.
function Reset-JtagHost {
  foreach ($n in 'quartus_pgm', 'jtagd', 'jtagserver') {
    Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object {
      Log "  stopping stale $($_.ProcessName) (pid $($_.Id))" 'Yellow'
      try { Stop-Process -Id $_.Id -Force } catch {}
    }
  }
  Start-Sleep -Seconds 2
}

# Parses `jtagconfig`: "1) DE-SoC [USB-1]" then device lines "  02D020DD   5CSEBA6(.|ES)/...".
function Get-Chain([string]$Bin) {
  $r = Invoke-Tool (Join-Path $Bin 'jtagconfig.exe') '' 25
  if ($r.TimedOut) { return [pscustomobject]@{ Cables = @(); Raw = 'jtagconfig timed out'; TimedOut = $true } }
  $cables = @(); $cur = $null
  foreach ($ln in ($r.Out -split "`r?`n")) {
    if ($ln -match '^\s*(\d+)\)\s+(.+?)\s*$') { $cur = [pscustomobject]@{ Name = $Matches[2]; Devices = @() }; $cables += $cur }
    elseif ($cur -and $ln -match '^\s+([0-9A-Fa-f]{8})\s+(.+?)\s*$') { $cur.Devices += [pscustomobject]@{ Id = $Matches[1]; Name = $Matches[2] } }
  }
  [pscustomobject]@{ Cables = $cables; Raw = $r.Out; TimedOut = $false }
}

# ---------------------------------------------------------------- start
"" | Set-Content $LogPath
Log "GARDA FPGA programmer  ($(Get-Date -Format s))" 'Cyan'

$bin = Find-QuartusBin
if (-not $bin) { Die 'Quartus Programmer not found. Install Quartus or pass -QuartusBin <dir containing quartus_pgm.exe>.' 2 }
Log "Quartus tools: $bin"

if (-not (Test-Path $Sof)) { Die "SOF not found: $Sof" 3 }
$Sof = (Resolve-Path $Sof).Path
if ((Get-Item $Sof).Length -lt 1024) { Die "SOF looks empty/corrupt: $Sof" 3 }
$bytes = [IO.File]::ReadAllBytes($Sof)
$ascii = [Text.Encoding]::ASCII.GetString($bytes[0..([Math]::Min($bytes.Length, 1048576) - 1)])
$sofDev = if ($ascii -match '(5C[A-Z0-9]{9,12}|10M[0-9A-Z]{6,12}|EP[0-9A-Z]{6,14})') { $Matches[1] } else { $null }
Log ("SOF: {0}  ({1:N0} bytes, target device string: {2})" -f $Sof, $bytes.Length, $(if ($sofDev) { $sofDev } else { 'not found' }))
if ($Sof -match 'igor\.sof$') { Log '  note: igor.sof is the historical build (igor_uart_top). Rebuild from source if the RTL changed.' 'Yellow' }

$ok = $false
for ($attempt = 1; $attempt -le $Retries -and -not $ok; $attempt++) {
  Log "--- attempt $attempt of $Retries ---" 'Cyan'
  if ($attempt -gt 1) { Reset-JtagHost }

  $chain = Get-Chain $bin
  if ($chain.TimedOut) { Log '  jtagconfig hung: JTAG server wedged, will reset it' 'Yellow'; Reset-JtagHost; continue }
  if ($chain.Cables.Count -eq 0) {
    Log '  no JTAG cable detected (board off? USB cable? USB-Blaster driver installed?)' 'Yellow'
    if ($attempt -eq $Retries) { Log $chain.Raw 'DarkGray' }
    Start-Sleep -Seconds 2; continue
  }

  $cab = if ($Cable) { $chain.Cables | Where-Object { $_.Name -eq $Cable } | Select-Object -First 1 } else { $chain.Cables[0] }
  if (-not $cab) { Die "cable '$Cable' not found. Present: $(($chain.Cables | ForEach-Object Name) -join '; ')" 4 }
  Log "  cable: $($cab.Name)"
  $i = 0; foreach ($d in $cab.Devices) { $i++; Log ("    [{0}] {1}  {2}" -f $i, $d.Id, $d.Name) }

  $idx = 0; $i = 0
  foreach ($d in $cab.Devices) { $i++; if (-not $idx -and $d.Name -match $DeviceRegex) { $idx = $i } }
  if (-not $idx) {
    if ($cab.Devices.Count -eq 1) { $idx = 1 }
    elseif ($Force) { $idx = 1 }
    else {
      Die "no device matching /$DeviceRegex/ in the chain; this SOF ($sofDev) is for a different board. For a DE10-Lite (MAX 10) pass a MAX 10 .sof with -DeviceRegex '10M' (or -Force)." 5
    }
  }
  $devName = $cab.Devices[$idx - 1].Name
  if ($sofDev -and -not $Force) {
    $fam = ($sofDev -replace '^(5C[A-Z]{2}|10M\d+|EP\d[A-Z]+).*', '$1')
    if ($devName -notmatch [regex]::Escape(($fam.Substring(0, [Math]::Min(3, $fam.Length))))) {
      Die "SOF targets $sofDev but the chain device is '$devName'. Use a matching .sof (or -Force)." 5
    }
  }

  $arg = "-m jtag -c `"$($cab.Name)`" -o `"p;$Sof@$idx`""
  if ($DryRun) { Log "  DRY RUN: would run  quartus_pgm $arg" 'Green'; $ok = $true; break }
  Log "  programming device [$idx] $devName ..."
  $r = Invoke-Tool (Join-Path $bin 'quartus_pgm.exe') $arg $ToolTimeoutSec
  Add-Content $LogPath $r.Out
  if ($r.Exit -eq 0 -and $r.Out -match 'successful') { $ok = $true; break }
  Log ("  quartus_pgm failed (exit {0}{1}). Last lines:" -f $r.Exit, $(if ($r.TimedOut) { ', timed out' } else { '' })) 'Yellow'
  ($r.Out -split "`r?`n" | Where-Object { $_ -match 'Error|Warning|failed' } | Select-Object -Last 4) | ForEach-Object { Log "    $_" 'DarkGray' }

  if ($attempt -eq $Retries) {   # last resort: no explicit cable/position, let Quartus auto-select
    Reset-JtagHost
    Log '  last resort: auto-select cable and device' 'Yellow'
    $r = Invoke-Tool (Join-Path $bin 'quartus_pgm.exe') "-m jtag -o `"p;$Sof`"" $ToolTimeoutSec
    Add-Content $LogPath $r.Out
    if ($r.Exit -eq 0 -and $r.Out -match 'successful') { $ok = $true }
  }
}

if (-not $ok) { Die "could not program the FPGA after $Retries attempts. See $LogPath. Check power, USB cable, driver, and that the .sof matches the board." 10 }
if ($DryRun) { Log 'Dry run OK: cable and device detected, nothing was programmed.' 'Green'; exit 0 }
Log 'FPGA programmed successfully (JTAG). Press KEY0 on the board to reset the design.' 'Green'
if ($Explorer) { Start-Process (Join-Path $Here 'uart_explorer\START_UART_EXPLORER.bat') }
exit 0
