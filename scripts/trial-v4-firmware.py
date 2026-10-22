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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['launch', 'recover'])
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    if not evidence.is_relative_to(ROOT / 'reports') or evidence.exists():
        raise ValueError('Evidence must be a fresh reports file')
    for path, digest in HASHES.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Pinned boot input changed')
    evidence.parent.mkdir(parents=True, exist_ok=True)
    report = dict(phase=args.phase, started_at=now(), commands=[], observations=[],
                  authorization='User explicitly approved temporary prepared v4 candidate trial; original recovery authorized',
                  candidate_sha256=HASHES[CANDIDATE], recovery_sha256=HASHES[ORIGINAL])

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
            unlocked = run('fastboot', serial, ['getvar', 'unlocked'])
            if unlocked.returncode or 'unlocked: yes' not in unlocked.stdout + unlocked.stderr:
                raise RuntimeError('Bootloader not unlocked')
            run('fastboot', serial, ['getvar', 'current-slot'])
            print('Launching hash-pinned v4 firmware candidate', flush=True)
            boot = run('fastboot', serial, ['boot', str(CANDIDATE)], timeout=50)
            print(boot.stdout + boot.stderr, flush=True)
            report['fastboot_boot_exit_code'] = boot.returncode
            save()
            # A returned success is command acceptance, not proof of SEC/DXE.
            for _ in range(15 if boot.returncode == 0 else 1):
                report['observations'].append(dict(at=now(),
                    selected_nuwa_in_fastboot=serial in devices('fastboot'),
                    adb_device_count=len(devices('adb'))))
                save()
                if boot.returncode == 0:
                    time.sleep(2)
        else:
            if serial:
                print('Temporarily loading original nuwa recovery boot', flush=True)
                boot = run('fastboot', serial, ['boot', str(ORIGINAL)], timeout=50)
                print(boot.stdout + boot.stderr, flush=True)
                if boot.returncode:
                    raise RuntimeError('Original boot rejected')
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                serial = adb_target()
                if serial:
                    p = run('adb', serial, ['shell', 'getprop sys.boot_completed'])
                    if p.returncode == 0 and p.stdout.strip() == '1':
                        report['android_boot_completed'] = '1'
                        print('Identified nuwa Android boot_completed=1', flush=True)
                        break
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
