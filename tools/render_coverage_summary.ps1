# Render measured JSON data as a presentation image, not a simulator screenshot.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$taskRoot = Split-Path $PSScriptRoot -Parent
$evidenceDir = Join-Path $taskRoot 'fpga/evidence/rtl_coverage'
$entries = Get-Content (Join-Path $evidenceDir 'coverage_summary.json') -Raw | ConvertFrom-Json
$rows = @($entries | Where-Object {
    $_.suite -eq 'core' -or $_.suite -eq 'gate' -or
    ($_.suite -eq 'board' -and $_.file -like '*igor_src_policy_de10_nano.v') -or
    ($_.suite -eq 'uart' -and $_.file -notlike '*igor_src_policy_core.v')
})
$canvas = New-Object System.Drawing.Bitmap(1400, (200 + 42 * $rows.Count))
$graphics = [System.Drawing.Graphics]::FromImage($canvas)
$graphics.Clear([System.Drawing.Color]::White)
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$titleFont = New-Object System.Drawing.Font('Segoe UI', 22, [System.Drawing.FontStyle]::Bold)
$bodyFont = New-Object System.Drawing.Font('Segoe UI', 12)
$dark = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(20, 37, 58))
$gray = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(84, 96, 110))
$graphics.DrawString('Measured RTL coverage | IGOR Parallel8', $titleFont, $dark, 28, 18)
$graphics.DrawString('Raw DUT counters, no waivers. Percentage = hit / total x 100. Per-suite results.', $bodyFont, $gray, 30, 63)
$cols = @(30, 135, 575, 820, 1040)
$heads = @('Suite', 'Source file', 'Metric', 'Hit / total', 'Coverage')
for ($j=0; $j -lt $heads.Count; $j++) { $graphics.DrawString($heads[$j], $bodyFont, $dark, $cols[$j], 103) }
$y=140
foreach ($entry in $rows) {
    $items = @($entry.suite, [System.IO.Path]::GetFileName($entry.file), $entry.metric, "$($entry.hit) / $($entry.total)", ('{0:N2}%' -f $entry.percent))
    for ($j=0; $j -lt $items.Count; $j++) { $graphics.DrawString([string]$items[$j], $bodyFont, $dark, $cols[$j], $y) }
    $y += 42
}
$graphics.DrawString('Generated evidence summary; not a simulator screenshot or whole-design sign-off.', $bodyFont, $gray, 30, ($y+8))
$canvas.Save((Join-Path $evidenceDir 'coverage_summary.png'), [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose(); $canvas.Dispose(); $titleFont.Dispose(); $bodyFont.Dispose(); $dark.Dispose(); $gray.Dispose()
