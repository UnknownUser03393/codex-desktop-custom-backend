param(
  [Parameter(Mandatory=$true)][string]$BuiltExe,
  [string]$TargetDir = (Join-Path $env:LOCALAPPDATA 'CodexCustomBackend')
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
$target = Join-Path $TargetDir 'codex.exe'
Copy-Item -LiteralPath $BuiltExe -Destination $target -Force
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
Write-Output "Installed: $target"
Write-Output "SHA256: $hash"
& "$PSScriptRoot\set_user_env_broadcast.ps1" -Name 'CODEX_CLI_PATH' -Value $target
Write-Output "Rollback: run restore_backend.ps1, then restart Codex Desktop."
