# Test the programming wrapper with isolated fake tools; no real JTAG access.
$ErrorActionPreference = 'Stop'
$fpgaRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$fixture = Join-Path $fpgaRoot ('.runtime/programmer_fixture_' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffff'))
$bin = Join-Path $fixture 'fake_tools'
foreach ($path in @($bin, (Join-Path $fixture 'scripts'), (Join-Path $fixture 'fpga_de10_nano/src_policy/output_files'))) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}
Copy-Item -LiteralPath (Join-Path $fpgaRoot 'scripts/program_fpga.ps1') -Destination (Join-Path $fixture 'scripts/program_fpga.ps1')
'print("FIXTURE ONLY: release check")' | Set-Content -LiteralPath (Join-Path $fixture 'scripts/freeze_release.py') -Encoding ASCII
$relativeSof = 'fpga_de10_nano/src_policy/output_files/igor_src_policy.sof'
$sof = Join-Path $fixture $relativeSof
'TEST FIXTURE ONLY: not an FPGA bitstream.' | Set-Content -LiteralPath $sof -Encoding ASCII
'set_global_assignment -name DEVICE 5CSEBA6U23I7' | Set-Content -LiteralPath (Join-Path $fixture 'fpga_de10_nano/src_policy/igor_src_policy.qsf') -Encoding ASCII
$manifestPath = Join-Path $fixture 'manifest.json'
$manifest = @{schema=1; files=@{}; projects=@{source_policy=@{sof=$relativeSof}}}
$manifest.files[$relativeSof] = @{sha256=(Get-FileHash -LiteralPath $sof -Algorithm SHA256).Hash.ToLowerInvariant(); bytes=(Get-Item -LiteralPath $sof).Length}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$marker = Join-Path $fixture 'FAKE_PROGRAM_OPERATION.txt'
$oldMarker = $env:IGOR_PROGRAM_TEST_MARKER
$oldMode = $env:IGOR_PROGRAM_TEST_MODE
$env:IGOR_PROGRAM_TEST_MARKER = $marker
$source = @'
using System;
using System.IO;
using System.Diagnostics;
public class IsolatedQuartusFixture {
  public static int Main(string[] args) {
    string mode = Environment.GetEnvironmentVariable("IGOR_PROGRAM_TEST_MODE");
    string executable = Path.GetFileNameWithoutExtension(Process.GetCurrentProcess().MainModule.FileName);
    if (executable == "jtagconfig") {
      if (mode == "unattached") { Console.WriteLine("1) Fixture USB-Blaster\n  Unable to lock chain - Hardware not attached"); return 0; }
      if (mode == "empty") { Console.WriteLine("1) Fixture USB-Blaster"); return 0; }
      Console.WriteLine("1) Fixture USB-Blaster");
      Console.WriteLine("  4BA00477   SOCVHPS");
      Console.WriteLine("  02D020DD   5CSEBA6(.|ES)/5CSEMA6/..");
      if (mode == "multiple") { Console.WriteLine("2) Another USB-Blaster\n  02D020DD   5CSEBA6(.|ES)/5CSEMA6/.."); }
      return 0;
    }
    if (Array.IndexOf(args, "--list") >= 0) { Console.WriteLine("1) Fixture USB-Blaster"); return 0; }
    if (Array.IndexOf(args, "-a") >= 0) { Console.WriteLine("1) SOCVHPS\n2) 5CSEBA6"); return 0; }
    if (Array.IndexOf(args, "-o") >= 0) {
      if (mode == "programfail") { Console.WriteLine("Error (209040): Device programming failed"); return 0; }
      File.WriteAllLines(Environment.GetEnvironmentVariable("IGOR_PROGRAM_TEST_MARKER"), args);
      Console.WriteLine("FIXTURE ONLY: simulated Programmer success");
      return 0;
    }
    return 3;
  }
}
'@
Add-Type -TypeDefinition $source -OutputAssembly (Join-Path $bin 'quartus_pgm.exe') -OutputType ConsoleApplication
Copy-Item -LiteralPath (Join-Path $bin 'quartus_pgm.exe') -Destination (Join-Path $bin 'jtagconfig.exe')
$script = Join-Path $fixture 'scripts/program_fpga.ps1'
$passed = @()
function Invoke-Fixture([string[]]$Options, [bool]$ExpectSuccess) {
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& powershell -NoProfile -File $script -QuartusBin $bin -Manifest $manifestPath @Options 2>&1 | ForEach-Object { $_.ToString() })
        $exit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $oldPreference }
    if (($exit -eq 0) -ne $ExpectSuccess) { throw "Unexpected fixture exit=$exit : $($output -join ' ')" }
    $latest = Get-ChildItem -LiteralPath (Join-Path $fixture 'evidence/current_programming') -Directory | Sort-Object Name | Select-Object -Last 1
    return Get-Content -LiteralPath (Join-Path $latest.FullName 'inspection.json') -Raw | ConvertFrom-Json
}
try {
    $env:IGOR_PROGRAM_TEST_MODE = ''
    $inspection = Invoke-Fixture @('-Cable', '1', '-DeviceIndex', '2') $true
    if (!$inspection.manifest_verified -or !$inspection.ready_to_program -or $inspection.hardware_programmed -or (Test-Path -LiteralPath $marker)) { throw 'Inspection issued a fake program operation or missed validation.' }
    if ($inspection.program_arguments[-1] -notlike 'P;*@2' -or $inspection.program_arguments[-3] -ne 'S;SOCVHPS@1') { throw 'FPGA at position 2 / HPS bypass construction is incorrect.' }
    $passed += 'inspect_detects_fpga_at_2_and_bypasses_hps_at_1_without_programming'
    $null = Invoke-Fixture @('-Cable', '1', '-DeviceIndex', '2', '-Program', '-WhatIf') $true
    if (Test-Path -LiteralPath $marker) { throw 'WhatIf issued a fake program operation.' }
    $passed += 'whatif_does_not_program'
    $null = Invoke-Fixture @('-Cable', '1', '-DeviceIndex', '1', '-Program') $false
    if (Test-Path -LiteralPath $marker) { throw 'HPS selection issued a fake program operation.' }
    $passed += 'hps_selection_rejected'
    $null = Invoke-Fixture @('-Program') $false
    if (Test-Path -LiteralPath $marker) { throw 'Missing cable issued a fake program operation.' }
    $passed += 'missing_cable_rejected'
    $null = Invoke-Fixture @('-Cable', '1', '-Program') $false
    if (Test-Path -LiteralPath $marker) { throw 'Missing device index issued a fake program operation.' }
    $passed += 'missing_device_index_rejected'
    $manifest.files[$relativeSof].sha256 = '0' * 64
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    $null = Invoke-Fixture @('-Cable', '1', '-DeviceIndex', '2', '-Program') $false
    if (Test-Path -LiteralPath $marker) { throw 'Hash mismatch issued a fake program operation.' }
    $passed += 'tampered_sof_hash_rejected'
    $manifest.files[$relativeSof].sha256 = (Get-FileHash -LiteralPath $sof -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    'import sys; sys.exit(7)' | Set-Content -LiteralPath (Join-Path $fixture 'scripts/freeze_release.py') -Encoding ASCII
    $null = Invoke-Fixture @('-Cable', '1', '-DeviceIndex', '2', '-Program') $false
    if (Test-Path -LiteralPath $marker) { throw 'Failed full release check issued a fake program operation.' }
    $passed += 'failed_full_source_build_release_check_rejected'
    'print("FIXTURE ONLY: release check")' | Set-Content -LiteralPath (Join-Path $fixture 'scripts/freeze_release.py') -Encoding ASCII
    $programmed = Invoke-Fixture @('-Cable', '1', '-DeviceIndex', '2', '-Program') $true
    if (!$programmed.hardware_programmed -or !(Test-Path -LiteralPath $marker)) { throw 'Explicit Program did not reach the isolated fake tool.' }
    $argsSeen = Get-Content -LiteralPath $marker
    if ($argsSeen[-1] -notlike 'P;*@2' -or $argsSeen[-3] -ne 'S;SOCVHPS@1') { throw 'Actual fake tool arguments differ from the reviewed operations.' }
    $passed += 'explicit_program_reaches_only_fake_tool_with_correct_arguments'
    Remove-Item -LiteralPath $marker
    foreach ($mode in @('unattached', 'empty', 'multiple')) {
        $env:IGOR_PROGRAM_TEST_MODE = $mode
        $null = Invoke-Fixture @('-AutoSelect', '-Program') $false
        if (Test-Path -LiteralPath $marker) { throw "Invalid chain $mode reached programmer." }
        $passed += "autoselect_rejects_$mode"
    }
    $env:IGOR_PROGRAM_TEST_MODE = ''
    $null = Invoke-Fixture @('-AutoSelect', '-Program', '-WhatIf') $true
    if (Test-Path -LiteralPath $marker) { throw 'AutoSelect WhatIf programmed.' }
    $passed += 'autoselect_whatif_does_not_program'
    # The fast project's compiled filename is identical to the baseline; the
    # handoff has a distinct name and must be selected, hash-checked and logged.
    $fastDir = Join-Path $fixture 'experiments/parallel8/output_files'
    New-Item -ItemType Directory -Path $fastDir -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $fixture 'bitstreams') -Force | Out-Null
    $fastRelative = 'experiments/parallel8/output_files/igor_src_policy.sof'
    Copy-Item -LiteralPath $sof -Destination (Join-Path $fixture $fastRelative)
    Copy-Item -LiteralPath $sof -Destination (Join-Path $fixture 'bitstreams/igor_src_policy_parallel8.sof')
    Copy-Item -LiteralPath (Join-Path $fixture 'fpga_de10_nano/src_policy/igor_src_policy.qsf') -Destination (Join-Path $fixture 'experiments/parallel8/igor_src_policy.qsf')
    $manifest.files[$fastRelative] = $manifest.files[$relativeSof]
    $manifest.projects.source_policy_parallel8 = @{sof=$fastRelative}
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    $fast = Invoke-Fixture @('-Project', 'source_policy_parallel8', '-AutoSelect', '-Program') $true
    $argsSeen = Get-Content -LiteralPath $marker
    if (!$fast.hardware_programmed -or $argsSeen[-1] -notlike 'P;*bitstreams*igor_src_policy_parallel8.sof@2') { throw 'Wrong Parallel8 handoff programmed.' }
    $cdf = Get-Content -LiteralPath $fast.detected_chain_cdf -Raw
    if ($cdf.IndexOf('PartName(SOCVHPS)') -gt $cdf.IndexOf('PartName(5CSEBA6)') -or $cdf -notmatch 'igor_src_policy_parallel8.sof') { throw 'Detected CDF has wrong chain/image.' }
    $passed += 'parallel8_selects_exact_handoff_and_generates_detected_cdf'
    Remove-Item -LiteralPath $marker
    'tampered handoff' | Set-Content -LiteralPath (Join-Path $fixture 'bitstreams/igor_src_policy_parallel8.sof')
    $null = Invoke-Fixture @('-Project', 'source_policy_parallel8', '-AutoSelect', '-Program') $false
    if (Test-Path -LiteralPath $marker) { throw 'Tampered handoff programmed.' }
    $passed += 'parallel8_handoff_mismatch_rejected'
    $env:IGOR_PROGRAM_TEST_MODE = 'programfail'
    $failed = Invoke-Fixture @('-AutoSelect', '-Program') $false
    if ($failed.hardware_programmed -or (Test-Path -LiteralPath $marker)) { throw 'Zero-exit error falsely claimed programming success.' }
    $passed += 'zero_exit_program_error_is_not_success'
    $outputDir = Join-Path $fpgaRoot 'evidence/current_programming'
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    @{schema=1; utc=[DateTime]::UtcNow.ToString('o'); evidence_kind='isolated fake executable fixture; not hardware evidence'; physical_hardware_accessed=$false; status='PASS'; count=$passed.Count; cases=$passed} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $outputDir 'tooling_tests.json') -Encoding UTF8
    Write-Output "PASS: $($passed.Count) programming-wrapper fixture cases. No real programmer used."
} finally { $env:IGOR_PROGRAM_TEST_MARKER = $oldMarker; $env:IGOR_PROGRAM_TEST_MODE = $oldMode }
