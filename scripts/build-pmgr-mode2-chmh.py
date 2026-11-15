#!/usr/bin/env python3
"""Fixed PMGR mode-2 CHMH host profile; audit actual FAT and outer bytes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import owner_bnch as O
import owner_payload as P

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = load('pthread_parent_chmh', 'build-chmh-only-payload.py')
V = load('pthread_parent_outer', 'build-owner-vendor-boot.py')
PROFILE = 'pmgr-mode2-chmh-20261113-r1'
ARGS = b'-v serial=3 nuwa-pmgr=2'
KERNEL = ROOT / 'out/nuwa-pmgr-kernel-20261113-r5/kernel.macho'
KERNEL_SHA = '81b85228316574782f9d5390956c3ce3d8c97e4b345a9ea1631feacf3280b5d1'
DIGEST = bytes.fromhex('4af690f92784ee79da2330dbd49372cadea6c242375dfd1e54cfd703f49fde6dc51c035adcd09db805e79c045afad502')
ADT_SHA = '59e78384804830a981e894451c66301c873afbb1da5d768220e538db2a4c8fff'
FAT_SHA = 'a9697c46d775e722d902cceea32070518ea2e8e5cfce8af8abc4eccd25afe701'
RECORD_SHA = 'be10c1a9c113e84ad3ac9d29f26e453c3ea01a02c0b7bbc75987f4208b1dd3c4'
STOCK = ROOT / '.cache/stock/vendor_boot_b.img'
BACKUP = ROOT / 'out/pmap-ret-run-pmap-ret-20261111-r4/vendor_boot_b.stock.img'
BACKUP_SHA = '493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad'
GPT = ROOT.parent / '.cache/device-evidence/20261107-recovery/gpt-sde.bin'
BASE = ROOT.parent.parent / 'UniXNU'
EVIDENCE = {
    'kernel_manifest': ('out/nuwa-pmgr-kernel-20261113-r5/kernel.json', 'd3c435d48dcd138d77d3d5fca03bbfae8b525f653c8ea4caf68cb69419190e1a'),
    'kernel_audit': ('out/nuwa-pmgr-kernel-20261113-r5/audit.json', '54f24ddbf85e34eee9c1cdbc4adeddef7c6e73f4dfeaa3d4413556df556b9853'),
    'startup_audit': ('out/nuwa-pmgr-kernel-20261113-r5/startup-audit.json', '216de401faacbb77e9dba181a8d4d861e544f70ac79e6c54f7ad69d3eb5e4253'),
    'provenance': ('out/nuwa-pmgr-kernel-20261113-r5/provenance.json', '82f6bb10d8adead8c3da824d564b51ad66b6298b5c0da23df8a19470d448207d'),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evidence():
    result = {}
    contents = {}
    for key, (path, pin) in EVIDENCE.items():
        raw = (ROOT / path).read_bytes()
        require(O.sha(raw) == pin, 'Evidence mismatch: ' + key)
        result[key] = {'path': path, 'sha256': pin}
        contents[key] = json.loads(raw)
    return result


def fixed(work):
    parent = C.extract(C.FAT, work / 'parent-readback')
    original = C.fixed_inputs(parent)
    C.check_inputs(original)
    require(parent['parent-adt'] == C.ADT.read_bytes(), 'Parent ADT differs from parent FAT')
    kernel = KERNEL.read_bytes()
    require(len(kernel) == 55451648 and O.sha(kernel) == KERNEL_SHA, 'New kernel mismatch')
    old = b'args = "-v serial=3"'
    require(original['config'].count(old) == 1, 'Parent config args mismatch')
    inputs = dict(original, kernel=kernel, args=ARGS,
                  config=original['config'].replace(old, b'args = "' + ARGS + b'"'),
                  **{'parent-config': original['config']})
    material = check_inputs(inputs)
    return parent, inputs, material, evidence()


def check_inputs(inputs):
    pins = dict(C.PINS, kernel=KERNEL_SHA)
    for key, pin in pins.items():
        require(O.sha(inputs['parent-config'] if key == 'config' else inputs[key]) == pin,
                'Fixed PMGR input mismatch: ' + key)
    old = b'args = "-v serial=3"'
    require(inputs['parent-config'].count(old) == 1 and
            inputs['config'] == inputs['parent-config'].replace(old, b'args = "' + ARGS + b'"'),
            'Fixed PMGR config mismatch')
    config = tomllib.loads(inputs['config'].decode())
    entries = [e for e in config['entry'] if e.get('id') == 'xnu']
    require(len(entries) == 1 and entries[0].get('args') == ARGS.decode() and
            inputs['args'] == ARGS, 'Fixed PMGR args mismatch')
    material, digest = C.digest_material(inputs)
    require(digest == DIGEST, 'Fixed PMGR CHMH material mismatch')
    return material


def replace_members(fat, kernel, adt, config, parent_fat):
    # Fixed timestamp + TZ for reproducible replacement/reconstruction; both
    # operations use the real FAT implementation, not assumptions about extents.
    for path in (kernel, adt, config):
        os.utime(path, (946684800, 946684800))
    for path, destination in ((kernel, 'Payloads/kernel.macho'), (adt, 'Payloads/kernel.macho.adt'), (config, 'unixnu.toml')):
        proc = subprocess.run(['mcopy', '-o', '-i', str(fat), str(path),
                               '::/EFI/UniXNU/' + destination],
                              env=dict(os.environ, TZ='UTC'), capture_output=True, text=True)
        require(proc.returncode == 0, 'FAT replacement failed: ' + proc.stderr)
    # mcopy uses wall-clock directory times even when source mtimes are fixed.
    # Restore only the already-reviewed directory timestamp fields for the
    # uniquely located parent ADT and kernel short entries.
    C.normalize_directory_time(fat, parent_fat)
    name = b'KERNEL~1MAC'
    require(parent_fat.count(name) == 1, 'Parent kernel short name not unique')
    at = parent_fat.index(name)
    raw = bytearray(fat.read_bytes())
    require(at % 32 == 0 and parent_fat[at + 11] == raw[at + 11] == 0x20 and
            raw[at:at + 11] == name, 'Kernel directory entry moved')
    raw[at + 13:at + 20] = parent_fat[at + 13:at + 20]
    raw[at + 22:at + 26] = parent_fat[at + 22:at + 26]
    name = b'UNIXNU~1TOM'
    require(parent_fat.count(name) == 1, 'Parent config short name not unique')
    at = parent_fat.index(name)
    require(at % 32 == 0 and parent_fat[at + 11] == raw[at + 11] == 0x20 and
            raw[at:at + 11] == name, 'Config directory entry moved')
    raw[at + 13:at + 20] = parent_fat[at + 13:at + 20]
    raw[at + 22:at + 26] = parent_fat[at + 22:at + 26]
    fat.write_bytes(raw)


def expected_record(inputs, material, ev, adt, fat):
    return {'type': 'experimental-unauthenticated-boot-set-identity', 'profile': PROFILE,
            'inputs_sha256': {k: O.sha(v) for k, v in inputs.items()}, 'evidence': ev,
            'material_hex': material.hex(), 'chmh_hex': DIGEST.hex(),
            'derived_adt_sha256': O.sha(adt), 'derived_adt_bytes': len(adt),
            'payload_sha256': O.sha(fat), 'layout': C.measure_layout(inputs, adt),
            'authentication': 'NOT REACHED', 'device_release': False}


def provenance(inputs, ev):
    return {'profile': PROFILE, 'kernel_path': str(KERNEL.relative_to(ROOT)),
            'kernel_sha256': KERNEL_SHA, 'args': ARGS.decode(),
            'inputs_sha256': {k: O.sha(v) for k, v in inputs.items()},
            'evidence': ev, 'authentication': 'NOT REACHED', 'device_release': False}


def inspect_payload(selected, parent, inputs, material, ev, work):
    work.mkdir(parents=True, exist_ok=True)
    require(material == check_inputs(inputs), 'Material binding mismatch')
    require(ev == evidence(), 'Evidence binding mismatch')
    require(json.loads((selected / 'provenance.json').read_text()) == provenance(inputs, ev),
            'Provenance binding mismatch')
    expected_adt = C.derived(inputs['parent-adt'], DIGEST)
    adt = (selected / 'derived.adt').read_bytes()
    C.check_adt(inputs['parent-adt'], adt, DIGEST)
    require(adt == expected_adt and O.sha(adt) == ADT_SHA, 'Derived ADT mismatch')
    require((selected / 'kernel.macho').read_bytes() == inputs['kernel'], 'Selected kernel mismatch')
    fat = (selected / 'payload.img').read_bytes()
    require(len(fat) == 67108864 and O.sha(fat) == FAT_SHA, 'FAT size/hash mismatch')
    members = C.extract(selected / 'payload.img', work / 'selected-readback')
    require(members['kernel'] == inputs['kernel'] and members['parent-adt'] == adt and
            members['trust'] == inputs['trust'] and members['config'] == inputs['config'], 'Selected FAT member mismatch')
    # Build a second FAT from the pinned parent and fixed source bytes.
    reference = work / 'reference-fat.img'
    reference.write_bytes(inputs['fat'])
    kernel_path = work / 'expected-kernel.macho'
    adt_path = work / 'expected.adt'
    kernel_path.write_bytes(inputs['kernel'])
    adt_path.write_bytes(expected_adt)
    config_path = work / 'unixnu.toml'
    config_path.write_bytes(inputs['config'])
    replace_members(reference, kernel_path, adt_path, config_path, inputs['fat'])
    require(reference.read_bytes() == fat, 'Selected FAT differs from fixed-parent reconstruction')
    expected = expected_record(inputs, material, ev, expected_adt, fat)
    record_path = selected / 'record.json'
    require(O.sha(record_path.read_bytes()) == RECORD_SHA and
            json.loads(record_path.read_text()) == expected, 'Selected record binding mismatch')
    require(json.loads((selected / 'layout.json').read_text()) == expected['layout'], 'Selected layout mismatch')
    return {'fat': fat, 'adt': adt, 'record_sha256': O.sha(record_path.read_bytes()), 'members': members}


def stock_inputs():
    stock, backup = STOCK.read_bytes(), BACKUP.read_bytes()
    require(len(stock) == 100663296 and O.sha(stock) == V.STOCK_SHA, 'Stock template mismatch')
    require(len(backup) == 100663296 and O.sha(backup) == BACKUP_SHA and O.sha(stock) != O.sha(backup), 'Original backup/template mismatch')
    partitions = V.gpt_capacity(GPT.read_bytes())
    require(partitions['vendor_boot_b']['bytes'] == len(stock), 'GPT capacity mismatch')
    require(O.sha(C.LOADER.read_bytes()) == V.R4_SHA, 'Loader mismatch')
    return stock, partitions


def audit_image(image, selected, inputs, material, ev, stock, work):
    require(O.sha(image) != O.sha(stock), 'Outer equals stock')
    ctx = inspect_payload(selected, None, inputs, material, ev, work)
    comparison = V.compare(stock, image, ctx['fat'], len(stock))
    ramdisk = V.parse(image)['ramdisk']
    ramdisk_path = work / 'actual-vendor-ramdisk.img'
    ramdisk_path.write_bytes(ramdisk)
    members = C.extract(ramdisk_path, work / 'outer-readback')
    require(members['kernel'] == inputs['kernel'] and members['parent-adt'] == ctx['adt'] and
            members['trust'] == inputs['trust'] and members['config'] == inputs['config'], 'Outer FAT member mismatch')
    C.check_adt(inputs['parent-adt'], members['parent-adt'], DIGEST)
    require(C.measure_layout(dict(inputs, kernel=members['kernel']), members['parent-adt']) ==
            json.loads((selected / 'layout.json').read_text()), 'Outer layout mismatch')
    return {'outer_sha256': O.sha(image), 'ramdisk_sha256': O.sha(ramdisk),
            'members_sha256': {k: O.sha(v) for k, v in members.items()}, 'comparison': comparison,
            'record_sha256': ctx['record_sha256']}


def audit_report(report, actual, selected):
    require(report.get('profile') == PROFILE and report.get('authentication') == 'NOT REACHED' and
            report.get('device_release') is False, 'Outer profile mismatch')
    path = report.get('record_path')
    require(type(path) is str and path, 'Missing selected record path')
    try:
        resolved = (Path(path) if Path(path).is_absolute() else ROOT / path).resolve(strict=True)
        expected = (selected / 'record.json').resolve(strict=True)
    except OSError as error:
        raise ValueError('Selected record path unavailable') from error
    require(resolved == expected and O.sha(resolved.read_bytes()) == actual['record_sha256'] == report.get('record_sha256'), 'Selected record path/hash mismatch')
    require(report.get('stock_sha256') == V.STOCK_SHA and report.get('original_backup_sha256') == BACKUP_SHA and
            report.get('original_backup_is_template') is False and report.get('loader_sha256') == V.R4_SHA,
            'Stock/backup/loader identity mismatch')
    for key in ('outer_sha256', 'ramdisk_sha256', 'members_sha256', 'comparison'):
        require(report.get(key) == actual[key], 'Outer report mismatch: ' + key)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--audit', type=Path, help='existing fixed-profile candidate to audit')
    a = p.parse_args()
    out = P.reserve(a.output)
    parent, inputs, material, ev = fixed(out)
    stock, partitions = stock_inputs()
    if a.audit:
        selected = P.reject_links(a.audit).resolve(strict=True)
        require(selected.is_relative_to((ROOT / 'out').resolve()), 'Selected output outside out/')
        actual = audit_image((selected / 'vendor_boot.img').read_bytes(), selected, inputs, material, ev, stock, out)
        audit_report(json.loads((selected / 'outer-record.json').read_text()), actual, selected)
        O.write_json(out / 'audit.json', dict(status='self-checked', **actual))
        print('self-checked audit', actual['outer_sha256'])
        return
    adt = C.derived(inputs['parent-adt'], DIGEST)
    C.check_adt(inputs['parent-adt'], adt, DIGEST)
    (out / 'kernel.macho').write_bytes(inputs['kernel'])
    (out / 'derived.adt').write_bytes(adt)
    (out / 'payload.img').write_bytes(inputs['fat'])
    (out / 'unixnu.toml').write_bytes(inputs['config'])
    replace_members(out / 'payload.img', out / 'kernel.macho', out / 'derived.adt', out / 'unixnu.toml', inputs['fat'])
    fat = (out / 'payload.img').read_bytes()
    rec = expected_record(inputs, material, ev, adt, fat)
    O.write_json(out / 'record.json', rec)
    O.write_json(out / 'layout.json', rec['layout'])
    O.write_json(out / 'provenance.json', provenance(inputs, ev))
    inspect_payload(out, parent, inputs, material, ev, out / 'prepack-audit')
    base = V.check_base(BASE)
    soc = P.verify_soc(ROOT.parent / 'UniXNU-sm8550-common')
    (out / 'build-input.toml').write_text('[build]\n')
    command = [sys.executable, '-B', str(base / 'unixnu'), 'vendor_boot', '--stock', str(STOCK),
               '--ramdisk', str(out / 'payload.img'), '-o', str(out / 'vendor_boot.img'), '-D', str(ROOT),
               '--out', str(out / 'context'), '--config', str(out / 'build-input.toml'),
               '--local-module', 'soc:sm8550=' + str(soc), '-j', '1']
    process = subprocess.run(command, cwd=base, capture_output=True, text=True)
    O.write_json(out / 'official-command.json', {'argv': command, 'cwd': str(base), 'exit': process.returncode,
                                                  'stdout': process.stdout, 'stderr': process.stderr})
    require(process.returncode == 0, 'Official vendor_boot failed; see official-command.json')
    audit_work = out / 'outer-audit'
    audit_work.mkdir()
    actual = audit_image((out / 'vendor_boot.img').read_bytes(), out, inputs, material, ev, stock, audit_work)
    report = {**actual, 'profile': PROFILE, 'record_path': str(out / 'record.json'),
              'stock_sha256': V.STOCK_SHA, 'original_backup_sha256': BACKUP_SHA,
              'original_backup_is_template': False, 'loader_sha256': V.R4_SHA,
              'partition_evidence': partitions, 'authentication': 'NOT REACHED', 'device_release': False}
    O.write_json(out / 'outer-record.json', report)
    audit_report(report, actual, out)
    O.write_json(out / 'audit.json', dict(status='self-checked', **actual))
    print(json.dumps({'status': 'self-checked', 'profile': PROFILE, 'kernel_sha256': KERNEL_SHA,
                      'adt_sha256': O.sha(adt), 'fat_sha256': O.sha(fat),
                      'record_sha256': actual['record_sha256'], 'outer_sha256': actual['outer_sha256'],
                      'chmh': DIGEST.hex()}, indent=2))


if __name__ == '__main__':
    main()
