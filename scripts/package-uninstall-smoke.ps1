[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$InstallRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.test-data\installed\PaperVault'))
$TestRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.test-data')) + [IO.Path]::DirectorySeparatorChar
if (-not $InstallRoot.StartsWith($TestRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe uninstall target.' }
$Uninstaller = Join-Path $InstallRoot 'uninstall.exe'
if (-not (Test-Path -LiteralPath $Uninstaller)) { throw 'The project test installation does not exist.' }
$RegistryRoots = @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall', 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall', 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')
$Registered = @($RegistryRoots | Where-Object { Test-Path $_ } | ForEach-Object { Get-ChildItem $_ -ErrorAction SilentlyContinue | Get-ItemProperty -ErrorAction SilentlyContinue } | Where-Object { $_.DisplayName -eq 'PaperVault' })
if (-not $Registered.Count) { throw 'The test installation is not registered; do not execute an unverified old uninstaller.' }
foreach ($Entry in $Registered) {
    $Owned = $Entry.UninstallString -and $Entry.UninstallString.Trim('"') -eq $Uninstaller
    if (-not $Owned) { throw 'A PaperVault registration points outside the project test installation; aborting uninstall.' }
}
$ProofPath = Join-Path $ProjectRoot 'artifacts\install-layout.json'
if (-not (Test-Path -LiteralPath $ProofPath)) { throw 'Run package-install-smoke.ps1 to record ownership of this test installation first.' }
$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
if ($Proof.install_root -ne $InstallRoot -or $Proof.application_sha256 -ne (Get-FileHash -LiteralPath (Join-Path $InstallRoot 'papervault.exe') -Algorithm SHA256).Hash) { throw 'Installed application differs from the verified installation record; do not uninstall an unknown binary.' }
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $Python scripts\package-retention.py prepare
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare data retention fixture.' }
$Removal = Start-Process -FilePath $Uninstaller -ArgumentList '/S' -WindowStyle Hidden -PassThru -Wait
if ($Removal.ExitCode -ne 0) { throw "Test uninstaller exited with $($Removal.ExitCode)" }
$Deadline = (Get-Date).AddSeconds(45)
while ((Test-Path -LiteralPath $Uninstaller) -and (Get-Date) -lt $Deadline) { Start-Sleep -Milliseconds 250 }
if ((Test-Path -LiteralPath (Join-Path $InstallRoot 'papervault.exe')) -or (Test-Path -LiteralPath $Uninstaller)) { throw 'Uninstallation has not finished.' }
& $Python scripts\package-retention.py verify --phase after_uninstall
if ($LASTEXITCODE -ne 0) { throw 'Uninstall data retention check failed.' }
if ((Test-Path -LiteralPath $InstallRoot) -and (Get-ChildItem -LiteralPath $InstallRoot -Force | Select-Object -First 1)) {
    # Preserve any untracked residual files (e.g. an earlier test build's license layout).
    # NSIS deliberately does not recursively delete unknown user files.
    $ResolvedSource = (Resolve-Path -LiteralPath $InstallRoot).Path
    $ResidualArchive = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $InstallRoot) ('PaperVault-uninstalled-' + [guid]::NewGuid().ToString('N'))))
    if (-not $ResolvedSource.StartsWith($TestRoot, [StringComparison]::OrdinalIgnoreCase) -or -not $ResidualArchive.StartsWith($TestRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe residual archive path.' }
    Move-Item -LiteralPath $ResolvedSource -Destination $ResidualArchive
    Write-Output "Preserved residual test-installation files at $ResidualArchive"
}
& (Join-Path $PSScriptRoot 'package-install-smoke.ps1') -Installer $Installer
& $Python scripts\package-retention.py verify --phase after_reinstall
if ($LASTEXITCODE -ne 0) { throw 'Reinstall data retention check failed.' }
Write-Output 'PASS: isolated NSIS uninstall preserved the library and original files; final package reinstalled and its real desktop flow verified.'
