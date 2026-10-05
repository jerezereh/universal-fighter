[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'upstreams.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.PSObject.Properties) {
    $source = $entry.Value
    $target = Join-Path $projectRoot $source.path
    if (Test-Path -LiteralPath $target) {
        $actual = & git -C $target rev-parse HEAD
        if ($LASTEXITCODE -ne 0) { throw "Cannot read checkout: $target" }
        if ($actual -ne $source.commit) { throw "Revision differs at $target. Preserve local work and resolve manually." }
        Write-Output "$($entry.Name): pinned revision present"
        continue
    }
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    & git -C $target init --quiet
    if ($LASTEXITCODE -ne 0) { throw "git init failed: $target" }
    & git -C $target remote add origin $source.url
    if ($LASTEXITCODE -ne 0) { throw "remote setup failed: $target" }
    & git -C $target fetch --depth 1 origin $source.commit
    if ($LASTEXITCODE -ne 0) { throw "fetch failed: $target" }
    & git -C $target checkout --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw "checkout failed: $target" }
}
