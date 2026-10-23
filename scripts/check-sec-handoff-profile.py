"""Check the logging-only SEC profile against the unchanged R-011 recipe."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FW = Path('D:/Code/uefi-nuwa')
UNIXNU = Path('D:/Code/PortingiOS/common/sources/UniXNU')
MU_FALLBACK = Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware')


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def git(root, *args):
    return subprocess.check_output(['git', '--no-optional-locks', '-c',
                                   f'safe.directory={root}', '-C', str(root), *args])


def sha(data):
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def main():
    base = load('config/firmware-factory-heap-profile.json')
    profile = load('config/firmware-sec-handoff-profile.json')
    published = load('reports/sec-handoff/source-publish.json')
    expected = copy.deepcopy(base)
    for key in ('scope', 'source_evidence'):
        expected[key] = profile[key]
    expected['recipe']['approval'] = profile['recipe']['approval']
    expected['recipe']['sources']['firmware']['commit'] = published['commit']
    for item in expected['recipe']['inputs']:
        if item['root'] == 'firmware' and item['path'] == published['source']:
            if item['lf_sha256'] != published['old_lf_sha256']:
                raise ValueError('Wrong SEC base input')
            item['lf_sha256'] = published['new_lf_sha256']
    if expected != profile:
        raise ValueError('Profile exceeds SEC-only source change')
    changed = git(FW, 'diff', '--name-only', published['base'], published['commit']).decode().splitlines()
    if changed != [published['source']] or git(FW, 'status', '--porcelain').strip():
        raise ValueError('Unexpected firmware changes')
    old = git(FW, 'show', published['base'] + ':' + published['source']).decode()
    new = git(FW, 'show', published['commit'] + ':' + published['source']).decode()
    # Reverse exactly the four log sites and the temporary return-value capture.
    expected_source = new.replace('    VOID    *EntryArgHob;\n', '')
    expected_source = '\n'.join(line for line in expected_source.split('\n')
                                if '[NUWA-HANDOFF]' not in line and '(VOID)EntryArgHob;' not in line)
    expected_source = expected_source.replace('    EntryArgHob = BuildGuidDataHob', '    BuildGuidDataHob')
    if expected_source != old:
        raise ValueError('SEC change exceeds logs and local return-value capture')
    checked = []
    for item in profile['recipe']['inputs']:
        if item['root'] == 'unixnu':
            raw = git(UNIXNU, 'show', profile['recipe']['sources']['unixnu']['commit'] + ':' + item['path'])
        elif item['path'].startswith('Mu_Basecore/'):
            # Pinned submodule objects; read-only fallback is a source reference.
            mu = FW / 'Mu_Basecore'
            if not (mu / '.git').exists():
                mu = MU_FALLBACK / 'Mu_Basecore'
            revision = git(FW, 'ls-tree', published['commit'], 'Mu_Basecore').decode().split()[2]
            raw = git(mu, 'show', revision + ':' + item['path'].split('/', 1)[1])
        else:
            raw = git(FW, 'show', published['commit'] + ':' + item['path'])
        actual = sha(raw)
        if actual != item['lf_sha256']:
            raise ValueError('Source hash differs: ' + item['path'])
        checked.append(dict(**item, actual=actual))
    for item in profile['candidate']['patches']:
        if hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Candidate patch changed')
    if sha((ROOT / 'board.toml').read_bytes()) != profile['recipe']['board_lf_sha256']:
        raise ValueError('Board changed')
    feed = git(UNIXNU, 'show', profile['recipe']['sources']['unixnu']['commit'] + ':feeds.toml')
    if sha(feed) != profile['recipe']['feed_lf_sha256']:
        raise ValueError('Feed changed')
    result = dict(result='static SEC-only profile checks passed', checks=checked,
                  changed_paths=changed, logging_change_reverses_exactly_to_base=True,
                  firmware_commit=published['commit'], board_feed_pins_retained=True,
                  recipe_other_inputs_unchanged=True, compiled=False, device_executed=False)
    (ROOT / 'reports/sec-handoff/profile-check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(result=result['result'], inputs=len(checked))))


if __name__ == '__main__':
    main()
