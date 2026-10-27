"""Recover a depth-one Git checkout when the smart HTTPS clone stalls.

Only the user-requested D:/Code/PortingiOS/nuwa/uefi-nuwa is written. Original Git objects are
reconstructed from verified read-only cached objects and API metadata. A final
repack removes the cache dependency. Never overlays an existing usable checkout.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import runpy
import zlib

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
REPO = 'wh1stl3/uefi-nuwa'
COMMIT = '0a3a51af229eabe76bcc9dcb90d3ce985223b125'
BRANCH = 'codex/nuwa-bringup'
GIT = 'C:/Program Files/Git/cmd/git.exe'


def api(path):
    return json.loads(subprocess.check_output(['C:/Program Files/GitHub CLI/gh.exe', 'api',
        'repos/'+REPO+'/'+path], env={**os.environ, 'GODEBUG': 'http2client=0'}))


def git(*args):
    return subprocess.check_output([GIT, '-C', str(TARGET), *args]).decode().strip()


def store(kind, data, expected):
    raw = kind.encode()+b' '+str(len(data)).encode()+b'\0'+data
    assert hashlib.sha1(raw).hexdigest() == expected, (kind, expected)
    directory = TARGET/'.git/objects'/expected[:2]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory/expected[2:]
    if not path.exists():
        path.write_bytes(zlib.compress(raw))


def identity(who):
    date = datetime.fromisoformat(who['date'].replace('Z', '+00:00'))
    # REST normalizes dates to UTC. This pinned Git object retains +0800;
    # the complete raw object's SHA below independently verifies this offset.
    return f"{who['name']} <{who['email']}> {int(date.timestamp())} +0800"


def main():
    assert TARGET.resolve() == Path('D:/Code/PortingiOS/nuwa/uefi-nuwa').resolve()
    TARGET.mkdir(exist_ok=True)
    assert not any(p.name != '.git' for p in TARGET.iterdir()), 'Preserve existing worktree files'
    if (TARGET/'.git').exists():
        assert (TARGET/'.git').is_dir() and not (TARGET/'.git').is_symlink()
        head = subprocess.run([GIT, '-C', str(TARGET), 'rev-parse', '--verify', 'HEAD'], capture_output=True)
        assert head.returncode != 0 or head.stdout.decode().strip() == COMMIT, 'Existing different checkout: do not overwrite'
    subprocess.run([GIT, 'init', str(TARGET)], check=True, capture_output=True)
    metadata = api('git/trees/'+COMMIT+'?recursive=1')
    assert not metadata['truncated']
    entries = {e['path']: e for e in metadata['tree']}
    for path in entries:
        assert not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts
    commit = api('git/commits/'+COMMIT)
    raw_commit = ('tree '+commit['tree']['sha']+'\n'+
        ''.join('parent '+p['sha']+'\n' for p in commit['parents'])+
        'author '+identity(commit['author'])+'\ncommitter '+identity(commit['committer'])+
        '\n\n'+commit['message']).encode()
    if hashlib.sha1(b'commit '+str(len(raw_commit)).encode()+b'\0'+raw_commit).hexdigest() != COMMIT:
        raw_commit += b'\n'
    store('commit', raw_commit, COMMIT)
    scope = runpy.run_path(str(ROOT/'scripts/provision-uefi-nuwa.py'), run_name='cache')
    bodies, _ = scope['prepare']()
    for path, data in bodies.items():
        store('blob', data, entries[path]['sha'])
    directories = {}
    for path, entry in entries.items():
        parent, _, name = path.rpartition('/')
        directories.setdefault(parent, []).append((name, entry))
    for directory, children in directories.items():
        children.sort(key=lambda pair: pair[0].encode()+(b'/' if pair[1]['type']=='tree' else b''))
        raw = b''.join(format(int(e['mode'], 8), 'o').encode()+b' '+name.encode()+b'\0'+bytes.fromhex(e['sha'])
                       for name, e in children)
        expected = entries[directory]['sha'] if directory else commit['tree']['sha']
        store('tree', raw, expected)
    (TARGET/'.git/shallow').write_bytes((COMMIT+'\n').encode('ascii'))
    git('config', 'core.bare', 'false')
    git('config', 'core.autocrlf', 'false')
    git('config', 'core.symlinks', 'false')
    git('config', 'core.filemode', 'false')
    git('config', 'remote.origin.url', 'https://github.com/'+REPO+'.git')
    git('config', 'remote.origin.fetch', '+refs/heads/'+BRANCH+':refs/remotes/origin/'+BRANCH)
    git('config', 'branch.'+BRANCH+'.remote', 'origin')
    git('config', 'branch.'+BRANCH+'.merge', 'refs/heads/'+BRANCH)
    git('symbolic-ref', 'HEAD', 'refs/heads/'+BRANCH)
    git('update-ref', 'refs/heads/'+BRANCH, COMMIT)
    git('update-ref', 'refs/remotes/origin/'+BRANCH, COMMIT)
    alternate = TARGET/'.git/objects/info/alternates'
    alternate.parent.mkdir(exist_ok=True, parents=True)
    original_objects = scope['FW']/'.git/objects'
    assert original_objects.is_dir()
    alternate.write_bytes((original_objects.as_posix()+'\n').encode('utf-8'))
    # Repack all objects reachable from our refs into this new repository. This
    # reads the alternate only; it does not modify its files, refs or index.
    git('repack', '-a')
    alternate.unlink()
    integrity = git('fsck', '--connectivity-only', '--no-reflogs')
    git('read-tree', 'HEAD')
    git('checkout-index', '-a')
    assert git('rev-parse', 'HEAD') == COMMIT
    assert not git('status', '--porcelain')
    result = dict(path=str(TARGET), repository=REPO, commit=COMMIT, branch=BRANCH,
        method='Read-only local object cache plus exact verified new objects; standalone depth-one checkout',
        tracked_entries=len([e for e in entries.values() if e['type'] != 'tree']),
        new_blobs=len(bodies), shared_cache_dependency_removed=not alternate.exists(), fsck=integrity,
        worktree_clean=True, submodules_initialized=False, firmware_generated=False)
    (ROOT/'reports/uefi-nuwa/local-checkout.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
