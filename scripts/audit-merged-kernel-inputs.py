"""Compare merged module/patch inputs without changing build pins or sources."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import runpy

from virtual_patch import Tree, PatchError

ROOT = Path(__file__).resolve().parents[1]
OLD = Path('D:/Code/PortingiOS/common/sources/UniXNU')
XNU = Path('D:/Code/PortingiOS/common/sources/xnu-ios16-full')
MERGED = '76dd64142decca55f6594b860565e848de71d271'
GH = 'C:/Program Files/GitHub CLI/gh.exe'


def api(path):
    for attempt in range(3):
        try:
            return json.loads(subprocess.check_output([GH, 'api', path],
                env={**os.environ, 'GODEBUG': 'http2client=0'}))
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(attempt+1)


def tree(repo, commit):
    data = api(f'repos/{repo}/git/trees/{commit}?recursive=1')
    assert not data['truncated']
    return {item['path']: item for item in data['tree']}


def content(repo, blob):
    data = api(f'repos/{repo}/git/blobs/{blob}')
    raw = base64.b64decode(data['content'])
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == blob
    return raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def main():
    base_tree = tree('wh1stl3/UniXNU', MERGED)
    kit_commit = base_tree['kits/NativePrelink']['sha']
    kit_tree = tree('UniXNU/NativePrelink', kit_commit)
    previous = json.loads((ROOT/'reports/xnu-8796-sequence/results.json').read_text())
    selected = [item for item in previous['selection'] if item['status'] == 'virtual-pass']
    assert len(selected) == 48
    comparison, chosen = [], []
    for item in selected:
        name = item['patch']
        candidate = ROOT/'patches/xnu-8796-candidates'/name
        is_kit = name.startswith('xnu-10063.')
        relative = ('patches/' if is_kit else 'patches/xnu/')+name
        repo, entries = ('UniXNU/NativePrelink', kit_tree) if is_kit else ('wh1stl3/UniXNU', base_tree)
        prefix = 'kits/NativePrelink/' if is_kit else ''
        old_raw = (OLD/prefix/relative).read_bytes()
        assert sha(old_raw) == item['upstream_sha256']
        entry = entries.get(relative)
        record = dict(patch=name, repository=repo, path=relative,
            new_git_blob=entry['sha'] if entry else None,
            old_sha256=sha(old_raw), upstream_unchanged=bool(entry and entry['sha'] == blob(old_raw)),
            device_override=candidate.is_file(), selected_sha256=item['sha256'])
        # The preserved device candidate is intentionally separate from an
        # upstream semantic update. Never replace it merely because it applies.
        raw = candidate.read_bytes() if candidate.is_file() else old_raw
        assert sha(raw) == item['sha256']
        chosen.append((record, raw))
        comparison.append(record)
    changed = [record for record in comparison if not record['upstream_unchanged'] and record['new_git_blob']]
    with ThreadPoolExecutor(max_workers=4) as pool:
        raw_changed = list(pool.map(lambda r: content(r['repository'], r['new_git_blob']), changed))
    replacements = {r['patch']: raw for r, raw in zip(changed, raw_changed)}
    for record, raw in chosen:
        new = replacements.get(record['patch'])
        if new is not None:
            record['new_sha256'] = sha(new)
            git_check = subprocess.run(['C:/Program Files/Git/cmd/git.exe', '-C', str(XNU),
                'apply', '--check', '-'], input=new, capture_output=True)
            record['latest_patch_git_check'] = dict(exit_code=git_check.returncode,
                output=git_check.stderr.decode(errors='replace'))
            try:
                Tree(XNU).apply(new.decode())
                record['latest_patch_individual_context'] = 'pass'
            except PatchError as error:
                record['latest_patch_individual_context'] = 'fail'
                record['latest_patch_error'] = str(error)
    # Re-check the exact preserved CI15 selection in order. This tests context,
    # not compatibility of newly changed upstream semantics or archives.
    overlay = Tree(XNU)
    for record, raw in chosen:
        overlay.apply(raw.decode())
        record['preserved_sequence_context'] = 'pass'
    paths = ('scripts/build-xnu-4k-baseline.sh', 'scripts/build-firehose.sh',
             'scripts/build-libpthread-kernel.py', 'scripts/build-corecrypto-14.py',
             'scripts/xnu_symbols.py', 'feeds.toml')
    scripts = []
    for path in paths:
        entry = base_tree.get(path)
        old = (OLD/path).read_bytes() if (OLD/path).exists() else None
        scripts.append(dict(path=path, old_sha256=sha(old) if old else None,
            new_git_blob=entry['sha'] if entry else None,
            unchanged=bool(entry and old is not None and entry['sha'] == blob(old))))
    baseline = content('wh1stl3/UniXNU', base_tree[paths[0]]['sha']).decode()
    baseline_hash = sha(baseline.encode())
    # Inspect the precise replacement guards in the existing build adapter.
    contexts = {
        'unstripped_noctf_replacements': ('.unstripped.noctf', 3),
        'clang_ios17_replacements': ('-miphoneos-version-min=17.0', 1),
        'link_ios17_replacements': ('-Wl,-ios_version_min,17.0', 1),
        'capture_make_start': ('\nmake -C .cache/xnu-work "${XNU_BUILD_TARGET:-build}"', 1),
        'capture_dstroot': ('DSTROOT="$ROOT/build/xnu/ios-dst"', 1)}
    guards = {key: dict(expected=count, actual=baseline.count(text), matches=baseline.count(text) == count)
              for key, (text, count) in contexts.items()}
    adapter = None
    if (ROOT/'config/kernel-merged-profile.json').exists():
        class RemoteInput:
            def __init__(self, path=''):
                self.path = path

            def __truediv__(self, part):
                return RemoteInput(self.path+'/'+str(part) if self.path else str(part))

            @property
            def name(self):
                return self.path.rsplit('/', 1)[-1]

            def read_bytes(self):
                if self.path == paths[0]:
                    return baseline.encode()
                raw = (OLD/self.path).read_bytes()
                if self.path.startswith('kits/NativePrelink/'):
                    entry = kit_tree[self.path.removeprefix('kits/NativePrelink/')]
                else:
                    entry = base_tree[self.path]
                assert blob(raw) == entry['sha'], 'Cannot substitute old changed input: '+self.path
                return raw

            def read_text(self, encoding='utf-8'):
                return self.read_bytes().decode(encoding)

        scope = runpy.run_path(str(ROOT/'scripts/ci/build-8796-source.py'), run_name='audit')
        patches, adapted, firehose = scope['inputs'](RemoteInput(), 'merged')
        for script in (adapted, firehose):
            subprocess.run(['C:/Program Files/Git/bin/bash.exe', '-n'],
                           input=script.encode(), check=True)
        adapter = dict(passed=True, patch_count=len(patches),
            baseline_sha256=sha(adapted.encode()), firehose_sha256=sha(firehose.encode()),
            scope='Real merged adapter in RAM; Bash syntax only, not a kernel build')
    report = dict(merged_commit=MERGED, native_prelink_commit=kit_commit,
        selected_count=len(selected), preserved_sequence_passed=True,
        upstream_selected_patch_changes=sum(not r['upstream_unchanged'] for r in comparison),
        changed_upstream_is_active=False, patches=comparison, scripts=scripts,
        existing_adapter_contexts=guards,
        merged_baseline_sha256=baseline_hash,
        merged_adapter_check=adapter,
        action='Do not replace pins or patch hashes blindly; review changed semantics and adapters separately',
        built=False, device_accessed=False, feed_modified=False)
    target = ROOT/'reports/upstream-merge/kernel-input-review.json'
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'patches'}, indent=2))


if __name__ == '__main__':
    main()
