[CmdletBinding()]
param([ValidateSet('Legacy34','User34','Hiwonder38','Restore40')][string]$Mode='Legacy34',[switch]$Elevated)
$ErrorActionPreference='Stop'
$fpgaDirectory=Split-Path $PSScriptRoot -Parent
$legacyDirectory=Join-Path $fpgaDirectory 'evidence/ch340_legacy'
$packages=@{
    Legacy34=@{inf='evidence/ch340_legacy/v34/CH341SER.INF';version='3.4.2014.8'}
    User34=@{inf='evidence/lidar_only/user_driver/extracted/CH341SER.INF';version='3.4.2014.8'}
    Hiwonder38=@{inf='evidence/ch340_legacy/hiwonder_package/CH341SER.INF';version='3.8.2023.2'}
    Restore40=@{inf='evidence/ch340_driver/package/CH341SER/CH341SER.INF';version='4.0.2026.2'}
}
$inf=Join-Path $fpgaDirectory $packages[$Mode].inf
$catalog=Join-Path (Split-Path $inf -Parent) 'CH341SER.CAT'
if ((Get-AuthenticodeSignature -LiteralPath $catalog).Status -ne 'Valid') {throw 'Driver catalog signature validation failed.'}
if ((Get-Content $inf -Raw) -notmatch 'USB\\VID_1A86&PID_7523') {throw 'Package does not match the detected CH340 hardware ID.'}
if ($Mode -eq 'Legacy34' -and (Get-FileHash (Join-Path $legacyDirectory 'Windows-CH340-Driver.zip')).Hash -ne '6956D370ECF0BCCB2D054F65CB22397D8D296FEBB9B0AE5C5BE416233E611005') {throw 'Legacy archive hash differs from the reviewed package.'}
$admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    if ($Elevated) {throw 'Administrator privileges were not granted.'}
    $arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$PSCommandPath+'" -Mode '+$Mode+' -Elevated'
    $process=Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -PassThru
    Write-Host "Driver switch process: $($process.Id), mode $Mode. Logs: $legacyDirectory"
    exit
}
function Read-DeviceState {
    Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -match 'VID_1A86&PID_7523'} | ForEach-Object {
        [pscustomobject]@{DeviceID=$_.InstanceId;Name=$_.FriendlyName;
            Version=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_DriverVersion).Data;
            Inf=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_DriverInfPath).Data;
            ProblemCode=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_ProblemCode).Data}
    }
}
$output=Join-Path $legacyDirectory ($Mode+'_'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ'))
New-Item -ItemType Directory -Path $output -Force | Out-Null
Start-Transcript -Path (Join-Path $output 'install.log') | Out-Null
$result=[ordered]@{mode=$Mode;inf=$inf;expected_version=$packages[$Mode].version;success=$false}
try {
    $before=@(Read-DeviceState)
    if ($before.Count -ne 1) {throw 'Exactly one CH340 adapter must be connected.'}
    $result.before=$before
    $backup=Join-Path $output 'previous_driver'
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    & "$env:SystemRoot\System32\pnputil.exe" /export-driver $before[0].Inf $backup
    if ($LASTEXITCODE -ne 0) {throw 'Previous driver backup failed; switch cancelled.'}
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class IgorDriverBinding {
 [DllImport("newdev.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 [return: MarshalAs(UnmanagedType.Bool)]
 public static extern bool UpdateDriverForPlugAndPlayDevicesW(IntPtr hwnd,string hardwareId,string inf,uint flags,out bool reboot);
}
'@
    $reboot=$false
    # FORCE changes driver selection for the requested version; Windows catalog/security checks still apply.
    $ok=[IgorDriverBinding]::UpdateDriverForPlugAndPlayDevicesW([IntPtr]::Zero,'USB\VID_1A86&PID_7523',$inf,1,[ref]$reboot)
    $result.api_success=$ok
    $result.reboot_required=$reboot
    if (-not $ok) {$result.win32_error=[Runtime.InteropServices.Marshal]::GetLastWin32Error();throw "Driver switch failed, Windows error $($result.win32_error)"}
    Start-Sleep -Seconds 2
    $after=@(Read-DeviceState)
    $result.after=$after
    $result.success=$after.Count -eq 1 -and [version]$after[0].Version -eq [version]$packages[$Mode].version -and $after[0].ProblemCode -eq 0
} catch {$result.error=$_.Exception.Message;Write-Host $result.error}
finally {
    $result | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $output 'result.json')
    $result | ConvertTo-Json -Depth 6 | Write-Host
    Stop-Transcript | Out-Null
}
