param([ValidateSet('parry-test','airdash-test')][string]$Rules = 'airdash-test', [switch]$Practice)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/host-baseline'
if (!(Test-Path (Join-Path $runtime "chars/uf-synthetic/$Rules.def"))) { throw 'Build the updated runtime first.' }
$oldDebug, $oldProbe, $oldSynthetic = $env:UF_FOREIGN_DEBUG, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_SYNTHETIC_PROBE
try {
    $env:UF_FOREIGN_DEBUG, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_SYNTHETIC_PROBE = '1', '', ''
    $opponent = if ($Rules -eq 'parry-test') { 'airdash-test' } else { 'parry-test' }
    $p2 = if ($Practice) { 'uf-probe/idle.def' } else { "uf-synthetic/$opponent.def" }
    $ai = if ($Practice) { '0' } else { '6' }
    # This launcher is explicitly interactive; the visible SDL window is intentional.
    Start-Process -FilePath (Join-Path $runtime 'Ikemen_GO.exe') -WorkingDirectory $runtime `
        -ArgumentList @('-p1',"uf-synthetic/$Rules.def",'-p2',$p2,'-p1.ai','0','-p2.ai',$ai,'-windowed','-time','-1')
    Write-Output 'Arrows: move/jump/crouch. Z: ground normal. Pause: freeze/resume. Scroll Lock: one paused frame.'
    if ($Rules -eq 'parry-test') { Write-Output 'X: six-tick ground parry, eighteen-tick cooldown; release before retrying.' }
    else { Write-Output 'X in air: dash (20 meter, once per airtime). X after a normal hits/is blocked: cancel (15 meter). Hold Back+X: ground resource guard (10 per contact, waives chip). No meter regeneration; round reset restores 100.' }
} finally { $env:UF_FOREIGN_DEBUG, $env:UF_FOREIGN_INPUT_PROBE, $env:UF_SYNTHETIC_PROBE = $oldDebug, $oldProbe, $oldSynthetic }
