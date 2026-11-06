"""Fallback for unavailable Git HTTPS: publish identical objects, never rewrite main.

Uses gh authentication without reading tokens. Every created blob, tree and
commit must match its local Git object ID before a non-force ref update.
"""
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GIT = 'C:/Program Files/Git/cmd/git.exe'
GH = 'C:/Program Files/GitHub CLI/gh.exe'
REPO = 'repos/wh1stl3/UniXNU-nuwa'
PAYLOAD = ROOT / 'out/github-object-request.json'


def git(*arguments):
    return subprocess.check_output([GIT, '-C', str(ROOT), *arguments])


def api(path, method='GET', body=None):
    command = [GH, 'api', '--method', method, f'{REPO}/{path}']
    if body is not None:
        PAYLOAD.write_text(json.dumps(body), encoding='utf-8')
        command += ['--input', str(PAYLOAD)]
    return json.loads(subprocess.check_output(command))


def identity(line):
    match = re.fullmatch(r'(.*) <([^<>]*)> (\d+) ([+-])(\d\d)(\d\d)', line)
    if not match:
        raise ValueError('Unsupported commit identity')
    name, email, timestamp, sign, hours, minutes = match.groups()
    offset = (int(hours)*60 + int(minutes)) * (1 if sign == '+' else -1)
    date = datetime.fromtimestamp(int(timestamp), timezone(timedelta(minutes=offset))).isoformat()
    return {'name': name, 'email': email, 'date': date}


def main():
    old = api('git/ref/heads/main')['object']['sha']
    head = git('log', '-1', '--format=%H').decode().strip()
    subprocess.run([GIT, '-C', str(ROOT), 'merge-base', '--is-ancestor', old, head], check=True)
    commits = git('rev-list', '--reverse', f'{old}..{head}').decode().splitlines()
    parent = old
    for commit in commits:
        header, message = git('cat-file', 'commit', commit).decode('utf-8').split('\n\n', 1)
        fields = {}
        for line in header.splitlines():
            key, value = line.split(' ', 1)
            if key not in ('tree', 'parent', 'author', 'committer') or key in fields:
                raise ValueError('Only reviewed linear, unsigned commits are supported')
            fields[key] = value
        if fields['parent'] != parent:
            raise ValueError('Unexpected commit chain')
        entries = []
        changed = git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', parent, commit)
        for path in changed.decode('utf-8').split('\0'):
            if not path:
                continue
            entry = git('ls-tree', '-z', commit, '--', path).decode('utf-8').rstrip('\0')
            if not entry:
                prior = git('ls-tree', '-z', parent, '--', path).decode().split(' ', 1)[0]
                entries.append({'path': path, 'mode': prior, 'type': 'blob', 'sha': None})
                continue
            metadata, listed_path = entry.split('\t')
            mode, kind, expected = metadata.split()
            if listed_path != path or kind != 'blob' or mode not in ('100644', '100755'):
                raise ValueError('Unsupported tree entry')
            data = git('show', f'{commit}:{path}')
            if len(data) >= 10_000_000:
                raise ValueError('Refusing oversized tracked file')
            blob = api('git/blobs', 'POST', {'encoding': 'base64', 'content': base64.b64encode(data).decode()})
            if blob['sha'] != expected:
                raise ValueError('Blob identity mismatch')
            entries.append({'path': path, 'mode': mode, 'type': 'blob', 'sha': expected})
        base_tree = git('show', '-s', '--format=%T', parent).decode().strip()
        tree = api('git/trees', 'POST', {'base_tree': base_tree, 'tree': entries})
        if tree['sha'] != fields['tree']:
            raise ValueError('Tree identity mismatch; ref untouched')
        created = api('git/commits', 'POST', {'message': message, 'tree': tree['sha'], 'parents': [parent],
                                           'author': identity(fields['author']),
                                           'committer': identity(fields['committer'])})
        if created['sha'] != commit:
            raise ValueError('Commit identity mismatch; ref untouched')
        print(f'Identical commit uploaded: {commit}', flush=True)
        parent = commit
    if api('git/ref/heads/main')['object']['sha'] != old:
        raise ValueError('Remote main moved; ref untouched')
    if head != old:
        api('git/refs/heads/main', 'PATCH', {'sha': head, 'force': False})
    if api('git/ref/heads/main')['object']['sha'] != head:
        raise ValueError('Remote head verification failed')
    report = {'repository': 'wh1stl3/UniXNU-nuwa', 'old': old, 'head': head,
              'identical_commits': commits, 'force': False}
    (ROOT / 'out/github-api-publish.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
