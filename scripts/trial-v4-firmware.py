"""Authorized temporary nuwa v4 firmware trial and original-boot recovery.

Only launch the pinned candidate or the pinned original recovery boot. No flash,
erase, slot changes, image generation, or persistent serial-number records.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / 'out/trial-boot/firmware-v4/boot-firmware-v4.img'
ORIGINAL = Path('D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
HASHES = {CANDIDATE: '12864ac6cc0ffc9909f4abbdfab91bfee216c3fdcfc5ab0d52b4d4b9cf4579f9',
          ORIGINAL: 'ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def devices(tool):
    p = subprocess.run([tool, 'devices'], capture_output=True, text=True, timeout=15, check=True)
    return [s[0] for line in p.stdout.splitlines() if len(s := line.split()) == 2
            and s[1] == ('device' if tool == 'adb' else 'fastboot')]


def capture_confirmed(gate, approval):
    confirmation = gate.get('human_capture_confirmation')
    if approval in ('MMU-BRANCHES-OFFLINE', 'HOB-QUERY-OFFLINE', 'VOLUME-PROBE-OFFLINE', 'HOB-INTEGRITY-OFFLINE', 'VOLUME-STATUS-OFFLINE'):
        return isinstance(confirmation, str) and bool(confirmation.strip())
    return confirmation == '可以，启动前通知我'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['launch', 'recover'])
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--package', type=Path, help='R-007/R-008/R-009 approved hash-pinned package report')
    parser.add_argument('--preflight', type=Path, help='Fresh D-021 process-log/recovery gate evidence, required for launch')
    parser.add_argument('--observation-seconds', type=int, default=120,
                        help='USB observation window after ACK, 120-600 seconds; not a process-log substitute')
    args = parser.parse_args()
    if not 120 <= args.observation_seconds <= 600:
        raise ValueError('Observation window must be 120-600 seconds')
    evidence = args.evidence.resolve()
    if not evidence.is_relative_to(ROOT / 'reports') or evidence.exists():
        raise ValueError('Evidence must be a fresh reports file')
    candidate, candidate_sha = CANDIDATE, HASHES[CANDIDATE]
    package_sha = None
    if args.package:
        package_path = args.package.resolve()
        scopes = {'R-007 A': ROOT / 'reports/sec-trace', 'R-008 A': ROOT / 'reports/relative-offset',
                  'R-009 A': ROOT / 'reports/pil-no-auto', 'R-010 A': ROOT / 'reports/dxe-allocation', 'R-011 A': ROOT / 'reports/factory-heap',
                  'SEC-HANDOFF-OFFLINE': ROOT / 'reports/sec-handoff',
                  'CONSTRUCTOR-TRACE-OFFLINE': ROOT / 'reports/constructor-trace',
                  'MMU-BRANCHES-OFFLINE': ROOT / 'reports/mmu-branches',
                  'HOB-QUERY-OFFLINE': ROOT / 'reports/hob-query',
                  'VOLUME-PROBE-OFFLINE': ROOT / 'reports/volume-envelope',
                  'HOB-INTEGRITY-OFFLINE': ROOT / 'reports/hob-integrity',
                  'VOLUME-STATUS-OFFLINE': ROOT / 'reports/volume-status'}
        package_raw = package_path.read_bytes()
        package = json.loads(package_raw)
        approval = package.get('approval')
        if approval in ("VOLUME-PROBE-OFFLINE", "HOB-INTEGRITY-OFFLINE", "VOLUME-STATUS-OFFLINE"):
            from volume_probe_package import validate
            validate(package_path)
        if approval in ('SEC-HANDOFF-OFFLINE', 'CONSTRUCTOR-TRACE-OFFLINE', 'MMU-BRANCHES-OFFLINE', 'HOB-QUERY-OFFLINE'):
            from sec_handoff_package import validate
            validate(package_path)
        if (approval not in scopes or not package_path.is_relative_to(scopes[approval])
                or package['header_version'] != 4
                or package['xnu_included'] or (package['fat_included'] and approval not in ('VOLUME-PROBE-OFFLINE', 'HOB-INTEGRITY-OFFLINE', 'VOLUME-STATUS-OFFLINE')) or package['appended_dtb']
                or package['original_boot_sha256'] != HASHES[ORIGINAL]):
            raise ValueError('Package is outside the approved trial scope')
        if approval == 'R-008 A' and (package['shim_text_offset'] != 0
                or package['fd_sha256'] != '9ea347a49e51472adac987cf12e20f9e0d99453a23f2113ad24efcd0a07f2eaf'
                or package['firmware_commit'] != '910ee079fbaef736c49c14fd24501b132e98bb90'
                or package['shim_bytes'] != 112 or package['fd_copy_destination'] != '0xa7100000'
                or not package['shim_changed_byte_offsets']
                or any(not 8 <= i < 16 for i in package['shim_changed_byte_offsets'])):
            raise ValueError('R-008 package exceeds the header-only scope')
        if approval in ('R-009 A', 'R-010 A', 'R-011 A') and (package['firmware_commit'] != (json.loads((ROOT / 'config/firmware-factory-heap-profile.json').read_text())['recipe']['sources']['firmware']['commit'] if approval == 'R-011 A' else '2ab6827d77dfe15010534b52e1abb76a26464a7d')
                or package['shim_text_offset'] != 0 or package['pil_auto_entries'] != []
                or package['pil_config_sha256'] != 'dbc9ee6e4c7728b32245453322f348c32d6a5eef0107f8c07662918bc3c23fdd'
                or package['pil_driver_sha256'] != '89e030af07847bdc596f0c213bdce0ac430be66e572db55b434d7ec66ad9afcb'
                or package['shim_sha256'] != '8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462'):
            raise ValueError('R-009 package exceeds the approved PIL configuration scope')
        r010_profile = json.loads((ROOT / 'config/firmware-dxe-allocation-profile.json').read_text())
        if approval in ('R-010 A', 'R-011 A') and (package.get('diagnostic_patch_sha256') != r010_profile['candidate']['patches'][-1]['sha256']
                or not package.get('allocation_trace')
                or not all(package['allocation_trace']['markers'].values())):
            raise ValueError('R-010 actual-core allocation diagnostics absent')
        if approval == 'R-011 A' and (not package.get('factory_heap')
                or package['factory_heap']['base'] != '0xbab00000'
                or package['factory_heap']['bytes'] != 0x0d1c0000):
            raise ValueError('R-011 actual SEC factory Heap evidence absent')
        candidate = (ROOT / package['image_path']).resolve()
        if not candidate.is_relative_to(ROOT / 'out/trial-boot'):
            raise ValueError('Diagnostic candidate escapes trial output')
        candidate_sha = package['image_sha256']
        package_sha = hashlib.sha256(package_raw).hexdigest()
    checked_hashes = {ORIGINAL: HASHES[ORIGINAL]}
    if args.phase == 'launch':
        checked_hashes[candidate] = candidate_sha
    for path, digest in checked_hashes.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Pinned boot input changed')
    gate = None
    if args.phase == 'launch':
        if not args.package or not args.preflight:
            raise ValueError('D-021: package and fresh process-log/recovery preflight required before device action')
        gate_path = args.preflight.resolve()
        if not gate_path.is_relative_to(ROOT / 'reports'):
            raise ValueError('Preflight evidence must be repo-local')
        gate = json.loads(gate_path.read_text())
        age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(gate['at'])).total_seconds()
        if (not 0 <= age <= 900 or gate['package_sha256'] != package_sha
                or gate['process_log_method'] != 'framebuffer photographed or recorded by user'
                or not capture_confirmed(gate, package['approval'])
                or gate['android_boot_completed'] != '1' or gate['device'] != 'nuwa'
                or gate['soc'] != 'kalama' or gate['original_boot_sha256'] != HASHES[ORIGINAL]):
            raise ValueError('D-021: log/recovery gate missing, stale, or mismatched')
        recovery = (ROOT / gate['recovery_evidence']['path']).resolve()
        if (not recovery.is_relative_to(ROOT / 'reports')
                or hashlib.sha256(recovery.read_bytes()).hexdigest() != gate['recovery_evidence']['sha256']
                or json.loads(recovery.read_text()).get('android_boot_completed') != '1'):
            raise ValueError('D-021: prior concrete recovery evidence absent')
    evidence.parent.mkdir(parents=True, exist_ok=True)
    report = dict(phase=args.phase, started_at=now(), commands=[], observations=[],
                  authorization=package['approval']+' explicit diagnostic trial/recovery approval' if args.package else
                  'User explicitly approved temporary prepared v4 candidate trial; original recovery authorized',
                  candidate_sha256=candidate_sha, candidate_package_sha256=package_sha,
                  recovery_sha256=HASHES[ORIGINAL], preflight=gate)
    if args.package and package['approval'] in ('SEC-HANDOFF-OFFLINE', 'CONSTRUCTOR-TRACE-OFFLINE', 'MMU-BRANCHES-OFFLINE', 'HOB-QUERY-OFFLINE'):
        report['authorization'] = 'Offline diagnostic preparation authorized; launch requires fresh D-021 log/recovery gate and immediate user capture notice'

    def save():
        evidence.write_text(json.dumps(report, indent=2) + '\n')

    def run(tool, serial, argv, timeout=20):
        p = subprocess.run([tool, '-s', serial, *argv], capture_output=True, text=True, timeout=timeout)
        report['commands'].append(dict(at=now(), argv=[tool, '-s', '<selected-nuwa>', *argv],
                                       exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr))
        save()
        return p

    def adb_target():
        found = []
        for serial in devices('adb'):
            p = subprocess.run(['adb', '-s', serial, 'shell', 'getprop ro.product.device'],
                               capture_output=True, text=True, timeout=10)
            if p.returncode or p.stdout.strip() != 'nuwa':
                continue
            identity = run('adb', serial, ['exec-out', "su -c 'cat /sys/firmware/devicetree/base/model; cat /sys/firmware/devicetree/base/compatible'"])
            if identity.returncode == 0 and 'nuwa' in identity.stdout.lower() and 'kalama' in identity.stdout.lower():
                found.append(serial)
        if len(found) > 1:
            raise ValueError('Ambiguous nuwa devices')
        return found[0] if found else None

    def fastboot_target():
        found = []
        for serial in devices('fastboot'):
            product = run('fastboot', serial, ['getvar', 'product'])
            if product.returncode == 0 and 'product: nuwa' in product.stdout + product.stderr:
                found.append(serial)
        if len(found) > 1:
            raise ValueError('Ambiguous nuwa bootloaders')
        return found[0] if found else None

    def reset_bootloader(serial):
        if run('fastboot', serial, ['reboot', 'bootloader']).returncode:
            raise RuntimeError('Cannot isolate bootloader state (D-016)')
        time.sleep(2)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            current = fastboot_target()
            if current:
                return current
            time.sleep(2)
        raise RuntimeError('Nuwa bootloader did not return after reset')

    try:
        serial = fastboot_target()
        if args.phase == 'launch':
            if not serial:
                serial = adb_target()
                if not serial:
                    raise RuntimeError('No identified nuwa target')
                p = run('adb', serial, ['shell', 'getprop sys.boot_completed'])
                if p.returncode or p.stdout.strip() != '1':
                    raise RuntimeError('Android precondition not complete')
                if run('adb', serial, ['reboot', 'bootloader']).returncode:
                    raise RuntimeError('Cannot enter bootloader')
                deadline = time.monotonic() + 60
                serial = None
                while time.monotonic() < deadline:
                    time.sleep(2)
                    serial = fastboot_target()
                    if serial:
                        break
            if not serial:
                raise RuntimeError('No nuwa bootloader after reboot')
            serial = reset_bootloader(serial)
            unlocked = run('fastboot', serial, ['getvar', 'unlocked'])
            if unlocked.returncode or 'unlocked: yes' not in unlocked.stdout + unlocked.stderr:
                raise RuntimeError('Bootloader not unlocked')
            run('fastboot', serial, ['getvar', 'current-slot'])
            print('Launching hash-pinned v4 firmware candidate', flush=True)
            boot = run('fastboot', serial, ['boot', str(candidate)], timeout=50)
            print(boot.stdout + boot.stderr, flush=True)
            report['fastboot_boot_exit_code'] = boot.returncode
            save()
            # A returned success is command acceptance, not proof of SEC/DXE.
            observed_from = time.monotonic()
            report['observation_scope'] = 'USB presence only; screen video needed for process logs'
            report['requested_observation_seconds'] = args.observation_seconds
            while True:
                report['observations'].append(dict(at=now(),
                    seconds_after_ack=round(time.monotonic() - observed_from, 3),
                    selected_nuwa_in_fastboot=serial in devices('fastboot'),
                    adb_device_count=len(devices('adb'))))
                save()
                if boot.returncode or time.monotonic() - observed_from >= args.observation_seconds:
                    break
                time.sleep(max(0, min(2, args.observation_seconds - (time.monotonic() - observed_from))))
        else:
            if serial:
                serial = reset_bootloader(serial)
                print('Temporarily loading original nuwa recovery boot', flush=True)
                boot = run('fastboot', serial, ['boot', str(ORIGINAL)], timeout=50)
                print(boot.stdout + boot.stderr, flush=True)
                if boot.returncode:
                    raise RuntimeError('Original boot rejected')
            original_sent = bool(serial)
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                serial = adb_target()
                if serial:
                    p = run('adb', serial, ['shell', 'getprop sys.boot_completed'])
                    if p.returncode == 0 and p.stdout.strip() == '1':
                        report['android_boot_completed'] = '1'
                        print('Identified nuwa Android boot_completed=1', flush=True)
                        break
                if not serial and not original_sent:
                    bootloader = fastboot_target()
                    if bootloader:
                        bootloader = reset_bootloader(bootloader)
                        boot = run('fastboot', bootloader, ['boot', str(ORIGINAL)], timeout=50)
                        print(boot.stdout + boot.stderr, flush=True)
                        if boot.returncode:
                            raise RuntimeError('Original recovery boot rejected after fastboot returned')
                        original_sent = True
                time.sleep(5)
            else:
                raise RuntimeError('Android completion not observed; recovery remains pending')
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        report['ended_at'] = now()
        save()


if __name__ == '__main__':
    main()
