[CmdletBinding()]
param([ValidateRange(30,600)][int]$TimeoutSeconds = 180)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $projectRoot 'artifacts/host-baseline'
$executable = Join-Path $runtime 'Ikemen_GO.exe'
if (!(Test-Path -LiteralPath $executable)) { throw 'Build the host with gather-dependencies.ps1 -Build first.' }
$runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
$matchLog = "baseline-$runId.txt"
$process = Start-Process -FilePath $executable -WorkingDirectory $runtime -WindowStyle Hidden -PassThru `
    -ArgumentList @('-p1','kfm','-p2','kfm','-p1.ai','8','-p2.ai','8',
        '-p1.life','100','-p2.life','100','-rounds','2','-time','20',
        '-windowed','-nosound','-nojoy','-log',$matchLog)
$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
while (!$process.WaitForExit(1000)) {
    if ([DateTime]::UtcNow -ge $deadline) {
        $process.Kill()
        throw "Baseline timed out; stopped only process $($process.Id). Check runtime logs."
    }
}
if ($process.ExitCode -ne 0) { throw "Baseline exited with code $($process.ExitCode). Check runtime logs." }
$logPath = Join-Path $runtime $matchLog
if (!(Test-Path -LiteralPath $logPath)) { throw 'Host exited without producing completed match statistics.' }
$statistics = Get-Content -LiteralPath $logPath -Raw
$round = [regex]::Match($statistics, '(?i)\["LastRound"\]\s*=>\s*(\d+)')
if (!$round.Success -or [int]$round.Groups[1].Value -lt 2) { throw "Two-round baseline was not established: $logPath" }
if ($statistics -notmatch '(?i)\["KO"\]\s*=>\s*true') { throw "No KO recorded: $logPath" }
Write-Output "Native/native baseline completed with multiple rounds and KO: $logPath"
Write-Output 'This automated match does not verify visual presentation or human controls.'
