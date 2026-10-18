param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Prepare','Infra','Migrate','Api','Worker','Smoke','PlanSmoke','Stop')]
    [string]$Action
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $root 'integrations\ai-retouch-agent\backend'
$runtime = Join-Path $root '.test_artifacts\retouch-runtime'
$bootstrap = Join-Path $root '.test_artifacts\retouch-bootstrap'
$python = Join-Path $runtime 'Scripts\python.exe'
$envFile = Join-Path $root '.test_artifacts\retouch-service.env'
$composeFile = Join-Path $root 'integrations\retouch-smoke.compose.yml'

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Exe (exit $LASTEXITCODE)" }
}

function New-Secret {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

if ($Action -eq 'Prepare') {
    if (-not (Test-Path -LiteralPath $backend)) { throw 'Run integrations/setup-retouch.ps1 first.' }
    if (-not (Test-Path -LiteralPath (Join-Path $bootstrap 'Scripts\python.exe'))) {
        Invoke-Checked 'python' @('-m','venv',$bootstrap)
    }
    $uv = Join-Path $bootstrap 'Scripts\uv.exe'
    if (-not (Test-Path -LiteralPath $uv)) {
        Invoke-Checked (Join-Path $bootstrap 'Scripts\python.exe') @('-m','pip','install','uv==0.13.1')
    }
    $previousUv = $env:UV_PROJECT_ENVIRONMENT
    try {
        $env:UV_PROJECT_ENVIRONMENT = $runtime
        Invoke-Checked $uv @('sync','--project',$backend,'--frozen','--extra','agent','--no-dev')
    } finally { $env:UV_PROJECT_ENVIRONMENT = $previousUv }
    if (-not (Test-Path -LiteralPath $envFile)) {
        $dbPassword = New-Secret
        $storagePassword = New-Secret
        $lines = @(
            "RETOUCH_DB_PASSWORD=$dbPassword",
            "RETOUCH_STORAGE_PASSWORD=$storagePassword",
            "DATABASE_URL=postgresql+asyncpg://retouch:${dbPassword}@127.0.0.1:7311/retouch",
            'REDIS_URL=redis://127.0.0.1:7312',
            'S3_ENDPOINT=http://127.0.0.1:7313',
            'S3_PUBLIC_ENDPOINT=http://127.0.0.1:7313',
            'S3_ACCESS_KEY=retouch',
            "S3_SECRET_KEY=$storagePassword",
            'S3_BUCKET=retouch',
            "JWT_SECRET=$(New-Secret)",
            'IMAGE_PROVIDER=mock',
            'DASHSCOPE_API_KEY=',
            'MATTING_PROVIDER=corner',
            'OCR_PROVIDER=none',
            'APP_ENV=development'
        )
        [IO.File]::WriteAllLines($envFile, $lines, (New-Object Text.UTF8Encoding($false)))
    }
    Write-Output 'Isolated Python environment and private local configuration ready.'
    exit 0
}

if (-not (Test-Path -LiteralPath $envFile)) { throw 'Run -Action Prepare first.' }
if ($Action -in @('Infra','Stop')) {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    $docker = if ($dockerCommand) { $dockerCommand.Source } else { 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' }
    if (-not (Test-Path -LiteralPath $docker)) { throw 'Docker Desktop is not installed.' }
    # Existing terminals may not see PATH changes made by the Docker installer.
    # The credential helper must be discoverable by the Docker CLI child process.
    $env:PATH = "$(Split-Path $docker -Parent);$env:PATH"
    Invoke-Checked $docker @('info','--format','{{.OSType}}')
    $composeArgs = @('compose','--project-name','photoai-retouch-smoke','--env-file',$envFile,'-f',$composeFile)
    if ($Action -eq 'Infra') {
        Invoke-Checked $docker ($composeArgs + @('up','-d','--wait','--wait-timeout','120'))
        $images = & $docker @composeArgs images --format json
        if ($LASTEXITCODE -ne 0) { throw 'Could not record image identities.' }
        [IO.File]::WriteAllText((Join-Path $root '.test_artifacts\retouch-images.json'), ($images -join "`n"))
    } else {
        # Retain data volumes; do not destroy test data automatically.
        Invoke-Checked $docker ($composeArgs + @('down'))
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $python)) { throw 'Run -Action Prepare first.' }
$savedEnvironment = @{}
try {
    foreach ($line in [IO.File]::ReadAllLines($envFile)) {
        if (-not $line -or $line.StartsWith('#')) { continue }
        $parts = $line -split '=', 2
        if ($parts.Count -ne 2) { throw 'Malformed private env file.' }
        $key = $parts[0]
        $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $parts[1], 'Process')
    }
    Push-Location $backend
    try {
        switch ($Action) {
            'Migrate' { Invoke-Checked $python @((Join-Path $PSScriptRoot 'migrate_retouch.py')) }
            'Api' { Invoke-Checked $python @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','7302') }
            'Worker' { Invoke-Checked (Join-Path $runtime 'Scripts\arq.exe') @('app.worker.WorkerSettings') }
            'Smoke' { Invoke-Checked $python @((Join-Path $PSScriptRoot 'check_retouch_minimal.py'),'api') }
            'PlanSmoke' { Invoke-Checked $python @((Join-Path $PSScriptRoot 'check_retouch_planner.py')) }
        }
    } finally { Pop-Location }
} finally {
    foreach ($key in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key], 'Process')
    }
}
