# 공유폴더/OneDrive에서 inbox로 PDF 복사 후 처리
param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,
    [switch]$UploadProduction,
    [switch]$Watch
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$inbox = Join-Path $Root "data\inbox"
New-Item -ItemType Directory -Force -Path $inbox | Out-Null

if (-not (Test-Path $SourcePath)) {
    Write-Error "Source path not found: $SourcePath"
}

Write-Host "Sync PDFs: $SourcePath -> $inbox"
robocopy $SourcePath $inbox *.pdf /XO /MOV /NFL /NDL /NJH /NJS /NC /NS | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Error "robocopy failed with exit code $LASTEXITCODE"
}

$pw = $null
if ($UploadProduction) {
    $pw = (railway variables --json 2>$null | ConvertFrom-Json).IMC_ADMIN_PASSWORD
}

if ($Watch) {
    if ($pw) {
        python backend/scripts/watch_pdf_inbox.py --upload-production --password $pw
    } else {
        python backend/scripts/watch_pdf_inbox.py
    }
} else {
    if ($pw) {
        python backend/scripts/process_pdf_inbox.py --upload-production --password $pw
    } else {
        python backend/scripts/process_pdf_inbox.py
    }
}

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Inbox sync complete."
