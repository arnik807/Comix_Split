# Install PaddlePaddle + PaddleOCR for Story Analyzer Stage 2a (CPU).
# Stop uvicorn / Gradio before running (opencv cv2.pyd lock on Windows).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "venv_311\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$PaddleBaseDir = Join-Path $Root "models\paddleocr"
$env:PADDLE_OCR_BASE_DIR = $PaddleBaseDir
New-Item -ItemType Directory -Force -Path $PaddleBaseDir | Out-Null

$OldHome = Join-Path $env:USERPROFILE ".paddleocr"
if ((Test-Path $OldHome) -and -not (Test-Path (Join-Path $PaddleBaseDir "whl"))) {
    Write-Host "==> Copy existing models from $OldHome -> $PaddleBaseDir" -ForegroundColor Cyan
    Copy-Item -Recurse -Force (Join-Path $OldHome "*") $PaddleBaseDir
}

Write-Host "==> PaddleOCR install (Stage 2a)" -ForegroundColor Cyan
Write-Host "    Model cache: $PaddleBaseDir" -ForegroundColor Yellow
Write-Host "    Close ComicSplit server / Gradio first." -ForegroundColor Yellow

& $Python -m pip install --upgrade pip
& $Python -m pip install "paddlepaddle==3.0.0" --no-deps
& $Python -m pip install "paddleocr==2.10.0" --no-deps
& $Python -m pip install decorator astor protobuf opt-einsum `
    beautifulsoup4 cython fire lmdb python-docx pyclipper shapely python-bidi `
    "albumentations==1.4.24" imgaug rapidfuzz openpyxl

Write-Host "==> Verify import (models/paddleocr)" -ForegroundColor Cyan
& $Python -c @"
import os
from pathlib import Path
root = Path(r'$Root')
base = root / 'models' / 'paddleocr'
os.environ['PADDLE_OCR_BASE_DIR'] = str(base)
from paddleocr import PaddleOCR
PaddleOCR(use_angle_cls=False, lang='ru', use_gpu=False, show_log=False)
print('PaddleOCR OK ->', base)
"@
exit $LASTEXITCODE
