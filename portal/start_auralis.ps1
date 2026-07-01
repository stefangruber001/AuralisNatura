# Auralis portal launcher (Windows). Same idea as the macOS .command:
# self-updates from GitHub main every 120s and keeps the server running.
Set-Location $PSScriptRoot
if (Test-Path .env) { Get-Content .env | ? {$_ -match '='} | % { $k,$v = $_ -split '=',2; [Environment]::SetEnvironmentVariable($k.Trim(),$v.Trim()) } }
while ($true) {
  git fetch origin main --quiet 2>$null
  if ((git rev-parse HEAD) -ne (git rev-parse origin/main 2>$null)) {
    git reset --hard origin/main --quiet; python -m pip install -q -r requirements.txt
  }
  Write-Host "Auralis portal running (Ctrl-C to stop)"
  $p = Start-Process python -ArgumentList "run.py" -PassThru -NoNewWindow
  while (-not $p.HasExited) {
    Start-Sleep 120
    git fetch origin main --quiet 2>$null
    if ((git rev-parse HEAD) -ne (git rev-parse origin/main 2>$null)) { Stop-Process $p.Id; break }
  }
}
