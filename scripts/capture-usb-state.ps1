param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskOutput = [IO.Path]::GetFullPath($OutputPath)
$taskReports = [IO.Path]::GetFullPath((Join-Path $taskRoot 'reports')) + [IO.Path]::DirectorySeparatorChar
if (-not $taskOutput.StartsWith($taskReports, [StringComparison]::OrdinalIgnoreCase) -or
    (Test-Path -LiteralPath $taskOutput)) { throw 'Choose a fresh reports output' }
$taskEntries = @(Get-PnpDevice -PresentOnly | ForEach-Object {
    if ($_.InstanceId -match '^USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})') {
        [PSCustomObject]@{ vid=$Matches[1]; pid=$Matches[2]; class=$_.Class; status=$_.Status }
    }
} | Sort-Object vid,pid,class,status -Unique)
$taskReport = [PSCustomObject]@{
    at_utc = [DateTime]::UtcNow.ToString('o')
    scope = 'Present USB VID/PID inventory only; no serial numbers or device operations'
    entries = $taskEntries
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($taskOutput)) | Out-Null
[IO.File]::WriteAllText($taskOutput, ($taskReport | ConvertTo-Json -Depth 5) + "`n", [Text.UTF8Encoding]::new($false))
$taskReport | ConvertTo-Json -Depth 5
