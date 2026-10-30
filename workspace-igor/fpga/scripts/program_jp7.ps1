[CmdletBinding()]
param([string]$QuartusBin='D:\Quartus-Program\quartus\bin64',[string]$Cable='1')
$ErrorActionPreference='Stop'
$fpgaRoot=Split-Path $PSScriptRoot -Parent
$bitstreams=Join-Path $fpgaRoot 'bitstreams'
$receipt=Get-Content (Join-Path $bitstreams 'igor_parallel8_jp7.json') -Raw | ConvertFrom-Json
if((Get-FileHash (Join-Path $bitstreams 'igor_parallel8_jp7.sof')).Hash.ToLowerInvariant() -ne $receipt.sha256){throw 'JP7 image hash mismatch'}
$logs=Join-Path $fpgaRoot ('evidence/jp7_uart/'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ'))
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$ErrorActionPreference='Continue'
try{
 $scan=@(& (Join-Path $QuartusBin 'jtagconfig.exe') --enum 2>&1 | ForEach-Object {$_.ToString()})
 $scanCode=$LASTEXITCODE
}finally{$ErrorActionPreference='Stop'}
$scan | Tee-Object -FilePath (Join-Path $logs 'chain.log') | Write-Host
if($scanCode -ne 0 -or ($scan -join "`n") -notmatch 'SOCVHPS' -or ($scan -join "`n") -notmatch '5CSEBA6'){throw 'Expected DE10-Nano chain not found'}
$ErrorActionPreference='Continue'
try{
 Push-Location $bitstreams
 $result=@(& (Join-Path $QuartusBin 'quartus_pgm.exe') -c $Cable -m JTAG 'igor_parallel8_jp7.cdf' 2>&1 | ForEach-Object {$_.ToString()})
 $code=$LASTEXITCODE
}finally{Pop-Location;$ErrorActionPreference='Stop'}
$result | Tee-Object -FilePath (Join-Path $logs 'programming.log') | Write-Host
if($code -ne 0 -or ($result -join "`n") -notmatch 'Configuration succeeded'){throw 'JP7 programming failed'}
$receipt | ConvertTo-Json | Set-Content (Join-Path $logs 'image_receipt.json')
Write-Host 'JP7 UART programmed: adapter TX -> pin 1, adapter RX <- pin 2, GND -> pin 12.' -ForegroundColor Green
Write-Host '921600 baud, 8N1. This binary protocol replies only to a valid observation frame.'
Write-Host 'The JTAG Terminal shortcut selects a different image; use PROGRAM_PARALLEL8_JP7.bat to restore JP7.'
Write-Host "Evidence: $logs"
