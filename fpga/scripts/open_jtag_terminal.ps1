[CmdletBinding()]
param(
    [string]$QuartusBin = 'D:\Quartus-Program\quartus\bin64',
    [string]$Cable = '1',
    [switch]$ProbeOnly,
    [switch]$ProgramJtagImage
)
$ErrorActionPreference = 'Stop'
$fpgaRoot = Split-Path $PSScriptRoot -Parent
$terminal = Join-Path $QuartusBin 'nios2-terminal.exe'
$scanner = Join-Path $QuartusBin 'jtagconfig.exe'
foreach ($file in @($terminal, $scanner)) {
    if (!(Test-Path -LiteralPath $file)) { throw "Quartus tool missing: $file" }
}
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$logs = Join-Path $fpgaRoot "evidence/jtag_terminal/$stamp"
New-Item -ItemType Directory -Path $logs -Force | Out-Null
Write-Host 'IGOR - USB-Blaster JTAG Terminal' -ForegroundColor Cyan
Write-Host 'Real Quartus JTAG UART terminal for the Parallel8 JTAG console variant.'
Write-Host "Cable selection: $Cable"
Write-Host "Log directory: $logs"
$ErrorActionPreference = 'Continue'
try {
    $scan = @(& $scanner --enum 2>&1 | ForEach-Object { $_.ToString() })
    $scanCode = $LASTEXITCODE
} finally { $ErrorActionPreference = 'Stop' }
$scan | Tee-Object -FilePath (Join-Path $logs 'chain.log') | Write-Host
if ($scanCode -ne 0 -or ($scan -join "`n") -match 'No JTAG hardware|Server error|Hardware not attached') {
    Write-Host 'JTAG connection unavailable. Check board power and USB-Blaster cable.' -ForegroundColor Yellow
    exit 1
}
if ($ProgramJtagImage) {
    $image = Join-Path $fpgaRoot 'bitstreams/igor_parallel8_jtag.sof'
    $receipt = Join-Path $fpgaRoot 'bitstreams/igor_parallel8_jtag.json'
    if (!(Test-Path $image) -or !(Test-Path $receipt)) { throw 'Validated JTAG image is not installed yet.' }
    $expected = (Get-Content $receipt -Raw | ConvertFrom-Json).sha256
    if ((Get-FileHash $image -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'JTAG SOF hash mismatch.' }
    Write-Host 'Programming the Parallel8 JTAG console image...' -ForegroundColor Cyan
    $ErrorActionPreference = 'Continue'
    try {
        Push-Location (Join-Path $fpgaRoot 'bitstreams')
        $program = @(& (Join-Path $QuartusBin 'quartus_pgm.exe') -c $Cable -m JTAG 'igor_parallel8_jtag.cdf' 2>&1 | ForEach-Object { $_.ToString() })
        $programCode = $LASTEXITCODE
    } finally { Pop-Location; $ErrorActionPreference = 'Stop' }
    $program | Tee-Object -FilePath (Join-Path $logs 'programming.log') | Write-Host
    if ($programCode -ne 0 -or ($program -join "`n") -notmatch 'Configuration succeeded') { throw 'JTAG programming did not succeed.' }
}
if (!$ProbeOnly) {
    Write-Host 'Opening console: r = known-vector inference; ! = CRC rejection test.' -ForegroundColor Green
    Write-Host 'Automatic demo runs once after programming. KEY1 must be released; KEY0 resets.'
    Write-Host 'Ctrl+C closes the terminal. No COM port or MobaXterm is required.'
    & $terminal -c $Cable
    exit $LASTEXITCODE
}
Write-Host 'Checking the JTAG UART instance (3-second bounded probe)...'
$ErrorActionPreference = 'Continue'
try {
    $probe = @(& $terminal -c $Cable --quit-after=3 2>&1 | ForEach-Object { $_.ToString() })
    $probeCode = $LASTEXITCODE
} finally { $ErrorActionPreference = 'Stop' }
$probe | Tee-Object -FilePath (Join-Path $logs 'terminal_probe.log') | Write-Host
if ($probeCode -ne 0 -or ($probe -join "`n") -match 'no JTAG UARTs|Unable to|cannot|could not') {
    Write-Host ''
    Write-Host 'NO JTAG UART IS AVAILABLE IN THE CURRENT FPGA IMAGE.' -ForegroundColor Yellow
    Write-Host 'The accepted Parallel8 image exposes physical UART on JP1 pins 1/2, at 921600 baud.'
    Write-Host 'USB-Blaster programming success does not create a COM port or JTAG UART.'
    Write-Host 'For this terminal to show FPGA data over USB-Blaster, a separately built image'
    Write-Host 'must instantiate and connect a JTAG UART interface to the core/transport.'
    Write-Host 'The existing working Parallel8 SOF has not been changed.'
    exit 2
}
exit 0
