$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m papervault --dev --config (Join-Path $projectRoot '.test-data\dev-config') --models (Join-Path $projectRoot '.cache\models')
exit $LASTEXITCODE
