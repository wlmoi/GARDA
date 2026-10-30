[CmdletBinding()]
param([string]$Port='COM12',[ValidateRange(1,1000)][int]$Iterations=10)
$ErrorActionPreference='Stop'
$fpgaRoot=Split-Path $PSScriptRoot -Parent
$repoRoot=Split-Path $fpgaRoot -Parent
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$logs=Join-Path $fpgaRoot ('evidence/jp1_uart/'+$stamp)
New-Item -ItemType Directory -Path $logs -Force | Out-Null
Write-Host 'IGOR - JP1 UART verification' -ForegroundColor Cyan
Write-Host "Adapter $Port TX -> JP1 pin 1 (FPGA RX); RX <- JP1 pin 2 (FPGA TX); GND -> pin 12."
Write-Host '921600 baud, 8N1. Jetson TX/RX must be disconnected from these pins.'
Write-Host 'Use the original Parallel8 JP1 image. This test does not program the board.'
Write-Host 'Release KEY1; press/release KEY0 if reset is needed. Close other apps on this COM port.'
[ordered]@{port=$Port;baud=921600;iterations=$Iterations;header='JP1';adapter_TX='pin 1 / FPGA RX V12';adapter_RX='pin 2 / FPGA TX E8';adapter_GND='pin 12';expected_q88=@(-46,60,34)} | ConvertTo-Json | Set-Content (Join-Path $logs 'request.json')
$ErrorActionPreference='Continue'
try {
 & python (Join-Path $repoRoot 'src/igor_pipeline/scripts/uart_test.py') --port $Port --baud 921600 --iter $Iterations --dump-hex --jsonl (Join-Path $logs 'transactions.jsonl') 2>&1 | Tee-Object -FilePath (Join-Path $logs 'host_test.log')
 $result=$LASTEXITCODE
} finally { $ErrorActionPreference='Stop' }
if($result -eq 0){Write-Host 'PASS: all requested inference checks passed.' -ForegroundColor Green}
else{Write-Host 'FAIL: UART inference has not been verified. Read the log above.' -ForegroundColor Yellow}
Write-Host "Evidence: $logs"
exit $result
