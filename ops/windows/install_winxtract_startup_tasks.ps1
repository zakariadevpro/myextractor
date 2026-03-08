$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$StartScript = Join-Path $Root "ops\windows\start_winxtract_services.ps1"
$TaskName = "WinXtract-Services"

if (-not (Test-Path $StartScript)) {
  throw "Start script not found: $StartScript"
}

$escapedScript = $StartScript.Replace("\", "\\")
$cmd = "powershell.exe -ExecutionPolicy Bypass -File `"$escapedScript`""

schtasks /Create /TN $TaskName /SC ONSTART /TR $cmd /RL HIGHEST /F | Out-Null
Write-Host "Scheduled task installed: $TaskName"
