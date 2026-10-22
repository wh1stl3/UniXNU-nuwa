param([string]$RunId = '39715232540')
# Read-only GitHub Actions observation. Artifacts stay under ignored out/.
$ErrorActionPreference = 'Stop'
if ($RunId -notmatch '^[0-9]+$') { throw 'Invalid run id' }
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$gh = 'C:/Program Files/GitHub CLI/gh.exe'
$folder = Join-Path $root "reports/kernel-ci/$RunId"
[IO.Directory]::CreateDirectory($folder) | Out-Null
$raw = & $gh run view $RunId --repo wh1stl3/UniXNU --json status,conclusion,jobs,headSha,url,createdAt,updatedAt
if ($LASTEXITCODE -ne 0) { throw 'Cannot read workflow run' }
$json = [string]::Join("`n", $raw)
[IO.File]::WriteAllText((Join-Path $folder 'run.json'), $json + "`n", [Text.UTF8Encoding]::new($false))
$run = $json | ConvertFrom-Json
Write-Output "$($run.status) $($run.conclusion) $($run.url)"
foreach ($job in $run.jobs) {
    Write-Output "$($job.name): $($job.status) $($job.conclusion)"
    $job.steps | Where-Object { $_.status -ne 'completed' -or $_.conclusion -eq 'failure' } | ForEach-Object { Write-Output "  $($_.name): $($_.status) $($_.conclusion)" }
}
if ($run.status -eq 'completed') {
    $logs = & $gh run view $RunId --repo wh1stl3/UniXNU --log
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read completed run logs' }
    [IO.File]::WriteAllText((Join-Path $folder 'run.log'), ([string]::Join("`n", $logs) + "`n"), [Text.UTF8Encoding]::new($false))
    $artifactFolder = Join-Path $root "out/kernel-ci/$RunId"
    [IO.Directory]::CreateDirectory($artifactFolder) | Out-Null
    & $gh run download $RunId --repo wh1stl3/UniXNU --dir $artifactFolder
    if ($LASTEXITCODE -ne 0) { Write-Output 'Artifacts unavailable; run log was retained' }
    Write-Output "Log: $folder/run.log"
}
