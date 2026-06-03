# Benchmark NCNN upscale: Real-ESRGAN, Real-CUGAN, SPAN (via anim/upscale.py).
# Run from project root:
#   powershell -ExecutionPolicy Bypass -File scripts\benchmark_upscale.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\benchmark_upscale.ps1 -Quick
#   powershell -ExecutionPolicy Bypass -File scripts\benchmark_upscale.ps1 -Input "exam_img\...\panel.png"

param(
    [string]$Input = "",
    [string]$OutDir = "exam_img\_upscale_benchmark",
    [switch]$Quick,
    [string]$Backends = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "venv_311\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$Script = Join-Path $PSScriptRoot "benchmark_upscale.py"
$argsList = @("--out-dir", $OutDir)
if ($Input) { $argsList += @("--input", $Input) }
if ($Quick) { $argsList += "--quick" }
if ($Backends) { $argsList += @("--backends", $Backends) }

Write-Host "==> Upscale benchmark" -ForegroundColor Cyan
Write-Host "    Python: $Python"
Write-Host ""

& $Python $Script @argsList
exit $LASTEXITCODE
