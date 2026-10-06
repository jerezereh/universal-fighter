[CmdletBinding()]
param([switch]$Sync, [string[]]$Scenario = @(), [ValidateRange(30,600)][int]$TimeoutSeconds = 180)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/host-baseline'
$cases = @(
    @{ Name='parry'; P1='uf-synthetic/airdash-test.def'; P2='uf-synthetic/parry-test.def' },
    @{ Name='miss'; P1='uf-synthetic/airdash-test.def'; P2='uf-synthetic/parry-test.def' },
    @{ Name='barrier'; P1='uf-synthetic/parry-test.def'; P2='uf-synthetic/airdash-test.def' },
    @{ Name='cancel'; P1='uf-synthetic/airdash-test.def'; P2='uf-synthetic/parry-test.def' },
    @{ Name='reset'; P1='uf-synthetic/parry-test.def'; P2='uf-synthetic/airdash-test.def'; Life=1; Rounds=2 },
    @{ Name='native-parry'; P1='uf-probe/high.def'; P2='uf-synthetic/parry-test.def' }
)
if ($Scenario.Count) {
    foreach ($name in $Scenario) { if ($name -notin $cases.Name) { throw "Unknown authored scene: $name" } }
    $cases = @($cases | Where-Object { $_.Name -in $Scenario })
}
foreach ($case in $cases) {
    $prefix = 'synthetic-' + $case.Name + '-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
    $config = Get-Content -LiteralPath (Join-Path $runtime 'save/config.ini') -Raw
    $rewind = if ($Sync) { 8 } else { 0 }
    foreach ($setting in @{ DesyncTest=[int][bool]$Sync; DesyncTestFrames=$rewind; DesyncTestAI=[int][bool]$Sync; GgpoLogsEnabled=1; StateLogsEnabled=1 }.GetEnumerator()) {
        $pattern = '(?m)^Rollback\.' + [regex]::Escape($setting.Key) + '\s*=.*$'
        if ($config -notmatch $pattern) { throw "Missing rollback setting: $($setting.Key)" }
        $config = [regex]::Replace($config, $pattern, "Rollback.$($setting.Key) = $($setting.Value)")
    }
    Set-Content -LiteralPath (Join-Path $runtime "$prefix.ini") -Value $config -Encoding utf8
    $oldTrace, $oldProbe, $oldSync, $oldSynthetic = $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_MIXED_DIAGNOSTICS, $env:UF_SYNTHETIC_PROBE
    $previousLogs = @(Get-ChildItem (Join-Path $runtime 'save/logs') -Filter 'Rollback-Desync-Test-*.log' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $life = if ($case.Life) { $case.Life } else { 1000 }
    $rounds = if ($case.Rounds) { $case.Rounds } else { 1 }
    try {
        $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_MIXED_DIAGNOSTICS, $env:UF_SYNTHETIC_PROBE = '1', '', '1', $case.Name
        $process = Start-Process -FilePath (Join-Path $runtime 'Ikemen_GO.exe') -WorkingDirectory $runtime -WindowStyle Hidden -PassThru `
            -RedirectStandardError (Join-Path $runtime "$prefix.stderr.txt") `
            -ArgumentList @('-config',"$prefix.ini",'-p1',$case.P1,'-p2',$case.P2,'-p1.ai','0','-p2.ai','0',
                '-p2.life',"$life",'-rounds',"$rounds",'-time','16','-windowed','-nosound','-nojoy','-log',"$prefix.txt")
    } finally { $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_MIXED_DIAGNOSTICS, $env:UF_SYNTHETIC_PROBE = $oldTrace, $oldProbe, $oldSync, $oldSynthetic }
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while (!$process.WaitForExit(1000)) {
        if ([DateTime]::UtcNow -ge $deadline) { $process.Kill(); throw "Authored scene timed out: $prefix" }
    }
    if ($process.ExitCode -ne 0) { throw "Host exited $($process.ExitCode): $prefix" }
    $trace = Get-Content -LiteralPath (Join-Path $runtime "$prefix.stderr.txt") -Raw
    $stats = Get-Content -LiteralPath (Join-Path $runtime "$prefix.txt") -Raw
    if ($stats -notmatch '\["LastRound"\]\s*=>\s*[1-9]\d*') { throw "No completed match: $prefix" }
    if ($trace -match 'panic:|WARNING.*[Ss]tate') { throw "Runtime warning: $prefix" }
    $parries = [regex]::Matches($trace,'\[ruleset-contact\].*parried=true').Count
    $barriers = [regex]::Matches($trace,'\[ruleset-contact\].*barrier=true').Count
    switch ($case.Name) {
        { $_ -in 'parry','native-parry' } {
            if ($parries -lt 2 -or $trace -match '\[ruleset-contact\].*parried=true.*damage=[1-9]') { throw "Parry evidence absent/incorrect: $prefix" }
            $lives = [regex]::Matches($stats,'\["Life"\]\s*=>\s*(\d+)')
            if (!$lives.Count -or @($lives | Where-Object { [int]$_.Groups[1].Value -ne 1000 }).Count) { throw "Parry match lost canonical health: $prefix" }
            if ($case.Name -eq 'parry' -and $trace -match '\[ruleset-frame\] owner=0.*cancels:[1-9]') { throw "Parried attack enabled cancel: $prefix" }
        }
        'miss' { if ($parries -ne 0 -or $trace -notmatch '\[ruleset-contact\].*damage=[1-9]') { throw "Window miss not proved: $prefix" } }
        'barrier' {
            if ($barriers -ne 10 -or $trace -notmatch 'meter:0' -or $trace -notmatch '\[ruleset-contact\].*barrier=false.*damage=3 ') { throw "Barrier exhaustion not proved: $prefix" }
        }
        'cancel' {
            if ($trace -notmatch '\[ruleset-frame\] owner=0.*dashes:[1-9]' -or $trace -notmatch '\[ruleset-frame\] owner=0.*cancels:[1-9]') { throw "Dash and confirmed cancel not proved: $prefix" }
        }
        'reset' {
            if ($stats -notmatch '\["LastRound"\]\s*=>\s*[2-9]\d*' -or $stats -notmatch '\["WinKO"\]\s*=>\s*true') { throw "KO/reset absent: $prefix" }
            # Guest animation clocks also advance during the native round introduction.
            if ($trace -notmatch '\[foreign-reset\].*round=2' -or $trace -notmatch '\[ruleset-frame\] owner=1 round=2 frame=\d+ .*meter:100 .*dashes:0 cancels:0 barriers:0') { throw "Round reset left private state: $prefix" }
        }
    }
    $seen = @{}
    foreach ($contact in [regex]::Matches($trace,'\[mixed-contact\] attacker=(\d+) foreign=true defender=(\d+) foreign=true result=\d+ life=\d+ activation=(\d+) projectile=false')) {
        # Activation IDs restart with rounds; the native ledger is also round-owned.
        $prior = $trace.Substring(0,$contact.Index)
        $round = [regex]::Matches($prior,'\[ruleset-frame\].*? round=(\d+)')[-1].Groups[1].Value
        $key = "$round/$($contact.Groups[1].Value)/$($contact.Groups[2].Value)/$($contact.Groups[3].Value)"
        if ($seen.ContainsKey($key)) { throw "Duplicate contact commit: $key; $prefix" }
        $seen[$key] = $true
    }
    $verified = 0
    if ($Sync) {
        $logs = @(Get-ChildItem (Join-Path $runtime 'save/logs') -Filter 'Rollback-Desync-Test-*.log' | Where-Object { $_.FullName -notin $previousLogs })
        if ($logs.Count -ne 1) { throw "Expected one GGPO log: $prefix" }
        $ggpo = Get-Content -LiteralPath $logs[0].FullName -Raw
        if (($ggpo + $trace) -match 'does not match|RaiseSyncError|RaiseDesyncError|panic:') { throw "Replay mismatch: $prefix" }
        $verified = [regex]::Matches($ggpo,'Checksum \d+ for frame \d+ matches\.').Count
        if ($verified -lt 100 -or $trace -notmatch '\[mixed-sync\].*replay=true') { throw "Insufficient replay coverage: $prefix" }
    }
    Write-Output "Authored $($case.Name) passed: parries=$parries barriers=$barriers unique=$($seen.Count) verified=$verified; $prefix.stderr.txt"
}
