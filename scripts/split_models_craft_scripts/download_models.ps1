# ========================= download_models.ps1 =========================
# MobileSAM берём уже готовые ONNX (Acly/MobileSAM).
# YOLO берём .pt (mosesb/best-comic-panel-detection) — конвертируем ниже.
# =====================================================================

$ModelDir = Join-Path -Path $PSScriptRoot -ChildPath "models"
if (-not (Test-Path $ModelDir)) {
    New-Item -ItemType Directory -Path $ModelDir | Out-Null
}

# ── Рабочие ссылки ────────────────────────────────────────────────────
$YOLO_URL        = "https://huggingface.co/mosesb/best-comic-panel-detection/resolve/main/best.pt?download=true"
$SAM_ENC_URL     = "https://huggingface.co/Acly/MobileSAM/resolve/main/mobile_sam_image_encoder.onnx?download=true"
$SAM_DEC_URL     = "https://huggingface.co/Acly/MobileSAM/resolve/main/sam_mask_decoder_single.onnx?download=true"

function Download-Model {
    param([string]$Url, [string]$OutPath)

    Write-Host "📥 Скачивание: $(Split-Path $OutPath -Leaf) ..."

    if ($env:HF_HUB_TOKEN) {
        $AuthHeader = "Authorization: Bearer $env:HF_HUB_TOKEN"
        & curl.exe -L --fail-with-body -H $AuthHeader -o $OutPath $Url 2>&1
    } else {
        & curl.exe -L --fail-with-body -o $OutPath $Url 2>&1
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Error "❌ curl завершился с ошибкой для $OutPath"
        return
    }

    $size = (Get-Item $OutPath).Length
    if ($size -lt 1MB) {
        Write-Warning "⚠️  Файл подозрительно мал ($size байт) — возможно HTML-ошибка."
        Write-Warning "    Попробуй задать токен: `$env:HF_HUB_TOKEN = 'hf_...' и перезапустить."
    } else {
        $mb = [math]::Round($size / 1MB, 1)
        Write-Host "✅ $(Split-Path $OutPath -Leaf) — $mb MB`n"
    }
}

# ── Скачивание ────────────────────────────────────────────────────────
Download-Model -Url $YOLO_URL    -OutPath (Join-Path $ModelDir "yolo_comic.pt")
Download-Model -Url $SAM_ENC_URL -OutPath (Join-Path $ModelDir "mobilesam_encoder.onnx")
Download-Model -Url $SAM_DEC_URL -OutPath (Join-Path $ModelDir "mobilesam_decoder.onnx")

Write-Host "Содержимое папки models:"
Get-ChildItem $ModelDir | Format-Table Name, @{L='Size MB';E={[math]::Round($_.Length/1MB,1)}} -AutoSize
# =====================================================================