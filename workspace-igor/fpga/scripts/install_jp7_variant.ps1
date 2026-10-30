$ErrorActionPreference = 'Stop'
$fpgaRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $fpgaRoot 'experiments/parallel8_jp7'
$reports = Join-Path $project 'output_files'
$compile = Get-Content (Join-Path $project 'compile.log') -Raw
if ($compile -notmatch 'Quartus Prime Full Compilation was successful. 0 errors') { throw 'JP7 full compile must complete with zero errors.' }
$timing = Get-Content (Join-Path $reports 'igor_parallel8_jp7.sta.summary') -Raw
$slacks = [regex]::Matches($timing,'Slack\s*:\s*(-?[0-9.]+)') | ForEach-Object { [double]$_.Groups[1].Value }
if (!$slacks -or ($slacks | Where-Object { $_ -lt 0 })) { throw 'Timing summary missing or negative slack detected.' }
$pins = Get-Content (Join-Path $reports 'igor_parallel8_jp7.pin') -Raw
if ($pins -notmatch 'UART_RX\s*:\s*Y15\s*:\s*input' -or $pins -notmatch 'UART_TX\s*:\s*AC24\s*:\s*output') { throw 'Fitted UART pin mapping does not match JP7 pins 1/2.' }
$manifest = Get-Content (Join-Path $project 'source_manifest.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.unchanged_files.PSObject.Properties) {
    $actual = (Get-FileHash (Join-Path $project $entry.Name)).Hash.ToLowerInvariant()
    $original = (Get-FileHash (Join-Path $fpgaRoot ('experiments/parallel8/'+$entry.Name))).Hash.ToLowerInvariant()
    if ($actual -ne $entry.Value -or $actual -ne $original) { throw "Original source/bank identity mismatch: $($entry.Name)" }
}
$image = Join-Path $fpgaRoot 'bitstreams/igor_parallel8_jp7.sof'
Copy-Item (Join-Path $reports 'igor_parallel8_jp7.sof') $image
[ordered]@{
    sha256 = (Get-FileHash $image).Hash.ToLowerInvariant()
    installed_utc = [DateTime]::UtcNow.ToString('o')
    project = 'fpga/experiments/parallel8_jp7/igor_parallel8_jp7.qpf'
    minimum_reported_slack_ns = ($slacks | Measure-Object -Minimum).Minimum
    rx = 'JP7 pin 1 / Y15'; tx = 'JP7 pin 2 / AC24'; ground = 'JP7 pin 12'; baud = 921600
    source_identity = 'Copied core, top, SDC and eight banks match original Parallel8 by SHA256'
} | ConvertTo-Json | Set-Content (Join-Path $fpgaRoot 'bitstreams/igor_parallel8_jp7.json')
Write-Host "Installed validated JP7 image: $image"
