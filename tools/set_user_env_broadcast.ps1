param([string]$Name,[string]$Value,[switch]$Remove)
$ErrorActionPreference = 'Stop'
if ($Remove) {
    if (Test-Path 'HKCU:\Environment') { Remove-ItemProperty -Path 'HKCU:\Environment' -Name $Name -ErrorAction SilentlyContinue }
} else {
    [Environment]::SetEnvironmentVariable($Name, $Value, 'User')
}
$sig = @'
using System; using System.Runtime.InteropServices;
public static class EnvBroadcast {
  [DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
  public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
}
'@
Add-Type -TypeDefinition $sig -ErrorAction SilentlyContinue
[UIntPtr]$r = [UIntPtr]::Zero
[void][EnvBroadcast]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$r)
Write-Output ("User env {0} = {1}" -f $Name, [Environment]::GetEnvironmentVariable($Name,'User'))
