"""Merge a pinned upstream into our GitHub fork and verify preservation.

No source checkout, image build, workflow dispatch or device access. The merge
endpoint is non-force; both expected branch tips are checked before mutation.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GH = 'C:/Program Files/GitHub CLI/gh.exe'
FORK = 'wh1stl3/UniXNU'
BEFORE = '02daabcbcf1387fc67c15efeaef8085614dd97f2'
UPSTREAM = '5fdbd5d08518bc2d5c196264c56a377dd80cf5ca'
OUT = ROOT / 'reports/upstream-merge'


def api(path, body=None):
    command = [GH, 'api', path]
    if body is not None:
        command += ['--method', 'POST', '--input', '-']
    return json.loads(subprocess.check_output(command,
        input=json.dumps(body).encode() if body is not None else None,
        env={**os.environ, 'GODEBUG': 'http2client=0'}))


def tree(repo, sha):
    data = api(f'repos/{repo}/git/trees/{sha}?recursive=1')
    if data['truncated']:
        raise ValueError('Incomplete tree')
    return {e['path']: (e['mode'], e['type'], e['sha'])
            for e in data['tree'] if e['type'] != 'tree'}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    patches = {str(p.relative_to(ROOT)).replace('\\', '/'):
               hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((ROOT / 'patches').rglob('*')) if p.is_file()}
    tip = api(f'repos/{FORK}/git/ref/heads/main')['object']['sha']
    if tip != BEFORE:
        raise ValueError(f'Fork tip changed: {tip}')
    old = tree(FORK, BEFORE)
    upstream = tree('UniXNU/UniXNU', UPSTREAM)
    comparison = api(f'repos/{FORK}/compare/{UPSTREAM}...{BEFORE}')
    common = tree(FORK, comparison['merge_base_commit']['sha'])
    ours = sorted(p for p in old.keys() | common.keys() if old.get(p) != common.get(p))
    if not all(p.startswith('.github/workflows/nuwa-') for p in ours) or len(ours) != 3:
        raise ValueError(f'Unexpected fork changes: {ours}')
    if old['feeds.toml'] != upstream['feeds.toml']:
        raise ValueError('Merge would change fork feeds.toml')
    if any(p in upstream and upstream[p] != common.get(p) for p in ours):
        raise ValueError('Upstream overlaps our workflow changes')
    # Save the exact preflight before the one mutation, for recovery after a
    # network interruption. Do not retry this POST blindly.
    preflight = dict(before=BEFORE, upstream=UPSTREAM,
                     merge_base=comparison['merge_base_commit']['sha'],
                     ahead_by=comparison['ahead_by'], behind_by=comparison['behind_by'],
                     own_paths={p: old[p] for p in ours}, device_patch_sha256=patches,
                     feed_blob=old['feeds.toml'])
    (OUT / 'preflight.json').write_text(json.dumps(preflight, indent=2)+'\n')
    result = api(f'repos/{FORK}/merges', dict(base='main', head=UPSTREAM,
        commit_message='[unixnu-nuwa][build] Merge upstream main and preserve nuwa CI\n\n'
        '[Change] Merge pinned upstream '+UPSTREAM+' without replacing our workflows.\n'
        '[Evidence] Three nuwa workflows have no upstream overlaps; feeds.toml blob unchanged.\n'
        '[Risk] Merged modules and Darwin22 integration require separate validation; no image or device test.'))
    (OUT / 'merge-response.json').write_text(json.dumps(dict(sha=result['sha'],
        parents=[p['sha'] for p in result['parents']], html_url=result['html_url']), indent=2)+'\n')
    merged = tree(FORK, result['sha'])
    expected = dict(upstream)
    expected.update({p: old[p] for p in ours})
    assert merged == expected, 'Merged tree differs from upstream plus preserved workflows'
    assert [p['sha'] for p in result['parents']] == [BEFORE, UPSTREAM]
    assert merged['feeds.toml'] == old['feeds.toml']
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == sha
               for p, sha in patches.items())
    evidence = dict(fork=FORK, before=BEFORE, upstream=UPSTREAM, merged=result['sha'],
        parents=[p['sha'] for p in result['parents']],
        preserved_workflows={p: merged[p][2] for p in ours},
        feed_blob_unchanged=True, device_patch_count=len(patches),
        device_patch_hashes_unchanged=True, complete_merged_tree_matches=True,
        merged_entry_count=len(merged), compiled=False, device_accessed=False,
        module_pins={p: e[2] for p, e in merged.items() if e[0] == '160000'})
    (OUT / 'verification.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
