"""Create one firmware source commit adding only SEC handoff boundary logs."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FW = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
BASE = '1ccf760d667b9eec6dd3491c90cc04ebb7c58340'
BRANCH = 'codex/nuwa-sec-handoff-trace'
SOURCE = 'Silicon/Silicium/SiliciumPkg/Sec/Sec.c'
GIT = 'C:/Program Files/Git/cmd/git.exe'


def git(*args):
    return subprocess.check_output([GIT, '-c', f'safe.directory={FW}', '-C', str(FW), *args])


def main():
    output = ROOT / 'reports/sec-handoff/source-local.json'
    if output.exists() or git('status', '--porcelain').strip() or git('log', '-1', '--format=%H').decode().strip() != BASE:
        raise ValueError('Fresh source record and clean pinned firmware checkout required')
    path = FW / SOURCE
    raw = path.read_bytes()
    before = raw.replace(b'\r\n', b'\n').decode()
    if before.encode() != git('show', BASE + ':' + SOURCE).replace(b'\r\n', b'\n'):
        raise ValueError('Source differs from pinned parent')
    old = '''    UINT64  EntryArg = gSecEntryArg0;

    BuildGuidDataHob (&gSiliciumEntryArgHobGuid, &EntryArg, sizeof (EntryArg));'''
    new = '''    UINT64  EntryArg = gSecEntryArg0;
    VOID    *EntryArgHob;

    DEBUG ((EFI_D_ERROR, "[NUWA-HANDOFF] before-entry-arg-hob list=%p\\n", GetHobList ()));
    EntryArgHob = BuildGuidDataHob (&gSiliciumEntryArgHobGuid, &EntryArg, sizeof (EntryArg));
    (VOID)EntryArgHob;
    DEBUG ((EFI_D_ERROR, "[NUWA-HANDOFF] after-entry-arg-hob data=%p\\n", EntryArgHob));'''
    if before.count(old) != 1 or before.count('  ProcessLibraryConstructorList ();') != 1:
        raise ValueError('Exact SEC context required')
    after = before.replace(old, new).replace('  ProcessLibraryConstructorList ();',
        '  DEBUG ((EFI_D_ERROR, "[NUWA-HANDOFF] before-library-constructors\\n"));\n'
        '  ProcessLibraryConstructorList ();\n'
        '  DEBUG ((EFI_D_ERROR, "[NUWA-HANDOFF] after-library-constructors\\n"));')
    patch = ROOT / 'patches/firmware-candidates/0010-sec-handoff-trace.patch'
    patch_data = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                            fromfile='a/' + SOURCE, tofile='b/' + SOURCE)).encode()
    if patch.exists() and patch.read_bytes().replace(b'\r\n', b'\n') != patch_data:
        raise ValueError('Existing proposal patch differs')
    patch.write_bytes(patch_data)
    # The pinned index has LF blobs; the Windows working copy has CRLF.
    # --cached --check reads the index without mutating it, with exact context.
    git('apply', '--cached', '--check', str(patch))
    message = '''[unixnu-nuwa][firmware] 细化入口参数HOB和库构造前后诊断

[Change] 仅在SEC的入口参数HOB与库构造前后加四处ERROR级日志，保持调用顺序和所有内存表、PIL及BootShim。
[Evidence] 中午原包照片末行为platform-hobs Success；实际SEC与固定Mu库审查尚不能定位唯一函数，同SoC也采用相同调用顺序。
[Risk] 诊断不是修复，新二进制编译及运行未验证；不操作设备，不改板值、ADT或验证标志。
'''
    queue = ROOT / 'docs/COMMIT-QUEUE.md'
    with queue.open('a', encoding='utf-8') as stream:
        stream.write('\n## FW-012 · SEC handoff边界诊断源码\n\n```text\n' + message.rstrip() + '\n```\n')
    msg = ROOT / 'out/FW-012-message.txt'
    msg.write_text(message, encoding='utf-8')
    git('switch', '-c', BRANCH)
    path.write_bytes(after.replace('\n', '\r\n').encode() if b'\r\n' in raw else after.encode())
    git('add', '--', SOURCE)
    git('diff', '--cached', '--check')
    # Preserve the pinned parent commit's agent identity without global config.
    author = git('show', '-s', '--format=%an%n%ae', BASE).decode().splitlines()
    git('-c', 'user.name=' + author[0], '-c', 'user.email=' + author[1],
        'commit', '--file', str(msg))
    commit = git('log', '-1', '--format=%H').decode().strip()
    changed = git('diff', '--name-only', BASE, commit).decode().splitlines()
    if changed != [SOURCE]:
        raise ValueError('Unexpected firmware changes')
    report = dict(repository='wh1stl3/uefi-nuwa', base=BASE, commit=commit, branch=BRANCH,
                  changed_paths=changed, source=SOURCE,
                  old_lf_sha256=hashlib.sha256(before.encode()).hexdigest(),
                  new_lf_sha256=hashlib.sha256(after.encode()).hexdigest(),
                  patch=str(patch.relative_to(ROOT)).replace('\\', '/'), patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),
                  scope='SEC logging only; no memory/configuration/call-order changes',
                  authorization='User requested continued offline mainline; image generation no longer requires hard stop',
                  device_accessed=False)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
