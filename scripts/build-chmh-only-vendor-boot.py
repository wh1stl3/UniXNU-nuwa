"""Pinned CHMH-only vendor_boot host packaging and actual-byte audit; never boots."""
import argparse
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import owner_bnch as O
import owner_payload as P

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V = load('outer', 'build-owner-vendor-boot.py')
C = load('chmh', 'build-chmh-only-payload.py')
SELECTED = ROOT / 'out/chmh-only-verifier-20261112'
BASE = ROOT.parent.parent / 'UniXNU'
STOCK = ROOT / '.cache/stock/vendor_boot_b.img'
GPT = ROOT.parent / '.cache/device-evidence/20261107-recovery/gpt-sde.bin'
FAT_SHA = '799190b496fa3398412dec551910fa8920498a4e5313de9d3cd792706109db68'
ADT_SHA = '42494097fcd5e0777bc9792b2225df7eb39dc64384a2cae38fe09c409a790eed'
RECORD_SHA = '992416d057b280ea5376b839c34d169889968c248129b43befcb2737a731b08a'
BACKUP_SHA = '493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad'


def check_record(raw):
    O.require(O.sha(raw) == RECORD_SHA, 'Verifier derived record hash mismatch')
    rec = json.loads(raw)
    O.require(rec['profile'] == 'chmh-only-20261112-r1' and
              rec['type'] == 'experimental-unauthenticated-boot-set-identity' and
              rec['device_release'] is False and rec['authentication'] == 'NOT REACHED', 'Wrong CHMH profile')
    return rec


def check_config(raw):
    config = tomllib.loads(raw.decode())
    entries = [e for e in config['entry'] if e.get('type') == 'xnu']
    O.require(len(entries) == 1 and entries[0]['args'] == '-v serial=3', 'Wrong XNU args')


def fixed(work):
    selected = SELECTED.resolve(strict=True)
    fat = (selected / 'payload.img').read_bytes()
    adt = (selected / 'derived.adt').read_bytes()
    raw_record = (selected / 'record.json').read_bytes()
    record = check_record(raw_record)
    O.require(len(fat) == 67108864 and O.sha(fat) == FAT_SHA, 'Verifier FAT hash/size')
    O.require(len(adt) == 13340 and O.sha(adt) == ADT_SHA, 'Verifier ADT hash/size')
    parent = C.extract(C.FAT, work / 'parent')
    inputs = C.fixed_inputs(parent)
    C.check_inputs(inputs)
    O.require(parent['parent-adt'] == C.ADT.read_bytes(), 'Parent ADT mismatch')
    C.check_adt(inputs['parent-adt'], adt, C.EXPECTED_DIGEST)
    C.audit(selected, parent, inputs, work / 'selected-fat-audit')
    check_config(inputs['config'])
    stock = STOCK.read_bytes()
    O.require(len(stock) == 100663296 and O.sha(stock) == V.STOCK_SHA, 'Historical stock template mismatch')
    partitions = V.gpt_capacity(GPT.read_bytes())
    O.require(partitions['vendor_boot_b']['bytes'] == len(stock), 'GPT capacity mismatch')
    backup = ROOT / 'out/pmap-ret-run-pmap-ret-20261111-r4/vendor_boot_b.stock.img'
    O.require(O.sha(backup.read_bytes()) == BACKUP_SHA and O.sha(stock) != BACKUP_SHA,
              'Original backup/template binding mismatch')
    O.require(O.sha(C.LOADER.read_bytes()) == V.R4_SHA, 'r4 loader mismatch')
    return {'fat': fat, 'adt': adt, 'record': record, 'parent': parent, 'inputs': inputs,
            'stock': stock, 'partitions': partitions}


