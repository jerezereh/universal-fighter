<# Launch the unmodified, fingerprinted SIGN bootstrap for local manual/offline checks.
The source game can create its normal player data; this script doesn't modify it.
#>
[CmdletBinding()]
param([string]$GameDirectory = 'C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$binaryDirectory = Join-Path $GameDirectory 'Binaries/Win32'
$executable = Join-Path $binaryDirectory 'GuiltyGearXrd.exe'
$expected = 'F7A2E990B664F882BF16EAFA94433FF0460F0B630C083FD0760A0D7949E08B78'
if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $expected) { throw 'Unverified SIGN executable build.' }
$bootstrap = Join-Path $binaryDirectory 'BootGGXrd.exe'
if ((Get-FileHash -LiteralPath $bootstrap -Algorithm SHA256).Hash -ne '998ECE44B49FD9F4442304ADE6AB71BA14A4F6DCA5B0E000D668FE934BA8F59B') {
    throw 'Unverified SIGN bootstrap build.'
}
if (Get-Process -Name GuiltyGearXrd -ErrorAction SilentlyContinue) { throw 'Close the existing SIGN instance before launching a source check.' }
$receiptPath = Join-Path $root 'local-cache/xrd-tools/oracle-dependencies.json'
if (!(Test-Path -LiteralPath $receiptPath)) { throw 'Run gather-xrd-oracle.ps1 first.' }
$receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
if (!$receipt.complete -or $receipt.dlls.Count -ne 3) { throw 'Incomplete source-check dependency receipt.' }
foreach ($entry in $receipt.dlls) {
    $dll = Join-Path $receipt.directory $entry.name
    if ((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Dependency fingerprint changed: $dll" }
}
$previousPath = $env:PATH
try {
    $env:PATH = $receipt.directory + ';' + $previousPath
    # BootGGXrd is required; direct GuiltyGearXrd startup failed before rendering.
    $launcher = Start-Process -FilePath $bootstrap -WorkingDirectory $binaryDirectory -WindowStyle Normal -PassThru
} finally { $env:PATH = $previousPath }
$deadline = (Get-Date).AddSeconds(20)
do {
    Start-Sleep -Milliseconds 250
    $game = Get-Process -Name GuiltyGearXrd -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }
} until ($game -or (Get-Date) -ge $deadline)
if (!$game) { throw "SIGN did not create a window; bootstrap PID was $($launcher.Id)." }
Write-Output "Original SIGN window ready (PID $($game.Id)). Use offline Practice/Training for source comparisons."
