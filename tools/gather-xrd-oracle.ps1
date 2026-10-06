<# Cache SIGN's missing x86 DirectX DLLs from the user's official Steam redistributables.
No installer, registry edit, global PATH edit or write to the source game is performed.
Use this folder only in the child source-game process's PATH for offline checks.
#>
[CmdletBinding()]
param([string]$CabinetRoot = 'C:/Program Files (x86)/Steam/steamapps/common/Steamworks Shared/_CommonRedist/DirectX/Jun2010')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$output = Join-Path $root ('local-cache/xrd-tools/directx-x86/' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $output -Force | Out-Null
$selected = @(
    @('APR2007_xinput_x86.cab', 'XInput1_3.dll'),
    @('Feb2010_X3DAudio_x86.cab', 'X3DAudio1_7.dll'),
    @('Jun2010_XAudio_x86.cab', 'XAPOFX1_5.dll')
)
$records = @()
foreach ($entry in $selected) {
    $cabinet = Join-Path $CabinetRoot $entry[0]
    if (!(Test-Path -LiteralPath $cabinet -PathType Leaf)) { throw "Official Steam DirectX cabinet missing: $cabinet" }
    $before = (Get-FileHash -LiteralPath $cabinet -Algorithm SHA256).Hash
    & (Join-Path $env:WINDIR 'System32/expand.exe') "-F:$($entry[1])" $cabinet $output | Out-Null
    if ($LASTEXITCODE) { throw "DirectX cabinet extraction failed: $cabinet" }
    $dll = Join-Path $output $entry[1]
    $bytes = [System.IO.File]::ReadAllBytes($dll)
    if ($bytes.Length -lt 64 -or [BitConverter]::ToUInt16($bytes, 0) -ne 0x5a4d) { throw 'Invalid DLL DOS header.' }
    $pe = [BitConverter]::ToInt32($bytes, 60)
    if ($pe -lt 64 -or $pe + 6 -gt $bytes.Length -or [BitConverter]::ToUInt32($bytes, $pe) -ne 0x4550 -or
        [BitConverter]::ToUInt16($bytes, $pe + 4) -ne 0x14c) { throw 'Expected an x86 PE DLL.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $dll
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
        throw "Unverified Microsoft redistributable DLL: $dll ($($signature.Status))"
    }
    if ((Get-FileHash -LiteralPath $cabinet -Algorithm SHA256).Hash -ne $before) { throw 'Source cabinet changed during extraction.' }
    $records += [ordered]@{ cabinet = $cabinet; cabinet_sha256 = $before; name = $entry[1]
        sha256 = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash; machine = 'x86'; signature = 'Valid' }
}
$receipt = [ordered]@{ schema = 1; complete = $true; directory = $output; dlls = $records }
$json = $receipt | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText((Join-Path $output 'receipt.json'), $json)
[System.IO.File]::WriteAllText((Join-Path $root 'local-cache/xrd-tools/oracle-dependencies.json'), $json)
Write-Output "Verified three Microsoft x86 DLLs in $output. Set only the offline game child's PATH to include this folder."
