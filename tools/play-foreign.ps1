param([switch]$Debug, [switch]$Practice)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/host-baseline'
if (!(Test-Path (Join-Path $runtime 'chars/kof13/foreign.json'))) { throw 'Import local KOF XIII data first.' }
# This is the interactive play command; the visible window is intentional.
$oldDebug, $oldTrace, $oldProbe = $env:UF_FOREIGN_DEBUG, $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE
try {
    if ($Debug) { $env:UF_FOREIGN_DEBUG = '1' }
    $arguments = @('-p1','kof13/kof13.def','-p1.ai','0','-windowed')
    if ($Practice) {
        $env:UF_FOREIGN_TRACE = '1'
        $env:UF_FOREIGN_INPUT_PROBE = ''
        $run = 'practice-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
        $arguments += @('-p2','uf-probe/idle.def','-p2.ai','0','-time','-1','-log',"$run.txt")
        Start-Process -FilePath (Join-Path $runtime 'Ikemen_GO.exe') -WorkingDirectory $runtime `
            -PassThru -RedirectStandardError (Join-Path $runtime "$run.stderr.txt") -ArgumentList $arguments
        Write-Output "Input trace: $runtime/$run.stderr.txt"
    } else {
        $arguments += @('-p2','kfm','-p2.ai','6')
        Start-Process -FilePath (Join-Path $runtime 'Ikemen_GO.exe') -WorkingDirectory $runtime -ArgumentList $arguments
    }
    Write-Output 'P1: arrows move/jump/crouch; Z normal; X standing ground flame.'
    Write-Output 'Debug: Pause freezes/resumes; Scroll Lock advances one paused frame; Ctrl+C boxes; Ctrl+D panel; F8 clears console.'
} finally { $env:UF_FOREIGN_DEBUG, $env:UF_FOREIGN_TRACE, $env:UF_FOREIGN_INPUT_PROBE = $oldDebug, $oldTrace, $oldProbe }
