"""Bounded unauthenticated CHMH/ASMB fixtures through the real initializer."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pip._vendor.tomli as tomli

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('init', ROOT / 'scripts/research-current-image4-initializer-amnm.py')
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)
A, B, U, C = I.A, I.B, I.U, I.C
KERNEL = Path('/root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho')
ADT = ROOT / 'out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt'
LOADER = ROOT / '.cache/boot-stage12-v4-r4.img'
TRUST = ROOT / 'out/owner-pmap-ret-continuation-verifier-final-20261111/extracted/EFI/UniXNU/Payloads/kernel.macho.trustcache'
TOML = ROOT / 'out/owner-pmap-ret-continuation-verifier-final-20261111/extracted/EFI/UniXNU/unixnu.toml'
PINS = {'kernel': '7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4',
        'parent-adt': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
        'loader': '692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5',
        'trust': '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e'}
DOMAIN = b'Nuwa.HostBootSetIdentity.v1\0'
sha = lambda x: hashlib.sha256(x).hexdigest()


def material(inputs):
    records = []
    for key in ('kernel', 'loader', 'trust', 'args', 'parent-adt'):
        label = key.encode('ascii')
        digest = hashlib.sha256(inputs[key]).digest()
        records.append(bytes([len(label)]) + label + digest)
    preimage = DOMAIN + b''.join(records)
    return preimage, hashlib.sha384(preimage).digest()


def fixture(parent, chmh, smb):
    tree = copy.deepcopy(C.parse(parent))
    chosen = C.find(tree, '/chosen')
    if chmh is not None:
        chosen['properties'].append(('boot-manifest-hash', 0, chmh))
    if smb is not None:
        assert all(C.name(n) != 'asmb' for n in chosen['children'])
        node = {'properties': [('name', 0, b'asmb\0')], 'children': []}
        node['properties'].extend((k, 0, v) for k, v in smb.items())
        chosen['children'].append(node)
    return C.encode(tree)


def candidate_admit(smb):
    """Research fixture gate only; this is not the project's release gate."""
    if smb and 'lp-smb0' in smb and 'lp-smb1' in smb:
        return False
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', required=True, type=Path)
    args = p.parse_args()
    out = args.output_dir.resolve()
    if not out.is_relative_to((ROOT / 'out').resolve()):
        raise ValueError('Output must be under ignored out/')
    out.mkdir(parents=True, exist_ok=False)
    inputs = {k: path.read_bytes() for k, path in [('kernel', KERNEL), ('parent-adt', ADT), ('loader', LOADER), ('trust', TRUST)]}
    for k, pin in PINS.items():
        if sha(inputs[k]) != pin:
            raise ValueError('Input pin mismatch: ' + k)
    toml = TOML.read_bytes()
    entries = [e for e in tomli.loads(toml.decode())['entry'] if e.get('id') == 'xnu']
    assert len(entries) == 1 and entries[0]['args'] == '-v serial=3'
    inputs['args'] = b'-v serial=3'
    preimage, digest = material(inputs)
    altered = dict(inputs, args=b'-v serial=4')
    changed_preimage, changed_digest = material(altered)
    assert digest != changed_digest
    macho = B.macho(inputs['kernel'])
    real_model = A.Model
    captures = []

    class TracedModel(real_model):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.selectors = []
            captures.append(self)
            self.u.hook_add(U.UC_HOOK_CODE, self.selector_trace)

        def selector_trace(self, u, pc, size, data):
            if pc == 0xfffffff0046f0fd0:
                self.selectors.append({'entry': hex(pc), 'x0': hex(u.reg_read(A.UC_ARM64_REG_X0)),
                                       'x1': u.reg_read(A.UC_ARM64_REG_X1),
                                       'return_pc': hex(u.reg_read(A.UC_ARM64_REG_LR))})
            elif self.selectors and pc == int(self.selectors[-1]['return_pc'], 16) and 'descriptor' not in self.selectors[-1]:
                ptr = u.reg_read(A.UC_ARM64_REG_X0)
                self.selectors[-1].update(descriptor=hex(ptr), level=int.from_bytes(u.mem_read(ptr + 8, 4), 'little'))

    A.Model = TracedModel
    val = b'\0\0\0\0'
    both = {'lp-smb0': val, 'lp-smb1': val}
    cases = [('baseline', None, None, False), ('chmh-only', digest, None, False),
             ('asmb-only', None, both, False), ('both', digest, both, False),
             ('chmh-wrong-type', digest, None, 'boot-manifest-hash'),
             ('chmh-length-49', digest + b'\0', None, False),
             ('chmh-material-mutated', changed_digest, None, False),
             ('asmb-empty', None, {}, False), ('asmb-only-0', None, {'lp-smb0': val}, False),
             ('asmb-only-1', None, {'lp-smb1': val}, False),
             ('asmb-wrong-type', None, {'lp-smb0': val}, 'lp-smb0'),
             ('asmb-length-5', None, {'lp-smb0': val + b'\0'}, False)]
    results = {}
    for name, chmh, smb, wrong in cases:
        raw = fixture(inputs['parent-adt'], chmh, smb)
        result = I.run_case(inputs['kernel'], macho, raw, wrong_type=wrong)
        result['selectors'] = captures[-1].selectors
        result['fixture_adt_sha256'] = sha(raw)
        result['fixture_admission_dual_smb_gate'] = candidate_admit(smb)
        results[name] = result
    for name, level in [('baseline', 0), ('chmh-only', 0), ('asmb-only', 2), ('both', 2),
                        ('asmb-empty', 0), ('asmb-only-0', 1), ('asmb-only-1', 1), ('chmh-material-mutated', 0)]:
        r = results[name]
        assert r['stop']['reason'] == 'boundary' and [s['x1'] for s in r['selectors']] == [0, 1]
        assert [s['level'] for s in r['selectors']] == [0, level]
        assert r['after']['bool_out_byte0'] == 1
    for name, expected in [('chmh-only', digest), ('both', digest), ('chmh-material-mutated', changed_digest)]:
        obj = bytes.fromhex(results[name]['after']['digest_object'])
        assert int.from_bytes(obj[8:12], 'little') == 48 and obj[16:64] == expected
    for name, errno in [('chmh-wrong-type', 96), ('chmh-length-49', 84), ('asmb-wrong-type', 96), ('asmb-length-5', 84)]:
        assert results[name]['stop']['reason'] == 'panic' and results[name]['stop']['variadic'][0] == errno
    assert not candidate_admit(both) and candidate_admit(None) and candidate_admit({'lp-smb0': val}) and candidate_admit({'lp-smb1': val})
    report = {'domain': DOMAIN.hex(), 'material_hex': preimage.hex(), 'chmh_hex': digest.hex(),
              'mutated_material_hex': changed_preimage.hex(), 'mutated_chmh_hex': changed_digest.hex(),
              'inputs': {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in inputs.items()},
              'toml_sha256': sha(toml), 'source_sha256': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in [Path(__file__), ROOT / 'scripts/research-current-image4-initializer-amnm.py', ROOT / 'scripts/audit-image4-runtime-provider.py', ROOT / 'scripts/build-kernel-entry-probe.py', ROOT / 'scripts/nuwa_launch_context.py']},
              'authentication': 'NOT REACHED', 'consumer_after_9b2c': 'DEFERRED', 'cases': results}
    with (out / 'evidence.json').open('x') as f:
        json.dump(report, f, indent=2); f.write('\n')
    print('wrote', out / 'evidence.json')


if __name__ == '__main__':
    main()
