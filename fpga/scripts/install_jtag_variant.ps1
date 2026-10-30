$ErrorActionPreference = 'Stop'
$fpgaRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $fpgaRoot 'experiments/parallel8_jtag'
$output = Join-Path $project 'output_files'
$flow = Get-Content (Join-Path $output 'igor_jtag.flow.rpt') -Raw
if ($flow -notmatch 'Flow Status\s*;\s*Successful') { throw 'Full Quartus compilation must succeed before installing the image.' }
$timing = Get-Content (Join-Path $output 'igor_jtag.sta.summary') -Raw
$slacks = [regex]::Matches($timing,'Slack\s*:\s*(-?[0-9.]+)') | ForEach-Object { [double]$_.Groups[1].Value }
if (!$slacks -or ($slacks | Where-Object { $_ -lt 0 })) { throw 'Timing summary missing or negative slack detected.' }
$simulation = Get-Content (Join-Path $project 'console_simulation.log') -Raw
$bridge = Get-Content (Join-Path $project 'bytes_simulation.log') -Raw
if ($simulation -notmatch 'PASS: real Parallel8 serial inference, CRC rejection, pasted hex frame, E-stop' -or $bridge -notmatch 'PASS: 200 ordered bytes') { throw 'Required simulation evidence missing.' }
$originalCore = Join-Path $fpgaRoot 'experiments/parallel8/igor_src_policy_core.v'
if ((Get-FileHash $originalCore).Hash -ne (Get-FileHash (Join-Path $project 'igor_src_policy_core.v')).Hash) { throw 'Parallel8 core differs from accepted source.' }
$destination = Join-Path $fpgaRoot 'bitstreams/igor_parallel8_jtag.sof'
Copy-Item -LiteralPath (Join-Path $output 'igor_jtag.sof') -Destination $destination
$receipt = [ordered]@{
    sha256 = (Get-FileHash $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    installed_utc = [DateTime]::UtcNow.ToString('o')
    project = 'fpga/experiments/parallel8_jtag/igor_jtag.qpf'
    minimum_reported_slack_ns = ($slacks | Measure-Object -Minimum).Minimum
    core_sha256 = (Get-FileHash $originalCore).Hash.ToLowerInvariant()
    console_sha256 = (Get-FileHash (Join-Path $project 'igor_jtag_console.v')).Hash.ToLowerInvariant()
    status_format_sha256 = (Get-FileHash (Join-Path $project 'status_chars.vh')).Hash.ToLowerInvariant()
    simulations = @('200-byte Avalon backpressure/order test','Parallel8 inference','CRC rejection','pasted hex frame','E-stop')
}
$receipt | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $fpgaRoot 'bitstreams/igor_parallel8_jtag.json')
Write-Host "Installed validated JTAG variant: $destination"
