"""Read-only nuwa Android state, partition hashes and D-021 trial preflight."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = Path('D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
ORIGINAL_SHA = 'ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31'

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--package', type=Path, help='Enable R-010 preflight using the user capture confirmation')
    cli.add_argument('--before', type=Path, help='Compare final partition hashes with this prior record')
    cli.add_argument('--capture-confirmation', help='Fresh user confirmation for this specific trial')
    args = cli.parse_args()
    if args.package:
        metadata = json.loads(args.package.read_text())
        if metadata.get('approval') == 'USB-RAMDISK-V3-OFFLINE':
            from usb_ramdisk_package import validate
            validate(args.package)
            if not (args.capture_confirmation or '').strip():
                raise ValueError('Fresh USB ramdisk capture confirmation required before device query')
        if metadata.get('approval') in ('EMBEDDED-PROBE-OFFLINE', 'BOOT-INPUT-AUDIT-OFFLINE', 'HOB-STAGE-AUDIT-OFFLINE', 'HOB-CACHE-HANDOFF-OFFLINE'):
            from embedded_probe_package import validate
            validate(args.package)
        if metadata.get("approval") in ("VOLUME-PROBE-OFFLINE", "HOB-INTEGRITY-OFFLINE", "VOLUME-STATUS-OFFLINE"):
            from volume_probe_package import validate
            validate(args.package)
        if metadata.get('approval') in ('SEC-HANDOFF-OFFLINE', 'CONSTRUCTOR-TRACE-OFFLINE', 'MMU-BRANCHES-OFFLINE', 'HOB-QUERY-OFFLINE'):
            from sec_handoff_package import validate
            validate(args.package)
        if metadata.get('approval') in ('MMU-BRANCHES-OFFLINE', 'HOB-QUERY-OFFLINE', 'VOLUME-PROBE-OFFLINE', 'HOB-INTEGRITY-OFFLINE', 'VOLUME-STATUS-OFFLINE', 'EMBEDDED-PROBE-OFFLINE', 'BOOT-INPUT-AUDIT-OFFLINE', 'HOB-STAGE-AUDIT-OFFLINE', 'HOB-CACHE-HANDOFF-OFFLINE') and not (args.capture_confirmation or '').strip():
            raise ValueError('Fresh user capture confirmation required before MMU trial preflight')
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'reports') or output.exists():
        raise ValueError('Fresh reports file required')
    found = []
    for line in subprocess.check_output(['adb', 'devices'],text=True).splitlines():
        parts = line.split()
        if len(parts)==2 and parts[1]=='device':
            p = subprocess.run(['adb','-s',parts[0],'shell','getprop','ro.product.device'],capture_output=True,text=True,timeout=15)
            if p.returncode==0 and p.stdout.strip()=='nuwa':
                found.append(parts[0])
    if len(found)!=1:
        raise ValueError('No unique nuwa ADB target')
    serial = found[0]
    report = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(), commands=[])
    values = {}
    for key, command in (
        ('identity', "su -c 'cat /sys/firmware/devicetree/base/model; cat /sys/firmware/devicetree/base/compatible'"),
        ('android_boot_completed', 'getprop sys.boot_completed'),
        ('slot', 'getprop ro.boot.slot_suffix'),
        ('partition_hashes', "su -c 'sha256sum /dev/block/by-name/boot_a /dev/block/by-name/vendor_boot_a /dev/block/by-name/init_boot_a'")):
        p=subprocess.run(['adb','-s',serial,'exec-out',command],capture_output=True,text=True,timeout=45)
        value=p.stdout.replace('\0','\n').strip()
        report['commands'].append(dict(argv=['adb','-s','<selected-nuwa>','exec-out',command],exit_code=p.returncode,stdout=value,stderr=p.stderr))
        if p.returncode:
            raise RuntimeError('Read-only query failed: '+key)
        values[key]=value
    if 'nuwa' not in values['identity'].lower() or 'kalama' not in values['identity'].lower() or values['android_boot_completed']!='1':
        raise ValueError('Target identity or Android completion gate failed')
    report.update(device='nuwa',soc='kalama',android_boot_completed='1',slot=values['slot'],
                  partition_hashes={line.split()[1]:line.split()[0] for line in values['partition_hashes'].splitlines()})
    if args.before:
        before=json.loads(args.before.read_text())
        report['three_partition_hashes_unchanged'] = report['partition_hashes']==before['partition_hashes']
        if not report['three_partition_hashes_unchanged']:
            raise ValueError('Partition hash changed')
    if args.package:
        package=args.package.resolve()
        scopes = {'R-010 A': ROOT/'reports/dxe-allocation', 'R-011 A': ROOT/'reports/factory-heap',
                  'SEC-HANDOFF-OFFLINE': ROOT/'reports/sec-handoff',
                  'CONSTRUCTOR-TRACE-OFFLINE': ROOT/'reports/constructor-trace',
                  'MMU-BRANCHES-OFFLINE': ROOT/'reports/mmu-branches',
                  'HOB-QUERY-OFFLINE': ROOT/'reports/hob-query',
                  'VOLUME-PROBE-OFFLINE': ROOT/'reports/volume-envelope',
                  'HOB-INTEGRITY-OFFLINE': ROOT/'reports/hob-integrity',
                  'VOLUME-STATUS-OFFLINE': ROOT/'reports/volume-status',
                  'EMBEDDED-PROBE-OFFLINE': ROOT/'reports/embedded-probe',
                  'BOOT-INPUT-AUDIT-OFFLINE': ROOT/'reports/boot-input-audit',
                  'HOB-STAGE-AUDIT-OFFLINE': ROOT/'reports/hob-stage-audit',
                  'HOB-CACHE-HANDOFF-OFFLINE': ROOT/'reports/hob-cache-handoff',
                  'USB-RAMDISK-V3-OFFLINE': ROOT/'reports/usb-ramdisk'}
        approval = json.loads(package.read_text())['approval']
        if approval not in scopes or not package.is_relative_to(scopes[approval]):
            raise ValueError('Unexpected allocation trial package report')
        if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()!=ORIGINAL_SHA:
            raise ValueError('Original recovery input changed')
        recovery=ROOT/'reports/dxe-allocation/39829943950/recovery.json'
        if json.loads(recovery.read_text()).get('android_boot_completed')!='1':
            raise ValueError('Concrete prior recovery evidence absent')
        report.update(package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
            process_log_method='framebuffer photographed or recorded by user',
            human_capture_confirmation=args.capture_confirmation or '可以，启动前通知我',
            human_capture_source=('Fresh user confirmation supplied for this trial; notify immediately before launch' if args.capture_confirmation else 'User confirmed capture on notice, supplied R-010 photos and approved R-011 A; notify immediately before launch'),
            recovery_path='Power plus volume down to fastboot (R-010 completed); reset bootloader and temporarily load pinned original boot; confirm Android completion',
            original_boot_sha256=ORIGINAL_SHA,
            recovery_evidence=dict(path=recovery.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(recovery.read_bytes()).hexdigest()))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('device','soc','android_boot_completed','slot')}))

if __name__=='__main__':
    main()
