$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/host-baseline'
if (!(Test-Path (Join-Path $runtime 'chars/kof13/foreign.json'))) { throw 'Import local KOF XIII data first.' }
# This is the interactive play command; the visible window is intentional.
Start-Process -FilePath (Join-Path $runtime 'Ikemen_GO.exe') -WorkingDirectory $runtime `
    -ArgumentList @('-p1','kof13/kof13.def','-p2','kfm','-p2.ai','6','-windowed')
