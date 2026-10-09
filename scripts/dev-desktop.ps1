$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $ProjectRoot '.tools\cargo\bin\rustc.exe')) {
    $env:RUSTUP_HOME = Join-Path $ProjectRoot '.tools\rustup'
    $env:CARGO_HOME = Join-Path $ProjectRoot '.tools\cargo'
    $env:Path = (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:Path
}
Push-Location -LiteralPath (Join-Path $ProjectRoot 'apps\desktop')
try { npx tauri dev; if ($LASTEXITCODE -ne 0) { throw 'Desktop development command failed.' } }
finally { Pop-Location }
