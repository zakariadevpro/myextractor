$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  throw "Python virtualenv not found at .venv\Scripts\python.exe"
}

New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null

$env:WINXTRACT_TASK_BACKEND = "db_queue"

Start-Process -FilePath ".\.venv\Scripts\python.exe" `
  -ArgumentList "-m","winxtract.cli","ui","--host","127.0.0.1","--port","8787" `
  -WorkingDirectory $Root `
  -RedirectStandardOutput ".\logs\ui.out.log" `
  -RedirectStandardError ".\logs\ui.err.log"

Start-Process -FilePath ".\.venv\Scripts\python.exe" `
  -ArgumentList "-m","winxtract.cli","queue-worker","--sources-dir","config/sources" `
  -WorkingDirectory $Root `
  -RedirectStandardOutput ".\logs\worker.out.log" `
  -RedirectStandardError ".\logs\worker.err.log"

Write-Host "WinXtract UI + worker started in background."
