#!/usr/bin/env python3
"""Strict host-only derived AMNM FAT/outer. Does not modify its parent profile."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import owner_bnch as O
import owner_payload as P

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

C = load('continuation_outer', 'build-owner-continuation-vendor-boot.py')
L = load('relative_layout', 'audit-owner-pmap-ret-package.py')
V = C.V
PROFILE = 'amnm-observe-20261111-r1'
KERNEL = Path('/root/nuwa-amnm-final-candidate-stage3-20261111/kernel-amnm.macho')
KERNEL_SHA = '1754a89e8e92e20baafeaf0e1f98361b0d41ddaea8f420dd44d34d1357f2d162'
ADT_SHA = '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4'
PARENT_SHA = 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57'
AUDIT_SHA = '1c55d23db13bb142a353a2ebdb3eeaa2b47cf1f91592624c93f79ecc8a265fcb'
AUDIT = Path('/root/nuwa-amnm-verifier-amnm-final-r3-20261111/audit.json')
PARENT = O.ROOT/'out/owner-pmap-ret-continuation-verifier-final-20261111'
LAYOUT = O.ROOT/'out/owner-pmap-ret-continuation-verifier-layout-20261111/layout.json'
OUTPUT = O.ROOT/'out/amnm-observe-20261111-r1'
BASE = O.ROOT.parent.parent/'UniXNU'
MEMBERS = {'Payloads/kernel.macho', 'Payloads/kernel.macho.adt',
           'Payloads/kernel.macho.trustcache', 'unixnu.toml'}

def validate_record(record, kernel, adt, trust, parent):
    O.require(record.get('type') == 'amnm-derived-input-v1' and record.get('profile') == PROFILE,
              'AMNM derived record type/profile mismatch')
    O.require(record.get('parent_record_sha256') == O.sha(parent) == PARENT_SHA,
              'AMNM parent record mismatch')
    O.require(record.get('kernel_sha256') == O.sha(kernel) == KERNEL_SHA and
              record.get('kernel_bytes') == len(kernel), 'AMNM kernel hash/size mismatch')
    O.require(record.get('adt_sha256') == O.sha(adt) == ADT_SHA and len(adt) == 13256,
              'AMNM ADT mismatch')
    O.require(record.get('trust_sha256') == O.sha(trust), 'AMNM trust mismatch')
    O.require(record.get('args') == ['-v', 'serial=3'] and record.get('device_release') is False,
              'AMNM argument/release mismatch')

def build():
    base = V.check_base(BASE)
    ctx = C.validate_inputs(PARENT, O.ROOT/'.cache/stock/vendor_boot_b.img',
        O.ROOT/'.cache/boot-stage12-v4-r4.img', LAYOUT)
    kernel = KERNEL.read_bytes(); adt = ctx.adt
    parent = ctx.record_path.read_bytes()
    trust = (PARENT/'inputs/kernel.macho.trustcache').read_bytes()
    O.require(O.sha(kernel) == KERNEL_SHA and len(kernel) == 55402496, 'AMNM kernel input mismatch')
    O.require(O.sha((O.ROOT/'scripts/audit-amnm-final.py').read_bytes()) == AUDIT_SHA, 'AMNM audit script mismatch')
    audit = json.loads(AUDIT.read_text())
    O.require(audit['candidate']['sha256'] == KERNEL_SHA and audit['candidate']['bytes'] == len(kernel)
              and audit['winner']['bytes'] == 4 and audit['log']['bytes'] == 1920
              and audit['panic_text']['bytes'] == 2048, 'AMNM verifier evidence mismatch')
    config_bytes = (PARENT/'extracted/EFI/UniXNU/unixnu.toml').read_bytes()
    config = tomllib.loads(config_bytes.decode())
    O.require(config['boot']['default'] == 'xnu' and len(config['entry']) == 4 and
              sum(e['type'] == 'xnu' for e in config['entry']) == 1 and
              sum(e['type'] == 'action' for e in config['entry']) == 3 and
              config['entry'][0]['args'] == '-v serial=3', 'AMNM menu/args mismatch')
    tree = O.inspect_adt(adt, O.load_record(ctx.record_path)[1])
    facts = P.diagnostic_adt(adt)
    base_va, end_va, segments = L.vm_layout(kernel)
    chosen = dict(O.find(tree, '/chosen')[1])
    window = int.from_bytes(chosen['darwinboot-memory-size'], 'little')
    layout = L.relative_layout(base_va, end_va, len(adt), len(trust), window)
    for obj in ('log','panic_text','winner'):
        lo, hi = int(audit[obj]['va'],16), int(audit[obj]['end'],16)
        O.require(any(s['name'] == '__DATA' and s['vmaddr'] <= lo < hi <= s['vmaddr']+s['vmsize']
                      for s in segments), 'AMNM ' + obj + ' outside VM data')
    record = {'type':'amnm-derived-input-v1', 'profile':PROFILE, 'parent_record_sha256':PARENT_SHA,
              'kernel_sha256':KERNEL_SHA, 'kernel_bytes':len(kernel), 'adt_sha256':ADT_SHA,
              'trust_sha256':O.sha(trust), 'args':['-v','serial=3'], 'device_release':False,
              'input_preservation':'parent ADT, BNCH, random seed, trust and arguments unchanged',
              'authentication':'NOT REACHED'}
    validate_record(record,kernel,adt,trust,parent)
    out = P.reserve(OUTPUT)
    O.write_json(out/'derived-record.json',record)
    fat = out/'payload.img'; fat.write_bytes(ctx.fat)
    kernel_file = out/'kernel.input'; kernel_file.write_bytes(kernel)
    P.capture(['mcopy','-o','-i',fat,kernel_file,'::/EFI/UniXNU/Payloads/kernel.macho'],out/'fat-write-command.json')
    extracted = out/'fat-extracted'; extracted.mkdir()
    P.capture(['mcopy','-s','-i',fat,'::/EFI',extracted],out/'fat-extract-command.json')
    expected = {'Payloads/kernel.macho':kernel, 'Payloads/kernel.macho.adt':adt,
                'Payloads/kernel.macho.trustcache':trust, 'unixnu.toml':config_bytes}
    O.require(set(expected) == MEMBERS, 'AMNM member list mismatch')
    hashes = P.verify_extracted(extracted, expected, adt, ctx.record_path,
                                SimpleNamespace(board=ctx.board), '-v serial=3')
    O.require(hashes['Payloads/kernel.macho.adt'] == ADT_SHA, 'FAT ADT drift')
    O.write_json(out/'build-input.toml.json', {'reason':'isolated official vendor_boot build'})
    (out/'build-input.toml').write_text('[build]\n')
    dest = out/'vendor_boot.img'
    command = [sys.executable,'-B',str(base/'unixnu'),'vendor_boot','--stock',str(ctx.stock_path),
               '--ramdisk',str(fat),'-o',str(dest),'-D',str(O.ROOT),'--out',str(out/'context'),
               '--config',str(out/'build-input.toml'),'--local-module','soc:sm8550='+str(P.verify_soc(O.ROOT.parent/'UniXNU-sm8550-common')),'-j','1']
    result = subprocess.run(command,cwd=base,capture_output=True,text=True)
    O.write_json(out/'official-command.json',{'command':command,'cwd':str(base),'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    O.require(result.returncode == 0, 'official vendor_boot failed; see official-command.json')
    outer = dest.read_bytes(); fat_bytes = fat.read_bytes()
    diff = V.compare(ctx.stock,outer,fat_bytes,ctx.partitions['vendor_boot_b']['bytes'])
    extracted_fat = out/'actual-vendor-ramdisk.img'; extracted_fat.write_bytes(V.parse(outer)['ramdisk'])
    O.require(extracted_fat.read_bytes() == fat_bytes,'outer ramdisk mismatch')
    outer_extract = out/'outer-extracted'; outer_extract.mkdir()
    P.capture(['mcopy','-s','-i',extracted_fat,'::/EFI',outer_extract],out/'outer-extract-command.json')
    O.require(P.verify_extracted(outer_extract,expected,adt,ctx.record_path,
              SimpleNamespace(board=ctx.board),'-v serial=3') == hashes,'outer FAT content mismatch')
    report = {'status':'self-checked','profile':PROFILE,'device_release':False,'readback_complete':True,
              'kernel_sha256':KERNEL_SHA,'kernel_bytes':len(kernel),'adt_sha256':ADT_SHA,
              'parent_record_sha256':PARENT_SHA,'fat_sha256':O.sha(fat_bytes),'fat_bytes':len(fat_bytes),
              'outer_sha256':O.sha(outer),'outer_bytes':len(outer),'fat_hashes':hashes,
              'historical_stock_sha256':C.STOCK_SHA,'current_backup':C.current_backup_comparison(ctx.stock),
              'loader_sha256':C.R4_SHA,'relative_layout':layout,'kernel_vm_base':base_va,'kernel_vm_end':end_va,
              'root_segments':segments,'adt_facts':facts,'outer_comparison':diff,
              'runtime_window':'not observed','authentication':'NOT REACHED'}
    O.write_json(out/'report.json',report)
    print(json.dumps(report,indent=2))

if __name__ == '__main__': build()
