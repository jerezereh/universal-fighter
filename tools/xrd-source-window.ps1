<# Fingerprinted SIGN window status, nonactivating restore and bounded background key messages. #>
[CmdletBinding()]
param(
    [ValidateSet('status','restore','post-key','return-focus')][string]$Action = 'status',
    [ValidateSet('escape','enter','up','down','left','right','punch')][string]$Key = 'escape',
    [long]$PreviousForeground = 0,
    [ValidateRange(0,2147483647)][int]$SourceProcessId = 0
)
$ErrorActionPreference = 'Stop'
$expectedExe = 'C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe'
$sourceGames = @(Get-Process -Name GuiltyGearXrd -ErrorAction SilentlyContinue)
$matchingProcesses = $sourceGames.Count
$sourceGames = @($sourceGames | Where-Object { $_.Path -and
    [IO.Path]::GetFullPath($_.Path) -eq [IO.Path]::GetFullPath($expectedExe) })
if ($SourceProcessId -ne 0) { $sourceGames = @($sourceGames | Where-Object { $_.Id -eq $SourceProcessId }) }
if ($sourceGames.Count -ne 1) { throw 'Expected exactly one running SIGN process.' }
$sourceGame = $sourceGames[0]
if ([IO.Path]::GetFullPath($sourceGame.Path) -ne [IO.Path]::GetFullPath($expectedExe) -or
    (Get-FileHash -LiteralPath $sourceGame.Path -Algorithm SHA256).Hash -ne 'F7A2E990B664F882BF16EAFA94433FF0460F0B630C083FD0760A0D7949E08B78') {
    throw 'Unverified source executable.'
}
if (-not ('SignWindow' -as [type])) { Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SignWindow {
    [StructLayout(LayoutKind.Sequential)] public struct LastInput { public uint Size, Time; }
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr window);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr window);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint pid);
    [DllImport("user32.dll")] public static extern bool GetLastInputInfo(ref LastInput info);
    [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr window, int command);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool PostMessageW(IntPtr window, uint message, UIntPtr key, IntPtr data);
    [DllImport("user32.dll")] public static extern uint MapVirtualKeyW(uint key, uint map);
    public static double Idle() {
        var info = new LastInput(); info.Size = (uint)Marshal.SizeOf(info);
        if (!GetLastInputInfo(ref info)) throw new InvalidOperationException("Idle query failed");
        return unchecked((uint)Environment.TickCount - info.Time) / 1000.0;
    }
}
'@
}
$window = $sourceGame.MainWindowHandle
[uint32]$windowOwner = 0
[void][SignWindow]::GetWindowThreadProcessId($window, [ref]$windowOwner)
if ($window -eq [IntPtr]::Zero -or $windowOwner -ne $sourceGame.Id) { throw 'Source window identity changed.' }
$foregroundBefore = [SignWindow]::GetForegroundWindow()
$minimizedBefore = [SignWindow]::IsIconic($window)
if ($Action -eq 'return-focus' -and $foregroundBefore -eq $window) {
    if ($PreviousForeground -le 0 -or $PreviousForeground -eq $window.ToInt64() -or
        ![SignWindow]::IsWindow([IntPtr]$PreviousForeground)) { throw 'Invalid previous foreground window.' }
    if (![SignWindow]::SetForegroundWindow([IntPtr]$PreviousForeground)) { throw 'Previous foreground could not be restored.' }
}
if ($Action -eq 'restore' -and $minimizedBefore) {
    # SW_SHOWNOACTIVATE: restore renderability without activating the source window.
    if (![SignWindow]::ShowWindowAsync($window, 4)) { throw 'Nonactivating restore failed.' }
    $restoreDeadline = (Get-Date).AddSeconds(3)
    while ([SignWindow]::IsIconic($window) -and (Get-Date) -lt $restoreDeadline) { Start-Sleep -Milliseconds 50 }
    if ([SignWindow]::IsIconic($window)) { throw 'Source remained minimized.' }
}
if ($Action -eq 'post-key') {
    if ([SignWindow]::IsIconic($window)) { throw 'Restore the source before sending menu messages.' }
    $virtualKeys = @{ escape=27; enter=13; up=38; down=40; left=37; right=39; punch=74 }
    [uint32]$virtualKey = $virtualKeys[$Key]
    [long]$keyData = 1 -bor ([long][SignWindow]::MapVirtualKeyW($virtualKey, 0) -shl 16)
    if ($Key -in @('up','down','left','right')) { $keyData = $keyData -bor 0x01000000 }
    try {
        if (![SignWindow]::PostMessageW($window, 0x100, [UIntPtr]$virtualKey, [IntPtr]$keyData)) { throw 'Key-down message failed.' }
        Start-Sleep -Milliseconds 80
    } finally {
        # Pair every posted key-down with a targeted key-up; never call global SendInput.
        if (![SignWindow]::PostMessageW($window, 0x101, [UIntPtr]$virtualKey, [IntPtr]($keyData -bor 3221225472))) { throw 'Key-up message failed.' }
    }
}
$foregroundAfter = [SignWindow]::GetForegroundWindow()
[pscustomobject]@{
    pid=$sourceGame.Id; hwnd=$window.ToInt64(); action=$Action
    minimized_before=$minimizedBefore; minimized=[SignWindow]::IsIconic($window)
    visible=[SignWindow]::IsWindowVisible($window); foreground=($foregroundAfter -eq $window)
    foreground_unchanged=($foregroundAfter -eq $foregroundBefore)
    foreground_hwnd=$foregroundAfter.ToInt64()
    idle_seconds=[SignWindow]::Idle(); source_verified=$true
    responding=$sourceGame.Responding
    matching_processes=$matchingProcesses
    key_message_posted=($Action -eq 'post-key'); key_effect_verified=$false
} | ConvertTo-Json -Compress
