param([Parameter(Mandatory=$true)][string]$DeviceRef)
# Manually dispatch only the source-kernel workflow in the user's base fork.
$ErrorActionPreference = 'Stop'
if ($DeviceRef -notmatch '^[0-9a-f]{40}$') { throw 'Exact device commit required' }
$gh = 'C:/Program Files/GitHub CLI/gh.exe'
$result = & $gh workflow run nuwa-8796-source.yml --repo wh1stl3/UniXNU --ref main -f "device_ref=$DeviceRef"
if ($LASTEXITCODE -ne 0) { throw 'Source workflow dispatch failed' }
Write-Output $result
