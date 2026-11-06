param([Parameter(Mandatory=$true)][string]$QueueId,
      [Parameter(Mandatory=$true)][string]$FilesFile,
      [switch]$Push)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$git = 'C:/Program Files/Git/cmd/git.exe'
$env:PATH = 'C:\Program Files\Git\cmd;C:\Program Files\GitHub CLI;' + $env:PATH
if ($QueueId -notmatch '^Q-[0-9]{3}$') { throw 'Invalid queue id' }
function Invoke-Git([string[]]$Arguments) {
    & $git -c "safe.directory=$root" -C $root @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments[0]) failed: $LASTEXITCODE" }
}
$pending = & $git -c "safe.directory=$root" -C $root diff --cached --name-only
if ($LASTEXITCODE -ne 0 -or $pending) { throw 'Index is not empty; preserve staged work' }
$paths = [string[]](ConvertFrom-Json -InputObject ([IO.File]::ReadAllText([IO.Path]::GetFullPath($FilesFile), [Text.Encoding]::UTF8)))
if (-not $paths.Count) { throw 'No files selected' }
foreach ($path in $paths) {
    if ([IO.Path]::IsPathRooted($path) -or $path -match '(^|[/\\])(\.\.|\.git|out|build)([/\\]|$)' -or
        -not (Test-Path -LiteralPath (Join-Path $root $path))) { throw "Unsafe/missing milestone path: $path" }
}
$queue = [IO.File]::ReadAllText((Join-Path $root 'docs/COMMIT-QUEUE.md'), [Text.Encoding]::UTF8)
$match = [regex]::Match($queue, '(?s)## ' + $QueueId + '\b.*?```text\r?\n(.*?)\r?\n```')
if (-not $match.Success) { throw "Message missing: $QueueId" }
$message = Join-Path $root "out/$QueueId-message.txt"
[IO.File]::WriteAllText($message, $match.Groups[1].Value + "`n", [Text.UTF8Encoding]::new($false))
Invoke-Git (@('add','--') + $paths)
Invoke-Git @('diff','--cached','--check','--','.',':(exclude)*.patch',':(exclude)*.diff',':(exclude)*.log')
Invoke-Git @('commit','--file',$message)
Invoke-Git @('log','-1','--format=%H')
if ($Push) { Invoke-Git @('push','origin','HEAD:main') }
