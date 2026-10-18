param([switch]$InstallFrontend)
$ErrorActionPreference = 'Stop'
$integrationDir = $PSScriptRoot
$source = Get-Content -LiteralPath (Join-Path $integrationDir 'retouch-source.json') -Encoding UTF8 | ConvertFrom-Json
$checkout = Join-Path $integrationDir 'ai-retouch-agent'
$patch = Join-Path $integrationDir 'retouch-photoai.patch'
if (-not (Test-Path -LiteralPath $checkout)) {
    git clone $source.repository $checkout
    if ($LASTEXITCODE -ne 0) { throw 'Clone failed.' }
    git -C $checkout checkout --detach $source.commit
    if ($LASTEXITCODE -ne 0) { throw 'Checkout failed.' }
}
$revision = git -C $checkout rev-parse HEAD
if ($revision -ne $source.commit) { throw 'Upstream revision differs from the pinned source. Preserve local work and resolve the version before applying this patch.' }
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
git -C $checkout apply --reverse --check $patch 2>$null
$alreadyApplied = $LASTEXITCODE -eq 0
$ErrorActionPreference = $previousPreference
if (-not $alreadyApplied) {
    git -C $checkout apply --check $patch
    if ($LASTEXITCODE -ne 0) { throw 'Patch conflicts; no files were overwritten.' }
    git -C $checkout apply $patch
    if ($LASTEXITCODE -ne 0) { throw 'Patch failed.' }
}
if ($InstallFrontend) {
    Push-Location (Join-Path $checkout 'frontend')
    try {
        npm.cmd install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency install failed.' }
    } finally { Pop-Location }
}
Write-Host 'Retouch checkout and PhotoAI adapter are ready. See docs/retouch-integration.md for service startup.'
