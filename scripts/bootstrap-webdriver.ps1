$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DriverRoot = Join-Path $ProjectRoot '.tools\edgedriver'
$ApplicationRoots = @(
    "${env:ProgramFiles(x86)}\Microsoft\EdgeWebView\Application",
    "$env:ProgramFiles\Microsoft\EdgeWebView\Application",
    "$env:LOCALAPPDATA\Microsoft\EdgeWebView\Application"
)
$Runtime = $ApplicationRoots | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Get-ChildItem -LiteralPath $_ -Directory | Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' }
} | Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $Runtime) { throw 'WebView2 Runtime was not found. Install the application with its WebView2 installer first.' }
New-Item -ItemType Directory -Path $DriverRoot -Force | Out-Null
$Archive = Join-Path $ProjectRoot '.tools\edgedriver_win64.zip'
Invoke-WebRequest -Uri "https://msedgedriver.microsoft.com/$($Runtime.Name)/edgedriver_win64.zip" -OutFile $Archive
Expand-Archive -LiteralPath $Archive -DestinationPath $DriverRoot -Force
$Signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $DriverRoot 'msedgedriver.exe')
if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'Microsoft') { throw 'Microsoft WebDriver signature validation failed.' }
Write-Output "WebDriver installed for WebView2 $($Runtime.Name)"

