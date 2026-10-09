[CmdletBinding()]
param([switch]$SkipInstall, [switch]$Clean)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Run scripts/bootstrap-windows.ps1 first.' }
$env:PYINSTALLER_CONFIG_DIR = Join-Path $ProjectRoot '.cache\pyinstaller'
New-Item -ItemType Directory -Path $env:PYINSTALLER_CONFIG_DIR -Force | Out-Null
$SourceSnapshot = {
    @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'backend') -Recurse -File -Filter '*.py' | Sort-Object FullName | ForEach-Object {
        [ordered]@{ path = $_.FullName.Substring($ProjectRoot.Length + 1); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    }) | ConvertTo-Json -Compress
}
$SourceBefore = & $SourceSnapshot
if (-not $SkipInstall) {
    if (Test-Path -LiteralPath 'requirements.lock') {
        & $Python -m pip install -r requirements.lock
        if ($LASTEXITCODE -ne 0) { throw 'Locked dependency installation failed.' }
        & $Python -m pip install -e . --no-deps
    } else {
        & $Python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.7.1' 'torchvision==0.22.1'
        if ($LASTEXITCODE -ne 0) { throw 'CPU inference dependency installation failed.' }
        & $Python -m pip install -e '.[dev,parser]'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}
$BuildArguments = @('-m', 'PyInstaller', '--noconfirm', '--distpath', 'build\backend-dist', '--workpath', 'build\pyinstaller', 'scripts\backend.spec')
if ($Clean) { $BuildArguments += '--clean' }
& $Python @BuildArguments
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
$SourceAfter = & $SourceSnapshot
if ($SourceBefore -ne $SourceAfter) { throw 'Backend sources changed during freezing. Rebuild before staging or shipping this artifact.' }
$SourceAfter | Set-Content -LiteralPath (Join-Path $ProjectRoot 'build\backend-source-sha256.json') -Encoding utf8
$BundleSource = Join-Path $ProjectRoot 'build\backend-dist\papervault-backend'
$Staging = Join-Path $ProjectRoot 'apps\desktop\src-tauri\binaries'
New-Item -ItemType Directory -Path $Staging -Force | Out-Null
# Only overwrite generated staging entries; never operate on a user library.
Copy-Item -LiteralPath (Join-Path $BundleSource 'papervault-backend.exe') -Destination (Join-Path $Staging 'papervault-backend-x86_64-pc-windows-msvc.exe') -Force
$StagedInternal = [IO.Path]::GetFullPath((Join-Path $Staging '_internal'))
if (-not $StagedInternal.StartsWith([IO.Path]::GetFullPath($Staging) + [IO.Path]::DirectorySeparatorChar)) { throw 'Unsafe staging path.' }
if (Test-Path -LiteralPath $StagedInternal) { Remove-Item -LiteralPath $StagedInternal -Recurse -Force }
Copy-Item -LiteralPath (Join-Path $BundleSource '_internal') -Destination $StagedInternal -Recurse
& $Python scripts\package-smoke.py --backend (Join-Path $Staging 'papervault-backend-x86_64-pc-windows-msvc.exe')
if ($LASTEXITCODE -ne 0) { throw 'Frozen backend startup smoke test failed.' }
Write-Output "Frozen backend staged at $Staging"