def audit_image(image, ctx, work):
    comparison = V.compare(ctx['stock'], image, ctx['fat'], 100663296)
    actual_fat = V.parse(image)['ramdisk']
    O.require(O.sha(actual_fat) == FAT_SHA, 'Outer ramdisk hash mismatch')
    path = work / 'actual-vendor-ramdisk.img'
    path.write_bytes(actual_fat)
    members = C.extract(path, work / 'outer-fat')
    for key in ('kernel', 'trust', 'config'):
        O.require(members[key] == ctx['inputs'][key], 'Outer FAT member mismatch: ' + key)
    O.require(members['parent-adt'] == ctx['adt'], 'Outer FAT ADT mismatch')
    C.check_adt(ctx['inputs']['parent-adt'], members['parent-adt'], C.EXPECTED_DIGEST)
    check_config(members['config'])
    return {'outer_sha256': O.sha(image), 'ramdisk_sha256': O.sha(actual_fat),
            'members_sha256': {k: O.sha(v) for k, v in members.items()}, 'comparison': comparison}


def audit_report(report, actual):
    O.require(report.get('profile') == 'chmh-only-20261112-r1' and
              report.get('record_sha256') == RECORD_SHA and report.get('device_release') is False and
              report.get('authentication') == 'NOT REACHED', 'Outer report scope/record mismatch')
    value = report.get('record_path')
    O.require(type(value) is str and value != '', 'Missing verifier record path')
    path = Path(value)
    try:
        path = (path if path.is_absolute() else ROOT / path).resolve(strict=True)
        expected = (SELECTED / 'record.json').resolve(strict=True)
        O.require(path == expected, 'Verifier record path mismatch')
        O.require(O.sha(path.read_bytes()) == RECORD_SHA, 'Verifier record bytes mismatch')
    except OSError as exc:
        raise ValueError('Cannot read verifier record path') from exc
    O.require(report.get('stock_sha256') == V.STOCK_SHA and
              report.get('original_backup_sha256') == BACKUP_SHA and
              report.get('original_backup_is_template') is False, 'Outer source provenance mismatch')
    O.require(report.get('outer_sha256') == actual['outer_sha256'] and
              report.get('ramdisk_sha256') == FAT_SHA and report.get('members_sha256') == actual['members_sha256'],
              'Outer report bytes mismatch')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--audit', type=Path, help='Audit existing image/report rather than build')
    args = p.parse_args()
    out = P.reserve(args.output)
    ctx = fixed(out)
    if args.audit:
        source = args.audit.resolve(strict=True)
        result = audit_image((source / 'vendor_boot.img').read_bytes(), ctx, out)
        audit_report(json.loads((source / 'outer-record.json').read_text()), result)
        O.write_json(out / 'audit.json', result)
        print('self-checked actual-byte outer audit', result['outer_sha256'])
        return
    base = V.check_base(BASE)
    soc = P.verify_soc(ROOT.parent / 'UniXNU-sm8550-common')
    (out / 'build-input.toml').write_text('[build]\n')
    image = out / 'vendor_boot.img'
    command = [sys.executable, '-B', str(base / 'unixnu'), 'vendor_boot', '--stock', str(STOCK),
               '--ramdisk', str(SELECTED / 'payload.img'), '-o', str(image), '-D', str(ROOT),
               '--out', str(out / 'context'), '--config', str(out / 'build-input.toml'),
               '--local-module', 'soc:sm8550=' + str(soc), '-j', '1']
    process = subprocess.run(command, cwd=base, capture_output=True, text=True)
    O.write_json(out / 'official-command.json', {'argv': command, 'cwd': str(base), 'exit': process.returncode,
                                                  'stdout': process.stdout, 'stderr': process.stderr})
    O.require(process.returncode == 0, 'Official vendor_boot failed; see official-command.json')
    result = audit_image(image.read_bytes(), ctx, out)
    report = {**result, 'profile': 'chmh-only-20261112-r1', 'record_path': str(SELECTED / 'record.json'),
              'record_sha256': RECORD_SHA, 'stock_sha256': V.STOCK_SHA, 'original_backup_sha256': BACKUP_SHA,
              'original_backup_is_template': False, 'loader_sha256': V.R4_SHA,
              'authentication': 'NOT REACHED', 'device_release': False}
    O.write_json(out / 'outer-record.json', report)
    audit_report(report, result)
    print('self-checked outer', result['outer_sha256'])


if __name__ == '__main__':
    main()
