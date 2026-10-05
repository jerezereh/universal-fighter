[CmdletBinding()]
param([ValidateRange(30,600)][int]$TimeoutSeconds = 120)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/host-baseline'
$executable = Join-Path $runtime 'Ikemen_GO.exe'
if (!(Test-Path (Join-Path $runtime 'chars/kof13/foreign.json'))) { throw 'Import local KOF XIII data first.' }
$runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
$matchLog = "foreign-$runId.txt"
$tracePath = Join-Path $runtime "foreign-$runId.stderr.txt"
$oldTrace = $env:UF_FOREIGN_TRACE
try {
    $env:UF_FOREIGN_TRACE = '1'
    $process = Start-Process -FilePath $executable -WorkingDirectory $runtime -WindowStyle Hidden -PassThru `
        -RedirectStandardError $tracePath -ArgumentList @('-p1','kfm','-p2','kof13/kof13.def',
            '-p1.ai','8','-p2.ai','8','-p1.life','500','-p2.life','1000','-rounds','1','-time','8',
            '-windowed','-nosound','-nojoy','-log',$matchLog)
} finally { $env:UF_FOREIGN_TRACE = $oldTrace }
$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
while (!$process.WaitForExit(1000)) {
    if ([DateTime]::UtcNow -ge $deadline) {
        $process.Kill()
        throw "Foreign smoke timed out; stopped only process $($process.Id). Inspect $tracePath"
    }
}
if ($process.ExitCode -ne 0) { throw "Host exited $($process.ExitCode); inspect $tracePath" }
if (!(Test-Path (Join-Path $runtime $matchLog))) { throw "No completed mixed match; inspect $tracePath" }
$statistics = Get-Content -LiteralPath (Join-Path $runtime $matchLog) -Raw
if ($statistics -notmatch '\["LastRound"\]\s*=>\s*1') {
    throw "A completed round was not recorded: $matchLog"
}
$trace = Get-Content -LiteralPath $tracePath -Raw
if ($trace -notmatch '\[foreign\] bound') { throw 'Foreign runtime was not bound.' }
if ($trace -notmatch 'action=(2|3) ') { throw 'Sampled host AI input did not produce foreign walking.' }
if ($trace -notmatch 'action=(12|15|20) .*y=-') { throw 'Sampled host AI input did not produce a foreign jump.' }
if ($trace -notmatch '\[foreign-frame\].*rendered=true') { throw 'Foreign sprite was not uploaded for rendering.' }
Write-Output "Mixed native/foreign locomotion smoke passed: $tracePath"
Write-Output 'Checks runtime binding, sampled AI input, locomotion and sprite upload. Use smoke-melee.ps1 for combat evidence; human/visual acceptance remains open.'
