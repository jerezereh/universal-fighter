[CmdletBinding()]
param([ValidateRange(30,600)][int]$TimeoutSeconds = 120)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/host-baseline'
# Authored native states/boxes make this a contact test, independent of random AI.
$cases = @(
    @{ Name='foreign-hit'; Native='high'; Input='melee'; Attacker='true'; Target='false'; Result=1 },
    @{ Name='native-hit'; Native='high'; Input='receive'; Attacker='false'; Target='true'; Result=1 },
    @{ Name='high-block'; Native='high'; Input='guard-high'; Attacker='false'; Target='true'; Result=2 },
    @{ Name='low-block'; Native='low'; Input='guard-low'; Attacker='false'; Target='true'; Result=2 },
    @{ Name='overhead-hit'; Native='high'; Input='guard-low'; Attacker='false'; Target='true'; Result=1 },
    @{ Name='low-hit'; Native='low'; Input='guard-high'; Attacker='false'; Target='true'; Result=1 },
    @{ Name='knockdown'; Native='down'; Input='receive'; Attacker='false'; Target='true'; Result=1 },
    @{ Name='foreign-ko'; Native='high'; Input='receive'; Attacker='false'; Target='true'; Result=1; Life=1 }
)
foreach ($case in $cases) {
    $runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
    $matchLog = "melee-$($case.Name)-$runId.txt"
    $tracePath = Join-Path $runtime "melee-$($case.Name)-$runId.stderr.txt"
    $oldTrace, $oldProbe = $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE
    $life = if ($case.Life) { $case.Life } else { 1000 }
    try {
        $env:UF_FOREIGN_TRACE = '1'
        $env:UF_FOREIGN_INPUT_PROBE = $case.Input
        $process = Start-Process -FilePath (Join-Path $runtime 'Ikemen_GO.exe') -WorkingDirectory $runtime `
            -WindowStyle Hidden -PassThru -RedirectStandardError $tracePath `
            -ArgumentList @('-p1',"uf-probe/$($case.Native).def",'-p2','kof13/kof13.def','-p1.ai','0','-p2.ai','8',
                '-p2.life',"$life",'-rounds','1','-time','8','-windowed','-nosound','-nojoy','-log',$matchLog)
    } finally { $env:UF_FOREIGN_TRACE = $oldTrace; $env:UF_FOREIGN_INPUT_PROBE = $oldProbe }
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while (!$process.WaitForExit(1000)) {
        if ([DateTime]::UtcNow -ge $deadline) {
            $process.Kill()
            throw "Melee smoke timed out; stopped only process $($process.Id). Inspect $tracePath"
        }
    }
    if ($process.ExitCode -ne 0) { throw "Host exited $($process.ExitCode); inspect $tracePath" }
    if (!(Test-Path (Join-Path $runtime $matchLog))) { throw "No completed match; inspect $tracePath" }
    $statistics = Get-Content -LiteralPath (Join-Path $runtime $matchLog) -Raw
    if ($statistics -notmatch '\["LastRound"\]\s*=>\s*[1-9]\d*') { throw 'A complete round was not recorded.' }
    $trace = Get-Content -LiteralPath $tracePath -Raw
    $pattern = "\[mixed-contact\].*foreign=$($case.Attacker) defender=\d+ foreign=$($case.Target) result=$($case.Result)"
    if ($trace -notmatch $pattern) { throw "Expected $($case.Name) contact absent; inspect $tracePath" }
    if ($case.Result -eq 2 -and $trace -match '\[mixed-contact\].*foreign=false defender=\d+ foreign=true result=1') {
        throw "Guard scenario accepted an unguarded hit: $tracePath"
    }
    $seen = @{}
    foreach ($contact in [regex]::Matches($trace, '\[mixed-contact\] attacker=(\d+) foreign=true defender=(\d+) foreign=false result=\d+ life=\d+ activation=(\d+)')) {
        $key = "$($contact.Groups[1].Value)/$($contact.Groups[2].Value)/$($contact.Groups[3].Value)"
        if ($seen.ContainsKey($key)) { throw "Duplicate foreign normal contact $key in $tracePath" }
        $seen[$key] = $true
    }
    $lives = [regex]::Matches($statistics, '\["Life"\]\s*=>\s*(\d+)')
    $defenderIndex = if ($case.Target -eq 'true') { 1 } else { 0 }
    $expectedLife = if ($case.Target -eq 'true') { $life } else { 1000 }
    $lostLife = $false
    for ($index = $defenderIndex; $index -lt $lives.Count; $index += 2) {
        $lostLife = $lostLife -or [int]$lives[$index].Groups[1].Value -lt $expectedLife
    }
    if ($lives.Count -lt 2 -or ($case.Result -eq 1 -and !$lostLife) -or ($case.Result -eq 2 -and $lostLife)) {
        throw "Unexpected defender life result: $matchLog"
    }
    if ($case.Name -eq 'knockdown' -and $trace -notmatch 'action=161 .*y=0.000') { throw 'Ground down pose was not observed.' }
    if ($case.Name -eq 'foreign-ko' -and $statistics -notmatch '\["WinKO"\]\s*=>\s*true') { throw 'Lethal contact did not reach host KO.' }
    Write-Output "Mixed melee $($case.Name) passed: $tracePath ($($seen.Count) unique foreign contacts)."
}
Write-Output 'Melee fixture matrix passed: both directions, high/low guard and mismatches, knockdown, lethal hitstop/KO and foreign duplicate protection.'
Write-Output 'Uses authored native geometry and local input probes. KFM regression, human/visual acceptance and full host rollback are separate checks.'
