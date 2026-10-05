# Windows x64; installs a project-local MSYS2 without changing machine PATH/registry.
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$Build
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($CheckOnly -and $Build) { throw '-CheckOnly and -Build cannot be combined.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$cache = Join-Path $projectRoot 'local-cache'
$msysRoot = Join-Path $cache 'msys64'
$bash = Join-Path $msysRoot 'usr/bin/bash.exe'
if ($env:OS -ne 'Windows_NT' -or ![Environment]::Is64BitOperatingSystem) {
    throw 'This setup targets Windows x64.'
}
if ($projectRoot -notmatch '^[A-Za-z]:\\[A-Za-z0-9_.\\-]+$') {
    throw 'IKEMEN/MSYS2 builds require an ASCII workspace path without spaces or shell metacharacters.'
}
function Invoke-Msys([string]$Script, [string[]]$Arguments = @(), [switch]$AllowCoreRestart) {
    $previousSystem = $env:MSYSTEM
    $previousPath = $env:CHERE_INVOKING
    try {
        $env:MSYSTEM = 'MINGW64'
        $env:CHERE_INVOKING = '1'
        & $bash --login $Script @Arguments | Tee-Object -Variable stepOutput
        $stepExit = $LASTEXITCODE
        if ($stepExit -ne 0) {
            if ($AllowCoreRestart -and $stepExit -eq 1 -and
                ($stepOutput -join "`n") -match 'To complete this update all MSYS2 processes') {
                Write-Output 'MSYS2 closed its shell to finish a core update; continuing in a fresh shell.'
            } else { throw "MSYS2 step failed ($stepExit): $Script" }
        }
    } finally {
        $env:MSYSTEM = $previousSystem
        $env:CHERE_INVOKING = $previousPath
    }
}
function ConvertTo-MsysPath([string]$Path) {
    '/' + $Path.Substring(0,1).ToLowerInvariant() + '/' + $Path.Substring(3).Replace('\','/')
}
if ($CheckOnly) {
    if (!(Test-Path -LiteralPath $bash)) { throw "Project-local MSYS2 missing. Run this script without -CheckOnly: $msysRoot" }
    Invoke-Msys (ConvertTo-MsysPath (Join-Path $PSScriptRoot 'verify-dependencies.sh')) @((ConvertTo-MsysPath $projectRoot))
    exit 0
}
New-Item -ItemType Directory -Path $cache -Force | Out-Null
if (!(Test-Path -LiteralPath $bash)) {
    if (Test-Path -LiteralPath $msysRoot) { throw "Partial MSYS2 installation at $msysRoot. Inspect it before retrying; setup will not overwrite it." }
    # Resolve a versioned archive, then verify its published SHA256 before execution.
    $releases = Invoke-RestMethod 'https://api.github.com/repos/msys2/msys2-installer/releases?per_page=30'
    $release = $releases | Where-Object { !$_.prerelease -and !$_.draft -and $_.tag_name -match '^\d{4}-\d{2}-\d{2}$' } | Select-Object -First 1
    if (!$release) { throw 'No dated stable MSYS2 release found.' }
    $asset = @($release.assets | Where-Object { $_.name -match '^msys2-base-x86_64-\d+\.sfx\.exe$' })
    if ($asset.Count -ne 1) { throw 'Expected exactly one MSYS2 x64 self-extracting archive.' }
    $download = Join-Path $cache $asset[0].name
    Invoke-WebRequest $asset[0].browser_download_url -OutFile $download -UseBasicParsing
    $expected = ''
    if ($asset[0].PSObject.Properties['digest'] -and $asset[0].digest -match '^sha256:([0-9a-f]{64})$') {
        $expected = $Matches[1]
    } else {
        $checksumText = (Invoke-WebRequest ($asset[0].browser_download_url + '.sha256') -UseBasicParsing).Content
        $expected = [regex]::Match([string]$checksumText, '(?i)\b[0-9a-f]{64}\b').Value
    }
    if (!$expected -or (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ne $expected) {
        throw 'MSYS2 archive checksum mismatch or missing checksum.'
    }
    @{ url = $asset[0].browser_download_url; sha256 = $expected; release = $release.tag_name } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $cache 'msys2-download.json')
    & $download '-y' "-o$cache"
    if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $bash)) { throw 'MSYS2 archive extraction failed.' }
}
# Separate shells accommodate the MSYS2 core update/restart boundary.
Invoke-Msys (ConvertTo-MsysPath (Join-Path $PSScriptRoot 'install-dependencies.sh')) @('core') -AllowCoreRestart
Invoke-Msys (ConvertTo-MsysPath (Join-Path $PSScriptRoot 'install-dependencies.sh')) @('packages')
$originalPath = $env:PATH
try {
    $env:PATH = (Join-Path $msysRoot 'usr/bin') + ';' + $originalPath
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
} finally { $env:PATH = $originalPath }
Invoke-Msys (ConvertTo-MsysPath (Join-Path $PSScriptRoot 'verify-dependencies.sh')) @((ConvertTo-MsysPath $projectRoot))
if ($Build) {
    Invoke-Msys (ConvertTo-MsysPath (Join-Path $PSScriptRoot 'build-host.sh')) @((ConvertTo-MsysPath $projectRoot))
}
Write-Output 'Dependencies gathered. Package versions and verification output are in local-cache/dependency-report.txt.'
