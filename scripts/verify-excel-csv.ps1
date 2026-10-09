[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Csv)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CsvPath = (Resolve-Path -LiteralPath $Csv).Path
$Before = (Get-FileHash -LiteralPath $CsvPath -Algorithm SHA256).Hash
$Excel = $null
$Workbook = $null
$Owned = $false
try {
    $Excel = New-Object -ComObject Excel.Application
    # Never take over or close an existing interactive workbook session.
    if ($Excel.UserControl -or $Excel.Workbooks.Count -ne 0) {
        throw 'Excel returned an existing user-controlled session; verification stopped without opening a file.'
    }
    $Owned = $true
    $Excel.Visible = $false
    $Excel.DisplayAlerts = $false
    $Workbook = $Excel.Workbooks.Open($CsvPath, 0, $true)
    $Sheet = $Workbook.Worksheets.Item(1)
    $Used = $Sheet.UsedRange
    $Rows = $Used.Rows.Count
    $Columns = $Used.Columns.Count
    if ($Rows -lt 2 -or $Columns -lt 2) { throw 'Excel did not recognize a multi-cell CSV table.' }
    $Header = $Used.Cells.Item(1, 1).Text
    $Last = $Used.Cells.Item($Rows, $Columns).Value2
    if ([Math]::Abs([double]$Last - (-0.0012)) -gt 0.000000001) {
        throw "Scientific notation was not read correctly: $Last"
    }
    $Result = [ordered]@{ passed=$true; excel_version=$Excel.Version; rows=$Rows; columns=$Columns; first_header=$Header; last_numeric_value=$Last; read_only=$Workbook.ReadOnly; source_sha256=$Before }
    $Workbook.Close($false)
    $Workbook = $null
    if ((Get-FileHash -LiteralPath $CsvPath -Algorithm SHA256).Hash -ne $Before) { throw 'CSV changed during read-only validation.' }
    $Result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ProjectRoot 'artifacts\excel-csv.json') -Encoding utf8
    $Result | ConvertTo-Json
} finally {
    if ($Workbook -ne $null) { $Workbook.Close($false) }
    if ($Owned -and $Excel -ne $null) { $Excel.Quit() }
    foreach ($Object in @($Used, $Sheet, $Workbook, $Excel)) {
        if ($null -ne $Object -and [Runtime.InteropServices.Marshal]::IsComObject($Object)) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Object)
        }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
