[CmdletBinding()]
param([switch]$SkipBackend, [switch]$OnlineWebViewInstaller)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $ProjectRoot '.tools\cargo\bin\rustc.exe')) {
    $env:RUSTUP_HOME = Join-Path $ProjectRoot '.tools\rustup'
    $env:CARGO_HOME = Join-Path $ProjectRoot '.tools\cargo'
    $env:Path = (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:Path
}
if (-not $SkipBackend) { & (Join-Path $PSScriptRoot 'build-backend.ps1'); if ($LASTEXITCODE -ne 0) { throw 'Backend build failed.' } }
Push-Location -LiteralPath (Join-Path $ProjectRoot 'apps\desktop')
try {
    $Config = 'src-tauri/tauri.bundle.conf.json'
    if ($OnlineWebViewInstaller) {
        $MergeFile = Join-Path $ProjectRoot 'build\tauri-online.json'
        $ConfigValue = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
        $ConfigValue.bundle.windows.webviewInstallMode.type = 'downloadBootstrapper'
        $ConfigValue | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $MergeFile -Encoding utf8
        $Config = $MergeFile
    }
    npx tauri build --target x86_64-pc-windows-msvc --config $Config
    if ($LASTEXITCODE -ne 0) { throw 'Tauri Windows package build failed.' }
} finally { Pop-Location }
$Output = Join-Path $ProjectRoot 'apps\desktop\src-tauri\target\x86_64-pc-windows-msvc\release\bundle\nsis'
Get-ChildItem -LiteralPath $Output -Filter '*.exe' | ForEach-Object {
    Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256 | Format-List
}
