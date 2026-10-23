"""Check pinned HOB diagnostic patch chain and unchanged traversal offline."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from virtual_patch import Tree


def main():
    spec = importlib.util.spec_from_file_location('ctor', ROOT / 'scripts/prepare-constructor-trace.py')
    ctor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctor)
    base = json.loads((ROOT / 'config/firmware-mmu-branches-profile.json').read_text())
    profile = json.loads((ROOT / 'config/firmware-hob-query-profile.json').read_text())
    proposal = json.loads((ROOT / 'reports/hob-query/proposal.json').read_text())
    fullpath = 'Mu_Basecore/' + proposal['path']
    expected = copy.deepcopy(base)
    for key in ('scope', 'source_evidence'):
        expected[key] = profile[key]
    expected['recipe']['approval'] = profile['recipe']['approval']
    expected['recipe']['inputs'].append(dict(root='firmware', path=fullpath, lf_sha256=proposal['pre_sha256']))
    expected['candidate']['post_patch_inputs'].append(dict(root='firmware', path=fullpath, lf_sha256=proposal['post_sha256']))
    expected['candidate']['patches'].append(dict(root='firmware', path=proposal['patch'], sha256=proposal['patch_sha256']))
    if expected != profile:
        raise ValueError('Unrelated profile changes')
    trees = {key: Tree(ROOT / 'out/nonexistent-source') for key in ('firmware', 'unixnu')}
    for item in profile['recipe']['inputs']:
        if item['root'] == 'unixnu':
            source = Path('D:/Code/PortingiOS/common/sources/UniXNU')
            pin, path = profile['recipe']['sources']['unixnu']['commit'], item['path']
        elif item['path'].startswith('Mu_Basecore/'):
            source, pin, path = ctor.MU, ctor.PIN, item['path'].split('/', 1)[1]
        else:
            source, pin, path = ctor.FW, ctor.FW_PIN, item['path']
        raw = ctor.blob(source, pin, path).replace(b'\r\n', b'\n')
        if hashlib.sha256(raw).hexdigest() != item['lf_sha256']:
            raise ValueError('Source pin mismatch: ' + item['path'])
        trees[item['root']].files[item['path']] = raw.decode()
    before = trees['firmware'].read(fullpath)
    for patch in profile['candidate']['patches']:
        raw = (ROOT / patch['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != patch['sha256']:
            raise ValueError('Patch hash mismatch')
        trees[patch['root']].apply(raw.decode().replace('\r\n', '\n'))
    for item in profile['candidate']['post_patch_inputs']:
        if hashlib.sha256(trees[item['root']].read(item['path']).encode()).hexdigest() != item['lf_sha256']:
            raise ValueError('Post patch mismatch: ' + item['path'])
    after = trees['firmware'].read(fullpath)
    stripped = after
    # Remove only the trace condition blocks, including the nested log-cap block.
    while match := re.search(r'^ *if \(mNuwaHobTraceActive[^\n]+\{\n', stripped, re.M):
        start, pos, depth = match.start(), match.end(), 1
        while depth:
            depth += (stripped[pos] == '{') - (stripped[pos] == '}')
            pos += 1
        stripped = stripped[:start] + stripped[pos + 1:]
    stripped = '\n'.join(line for line in stripped.split('\n')
                         if '[NUWA-HOB]' not in line
                         and 'mNuwaHobTrace' not in line
                         and 'Bounded diagnostic output only' not in line
                         and line.strip() != 'VOID  *Result;')
    stripped = stripped.replace('  Result = GetNextGuidHob (Guid, HobList);', '  return GetNextGuidHob (Guid, HobList);')
    stripped = stripped.replace('  return Result;\n', '')
    if re.sub(r'\s+', '', stripped) != re.sub(r'\s+', '', before):
        raise ValueError('Traversal or return expressions changed')
    report = dict(result='40 pins, complete patch chain and original traversal static checks passed',
                  inputs=len(profile['recipe']['inputs']), post_patch_inputs=len(profile['candidate']['post_patch_inputs']),
                  log_rows_per_query=128, additional_header_length_reads=True,
                  timing_and_logger_effects_unverified=True, device_accessed=False, compiled=False)
    (ROOT / 'reports/hob-query/profile-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
