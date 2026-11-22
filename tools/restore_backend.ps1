$ErrorActionPreference = 'Stop'
& "$PSScriptRoot\set_user_env_broadcast.ps1" -Name 'CODEX_CLI_PATH' -Remove
$cacheRoot = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'
Write-Output "Removed user CODEX_CLI_PATH. Restart Codex Desktop to use the packaged original."
if (Test-Path $cacheRoot) {
  Write-Output "Packaged cache area (untouched by this tool):"
  Get-ChildItem -Path $cacheRoot -Recurse -Filter 'codex.exe' -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Output ("  " + $_.FullName) }
}
