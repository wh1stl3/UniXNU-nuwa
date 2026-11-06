"""Read-only identity gate. Refuse nuwa boot preparation on another device."""
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    devices = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=15, check=True)
    matches = []
    for line in devices.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 2 or parts[1] != 'device':
            continue
        candidate = parts[0]
        identity = subprocess.run(['adb', '-s', candidate, 'exec-out',
                                   "su -c 'cat /sys/firmware/devicetree/base/model; cat /sys/firmware/devicetree/base/compatible'"],
                                  capture_output=True, text=True, timeout=15)
        if identity.returncode == 0 and 'nuwa' in identity.stdout.lower() and 'kalama' in identity.stdout.lower():
            matches.append(candidate)
    if len(matches) != 1:
        print('nuwa identity gate: no unique authorized nuwa ADB target')
        raise SystemExit(2)
    serial = matches[0]  # Host-only selection; never persist device serials.
    commands = {
        'model': 'cat /sys/firmware/devicetree/base/model',
        'compatible': 'cat /sys/firmware/devicetree/base/compatible',
        'machine': 'cat /sys/devices/soc0/machine',
        'vendor_device': 'getprop ro.product.vendor.device',
        'boot_completed': 'getprop sys.boot_completed',
    }
    records, values = [], {}
    for name, command in commands.items():
        argv = ['adb', '-s', serial, 'exec-out', 'su -c ' + shlex.quote(command)]
        result = subprocess.run(argv, capture_output=True, timeout=20)
        value = result.stdout.decode(errors='replace').replace('\0', '\n').strip()
        records.append(dict(name=name, argv=[*argv[:2], '<selected-nuwa>', *argv[3:]], exit_code=result.returncode,
                            stdout=value, stderr=result.stderr.decode(errors='replace')))
        values[name] = value
    accepted = (all(r['exit_code'] == 0 for r in records)
                and 'nuwa' in values['model'].lower()
                and 'kalama' in values['compatible'].lower()
                and values['machine'].upper() in ('KALAMA', 'SM8550')
                and values['boot_completed'] == '1')
    out = ROOT / 'reports/trial-boot-preflight/identity-gate.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(target_matches=accepted, observations=records,
                                   scope='Identity only; not boot or recovery verification'), indent=2) + '\n')
    print('nuwa identity gate: ' + ('PASS' if accepted else 'REJECT'))
    raise SystemExit(0 if accepted else 2)


if __name__ == '__main__':
    main()
