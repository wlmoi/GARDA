<# Compiles quartus_de10lite (DE10-Lite, MAX 10 10M50DAF484C7G) and prints resources, timing and estimated power.
   Needs MAX 10 device support in Quartus Lite 23.1std. Output: quartus_de10lite\output_files\garda_de10lite.sof #>
param([string]$QuartusBin)
$ErrorActionPreference = 'Stop'
$proj = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'quartus_de10lite'
if (-not $QuartusBin) { $QuartusBin = (Get-ChildItem 'C:\intelFPGA_lite\*\quartus\bin64' -Directory -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1).FullName }
if (-not $QuartusBin) { throw 'Quartus bin64 not found; pass -QuartusBin' }
$dev = Join-Path (Split-Path -Parent $QuartusBin) 'common\devinfo'
if (-not (Get-ChildItem $dev -Directory -Filter 'max10*' -ErrorAction SilentlyContinue)) {
  Write-Host "MAX 10 device support not found under $dev. Install it (Quartus: Tools > Install Devices) and re-run." -ForegroundColor Red; exit 2 }
Push-Location $proj
try {
  & (Join-Path $QuartusBin 'quartus_sh.exe') --flow compile garda_de10lite
  if ($LASTEXITCODE -ne 0) { throw "compile failed (exit $LASTEXITCODE)" }
  & (Join-Path $QuartusBin 'quartus_pow.exe') garda_de10lite 2>&1 | Out-Null
  Get-Content output_files\garda_de10lite.fit.summary
  Get-Content output_files\garda_de10lite.pow.summary -ErrorAction SilentlyContinue
  Get-Content output_files\garda_de10lite.sta.summary -ErrorAction SilentlyContinue | Select-Object -First 12
  Write-Host "SOF: $proj\output_files\garda_de10lite.sof" -ForegroundColor Green
} finally { Pop-Location }
