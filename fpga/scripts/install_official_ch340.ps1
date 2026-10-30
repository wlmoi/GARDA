[CmdletBinding()]
param([switch]$Elevated,[switch]$VerifyOnly,[switch]$RestartOnly)
$ErrorActionPreference = 'Stop'
$fpgaDirectory = Split-Path $PSScriptRoot -Parent
$driverDirectory = Join-Path $fpgaDirectory 'evidence/ch340_driver'
$inf = Join-Path $driverDirectory 'package/CH341SER/CH341SER.INF'
$catalog = Join-Path $driverDirectory 'package/CH341SER/CH341SER.CAT'
function Get-CH340State {
    @(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -match 'VID_1A86&PID_7523'}) | ForEach-Object {
        [pscustomobject]@{
            DeviceName=$_.FriendlyName; DeviceID=$_.InstanceId
            DriverVersion=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_DriverVersion).Data
            InfName=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_DriverInfPath).Data
            ProblemCode=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_ProblemCode).Data
        }
    }
}
if ($VerifyOnly) {
    $active = @(Get-CH340State)
    $verification = [ordered]@{timestamp_utc=[DateTime]::UtcNow.ToString('o'); active=$active; success=($active.Count -eq 1 -and [version]$active[0].DriverVersion -eq [version]'4.0.2026.2' -and $active[0].ProblemCode -eq 0); method='Live PnP device properties; avoids stale Win32_PnPSignedDriver cache'}
    $verification | ConvertTo-Json -Depth 5 | Tee-Object -FilePath (Join-Path $driverDirectory 'active_verification.json') | Write-Host
    exit
}
$admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    if ($Elevated) { throw 'Windows administrator elevation was not granted.' }
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Elevated'
    if ($RestartOnly) { $arguments += ' -RestartOnly' }
    $child = Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -PassThru
    Write-Host "Administrator install process: $($child.Id). Logs: $driverDirectory"
    exit
}
if ($RestartOnly) {
    $active = @(Get-CH340State)
    if ($active.Count -ne 1) { throw 'Expected exactly one CH340 device before restart.' }
    & "$env:SystemRoot\System32\pnputil.exe" /restart-device $active[0].DeviceID 2>&1 | Tee-Object -FilePath (Join-Path $driverDirectory 'device_restart.log') | Write-Host
    exit $LASTEXITCODE
}
if ((Get-AuthenticodeSignature -LiteralPath $catalog).Status -ne 'Valid') { throw 'Official driver catalog signature is not valid.' }
if ((Get-Content $inf -Raw) -notmatch 'USB\\VID_1A86&PID_7523') { throw 'Driver does not support the detected CH340 hardware ID.' }
$timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$output = Join-Path $driverDirectory ('install_'+$timestamp)
New-Item -ItemType Directory -Path $output -Force | Out-Null
Start-Transcript -Path (Join-Path $output 'install.log') | Out-Null
$result = [ordered]@{source='https://www.wch-ic.com/download/file?id=5'; package_sha256=(Get-FileHash (Join-Path $driverDirectory 'CH341SER.ZIP')).Hash; expected_version='4.0.2026.02'; success=$false}
try {
    $previous = @(Get-CH340State)
    if ($previous.Count -ne 1) { throw 'Expected exactly one connected CH340 device.' }
    $result.before = @($previous | Select-Object DeviceName,DeviceID,DriverVersion,InfName,IsSigned)
    $backup = Join-Path $output 'previous_driver'
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    & "$env:SystemRoot\System32\pnputil.exe" /export-driver $previous[0].InfName $backup
    if ($LASTEXITCODE -ne 0) { throw 'Could not export previous driver; update not attempted.' }
    & "$env:SystemRoot\System32\pnputil.exe" /add-driver $inf /install
    $result.pnputil_exit_code = $LASTEXITCODE
    if ($LASTEXITCODE -notin @(0,3010)) { throw "Driver installation failed: $LASTEXITCODE" }
    Start-Sleep -Seconds 2
    $after = @(Get-CH340State)
    $result.after = @($after | Select-Object DeviceName,DeviceID,DriverVersion,InfName,IsSigned)
    $result.success = $after.Count -eq 1 -and [version]$after[0].DriverVersion -eq [version]'4.0.2026.2' -and $after[0].ProblemCode -eq 0
    $result.reboot_required = $result.pnputil_exit_code -eq 3010
    if (-not $result.success) { $result.note = 'Package installed/staged; device has not yet reported expected version. Reconnect device and recheck before claiming updated.' }
} catch {
    $result.error = $_.Exception.Message
    Write-Host $result.error
} finally {
    $result | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $output 'result.json')
    $result | ConvertTo-Json -Depth 6 | Write-Host
    Stop-Transcript | Out-Null
}
