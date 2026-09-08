# 일일 PDF 수집: inbox -> 로컬 DB -> (선택) 프로덕션 업로드
param(
    [switch]$UploadProduction
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

New-Item -ItemType Directory -Force -Path "data\inbox" | Out-Null

$uploadFlag = if ($UploadProduction) { "--upload-production" } else { "" }
$pw = $null
if ($UploadProduction) {
    $pw = (railway variables --json 2>$null | ConvertFrom-Json).IMC_ADMIN_PASSWORD
    if (-not $pw) {
        Write-Error "IMC_ADMIN_PASSWORD not found. Run: railway link -p charming-transformation"
    }
}

if ($pw) {
    python backend/scripts/process_pdf_inbox.py --upload-production --password $pw
} else {
    python backend/scripts/process_pdf_inbox.py
}

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Daily PDF sync complete."
