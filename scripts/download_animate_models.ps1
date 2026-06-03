# scripts/download_animate_models.ps1
# Download models for anim/ module
# Run: powershell -ExecutionPolicy Bypass -File scripts\download_animate_models.ps1

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$ModelsDir = Join-Path $RootDir "models\anim"
$PythonExe = Join-Path $RootDir "venv_311\Scripts\python.exe"
$PipExe = Join-Path $RootDir "venv_311\Scripts\pip.exe"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}
function Write-OK($msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}
function Write-Skip($msg) {
    Write-Host "    [SKIP] $msg (already exists)" -ForegroundColor Yellow
}
function Write-Fail($msg) {
    Write-Host "    [FAIL] $msg" -ForegroundColor Red
}

function Download-File($url, $dest) {
    if (Test-Path $dest) {
        Write-Skip (Split-Path $dest -Leaf)
        return
    }
    Write-Host "    Download: $(Split-Path $dest -Leaf)..."
    try {
        $destDir = Split-Path $dest -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        }
        & curl.exe -L --fail-with-body -o $dest $url
        if ($LASTEXITCODE -ne 0) {
            throw "curl exit code $LASTEXITCODE"
        }
        $size = (Get-Item $dest).Length
        if ($size -lt 1MB) {
            Remove-Item $dest -Force -ErrorAction SilentlyContinue
            throw "file too small ($size bytes), likely HTML error page"
        }
        Write-OK (Split-Path $dest -Leaf)
    }
    catch {
        Write-Fail "Download failed $url : $_"
        throw
    }
}

# 1. Directories
Write-Step "Create directories"
$dirs = @(
    "$ModelsDir\upscale\models",
    "$ModelsDir\depth",
    "$ModelsDir\tpsmm"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    Write-OK $d
}

# 2. Real-ESRGAN NCNN Vulkan
Write-Step "Real-ESRGAN NCNN Vulkan (upscale)"
$esrganZip = "$ModelsDir\upscale\realesrgan-ncnn-vulkan-windows.zip"
$esrganExe = "$ModelsDir\upscale\realesrgan-ncnn-vulkan.exe"

Download-File `
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip" `
    $esrganZip

if (-not (Test-Path $esrganExe)) {
    Write-Host "    Extracting archive..."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($esrganZip)
    foreach ($entry in $zip.Entries) {
        $destPath = Join-Path "$ModelsDir\upscale" $entry.FullName
        $destDir = Split-Path $destPath -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        }
        if ($entry.Name -ne "") {
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destPath, $true)
        }
    }
    $zip.Dispose()
    Write-OK "Archive extracted"
}
else {
    Write-Skip "realesrgan-ncnn-vulkan.exe"
}

# 3. MiDaS small ONNX
Write-Step "MiDaS small (depth map)"
$midasDest = "$ModelsDir\depth\midas_v21_small_256.onnx"
$midasUrls = @(
    "https://huggingface.co/julienkay/sentis-MiDaS/resolve/main/onnx/midas_v21_small_256.onnx",
    "https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx"
)
if (-not (Test-Path $midasDest)) {
    $midasOk = $false
    foreach ($u in $midasUrls) {
        try {
            Download-File $u $midasDest
            $midasOk = $true
            break
        }
        catch {
            Write-Host "    Trying fallback URL..." -ForegroundColor Yellow
        }
    }
    if (-not $midasOk) {
        Write-Fail "MiDaS download failed from all URLs"
    }
}
else {
    Write-Skip "midas_v21_small_256.onnx"
}

# 4. TPSMM ONNX
Write-Step "TPSMM ONNX (motion transfer)"
$tpsmmZip = "$ModelsDir\tpsmm\tpsmm-onnx.zip"
$tpsmmKp = "$ModelsDir\tpsmm\kp_detector.onnx"
$tpsmmRel = "$ModelsDir\tpsmm\tpsmm_rel.onnx"

if (-not (Test-Path $tpsmmKp) -or -not (Test-Path $tpsmmRel)) {
    Write-Host "    Fetching latest TPSMM release..."
    try {
        $releaseInfo = Invoke-RestMethod `
            -Uri "https://api.github.com/repos/instant-high/Thin-plate-spline-motion-model-ONNX/releases/latest" `
            -UseBasicParsing
        $zipAsset = $releaseInfo.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
        if ($zipAsset) {
            Download-File $zipAsset.browser_download_url $tpsmmZip
            Write-Host "    Extracting TPSMM models..."
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [System.IO.Compression.ZipFile]::OpenRead($tpsmmZip)
            foreach ($entry in $zip.Entries) {
                if ($entry.Name -like "*.onnx") {
                    $destPath = Join-Path "$ModelsDir\tpsmm" $entry.Name
                    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destPath, $true)
                    Write-OK $entry.Name
                }
            }
            $zip.Dispose()
        }
        else {
            Write-Fail "No zip asset in TPSMM release"
            Write-Host "    Manual: https://github.com/instant-high/Thin-plate-spline-motion-model-ONNX/releases" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Fail "GitHub API error: $_"
        Write-Host "    Manual: https://github.com/instant-high/Thin-plate-spline-motion-model-ONNX/releases" -ForegroundColor Yellow
    }
}
else {
    Write-Skip "kp_detector.onnx + tpsmm_rel.onnx"
}

# 5. DepthFlow (pip)
Write-Step "DepthFlow (parallax)"
if (-not (Test-Path $PythonExe)) {
    Write-Fail "venv python not found: $PythonExe"
}
else {
    $dfCheckCmd = "import depthflow; print('ok')"
    $dfOut = & $PythonExe -c $dfCheckCmd 2>&1 | Out-String
    $dfOut = $dfOut.Trim()
    if ($dfOut -eq "ok") {
        Write-Skip "depthflow already installed"
    }
    else {
        Write-Host "    Installing depthflow (may take a few minutes)..."
        & $PipExe install depthflow --quiet
        $dfOut2 = & $PythonExe -c $dfCheckCmd 2>&1 | Out-String
        $dfOut2 = $dfOut2.Trim()
        if ($dfOut2 -eq "ok") {
            Write-OK "depthflow installed"
        }
        else {
            Write-Fail "depthflow install failed - run: pip install depthflow"
            Write-Host "    $dfOut2" -ForegroundColor Yellow
        }
    }
}

# 6. ffmpeg check
Write-Step "ffmpeg (MP4 render)"
$ffmpegCheck = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegCheck) {
    Write-Skip "ffmpeg available: $($ffmpegCheck.Source)"
}
else {
    Write-Host "    ffmpeg NOT in PATH" -ForegroundColor Yellow
    Write-Host "    Download: https://ffmpeg.org/download.html" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Download finished." -ForegroundColor Cyan
Write-Host " Next: python scripts\quantize_animate_models.py" -ForegroundColor White
Write-Host " Optional: scripts\download_upscale_backends.ps1 (Real-CUGAN + SPAN)" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
