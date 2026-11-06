"""Publish the one approved R-007 source commit as identical GitHub objects."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
BASE = '0a3a51af229eabe76bcc9dcb90d3ce985223b125'
COMMIT = '5e4a8c814b89f62a4ba2bc145249314fed5db787'
BRANCH = 'codex/nuwa-sec-trace'
SOURCE = 'Silicon/Silicium/SiliciumPkg/Sec/Sec.c'


def main():
    spec = importlib.util.spec_from_file_location('object_publisher', ROOT / 'scripts/publish-main-via-api.py')
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)
    publisher.ROOT = FIRMWARE
    publisher.REPO = 'repos/wh1stl3/uefi-nuwa'
    publisher.PAYLOAD = ROOT / 'out/sec-source-object-request.json'
    git, api = publisher.git, publisher.api
    if git('log', '-1', '--format=%H').decode().strip() != COMMIT:
        raise ValueError('Unexpected local firmware commit')
    if git('status', '--porcelain').strip():
        raise ValueError('Firmware worktree must be clean')
    changed = git('diff-tree', '--no-commit-id', '--name-only', '-r', BASE, COMMIT).decode().splitlines()
    if changed != [SOURCE]:
        raise ValueError('R-007 source scope must be SEC.c only')
    if api('git/ref/heads/codex/nuwa-bringup')['object']['sha'] != BASE:
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
    metadata = git('ls-tree', COMMIT, '--', SOURCE).decode().split('\t')[0]
    mode, kind, blob_id = metadata.split()
    if (mode, kind) != ('100644', 'blob'):
        raise ValueError('Unexpected source entry')
    data = git('show', COMMIT + ':' + SOURCE)
    blob = api('git/blobs', 'POST', {'encoding': 'base64', 'content': base64.b64encode(data).decode()})
    if blob['sha'] != blob_id:
        raise ValueError('Source blob identity mismatch')
    tree = api('git/trees', 'POST', {'base_tree': git('show', '-s', '--format=%T', BASE).decode().strip(),
                                    'tree': [{'path': SOURCE, 'mode': mode, 'type': kind, 'sha': blob_id}]})
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
              'authorization': 'User approved R-007 A', 'image_generated': False}
    destination = ROOT / 'reports/sec-trace/source-publish.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
