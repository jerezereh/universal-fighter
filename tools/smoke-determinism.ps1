[CmdletBinding()]
param([ValidateRange(30,600)][int]$TimeoutSeconds = 180, [string[]]$Scenario = @())
$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/host-baseline'
$cases = @(
    @{ Name='melee'; Native='high'; Input='melee'; Phases=@('startup','contact','hitstop') },
    @{ Name='foreign-projectile'; Native='idle'; Input='projectile'; Phases=@('startup','projectile','contact','hitstop') },
    @{ Name='native-projectile'; Native='projectile'; Input='receive'; Phases=@('projectile','contact','hitstop') },
    @{ Name='pause'; Native='pause'; Input='projectile'; Phases=@('pause','projectile') },
    @{ Name='ko-reset'; Native='projectile'; Input='receive'; Life=1; Rounds=2; Phases=@('ko','reset','contact','hitstop') }
)
if ($Scenario.Count) {
    foreach ($name in $Scenario) { if ($name -notin $cases.Name) { throw "Unknown scenario: $name" } }
    $cases = @($cases | Where-Object { $_.Name -in $Scenario })
}
foreach ($case in $cases) {
    $runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
    $prefix = "sync-$($case.Name)-$runId"
    $config = Get-Content -LiteralPath (Join-Path $runtime 'save/config.ini') -Raw
    foreach ($setting in @{ DesyncTest=1; DesyncTestFrames=8; DesyncTestAI=1; GgpoLogsEnabled=1; StateLogsEnabled=1 }.GetEnumerator()) {
        $pattern = '(?m)^Rollback\.' + [regex]::Escape($setting.Key) + '\s*=.*$'
        if ($config -notmatch $pattern) { throw "Missing rollback setting: $($setting.Key)" }
        $config = [regex]::Replace($config,$pattern,"Rollback.$($setting.Key) = $($setting.Value)")
    }
    Set-Content -LiteralPath (Join-Path $runtime "$prefix.ini") -Value $config -Encoding utf8
    $rounds = if ($case.Rounds) { $case.Rounds } else { 1 }
    $life = if ($case.Life) { $case.Life } else { 1000 }
    $oldTrace, $oldProbe, $oldSync = $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_MIXED_DIAGNOSTICS
    $previousLogs = @(Get-ChildItem (Join-Path $runtime 'save/logs') -Filter 'Rollback-Desync-Test-*.log' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    try {
        $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_MIXED_DIAGNOSTICS = '1', $case.Input, '1'
        $process = Start-Process -FilePath (Join-Path $runtime 'Ikemen_GO.exe') -WorkingDirectory $runtime `
            -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $runtime "$prefix.stderr.txt") `
            -ArgumentList @('-config',"$prefix.ini",'-p1',"uf-probe/$($case.Native).def",'-p2','kof13/kof13.def',
                '-p1.ai','0','-p2.ai','8','-p2.life',"$life",'-rounds',"$rounds",'-time','8','-windowed','-nosound','-nojoy','-log',"$prefix.txt")
    } finally { $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_MIXED_DIAGNOSTICS = $oldTrace, $oldProbe, $oldSync }
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while (!$process.WaitForExit(1000)) {
        if ([DateTime]::UtcNow -ge $deadline) { $process.Kill(); throw "Sync test timed out: $prefix" }
    }
    if ($process.ExitCode -ne 0) { throw "Sync host exited $($process.ExitCode): $prefix.stderr.txt" }
    $trace = Get-Content -LiteralPath (Join-Path $runtime "$prefix.stderr.txt") -Raw
    $statistics = Get-Content -LiteralPath (Join-Path $runtime "$prefix.txt") -Raw
    if ($statistics -notmatch '\["LastRound"\]\s*=>\s*[1-9]\d*') { throw "No completed match: $prefix" }
    $newLogs = @(Get-ChildItem (Join-Path $runtime 'save/logs') -Filter 'Rollback-Desync-Test-*.log' | Where-Object { $_.FullName -notin $previousLogs })
    if ($newLogs.Count -ne 1) { throw "Expected one new GGPO verification log: $prefix" }
    $ggpo = Get-Content -LiteralPath $newLogs[0].FullName -Raw
    if (($ggpo + $trace) -match 'does not match|RaiseSyncError|RaiseDesyncError|panic:') { throw "Host sync mismatch: $prefix" }
    $verified = [regex]::Matches($ggpo,'Checksum \d+ for frame \d+ matches\.').Count
    $phases = @{}; $replayed = @{}; $pausedCore = @{}
    foreach ($entry in [regex]::Matches($trace,'\[mixed-sync\] round=(\d+) tick=(\d+) replay=(true|false) checksum=([0-9a-f]+) core=(\d+) phases=([^\r\n]*)')) {
        if ($entry.Groups[3].Value -eq 'false') {
            foreach ($phase in $entry.Groups[6].Value.Split(',')) { $phases[$phase] = $true }
            if ($entry.Groups[6].Value.Split(',') -contains 'pause') {
                $pauseKey = "$($entry.Groups[1].Value)/$($entry.Groups[5].Value)"
                $pausedCore[$pauseKey] = 1 + [int]$pausedCore[$pauseKey]
            }
        } else {
            foreach ($phase in $entry.Groups[6].Value.Split(',')) { $replayed[$phase] = $true }
        }
    }
    if ($verified -lt 30) { throw "Insufficient verified replay frames: $prefix" }
    foreach ($phase in $case.Phases) { if (!$phases.ContainsKey($phase) -or !$replayed.ContainsKey($phase)) { throw "Missing $phase save/replay coverage: $prefix" } }
    if ($case.Name -eq 'pause' -and !(@($pausedCore.Values | Where-Object { $_ -ge 2 }).Count)) { throw 'Foreign frame clock did not freeze across host pause.' }
    if ($case.Name -eq 'ko-reset' -and ($statistics -notmatch '\["LastRound"\]\s*=>\s*[2-9]\d*' -or $statistics -notmatch '\["WinKO"\]\s*=>\s*true')) { throw 'KO and restarted round were not observed.' }
    Write-Output "Mixed sync $($case.Name) passed: $verified GGPO-verified replay frames; $prefix.stderr.txt; $($newLogs[0].Name)"
}
Write-Output "All $($cases.Count) requested offline sync scenes passed. Visual/controls and online netplay remain separate."
