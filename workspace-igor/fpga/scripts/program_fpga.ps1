# Inspect the DE10-Nano chain by default. Hardware configuration requires -Program.
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [ValidateSet('source_policy', 'source_policy_parallel8', 'planner')][string]$Project = 'source_policy',
    [string]$QuartusBin = 'D:\Quartus-Program\quartus\bin64',
    [string]$Cable,
    [ValidateRange(1, 64)][int]$DeviceIndex,
    [switch]$Program,
    [switch]$AutoSelect,
    [string]$Manifest,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
# Keep read-only inspection and evidence usable under -WhatIf; apply it only
# to the actual hardware configuration operation below.
$requestedWhatIf = [bool]$WhatIfPreference
$WhatIfPreference = $false
$fpgaRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$relativeSof = if ($Project -eq 'source_policy_parallel8') {
    'experiments/parallel8/output_files/igor_src_policy.sof'
} elseif ($Project -eq 'source_policy') {
    'fpga_de10_nano/src_policy/output_files/igor_src_policy.sof'
} else { 'fpga_de10_nano/quartus/output_files/igor.sof' }
$relativeQsf = if ($Project -eq 'source_policy_parallel8') {
    'experiments/parallel8/igor_src_policy.qsf'
} elseif ($Project -eq 'source_policy') {
    'fpga_de10_nano/src_policy/igor_src_policy.qsf'
} else { 'fpga_de10_nano/quartus/igor.qsf' }
$sof = Join-Path $fpgaRoot $relativeSof
$programSof = if ($Project -eq 'source_policy_parallel8') {
    Join-Path $fpgaRoot 'bitstreams/igor_src_policy_parallel8.sof'
} else { $sof }
$qsf = Join-Path $fpgaRoot $relativeQsf
if (!$Manifest) { $Manifest = Join-Path $fpgaRoot 'evidence/current_release/manifest.json' }
$programmer = Join-Path $QuartusBin 'quartus_pgm.exe'
$jtagconfig = Join-Path $QuartusBin 'jtagconfig.exe'
foreach ($requiredFile in @($programmer, $jtagconfig, $sof, $programSof, $qsf)) {
    if (!(Test-Path -LiteralPath $requiredFile -PathType Leaf)) { throw "Missing file: $requiredFile" }
}
if ((Get-Content -LiteralPath $qsf -Raw) -notmatch '(?m)^set_global_assignment\s+-name DEVICE\s+"?5CSEBA6U23I7"?\s*$') {
    throw 'Selected QSF is not configured for DE10-Nano 5CSEBA6U23I7.'
}
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$evidenceDir = Join-Path $fpgaRoot "evidence/current_programming/$stamp"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$report = [ordered]@{
    schema = 1; utc = [DateTime]::UtcNow.ToString('o'); project = $Project
    sof = $relativeSof; sof_sha256 = (Get-FileHash -LiteralPath $sof -Algorithm SHA256).Hash.ToLowerInvariant()
    expected_device = '5CSEBA6U23I7'; requested_cable = $Cable
    quartus_bin = [IO.Path]::GetFullPath($QuartusBin)
    requested_device_index = $DeviceIndex; manifest = $Manifest
    manifest_verified = $false; full_release_verified = $false; ready_to_program = $false
    mode = 'inspection'; hardware_available = $false
    hardware_programmed = $false; uart_function_verified = $false
    auto_select = [bool]$AutoSelect; programming_image = $programSof
}
function Run-QuartusTool([string]$Executable, [string[]]$ToolArguments, [string]$LogName, [bool]$AllowNoHardware = $false) {
    # Quartus writes harmless TBB diagnostics on stderr even on success.
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $lines = @(& $Executable @ToolArguments 2>&1 | ForEach-Object { $_.ToString() })
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $oldPreference }
    $lines | Set-Content -LiteralPath (Join-Path $evidenceDir $LogName) -Encoding UTF8
    if (($lines -join "`n") -match 'Unable to lock chain|Hardware not attached|Error \(\d+\)|was unsuccessful') {
        throw "$LogName reports a hardware/tool error. See $evidenceDir"
    }
    if ($code -ne 0 -and !($AllowNoHardware -and $code -eq 4 -and ($lines -join "`n") -match 'No JTAG hardware available')) {
        throw "$LogName failed with exit $code. See $evidenceDir"
    }
    return ,$lines
}
try {
    if (Test-Path -LiteralPath $Manifest -PathType Leaf) {
        $release = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
        $entry = $release.files.PSObject.Properties[$relativeSof]
        $releaseProject = $release.projects.PSObject.Properties[$Project]
        if (!$entry -or !$releaseProject -or $releaseProject.Value.sof -ne $relativeSof) {
            throw "Manifest lacks the exact selected project/SOF: $relativeSof"
        }
        if ($entry.Value.sha256 -ne $report.sof_sha256 -or $entry.Value.bytes -ne (Get-Item -LiteralPath $sof).Length) {
            throw 'SOF differs from the current release manifest. Rebuild and freeze the release before programming.'
        }
        $report.manifest_verified = $true
        if ((Get-FileHash -LiteralPath $programSof -Algorithm SHA256).Hash.ToLowerInvariant() -ne $report.sof_sha256) {
            throw 'Programming handoff SOF differs from the accepted compiled image.'
        }
    } elseif ($Program) { throw 'Programming requires evidence/current_release/manifest.json; run the documented release freeze first.' }
    $inventory = Run-QuartusTool $programmer @('--list') 'jtag_inventory.log'
    $chainText = Run-QuartusTool $jtagconfig @('--enum') 'jtag_chain.log' $true
    # jtagconfig enumerates cable headers "1) NAME" followed by IDCODE/device rows.
    $chains = @()
    $current = $null
    foreach ($line in $chainText) {
        if ($line -match '^\s*(\d+)\)\s+(.+?)\s*$') {
            $current = [pscustomobject]@{ index = [int]$Matches[1]; name = $Matches[2]; devices = @() }
            $chains += $current
        } elseif ($current -and $line -match '^\s+([0-9A-Fa-f]{8})\s+(.+?)\s*$') {
            $current.devices += [pscustomobject]@{ index = $current.devices.Count + 1; idcode = $Matches[1]; name = $Matches[2] }
        }
    }
    $report.chains = $chains
    $report.hardware_available = $chains.Count -gt 0
    $report.fpga_detected = @($chains | ForEach-Object { $_.devices } | Where-Object {
        $_.name -match '(^|[/\s])5CSEBA6(?:\(\.\|ES\))?([/\s]|$)'
    }).Count -gt 0
    if ($AutoSelect) {
        $candidates = @()
        foreach ($item in $chains) {
            if ($Cable -and $item.name -ne $Cable -and "$($item.index)" -ne $Cable) { continue }
            foreach ($part in $item.devices) {
                if ($part.name -match '(^|[/\s])5CSEBA6(?:\(\.\|ES\))?([/\s]|$)' -and (!$DeviceIndex -or $part.index -eq $DeviceIndex)) {
                    $candidates += [pscustomobject]@{ cable = $item.index; device = $part.index }
                }
            }
        }
        if ($candidates.Count -ne 1) {
            throw "AutoSelect requires exactly one detected 5CSEBA6 FPGA; found $($candidates.Count). Check power/USB/JTAG or select -Cable and -DeviceIndex. No programming operation was issued."
        }
        $Cable = "$($candidates[0].cable)"
        $DeviceIndex = $candidates[0].device
    }
    if (!$report.hardware_available) {
        if ($Program) { throw 'No JTAG cable detected; no programming operation was issued.' }
        Write-Host 'No JTAG hardware available. Inspection completed; no board was programmed.'
    } elseif (!$Cable) {
        if ($Program) { throw 'Specify -Cable using the cable number or complete name in the inspection report.' }
        Write-Host 'Choose -Cable and -DeviceIndex from jtag_chain.log; no programming operation was issued.'
    } else {
        $selected = @($chains | Where-Object { $_.name -eq $Cable -or "$($_.index)" -eq $Cable })
        if ($selected.Count -ne 1) { throw 'Cable must select exactly one detected chain.' }
        $chain = $selected[0]
        $report.selected_chain = $chain
        # Quartus --auto is another read-only identity check on the exact selected cable.
        $autoText = Run-QuartusTool $programmer @('-c', "$($chain.index)", '-a') 'quartus_auto_detect.log'
        if (($autoText -join "`n") -notmatch '5CSEBA6') {
            throw 'Quartus Auto Detect did not confirm 5CSEBA6; no programming operation was issued.'
        }
        if (!$DeviceIndex) {
            if ($Program) { throw 'Specify the one-based -DeviceIndex after reviewing Auto Detect; FPGA is not assumed to be @1.' }
        } else {
            $target = @($chain.devices | Where-Object { $_.index -eq $DeviceIndex })
            if ($target.Count -ne 1 -or $target[0].name -notmatch '(^|[/\s])5CSEBA6(?:\(\.\|ES\))?([/\s]|$)') {
                throw "Selected JTAG position $DeviceIndex is not an identified 5CSEBA6 FPGA. Review jtag_chain.log."
            }
            $operations = @()
            foreach ($device in $chain.devices) {
                if ($device.index -eq $DeviceIndex) { $operations += @('-o', "P;$programSof@$DeviceIndex") }
                else {
                    # Only a uniquely named bypass device is safe to pass to Quartus.
                    if ($device.name -notmatch '^[A-Za-z][A-Za-z0-9_]*$') {
                        throw "Ambiguous bypass part '$($device.name)'; use the GUI Auto Detect/CDF workflow."
                    }
                    $operations += @('-o', "S;$($device.name)@$($device.index)")
                }
            }
            $programArguments = @('-c', "$($chain.index)", '-m', 'JTAG') + $operations
            $report.program_arguments = $programArguments
            # A native Quartus programming project built from the observed chain,
            # including HPS bypass at its actual position (never assumed @1/@2).
            $cdf = @('JedecChain;', 'FileRevision(JESD32A);', 'DefaultMfr(6E);')
            foreach ($device in $chain.devices) {
                if ($device.index -eq $DeviceIndex) {
                    $cdfPath = ([IO.Path]::GetDirectoryName($programSof) -replace '\\', '/') + '/'
                    $cdf += 'P ActionCode(Cfg)'
                    $cdf += ('  Device PartName(5CSEBA6) Path("{0}") File("{1}") MfrSpec(OpMask(1));' -f $cdfPath, [IO.Path]::GetFileName($programSof))
                } else {
                    $cdf += 'P ActionCode(Ign)'
                    $cdf += ('  Device PartName({0}) MfrSpec(OpMask(0));' -f $device.name)
                }
            }
            $cdf += @('ChainEnd;', 'AlteraBegin;', 'ChainType(JTAG);', 'AlteraEnd;')
            $cdfFile = Join-Path $evidenceDir 'detected_board.cdf'
            $cdf | Set-Content -LiteralPath $cdfFile -Encoding ASCII
            $report.detected_chain_cdf = $cdfFile
            $report.ready_to_program = $report.manifest_verified
            $performProgram = $false
            if ($Program) {
                $freezeScript = Join-Path $fpgaRoot 'scripts/freeze_release.py'
                if (!(Test-Path -LiteralPath $freezeScript -PathType Leaf)) { throw 'Missing freeze_release.py; cannot validate source/build provenance.' }
                if (!(Get-Command $Python -ErrorAction SilentlyContinue)) { throw "Python '$Python' is unavailable. Select -Python or run the release check in a configured shell." }
                $null = Run-QuartusTool $Python @($freezeScript, '--check') 'release_check.log'
                $report.full_release_verified = $true
                try {
                    $WhatIfPreference = $requestedWhatIf
                    $performProgram = $PSCmdlet.ShouldProcess("$($chain.name), FPGA @$DeviceIndex", "Configure SRAM with $relativeSof SHA256=$($report.sof_sha256)")
                } finally { $WhatIfPreference = $false }
            }
            if ($performProgram) {
                $report.mode = 'programming_attempt'
                $null = Run-QuartusTool $programmer $programArguments 'programming.log'
                $report.hardware_programmed = $true
                $report.mode = 'programming_completed'
                Write-Host 'Quartus reported successful SRAM configuration. Verify matching UART functionality separately.'
            } else { Write-Host 'Inspection only. The reviewed selection is in inspection.json; use -Program to configure SRAM.' }
        }
    }
} catch {
    $report.error = $_.Exception.Message
    throw
} finally {
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $evidenceDir 'inspection.json') -Encoding UTF8
    Write-Host "Evidence: $evidenceDir"
}
