[CmdletBinding()]
param([string]$Port='', [int]$Iterations=10)
$ErrorActionPreference='Stop'
$fpgaRoot=Split-Path $PSScriptRoot -Parent
$repoRoot=Split-Path $fpgaRoot -Parent
if(!$Port){
 $portJson=& python -c 'import json; from serial.tools import list_ports; print(json.dumps([{"DeviceID":p.device,"Name":p.description} for p in list_ports.comports() if p.hwid.startswith("USB")]))'
 if($LASTEXITCODE -ne 0){throw 'Cannot enumerate USB serial ports using pyserial.'}
 $ports=@($portJson | ConvertFrom-Json)
 if($ports.Count -eq 0){Write-Host 'No USB serial COM port detected. Connect the USB end of the 3.3 V TTL adapter to this laptop.' -ForegroundColor Yellow;exit 2}
 if($ports.Count -ne 1){$ports | Select-Object DeviceID,Name | Format-Table;throw 'Multiple USB serial adapters: run test_jp7_uart.ps1 -Port COMx explicitly.'}
 $Port=$ports[0].DeviceID
}
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$logs=Join-Path $fpgaRoot ('evidence/jp7_uart/'+$stamp)
New-Item -ItemType Directory -Path $logs -Force | Out-Null
Write-Host "Testing real JP7 UART on $Port at 921600 baud, 8N1. Close MobaXterm on that port first."
[ordered]@{port=$Port;baud=921600;iterations=$Iterations;expected_q88=@(-46,60,34);utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $logs 'request.json')
& python (Join-Path $repoRoot 'src/igor_pipeline/scripts/uart_test.py') --port $Port --baud 921600 --iter $Iterations --dump-hex --jsonl (Join-Path $logs 'transactions.jsonl') 2>&1 | Tee-Object -FilePath (Join-Path $logs 'host_test.log')
$result=$LASTEXITCODE
Write-Host "Evidence: $logs"
exit $result
