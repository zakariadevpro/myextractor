$ErrorActionPreference = "SilentlyContinue"

$targets = Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match "winxtract\.cli ui" -or $_.CommandLine -match "winxtract\.cli queue-worker"
}

if (-not $targets) {
  Write-Host "No WinXtract UI/worker process found."
  exit 0
}

$targets | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host ("Stopped {0} WinXtract process(es)." -f $targets.Count)
