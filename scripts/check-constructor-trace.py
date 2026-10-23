"""Validate exact constructor diagnostics and 39 pinned inputs, without writes to sources."""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from virtual_patch import Tree
import importlib.util
spec = importlib.util.spec_from_file_location('ctor_proposal', ROOT / 'scripts/prepare-constructor-trace.py')
proposal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proposal)


def main():
    base = json.loads((ROOT / 'config/firmware-sec-handoff-profile.json').read_text())
    profile = json.loads((ROOT / 'config/firmware-constructor-trace-profile.json').read_text())
    record = json.loads((ROOT / 'reports/constructor-trace/proposal.json').read_text())
    patch = (ROOT / record['patch']).read_bytes()
    if hashlib.sha256(patch).hexdigest() != record['patch_sha256']:
        raise ValueError('Patch changed')
    tree = Tree(proposal.MU)
    tree.apply(patch.decode().replace('a/Mu_Basecore/', 'a/').replace('b/Mu_Basecore/', 'b/'))
    expected = copy.deepcopy(base)
    for key in ('scope', 'source_evidence'):
        expected[key] = profile[key]
    expected['recipe']['approval'] = profile['recipe']['approval']
    effects = []
    for item in record['files']:
        expected['recipe']['inputs'].append(dict(root='firmware', path=item['path'], lf_sha256=item['original_lf_sha256']))
        expected['candidate']['post_patch_inputs'].append(dict(root='firmware', path=item['path'], lf_sha256=item['post_lf_sha256']))
        path = item['path'].split('/', 1)[1]
        old = proposal.blob(proposal.MU, proposal.PIN, path).replace(b'\r\n', b'\n').decode()
        new = tree.read(path)
        a, b = proposal.function(old, item['constructor'])
        c, d = proposal.function(new, item['constructor'])
        body = '\n'.join(line for line in new[c:d].splitlines() if '[NUWA-CTOR]' not in line)
        if item['label'] == 'Debug':
            body = body.replace('RETURN_STATUS Status;', '').replace('Status = SerialPortInitialize ();',
                                                                        'return SerialPortInitialize ();').replace('return Status;', '')
        elif item['label'] == 'Lzma':
            body = body.replace('EFI_STATUS Status;', '').replace('Status = ExtractGuidedSectionRegisterHandlers (',
                                                                         'return ExtractGuidedSectionRegisterHandlers (').replace('return Status;', '')
        if re.sub(r'\s+', '', body) != re.sub(r'\s+', '', old[a:b]):
            raise ValueError('Calls or return expressions changed in ' + item['constructor'])
        if hashlib.sha256(new.encode()).hexdigest() != item['post_lf_sha256']:
            raise ValueError('Post-patch source changed')
        effects.append(dict(constructor=item['constructor'], original_calls_and_returns_preserved=True))
    expected['candidate']['patches'].append(dict(path=record['patch'], root='firmware', sha256=record['patch_sha256']))
    if expected != profile:
        raise ValueError('Profile exceeds four constructor logging files')
    checked = []
    unixnu = Path('D:/Code/PortingiOS/common/sources/UniXNU')
    for item in profile['recipe']['inputs']:
        if item['root'] == 'unixnu':
            raw = proposal.blob(unixnu, profile['recipe']['sources']['unixnu']['commit'], item['path'])
        elif item['path'].startswith('Mu_Basecore/'):
            raw = proposal.blob(proposal.MU, proposal.PIN, item['path'].split('/', 1)[1])
        else:
            raw = proposal.blob(proposal.FW, proposal.FW_PIN, item['path'])
        actual = hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()
        if actual != item['lf_sha256']:
            raise ValueError('Pinned source differs: ' + item['path'])
        checked.append(dict(path=item['path'], actual=actual))
    for item in profile['candidate']['patches']:
        if hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Other patch changed')
    if hashlib.sha256((ROOT / 'board.toml').read_bytes().replace(b'\r\n', b'\n')).hexdigest() != profile['recipe']['board_lf_sha256']:
        raise ValueError('Board changed')
    result = dict(result='39 input pins and constructor logging semantics static checks passed', inputs=checked,
                  constructors=effects, shared_library_consumers_also_affected=True,
                  board_feed_recipe_retained=True, compiled=False, device_executed=False,
                  limitation='Normalized call/return equivalence does not prove identical timing or runtime logger behavior')
    (ROOT / 'reports/constructor-trace/profile-check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(result=result['result'], inputs=len(checked))))


if __name__ == '__main__':
    main()
