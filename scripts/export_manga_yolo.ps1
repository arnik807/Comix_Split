# Export manga panel YOLO26n -> models/yolo_manga_int8.onnx
# Run from repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\export_manga_yolo.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "venv_311\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Write-Host "==> Manga YOLO export" -ForegroundColor Cyan
& $Python (Join-Path $PSScriptRoot "export_manga_yolo.py")
exit $LASTEXITCODE
