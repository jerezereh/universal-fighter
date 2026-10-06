[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'bootstrap.ps1')
$output = Join-Path $root 'local-cache/xrd-tools'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$compiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
if (!(Test-Path -LiteralPath $compiler)) { throw 'The .NET Framework C# compiler is required.' }
$source = Join-Path $root 'tools/references/xrd-decrypt/GGXrdRevelator'
& $compiler /nologo "/out:$(Join-Path $output 'GGXrdRevelator.exe')" (Join-Path $source 'Program.cs') (Join-Path $source 'MersenneTwister.cs')
if ($LASTEXITCODE) { throw 'SIGN reader build failed.' }
$bash = Join-Path $root 'local-cache/msys64/usr/bin/bash.exe'
if (!(Test-Path -LiteralPath $bash)) { throw 'Gather the existing project MSYS2 toolchain first.' }
$posixRoot = '/' + $root.Substring(0,1).ToLower() + $root.Substring(2).Replace('\','/')
$oldSystem, $oldInvoking = $env:MSYSTEM, $env:CHERE_INVOKING
try {
    $env:MSYSTEM, $env:CHERE_INVOKING = 'MINGW64', '1'
    & $bash --login "$posixRoot/tools/build-xrd-tools.sh" $posixRoot
    if ($LASTEXITCODE) { throw 'Safe LZO decoder build failed.' }
} finally { $env:MSYSTEM, $env:CHERE_INVOKING = $oldSystem, $oldInvoking }
Write-Output "SIGN reader and safe LZO DLL built in $output. UE Viewer uses its pinned repository binary."
