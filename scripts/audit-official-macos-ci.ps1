param(
    [string]$Repository = 'UniXNU/UniXNU',
    [string]$Ref = 'main',
    [string]$Owner = 'wh1stl3',
    [string]$Output = 'reports/official-ci-plan/remote-audit.json'
)

# Read-only HTTPS requests. No git invocation, checkout, source-tree copy or CI dispatch.
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$destination = [IO.Path]::GetFullPath((Join-Path $workspace $Output))
$reportRoot = [IO.Path]::GetFullPath((Join-Path $workspace 'reports')) + [IO.Path]::DirectorySeparatorChar
if (-not $destination.StartsWith($reportRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Output must stay under this workspace reports/ directory'
}
if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'Invalid repository' }
if ($Ref -notmatch '^[A-Za-z0-9_.-]+$') { throw 'Invalid ref' }
if ($Owner -notmatch '^[A-Za-z0-9-]+$') { throw 'Invalid owner' }
$headers = @{ 'User-Agent' = 'UniXNU-nuwa-readonly-audit'; 'Accept' = 'application/vnd.github+json' }
$requests = [Collections.Generic.List[string]]::new()
function Get-Api([string]$Suffix) {
    $uri = "https://api.github.com/repos/$Repository/$Suffix"
    $requests.Add($uri)
    return (Invoke-WebRequest -UseBasicParsing -Uri $uri -Headers $headers -TimeoutSec 45).Content | ConvertFrom-Json
}
function Get-Hash([byte[]]$Bytes, [string]$Algorithm) {
    $hasher = [Security.Cryptography.HashAlgorithm]::Create($Algorithm)
    try { return ([BitConverter]::ToString($hasher.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}
$head = Get-Api "commits/$Ref"
$commit = $head.sha
$tree = Get-Api "git/trees/${commit}?recursive=1"
$paths = @('.github/workflows/macos.yml', 'scripts/unixnu/kernel.py', 'scripts/unixnu/cli.py', 'scripts/build-xnu-4k-baseline.sh', 'feeds.toml', '.gitmodules')
$files = @()
foreach ($path in $paths) {
    $file = Get-Api "contents/${path}?ref=$commit"
    $bytes = [Convert]::FromBase64String($file.content)
    $blobPrefix = [Text.Encoding]::UTF8.GetBytes("blob $($bytes.Length)`0")
    $blobHash = Get-Hash ($blobPrefix + $bytes) 'SHA1'
    if ($blobHash -ne $file.sha) { throw "Blob identity mismatch: $path" }
    $content = [Text.Encoding]::UTF8.GetString($bytes)
    $local = Join-Path 'D:/Code/PortingiOSLegacy/common/sources/UniXNU' $path
    $cached = Join-Path 'D:/Code/PortingiOSLegacy/common/sources/UniXNU-latest-audit' $path
    $localHash = if (Test-Path -LiteralPath $local -PathType Leaf) { Get-Hash ([IO.File]::ReadAllBytes($local)) 'SHA256' } else { $null }
    $cachedHash = if (Test-Path -LiteralPath $cached -PathType Leaf) { Get-Hash ([IO.File]::ReadAllBytes($cached)) 'SHA256' } else { $null }
    $remoteHash = Get-Hash $bytes 'SHA256'
    $lines = $content -split "`n"
    $pattern = if ($path -like '*.yml') {
        'name:|workflow_dispatch|device_|defconfig|steps:|pre_build|runs-on|permissions:|contents:|uses:|xcode|XCODE|brew|unixnu |ipsw|upload|cleanup|rm -|UNIXNU_|actions/'
    } elseif ($path -like '*baseline.sh') {
        'SDK|ios17|IOS|unstripped|xcode|xcrun|git |BUILD_JSON|MJ|RECORD|KERNEL_CONFIG|TARGET_CONFIG|XNU_BOOTSTRAP|XNU_BUILD_ARCHIVES'
    } elseif ($path -like '*kernel.py') {
        'def build|def prelink|archives|record|bootstrap|unstripped|subprocess_env|except Error|unlink|apply|_ARCHIVE'
    } elseif ($path -like '*cli.py') {
        'prelink|kernel\.build|kernel\.prelink|SKIP_|NO_|def cmd_build|steps|kernel.*config'
    } else { 'xnu|10063|8796|ref =|url =|submodule|path =|NativePrelink' }
    $excerpts = @()
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match $pattern) { $excerpts += [ordered]@{line = $index + 1; text = $lines[$index].TrimEnd("`r")} }
    }
    $files += [ordered]@{
        path = $path; url = "https://github.com/$Repository/blob/$commit/$path";
        bytes = $bytes.Length; blob_sha1 = $blobHash; sha256 = $remoteHash;
        baseline_sha256 = $localHash; matches_baseline = ($localHash -eq $remoteHash);
        cached_sha256 = $cachedHash; matches_cached = ($cachedHash -eq $remoteHash);
        excerpts = $excerpts
    }
    if ($path -like '*.yml') {
        Write-Output "WORKFLOW $commit $path (in-memory inspection; no source file saved)"
        for ($index = 0; $index -lt $lines.Count; $index++) { Write-Output ('{0,4}: {1}' -f ($index + 1), $lines[$index]) }
    } elseif ($path -like '*kernel.py') {
        Write-Output "KERNEL DRIVER $commit (in-memory inspection; no source file saved)"
        for ($index = 0; $index -lt $lines.Count; $index++) { Write-Output ('{0,4}: {1}' -f ($index + 1), $lines[$index]) }
    } elseif ($path -like '*cli.py' -or $path -eq '.gitmodules') {
        Write-Output "SELECTED EXCERPTS $path"
        foreach ($excerpt in $excerpts) { Write-Output ('{0,4}: {1}' -f $excerpt.line, $excerpt.text) }
    }
}
$comparison = Get-Api "compare/75bc13dd34dc4e403826793739e316a264ce00dd...$commit"
$baselineTree = Get-Api 'git/trees/75bc13dd34dc4e403826793739e316a264ce00dd?recursive=1'
if ($tree.truncated -or $baselineTree.truncated) { throw 'Tree inventory truncated; refuse complete delta claim' }
$baselineMap = @{}
$remoteMap = @{}
foreach ($entry in $baselineTree.tree) { if ($entry.type -ne 'tree') { $baselineMap[$entry.path] = $entry.sha } }
foreach ($entry in $tree.tree) { if ($entry.type -ne 'tree') { $remoteMap[$entry.path] = $entry.sha } }
$delta = @()
foreach ($path in @(@($baselineMap.Keys) + @($remoteMap.Keys) | Sort-Object -Unique)) {
    if ($baselineMap[$path] -ne $remoteMap[$path]) {
        $status = if (-not $baselineMap.ContainsKey($path)) { 'added' } elseif (-not $remoteMap.ContainsKey($path)) { 'removed' } else { 'modified' }
        $delta += [ordered]@{path = $path; status = $status; baseline_blob = $baselineMap[$path]; remote_blob = $remoteMap[$path]}
    }
}
$changes = @($comparison.files | ForEach-Object {
    $patch = if ($_.filename -in $paths) { $_.patch } else { $null }
    [ordered]@{path = $_.filename; status = $_.status; additions = $_.additions; deletions = $_.deletions; patch = $patch}
})
$ownerRepositories = @()
foreach ($name in @('UniXNU', 'UniXNU-nuwa', 'uefi-nuwa')) {
    $uri = "https://api.github.com/repos/$Owner/$name"
    $requests.Add($uri)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $uri -Headers $headers -TimeoutSec 45
        $repo = $response.Content | ConvertFrom-Json
        $ownerRepositories += [ordered]@{repository = "$Owner/$name"; http_status = [int]$response.StatusCode; full_name = $repo.full_name; fork = $repo.fork; parent = $repo.parent.full_name; default_branch = $repo.default_branch; html_url = $repo.html_url}
    } catch {
        $statusCode = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { $null }
        $ownerRepositories += [ordered]@{repository = "$Owner/$name"; http_status = $statusCode; note = 'Unauthenticated read only: 404 does not distinguish private from absent'; error = $_.Exception.Message}
    }
}
$report = [ordered]@{
    captured_at_utc = [DateTime]::UtcNow.ToString('o'); repository = $Repository; ref = $Ref; commit = $commit;
    committed_at = $head.commit.committer.date; commit_message = $head.commit.message;
    workflow_paths = @($tree.tree | Where-Object { $_.path -like '.github/workflows/*' } | Select-Object -ExpandProperty path);
    api_tree_truncated = $tree.truncated; files = $files;
    gitlinks = @($tree.tree | Where-Object { $_.type -eq 'commit' } | Select-Object path,sha);
    owner_repositories = $ownerRepositories;
    comparison = [ordered]@{baseline = '75bc13dd34dc4e403826793739e316a264ce00dd'; status = $comparison.status; ahead_by = $comparison.ahead_by; total_commits = $comparison.total_commits; compare_api_file_count = $changes.Count; compare_api_files_may_be_capped = ($changes.Count -ge 300); files = $changes; complete_tree_delta = $delta};
    requests = @($requests); git_commands_executed = @(); sources_modified = $false;
    source_tree_copied = $false; workflow_dispatched = $false
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
[IO.File]::WriteAllText($destination, ($report | ConvertTo-Json -Depth 30) + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "Report: $destination"
Write-Output "Pinned upstream commit: $commit"
Write-Output "Compare status: $($comparison.status), ahead $($comparison.ahead_by), complete tree delta $($delta.Count); compare API returned $($changes.Count) files (cap 300)"
