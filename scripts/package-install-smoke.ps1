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
    $OwnedInstall = $Entry.InstallLocation -and [IO.Path]::GetFullPath($Entry.InstallLocation.Trim('"')).TrimEnd('\') -eq $InstallRoot.TrimEnd('\')
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
foreach ($Relative in @('papervault.exe', 'papervault-backend.exe', '_internal\python312.dll', '_internal\msvcp140.dll', '_internal\papervault\migrations\env.py', '_internal\latex2mathml\unimathsymbols.txt', 'licenses\THIRD_PARTY_NOTICES.md', 'licenses\web-rust-dependencies.json', 'licenses\third-party-licenses\CPython-runtime\LICENSE.txt', 'licenses\MPL-SOURCE-NOTICE.md', 'licenses\license-supplements.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot $Relative))) { throw "Installed package is missing $Relative" }
}
$ExpectedBackend = Join-Path $ProjectRoot 'apps\desktop\src-tauri\binaries\papervault-backend-x86_64-pc-windows-msvc.exe'
if ((Get-FileHash -LiteralPath $ExpectedBackend -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath (Join-Path $InstallRoot 'papervault-backend.exe') -Algorithm SHA256).Hash) { throw 'Installed backend differs from the verified staged binary.' }
$SourceArchiveRoot = Join-Path $ProjectRoot 'docs\third-party-sources'
foreach ($Archive in (Get-ChildItem -LiteralPath $SourceArchiveRoot -Recurse -File)) {
    $Relative = $Archive.FullName.Substring($SourceArchiveRoot.Length + 1)
    $InstalledArchive = Join-Path $InstallRoot ('licenses\third-party-sources\' + $Relative)
    if (-not (Test-Path -LiteralPath $InstalledArchive) -or (Get-FileHash -LiteralPath $Archive.FullName -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $InstalledArchive -Algorithm SHA256).Hash) { throw "Installed source archive differs or is missing: $Relative" }
}
$LicenseRoot = Join-Path $ProjectRoot 'docs\third-party-licenses'
foreach ($License in (Get-ChildItem -LiteralPath $LicenseRoot -Recurse -File)) {
    $Relative = $License.FullName.Substring($LicenseRoot.Length + 1)
    $InstalledLicense = Join-Path $InstallRoot ('licenses\third-party-licenses\' + $Relative)
    if (-not (Test-Path -LiteralPath $InstalledLicense) -or (Get-FileHash -LiteralPath $License.FullName -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $InstalledLicense -Algorithm SHA256).Hash) { throw "Installed license differs or is missing: $Relative" }
}
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& (Join-Path $PSScriptRoot 'bootstrap-webdriver.ps1')
$SmokeArguments = @('scripts\package-desktop-smoke.py', '--app', $Application, '--driver', '.tools\edgedriver\msedgedriver.exe', '--output', 'artifacts\installed-desktop')
if (-not $SkipParse) { $SmokeArguments += @('--models', '.cache\models', '--pdf', 'tests\fixtures\academic.pdf', '--expect-figures', '1', '--expect-tables', '1') }
& $Python @SmokeArguments
if ($LASTEXITCODE -ne 0) { throw 'The installed desktop smoke test failed.' }
$InstallProof = [ordered]@{
    install_root = $InstallRoot
    application_sha256 = (Get-FileHash -LiteralPath $Application -Algorithm SHA256).Hash
    backend_sha256 = (Get-FileHash -LiteralPath (Join-Path $InstallRoot 'papervault-backend.exe') -Algorithm SHA256).Hash
    installer_path = $InstallerPath
    installer_sha256 = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash
    license_files_verified = @(Get-ChildItem -LiteralPath $LicenseRoot -Recurse -File).Count
    source_archives_verified = @(Get-ChildItem -LiteralPath $SourceArchiveRoot -Recurse -File).Count
    verified_at = [DateTime]::UtcNow.ToString('o')
}
$InstallProof | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $ProjectRoot 'artifacts\install-layout.json') -Encoding utf8
Write-Output "Installed and verified PaperVault at $InstallRoot. This host has development tools; this is not a clean-VM test."
