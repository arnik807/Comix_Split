# scripts/download_upscale_backends.ps1
# Download optional NCNN Vulkan upscale backends (Real-CUGAN, SPAN).
# Real-ESRGAN remains in download_animate_models.ps1.
#
# Run:
#   powershell -ExecutionPolicy Bypass -File scripts\download_upscale_backends.ps1

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$UpscaleRoot = Join-Path $RootDir "models\anim\upscale"

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
        $size = (Get-Item $dest).Length
        if ($size -gt 1MB) {
            Write-Skip (Split-Path $dest -Leaf)
            return
        }
        Remove-Item $dest -Force -ErrorAction SilentlyContinue
    }
    Write-Host "    Download: $(Split-Path $dest -Leaf)..."
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
        throw "file too small ($size bytes)"
    }
    Write-OK (Split-Path $dest -Leaf)
}

function Expand-ZipToDir($zipPath, $destDir) {
    if (-not (Test-Path $zipPath)) {
        throw "Zip not found: $zipPath"
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $tempDir = Join-Path $env:TEMP ("comicsplit_upscale_" + [Guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    try {
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $tempDir)
        $exe = Get-ChildItem -Path $tempDir -Recurse -Filter "*.exe" |
            Where-Object { $_.Name -match "ncnn-vulkan" } |
            Select-Object -First 1
        if (-not $exe) {
            throw "No *-ncnn-vulkan.exe in archive"
        }
        $srcRoot = $exe.Directory.FullName
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        }
        Get-ChildItem -Path $srcRoot -Force | ForEach-Object {
            $target = Join-Path $destDir $_.Name
            if ($_.PSIsContainer) {
                if (Test-Path $target) {
                    Remove-Item $target -Recurse -Force
                }
                Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
            }
            else {
                Copy-Item -Path $_.FullName -Destination $target -Force
            }
        }
        Write-OK "Extracted -> $destDir"
        return $exe.Name
    }
    finally {
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# --- Real-CUGAN ---
Write-Step "Real-CUGAN NCNN Vulkan"
$cuganDir = Join-Path $UpscaleRoot "realcugan"
$cuganExe = Join-Path $cuganDir "realcugan-ncnn-vulkan.exe"
$cuganZip = Join-Path $UpscaleRoot "_zip_realcugan-windows.zip"
$cuganUrl = "https://github.com/nihui/realcugan-ncnn-vulkan/releases/download/20220728/realcugan-ncnn-vulkan-20220728-windows.zip"

if (Test-Path $cuganExe) {
    Write-Skip "realcugan-ncnn-vulkan.exe"
}
else {
    Download-File $cuganUrl $cuganZip
    Expand-ZipToDir $cuganZip $cuganDir | Out-Null
}

# --- SPAN ---
Write-Step "SPAN NCNN Vulkan"
$spanDir = Join-Path $UpscaleRoot "span"
$spanExe = Join-Path $spanDir "span-ncnn-vulkan.exe"
$spanZip = Join-Path $UpscaleRoot "_zip_span-windows.zip"
$spanUrl = "https://github.com/TNTwise/SPAN-ncnn-vulkan/releases/download/20240831-055257/span-ncnn-vulkan-20240831-055257-windows.zip"

if (Test-Path $spanExe) {
    Write-Skip "span-ncnn-vulkan.exe"
}
else {
    Download-File $spanUrl $spanZip
    Expand-ZipToDir $spanZip $spanDir | Out-Null
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Upscale backends download finished." -ForegroundColor Cyan
Write-Host " Verify: python scripts\verify_upscale_backends.py" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
