[CmdletBinding()]
param([ValidateSet('JP7','JP1_3_4','JP1_1_2')][string]$Header='JP1_3_4')
$ErrorActionPreference='Stop'
$fpgaRoot=Split-Path $PSScriptRoot -Parent
$folder=@{JP7='jp7_monitor';JP1_3_4='jp1_3_4_monitor';JP1_1_2='jp1_1_2_monitor'}[$Header]
$project=Join-Path $fpgaRoot ('experiments/'+$folder)
$reports=Join-Path $project 'output_files'
$compile=Get-Content (Join-Path $project 'compile.log') -Raw
if($compile -notmatch 'Quartus Prime Full Compilation was successful. 0 errors'){throw 'Monitor full compile must finish with zero errors.'}
$timing=Get-Content (Join-Path $reports 'igor_jp7_monitor.sta.summary') -Raw
$slacks=[regex]::Matches($timing,'Slack\s*:\s*(-?[0-9.]+)') | ForEach-Object {[double]$_.Groups[1].Value}
if(!$slacks -or ($slacks | Where-Object {$_ -lt 0})){throw 'Timing missing or negative slack.'}
$simulation=Get-Content (Join-Path $project 'simulation.log') -Raw
if($simulation -notmatch 'PASS: physical UART decoding/counters'){throw 'Monitor simulation has not passed.'}
$pins=Get-Content (Join-Path $reports 'igor_jp7_monitor.pin') -Raw
$rx=@{JP7='Y15';JP1_3_4='W12';JP1_1_2='V12'}[$Header]
$tx=@{JP7='AC24';JP1_3_4='D11';JP1_1_2='E8'}[$Header]
if($pins -notmatch ('UART_RX\s*:\s*'+$rx+'\s*:\s*input') -or $pins -notmatch ('UART_TX\s*:\s*'+$tx+'\s*:\s*output')){throw 'Fitted UART pads do not match requested header.'}
if((Get-FileHash (Join-Path $project 'igor_src_policy_core.v')).Hash -ne (Get-FileHash (Join-Path $fpgaRoot 'experiments/parallel8/igor_src_policy_core.v')).Hash){throw 'Neural core source mismatch'}
$name='igor_parallel8_'+$folder
$bitstreams=Join-Path $fpgaRoot 'bitstreams'
$image=Join-Path $bitstreams ($name+'.sof')
Copy-Item (Join-Path $reports 'igor_jp7_monitor.sof') $image
$logs=Join-Path $fpgaRoot ('evidence/'+$folder+'/'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ'))
New-Item -ItemType Directory -Path $logs -Force | Out-Null
[ordered]@{header=$Header;rx_fpga_pad=$rx;tx_fpga_pad=$tx;sha256=(Get-FileHash $image).Hash.ToLowerInvariant();minimum_reported_slack_ns=($slacks|Measure-Object -Minimum).Minimum;core_sha256=(Get-FileHash (Join-Path $project 'igor_src_policy_core.v')).Hash.ToLowerInvariant()} | ConvertTo-Json | Set-Content (Join-Path $logs 'image_receipt.json')
$ErrorActionPreference='Continue'
try{
 Push-Location $bitstreams
 $result=@(& D:\Quartus-Program\quartus\bin64\quartus_pgm.exe -c 1 -m JTAG ($name+'.cdf') 2>&1 | ForEach-Object {$_.ToString()})
 $code=$LASTEXITCODE
}finally{Pop-Location;$ErrorActionPreference='Stop'}
$result|Tee-Object -FilePath (Join-Path $logs 'programming.log')|Write-Host
if($code -ne 0 -or ($result -join "`n") -notmatch 'Configuration succeeded'){throw 'Monitor programming failed'}
Write-Host "Programmed $Header monitor; evidence: $logs"
