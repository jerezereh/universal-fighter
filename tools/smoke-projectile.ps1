[CmdletBinding()]
param([ValidateRange(30,600)][int]$TimeoutSeconds = 120, [string[]]$Scenario = @())
$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/host-baseline'
$cases = @(
    @{ Name='foreign-hit'; Native='idle'; Input='projectile'; Foreign='true'; Result=1 },
    @{ Name='foreign-block'; Native='guard'; Input='projectile'; Foreign='true'; Result=2 },
    @{ Name='native-hit'; Native='projectile'; Input='receive'; Foreign='false'; Result=1 },
    @{ Name='native-high-block'; Native='projectile'; Input='guard-high'; Foreign='false'; Result=2 },
    @{ Name='native-low-block'; Native='projectile'; Input='guard-low'; Foreign='false'; Result=2 },
    @{ Name='miss-cleanup'; Native='miss'; Input='projectile'; Foreign='true'; Result=0 },
    @{ Name='native-rounds'; Native='projectile'; Input='receive'; Foreign='false'; Result=1; P2Life=1; Rounds=2 },
    @{ Name='foreign-rounds'; Native='idle'; Input='projectile'; Foreign='true'; Result=1; P1Life=1; Rounds=2 }
)
if ($Scenario.Count) {
    foreach ($name in $Scenario) { if ($name -notin $cases.Name) { throw "Unknown scenario: $name" } }
    $cases = @($cases | Where-Object { $_.Name -in $Scenario })
}
foreach ($case in $cases) {
    $runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
    $matchLog = "projectile-$($case.Name)-$runId.txt"
    $tracePath = Join-Path $runtime "projectile-$($case.Name)-$runId.stderr.txt"
    $p1Life = if ($case.P1Life) { $case.P1Life } else { 1000 }
    $p2Life = if ($case.P2Life) { $case.P2Life } else { 1000 }
    $rounds = if ($case.Rounds) { $case.Rounds } else { 1 }
    $oldTrace, $oldProbe = $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE
    try {
        $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE = '1', $case.Input
        $process = Start-Process -FilePath (Join-Path $runtime 'Ikemen_GO.exe') -WorkingDirectory $runtime `
            -WindowStyle Hidden -PassThru -RedirectStandardError $tracePath `
            -ArgumentList @('-p1',"uf-probe/$($case.Native).def",'-p2','kof13/kof13.def','-p1.ai','0','-p2.ai','8',
                '-p1.life',"$p1Life",'-p2.life',"$p2Life",'-rounds',"$rounds",'-time','8','-windowed','-nosound','-nojoy','-log',$matchLog)
    } finally { $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE = $oldTrace, $oldProbe }
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while (!$process.WaitForExit(1000)) {
        if ([DateTime]::UtcNow -ge $deadline) { $process.Kill(); throw "Projectile smoke timed out: $tracePath" }
    }
    if ($process.ExitCode -ne 0) { throw "Host exited $($process.ExitCode): $tracePath" }
    $statistics = Get-Content -LiteralPath (Join-Path $runtime $matchLog) -Raw
    $trace = Get-Content -LiteralPath $tracePath -Raw
    $lastRound = [regex]::Match($statistics, '\["LastRound"\]\s*=>\s*(\d+)')
    if (!$lastRound.Success -or [int]$lastRound.Groups[1].Value -lt $rounds) { throw "Incomplete match: $matchLog" }
    $target = if ($case.Foreign -eq 'true') { 'false' } else { 'true' }
    $pattern = "\[mixed-contact\].*foreign=$($case.Foreign) defender=\d+ foreign=$target result=$($case.Result).*projectile=true"
    if ($case.Result -ne 0 -and $trace -notmatch $pattern) { throw "Expected projectile result absent: $tracePath" }
    if ($case.Result -in 0,2 -and $trace -match '\[mixed-contact\].*result=1.*projectile=true') { throw "Unexpected unguarded projectile hit: $tracePath" }
    $lives = [regex]::Matches($statistics, '\["Life"\]\s*=>\s*(\d+)')
    $index = if ($target -eq 'true') { 1 } else { 0 }
    $initial = if ($index -eq 1) { $p2Life } else { $p1Life }
    if ($lives.Count -lt 2 -or ($case.Result -eq 1 -and [int]$lives[$index].Groups[1].Value -ge $initial) -or
        ($case.Result -in 0,2 -and [int]$lives[$index].Groups[1].Value -ne $initial)) { throw "Unexpected projectile damage: $matchLog" }
    $spawns, $contacts, $removals = @{}, @{}, @{}
    foreach ($entry in [regex]::Matches($trace, '\[foreign-projectile\] (spawn|contact|remove) owner=(\d+) entity=(\d+) round=(\d+)')) {
        $key = "$($entry.Groups[2].Value)/$($entry.Groups[4].Value)/$($entry.Groups[3].Value)"
        switch ($entry.Groups[1].Value) {
            'spawn' { if ($spawns.ContainsKey($key)) { throw "Duplicate spawn $key" }; $spawns[$key] = $true }
            'contact' { if (!$spawns.ContainsKey($key) -or $contacts.ContainsKey($key)) { throw "Duplicate/unknown projectile contact $key" }; $contacts[$key] = $true }
            'remove' { if (!$spawns.ContainsKey($key)) { throw "Unknown projectile removal $key" }; $removals[$key] = $true }
        }
    }
    if ($case.Foreign -eq 'true') {
        if (!$spawns.Count -or $removals.Count -ne $spawns.Count) { throw "Foreign entities were not all removed: $tracePath" }
        if ($case.Result -eq 0 -and $contacts.Count) { throw 'Invulnerable target accepted a projectile.' }
    }
    if ($rounds -gt 1) {
        if ($statistics -notmatch '\["WinKO"\]\s*=>\s*true' -or $trace -notmatch '\[foreign-reset\].*round=2 entities=0') { throw "KO/reset not established: $tracePath" }
        # CLI life overrides apply to the first round. Verify new contacts after
        # reset at restored host health, rather than requiring another short KO.
        $resets = [regex]::Matches($trace, '\[foreign-reset\].*round=2 entities=0')
        $reset = $resets[$resets.Count - 1]
        $secondRound = $trace.Substring($reset.Index + $reset.Length)
        if ($secondRound -notmatch $pattern) { throw "Projectile contacts did not resume after reset: $tracePath" }
        if ($case.Foreign -eq 'false' -and $secondRound -notmatch 'action=(1|2) .*y=0.000') { throw 'Foreign runtime remained in its defeated state after reset.' }
        if ($case.Foreign -eq 'false' -and ($trace -notmatch '\[foreign-ko\]' -or $trace -notmatch 'action=161 .*y=0.000')) { throw 'Foreign KO presentation was not observed.' }
        if ($case.Foreign -eq 'true' -and $trace -notmatch '\[foreign-projectile\] spawn .*entity=1 round=2') { throw 'Round reset retained the projectile activation counter.' }
    }
    Write-Output "Projectile $($case.Name) passed: $tracePath ($($spawns.Count) spawns, $($contacts.Count) contacts, $($removals.Count) removals)."
}
Write-Output "All $($cases.Count) requested projectile scenarios passed. Visual fidelity and full host rollback remain separate."
