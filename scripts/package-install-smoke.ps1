[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Installer, [switch]$SkipParse)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$InstallRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.test-data\installed\PaperVault'))
$TestRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.test-data')) + [IO.Path]::DirectorySeparatorChar
if (-not $InstallRoot.StartsWith($TestRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Installation target must stay inside the project test directory.' }
$RegistryRoots = @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall', 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall', 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')
$Existing = @($RegistryRoots | Where-Object { Test-Path $_ } | ForEach-Object {
    Get-ChildItem $_ -ErrorAction SilentlyContinue | Get-ItemProperty -ErrorAction SilentlyContinue
} | Where-Object { $_.DisplayName -eq 'PaperVault' })
foreach ($Entry in $Existing) {
    $OwnedInstall = $Entry.InstallLocation -and [IO.Path]::GetFullPath($Entry.InstallLocation).TrimEnd('\') -eq $InstallRoot.TrimEnd('\')
    $OwnedUninstaller = $Entry.UninstallString -and $Entry.UninstallString.Trim('"') -eq (Join-Path $InstallRoot 'uninstall.exe')
    if (-not ($OwnedInstall -or $OwnedUninstaller)) { throw 'An existing PaperVault installation outside this test directory was found. This smoke test will not replace it.' }
}
if (-not $Existing.Count -and (Test-Path -LiteralPath $InstallRoot) -and (Get-ChildItem -LiteralPath $InstallRoot -Force | Select-Object -First 1)) {
    throw 'The unregistered test installation directory is not empty; inspect it before installing.'
}
$InstallerPath = (Resolve-Path -LiteralPath $Installer).Path
New-Item -ItemType Directory -Path (Split-Path -Parent $InstallRoot) -Force | Out-Null
# NSIS requires /D to be the final argument and does not want quotes around its value.
$Setup = Start-Process -FilePath $InstallerPath -ArgumentList "/S /D=$InstallRoot" -WindowStyle Hidden -PassThru -Wait
if ($Setup.ExitCode -ne 0) { throw "Installer exited with $($Setup.ExitCode)" }
$Application = Join-Path $InstallRoot 'papervault.exe'
foreach ($Relative in @('papervault.exe', 'papervault-backend.exe', '_internal\python312.dll', '_internal\papervault\migrations\env.py', '_internal\latex2mathml\unimathsymbols.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot $Relative))) { throw "Installed package is missing $Relative" }
}
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$SmokeArguments = @('scripts\package-desktop-smoke.py', '--app', $Application, '--driver', '.tools\edgedriver\msedgedriver.exe', '--output', 'artifacts\installed-desktop')
if (-not $SkipParse) { $SmokeArguments += @('--models', '.cache\models', '--pdf', 'tests\fixtures\academic.pdf', '--expect-figures', '1', '--expect-tables', '1') }
& $Python @SmokeArguments
if ($LASTEXITCODE -ne 0) { throw 'The installed desktop smoke test failed.' }
Write-Output "Installed and verified PaperVault at $InstallRoot. This host has development tools; this is not a clean-VM test."

