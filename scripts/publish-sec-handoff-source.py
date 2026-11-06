"""Publish the recorded SEC-only source commit; preserve existing branch refs."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FW = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')


def main():
    record = json.loads((ROOT / 'reports/sec-handoff/source-local.json').read_text())
    spec = importlib.util.spec_from_file_location('sec_git_objects', ROOT / 'scripts/publish-main-via-api.py')
    pub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    pub.REPO = 'repos/wh1stl3/uefi-nuwa'
    git = lambda *args: subprocess.check_output([pub.GIT, '-c', f'safe.directory={FW}', '-C', str(FW), *args])
    base, commit, branch = record['base'], record['commit'], record['branch']
    if base != '1ccf760d667b9eec6dd3491c90cc04ebb7c58340' or branch != 'codex/nuwa-sec-handoff-trace':
        raise ValueError('Unexpected source scope')
    if pub.api('git/ref/heads/codex/nuwa-factory-heap')['object']['sha'] != base:
        raise ValueError('Stable factory-heap source moved')
    if git('diff', '--name-only', base, commit).decode().splitlines() != ['Silicon/Silicium/SiliciumPkg/Sec/Sec.c']:
        raise ValueError('Unexpected changed source')
    header, message = git('cat-file', 'commit', commit).decode().split('\n\n', 1)
    fields = {}
    for line in header.splitlines():
        key, value = line.split(' ', 1)
        if key not in ('tree', 'parent', 'author', 'committer') or key in fields:
            raise ValueError('Unexpected commit header')
        fields[key] = value
    if fields['parent'] != base:
        raise ValueError('Wrong source parent')
    source = record['source']
    mode, kind, blob = git('ls-tree', commit, '--', source).decode().split('\t')[0].split()
    raw = git('show', commit + ':' + source)
    actual_blob = pub.api('git/blobs', 'POST', dict(encoding='base64', content=base64.b64encode(raw).decode()))
    if actual_blob['sha'] != blob or (mode, kind) != ('100644', 'blob'):
        raise ValueError('Blob identity differs')
    tree = pub.api('git/trees', 'POST', dict(base_tree=git('show', '-s', '--format=%T', base).decode().strip(),
                                          tree=[dict(path=source, mode=mode, type=kind, sha=blob)]))
    if tree['sha'] != fields['tree']:
        raise ValueError('Full tree identity differs')
    remote = pub.api('git/commits', 'POST', dict(tree=tree['sha'], parents=[base], message=message,
                     author=pub.identity(fields['author']), committer=pub.identity(fields['committer'])))
    if remote['sha'] != commit:
        raise ValueError('Commit identity differs')
    probe = subprocess.run([pub.GH, 'api', pub.REPO + '/git/ref/heads/' + branch], capture_output=True, text=True)
    if probe.returncode:
        if '404' not in probe.stderr:
            raise ValueError('Cannot determine branch state')
        pub.api('git/refs', 'POST', dict(ref='refs/heads/' + branch, sha=commit))
    elif json.loads(probe.stdout)['object']['sha'] != commit:
        raise ValueError('Existing diagnostic ref differs')
    if pub.api('git/ref/heads/' + branch)['object']['sha'] != commit:
        raise ValueError('Remote ref differs')
    output = dict(**record, identical_full_tree=True, factory_heap_ref_unchanged=True)
    (ROOT / 'reports/sec-handoff/source-publish.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(dict(branch=branch, commit=commit, identical_full_tree=True)))


if __name__ == '__main__':
    main()
