$ErrorActionPreference = "Stop"

$backendDir = Join-Path $PSScriptRoot ".." "backend"
$port = 8001

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'uvicorn.*interfaces\.api\.main' } |
  ForEach-Object {
    Write-Host "Stopping uvicorn PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }

Start-Sleep -Seconds 1

Set-Location $backendDir
$env:PYTHONPATH = "src"

Write-Host "Starting IMC API on http://127.0.0.1:$port"
uvicorn interfaces.api.main:app --reload --reload-dir src --app-dir src --host 127.0.0.1 --port $port
