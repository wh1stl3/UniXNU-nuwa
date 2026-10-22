param(
    [string]$Git = 'C:/Program Files/Git/cmd/git.exe',
    [string]$Source = 'D:/Code/PortingiOS/common/sources/xnu-ios16-full',
    [string]$Base = 'D:/Code/PortingiOS/common/sources/UniXNU',
    [string]$Output = 'reports/patch-portability-8796'
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$utf8 = [System.Text.UTF8Encoding]::new($false)
New-Item -ItemType Directory -Force $Output | Out-Null
function Invoke-ReadGit([string]$Repo, [string[]]$GitArgs) {
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $Git
    $allArgs = @('-c', "safe.directory=$Repo", '--no-optional-locks', '-C', $Repo) + $GitArgs
    $info.Arguments = ($allArgs | ForEach-Object { '"' + ($_ -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"' }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = [System.Diagnostics.Process]::Start($info)
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $result = [pscustomobject]@{ exit_code = $process.ExitCode; output = ($stdout.Result + $stderr.Result).TrimEnd() }
    $process.Dispose()
    return $result
}
$sourceHead = Invoke-ReadGit $Source @('rev-parse', 'HEAD')
$baseHead = Invoke-ReadGit $Base @('rev-parse', 'HEAD')
$before = Invoke-ReadGit $Source @('status', '--porcelain', '--untracked-files=all')
if ($sourceHead.exit_code -ne 0 -or $baseHead.exit_code -ne 0 -or $before.exit_code -ne 0) { throw 'Cannot establish source provenance' }
if ($before.output) { throw 'Source tree is not clean; refusing contaminated baseline' }
$patches = @(Get-ChildItem "$Base/patches/xnu" -Filter '*.patch' | Sort-Object Name)
if ($patches.Count -ne 49) { throw "Expected 49 patches, got $($patches.Count)" }
$rows = @()
foreach ($patch in $patches) {
    $result = Invoke-ReadGit $Source @('apply', '--check', '--verbose', $patch.FullName)
    $command = "git -c safe.directory=$Source --no-optional-locks -C $Source apply --check --verbose $($patch.FullName)"
    [System.IO.File]::WriteAllText((Join-Path (Resolve-Path $Output) ($patch.Name + '.log')), "$command`nexit_code=$($result.exit_code)`n$($result.output)`n", $utf8)
    $rows += [pscustomobject]@{ patch=$patch.Name; sha256=(Get-FileHash $patch.FullName -Algorithm SHA256).Hash.ToLower(); exit_code=$result.exit_code; output=$result.output }
}
$after = Invoke-ReadGit $Source @('status', '--porcelain', '--untracked-files=all')
$pmapPatch = "$Base/patches/xnu/zzx-pmap-sync-64bit-pa.patch"
$pmapCommand = "git -c safe.directory=$Source --no-optional-locks -C $Source apply --check --verbose --exclude=osfmk/arm64/sptm/pmap/pmap.c $pmapPatch"
$pmapResult = Invoke-ReadGit $Source @('apply', '--check', '--verbose', '--exclude=osfmk/arm64/sptm/pmap/pmap.c', $pmapPatch)
[System.IO.File]::WriteAllText((Join-Path (Resolve-Path $Output) 'pmap-existing-path-only.log'), "$pmapCommand`nexit_code=$($pmapResult.exit_code)`n$($pmapResult.output)`n", $utf8)
$report = [ordered]@{
    timestamp=(Get-Date -Format o); git_version=(Invoke-ReadGit $Source @('--version')).output
    mode='Independent --check against unchanged source; no patches applied; not a cumulative build check'
    source=$Source; source_head=$sourceHead.output; source_commit=(Invoke-ReadGit $Source @('log','-1','--format=%B')).output
    base=$Base; base_head=$baseHead.output; base_status=(Invoke-ReadGit $Base @('status','--porcelain','--untracked-files=no')).output
    source_status_before=$before; source_status_after=$after
    feeds_sha256=(Get-FileHash "$Base/feeds.toml" -Algorithm SHA256).Hash.ToLower()
    pmap_existing_path_only=$pmapResult
    results=$rows
}
[System.IO.File]::WriteAllText((Join-Path (Resolve-Path $Output) 'results.json'), ($report | ConvertTo-Json -Depth 8) + "`n", $utf8)
if ($after.exit_code -ne 0 -or $after.output) { throw 'Source status changed during read-only checks' }
$rows | Select-Object patch, exit_code | Format-Table -AutoSize
"PASS=$(@($rows | Where-Object exit_code -eq 0).Count) FAIL=$(@($rows | Where-Object exit_code -ne 0).Count)"
