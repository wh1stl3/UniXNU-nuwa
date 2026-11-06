"""Publish the one approved R-011 source commit as identical GitHub objects."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
BASE = '2ab6827d77dfe15010534b52e1abb76a26464a7d'
COMMIT = '1ccf760d667b9eec6dd3491c90cc04ebb7c58340'
BRANCH = 'codex/nuwa-factory-heap'
SOURCES = ['Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c']


def main():
    spec = importlib.util.spec_from_file_location('object_publisher', ROOT / 'scripts/publish-main-via-api.py')
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)
    publisher.ROOT = FIRMWARE
    publisher.REPO = 'repos/wh1stl3/uefi-nuwa'
    publisher.PAYLOAD = ROOT / 'out/factory-heap-source-object-request.json'
    git, api = publisher.git, publisher.api
    if git('log', '-1', '--format=%H').decode().strip() != COMMIT:
        raise ValueError('Unexpected local firmware commit')
    if git('status', '--porcelain').strip():
        raise ValueError('Firmware worktree must be clean')
    changed = git('diff-tree', '--no-commit-id', '--name-only', '-r', BASE, COMMIT).decode().splitlines()
    if changed != SOURCES:
        raise ValueError('R-011 source scope must be the one exact factory heap path')
    if api('git/ref/heads/codex/nuwa-no-auto-abl')['object']['sha'] != BASE:
        raise ValueError('Stable firmware branch moved')
    if api('git/ref/heads/codex/nuwa-bringup')['object']['sha'] != '0a3a51af229eabe76bcc9dcb90d3ce985223b125':
        raise ValueError('Stable firmware branch moved')
    header, message = git('cat-file', 'commit', COMMIT).decode().split('\n\n', 1)
    fields = {}
    for line in header.splitlines():
        key, value = line.split(' ', 1)
        if key not in ('tree', 'parent', 'author', 'committer') or key in fields:
            raise ValueError('Only one unsigned linear commit is supported')
        fields[key] = value
    if fields['parent'] != BASE:
        raise ValueError('Wrong firmware parent')
    entries = []
    for source in SOURCES:
        metadata = git('ls-tree', COMMIT, '--', source).decode().split('\t')[0]
        mode, kind, blob_id = metadata.split()
        if (mode, kind) != ('100644', 'blob'):
            raise ValueError('Unexpected source entry')
        data = git('show', COMMIT + ':' + source)
        blob = api('git/blobs', 'POST', {'encoding': 'base64', 'content': base64.b64encode(data).decode()})
        if blob['sha'] != blob_id:
            raise ValueError('Source blob identity mismatch')
        entries.append({'path': source, 'mode': mode, 'type': kind, 'sha': blob_id})
    tree = api('git/trees', 'POST', {'base_tree': git('show', '-s', '--format=%T', BASE).decode().strip(), 'tree': entries})
    if tree['sha'] != fields['tree']:
        raise ValueError('Full tree identity mismatch')
    commit = api('git/commits', 'POST', {'tree': tree['sha'], 'parents': [BASE], 'message': message,
                                       'author': publisher.identity(fields['author']),
                                       'committer': publisher.identity(fields['committer'])})
    if commit['sha'] != COMMIT:
        raise ValueError('Commit identity mismatch')
    probe = subprocess.run([publisher.GH, 'api', publisher.REPO + '/git/ref/heads/' + BRANCH],
                           capture_output=True, text=True)
    if probe.returncode:
        if '404' not in probe.stderr:
            raise RuntimeError('Cannot determine diagnostic branch state')
        api('git/refs', 'POST', {'ref': 'refs/heads/' + BRANCH, 'sha': COMMIT})
    elif json.loads(probe.stdout)['object']['sha'] != COMMIT:
        raise ValueError('Diagnostic branch already differs; refusing to overwrite')
    if api('git/ref/heads/' + BRANCH)['object']['sha'] != COMMIT:
        raise ValueError('Remote diagnostic head mismatch')
    report = {'repository': 'wh1stl3/uefi-nuwa', 'branch': BRANCH, 'base': BASE, 'commit': COMMIT,
              'changed_paths': changed, 'identical_full_tree': True, 'stable_branch_unchanged': True,
              'authorization': 'User approved R-011 A', 'image_generated': False}
    destination = ROOT / 'reports/factory-heap/source-publish.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
