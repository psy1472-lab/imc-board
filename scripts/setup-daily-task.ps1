# Windows scheduled task: daily 07:00 PDF inbox sync + production upload
param(
    [string]$RunTime = "07:00",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$TaskName = "IMC-Daily-PDF-Sync"
$ScriptPath = Join-Path $Root "scripts\daily-pdf-sync.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" -UploadProduction" `
    -WorkingDirectory $Root

$trigger = New-ScheduledTaskTrigger -Daily -At $RunTime
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "IMC daily PDF inbox sync and production upload" `
    -Force | Out-Null

Write-Host "Scheduled task registered: $TaskName at $RunTime daily"
Get-ScheduledTask -TaskName $TaskName | Format-List TaskName, State
