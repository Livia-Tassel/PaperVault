[CmdletBinding()]
param([switch]$InstallToolchain, [switch]$SkipParser)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$ToolsRoot = Join-Path $ProjectRoot '.tools'
New-Item -ItemType Directory -Path $ToolsRoot -Force | Out-Null
if ($InstallToolchain -or (Test-Path -LiteralPath (Join-Path $ToolsRoot 'cargo\bin\rustc.exe'))) {
    $env:RUSTUP_HOME = Join-Path $ToolsRoot 'rustup'
    $env:CARGO_HOME = Join-Path $ToolsRoot 'cargo'
    $env:Path = (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:Path
}
if ($InstallToolchain) {
    if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
        $RustInstaller = Join-Path $ToolsRoot 'rustup-init.exe'
        if (-not (Test-Path -LiteralPath $RustInstaller)) {
            Invoke-WebRequest 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe' -OutFile $RustInstaller
        }
        & $RustInstaller -y --no-modify-path --profile minimal --default-toolchain stable --default-host x86_64-pc-windows-msvc
        if ($LASTEXITCODE -ne 0) { throw 'Rust installation failed.' }
    }
    $VsWhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
    $VsInstall = if (Test-Path -LiteralPath $VsWhere) { & $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath }
    if (-not $VsInstall) {
        $VsInstaller = Join-Path $ToolsRoot 'vs_BuildTools.exe'
        if (-not (Test-Path -LiteralPath $VsInstaller)) { Invoke-WebRequest 'https://aka.ms/vs/17/release/vs_BuildTools.exe' -OutFile $VsInstaller }
        $Signature = Get-AuthenticodeSignature -LiteralPath $VsInstaller
        if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'Microsoft') { throw 'Microsoft installer signature validation failed.' }
        $Install = Start-Process -FilePath $VsInstaller -ArgumentList @('--quiet','--wait','--norestart','--nocache','--add','Microsoft.VisualStudio.Workload.VCTools','--includeRecommended') -WindowStyle Hidden -PassThru -Wait
        if ($Install.ExitCode -notin @(0,3010)) { throw "Build Tools installation failed: $($Install.ExitCode)" }
        if ($Install.ExitCode -eq 3010) { Write-Warning 'Windows requests a restart to finish installation.' }
    }
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv }
if ($LASTEXITCODE -ne 0) { throw 'Creating Python environment failed.' }
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }
if (-not $SkipParser -and (Test-Path -LiteralPath 'requirements.lock')) {
    & $Python -m pip install -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Locked Python dependency installation failed.' }
    & $Python -m pip install -e . --no-deps
} elseif ($SkipParser) {
    & $Python -m pip install -e '.[dev]'
} else {
    & $Python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.7.1' 'torchvision==0.22.1'
    if ($LASTEXITCODE -ne 0) { throw 'CPU inference dependency installation failed.' }
    & $Python -m pip install -e '.[dev,parser]'
}
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Push-Location -LiteralPath (Join-Path $ProjectRoot 'apps\desktop')
try {
    if (Test-Path -LiteralPath 'package-lock.json') { npm ci } else { npm install }
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
} finally { Pop-Location }
Write-Output 'Development environment ready. Run scripts/dev-desktop.ps1 for the desktop application.'
