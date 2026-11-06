"""Collect allowlisted Android driver metadata through read-only root ADB.

No reboot, writes, raw DTB/partition reads, serials, or firmware control nodes.
This observes Android bindings, not XNU driver execution.
"""
import datetime
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {
    'identity': 'getprop sys.boot_completed; getprop ro.product.device; uname -a; id; cat /proc/device-tree/model; echo; tr "\\000" "\\n" < /proc/device-tree/compatible',
    'input-bindings': 'for d in /sys/class/input/input*; do echo "INPUT $d"; cat "$d/name"; readlink -f "$d/device"; readlink -f "$d/device/driver"; done',
    'spi-bindings': 'for d in /sys/bus/spi/devices/*; do echo "SPI $d"; cat "$d/modalias"; readlink -f "$d/driver"; readlink -f "$d/driver/module"; readlink -f "$d/of_node"; ls "$d"; done',
    'platform-bindings': 'for d in /sys/bus/platform/devices/*; do case "$d" in *ufs*|*smmu*|*gpu*|*kgsl*|*display*|*dsi*|*mdss*) echo "PLATFORM $d"; readlink -f "$d/driver"; readlink -f "$d/driver/module"; readlink -f "$d/of_node";; esac; done',
    'modules': 'cat /proc/modules | cut -d " " -f 1-3; for d in /sys/module/*; do case "$d" in *fts*|*focal*|*touch*|*goodix*|*kgsl*|*drm*|*ufs*|*smmu*) echo "MODULE $d"; for p in version srcversion; do if test -r "$d/$p"; then echo "$p"; cat "$d/$p"; fi; done;; esac; done',
    'display': 'for d in /sys/class/drm/* /sys/class/graphics/fb*; do test -e "$d" || continue; echo "DISPLAY $d"; readlink -f "$d/device"; for p in name modes status enabled virtual_size bits_per_pixel; do if test -r "$d/$p"; then echo "$p"; cat "$d/$p"; fi; done; done',
    'gpu-storage': 'for p in /sys/class/kgsl/kgsl-3d0/gpu_model /sys/class/kgsl/kgsl-3d0/gpu_available_frequencies /sys/class/scsi_device/*/device/vendor /sys/class/scsi_device/*/device/model /sys/class/scsi_device/*/device/rev; do test -r "$p" || continue; echo "$p"; cat "$p"; done',
    'dt-node-paths': 'find /sys/firmware/devicetree/base -type d | grep -Ei "fts|focal|touch|goodix|panel|dsi|mdss|ufs|smmu|gpu|kgsl|spi@|spi$"',
    'kernel-config': 'if test -r /proc/config.gz; then zcat /proc/config.gz | grep -E "^CONFIG_(TOUCHSCREEN|FTS|FOCAL|GOODIX|QCOM|SCSI_UFS|ARM_SMMU|DRM_MSM|FB_MSM|QCOM_KGSL)"; else echo "CONFIG_UNAVAILABLE"; fi',
    'iomem': 'cat /proc/iomem',
    'boot-completed-after': 'getprop sys.boot_completed',
}


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    dest = ROOT / 'reports/android-driver-evidence' / now.strftime('%Y%m%dT%H%M%SZ')
    dest.mkdir(parents=True, exist_ok=False)
    records = []
    for name, command in COMMANDS.items():
        argv = ['adb', 'exec-out', 'su -c ' + shlex.quote(command)]
        result = subprocess.run(argv, capture_output=True, timeout=45)
        output = result.stdout.decode('utf-8', errors='replace')
        stderr = result.stderr.decode('utf-8', errors='replace')
        # Commands intentionally never request a device serial or unique ID.
        (dest / (name + '.txt')).write_text(output, encoding='utf-8')
        records.append({'name': name, 'argv': argv, 'exit_code': result.returncode,
                        'stderr': stderr, 'bytes': len(result.stdout)})
        print(name, result.returncode, len(result.stdout), flush=True)
    (dest / 'commands.json').write_text(json.dumps({
        'collected_at': now.isoformat(), 'scope': 'read-only Android observations; XNU untested',
        'commands': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(dest)


if __name__ == '__main__':
    main()
