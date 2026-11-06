# Publish only reviewed source/docs, never source trees, binaries or credentials.
# Git writes are authorized by the user's later "all Git commands allowed" reply.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$git = 'C:/Program Files/Git/cmd/git.exe'
function Invoke-Git([string[]]$Arguments) {
    & $git -c "safe.directory=$root" -c core.autocrlf=false -C $root @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments[0]) failed: $LASTEXITCODE" }
}
$pending = & $git -c "safe.directory=$root" -C $root diff --cached --name-only
if ($LASTEXITCODE -ne 0 -or $pending) { throw 'Index is not empty; preserve existing staged changes' }
$files = & $git -c "safe.directory=$root" -C $root ls-files --cached --others --exclude-standard
if ($LASTEXITCODE -ne 0) { throw 'File inventory failed' }
$findings = @()
foreach ($relative in $files) {
    $path = Join-Path $root $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    $file = Get-Item -LiteralPath $path
    if ($relative -match '(^|/)(out|build|\.git)/|\.(img|fd|Fv|efi|dtb|dtbo|o|a|pem|key)$|(^|/)\.ghtoken$|(^|/)\.ghhdr$') {
        $findings += "$relative : excluded name"
    }
    if ($file.Length -ge 10MB) { $findings += "$relative : >=10MB" }
    $text = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
    if ($text -match 'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----') {
        $findings += "$relative : credential-like content (value withheld)"
    }
}
if ($findings.Count) { throw ($findings -join "`n") }
$queue = [IO.File]::ReadAllText((Join-Path $root 'docs/COMMIT-QUEUE.md'), [Text.Encoding]::UTF8)
$groups = @(
    @{id='001';paths=@('scripts/check-xnu-patch-portability.ps1','reports/patch-portability-8796','reports/patch-portability-8796-recheck','docs/operations/2026-10-22-patch-portability-8796.md')},
    @{id='002';paths=@('docs/operations/2026-10-22-readonly-base-integration.md')},
    @{id='003';paths=@('board.toml')},
    @{id='004';paths=@('scripts/check_native_support.py','scripts/check-native-prelink-8796.py','reports/native-prelink-8796','docs/operations/2026-10-22-native-prelink-8796.md')},
    @{id='005';paths=@('scripts/prepare-8796-context-candidates.py','reports/xnu-8796-candidates','docs/operations/2026-10-22-8796-context-candidates.md','patches/xnu-8796-candidates/apple-only-cpu-tunables.patch','patches/xnu-8796-candidates/external-archive-dependencies.patch','patches/xnu-8796-candidates/native-aes-personality.patch','patches/xnu-8796-candidates/source-machine-layer.patch','patches/xnu-8796-candidates/zzx-pmap-sync-64bit-pa.patch')},
    @{id='006';paths=@('scripts/virtual_patch.py','scripts/check-8796-sequence.py','reports/xnu-8796-sequence','reports/board-integration','patches/xnu-8796-candidates/README.md','patches/xnu-8796-candidates/public-entitlements-header.patch','patches/xnu-8796-candidates/offline-owner-systemos-mount.patch','patches/xnu-8796-candidates/zzz-boot-progress.patch','docs/operations/2026-10-22-8796-selected-sequence.md')},
    @{id='007';paths=@('scripts/audit-darwin22-interfaces.py','reports/darwin22-audit/interfaces.json','docs/operations/2026-10-22-darwin22-interfaces-and-wsl.md')},
    @{id='008';paths=@('scripts/probe-wsl-toolchain.sh','reports/darwin22-audit/wsl-toolchain.log')},
    @{id='009';paths=@('docs/NEED-REVIEW.md')},
    @{id='010';paths=@('config/toolchains','scripts/wsl_kernel_adapter.py','scripts/run-wsl-firststage.sh','tests/test_wsl_kernel_adapter.py','reports/wsl-firststage','docs/operations/2026-10-22-wsl-firststage-adapter.md')},
    @{id='011';paths=@('reports/official-ci-plan/local-comparison.json','reports/official-ci-plan/scripts_unixnu_kernel.py.diff','reports/official-ci-plan/scripts_build-xnu-4k-baseline.sh.diff')},
    @{id='012';paths=@('scripts/audit-official-macos-ci.ps1','scripts/prepare-official-ci-candidate.py','reports/official-ci-plan/remote-audit.json','reports/official-ci-plan/candidate-check.json','patches/base-ci-candidates','docs/operations/2026-10-22-official-ci-route.md','docs/DECISIONS.md')},
    @{id='013';paths=@('scripts/ci','ci/workflows','scripts/publish-device-milestones.ps1','reports/official-ci-plan/source-input-check.json','reports/official-ci-plan/repository-setup.json','docs/operations/2026-10-22-source-kernel-ci.md','docs/STATUS.md','docs/WORKLOG.md','docs/COMMIT-QUEUE.md')}
)
$result = @()
$messagePath = Join-Path $root 'out/queued-commit-message.txt'
[IO.Directory]::CreateDirectory((Split-Path -Parent $messagePath)) | Out-Null
foreach ($group in $groups) {
    $pattern = '(?s)## Q-' + $group.id + '\b.*?```text\r?\n(.*?)\r?\n```'
    $match = [regex]::Match($queue, $pattern)
    if (-not $match.Success) { throw "Missing message Q-$($group.id)" }
    foreach ($relative in $group.paths) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $relative))) { throw "Missing milestone input: $relative" }
    }
    Invoke-Git (@('add','--') + $group.paths)
    # Verbatim patch/diff/log evidence contains intentional context whitespace.
    Invoke-Git @('diff','--cached','--check','--','.',':(exclude)*.patch',':(exclude)*.diff',':(exclude)*.log')
    [IO.File]::WriteAllText($messagePath, $match.Groups[1].Value.Replace("`r`n", "`n") + "`n", [Text.UTF8Encoding]::new($false))
    Invoke-Git @('commit','--file',$messagePath)
    $head = & $git -C $root log -1 --format=%H
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read committed HEAD' }
    $result += [ordered]@{queue = "Q-$($group.id)"; commit = $head}
}
[IO.File]::WriteAllText((Join-Path $root 'out/published-milestone-commits.json'), ($result | ConvertTo-Json) + "`n", [Text.UTF8Encoding]::new($false))
Invoke-Git @('remote','add','origin','https://github.com/wh1stl3/UniXNU-nuwa.git')
Invoke-Git @('push','--set-upstream','origin','HEAD:main')
