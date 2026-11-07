#!/usr/bin/env python3
"""Stage the firmware device tree for the boot image.

Runs as board.toml [firmware] preflight from the assembled build tree (cwd is the tree,
UNIXNU_UEFI points at the Mu-Silicium checkout). release packs the boot image with [bootimg]
dtb, which the base resolves relative to the tree, so the firmware checkout's compiled DTB is
copied to that path unchanged: no node or value is edited here, and the FDT blob the FDF embeds
is not an appended DTB.

usage: UNIXNU_UEFI=<uefi-nuwa checkout> python3 scripts/prepare-nuwa-firmware.py
"""
import os
import shutil
import sys
from pathlib import Path

SOURCE = Path('Platforms/Xiaomi/nuwaPkg/FdtBlob/sm8550-xiaomi-nuwa.dtb')
DESTINATION = Path('build/nuwa/sm8550-xiaomi-nuwa.dtb')


def main():
    uefi = os.environ.get('UNIXNU_UEFI')
    if not uefi:
        sys.exit('prepare-nuwa-firmware: UNIXNU_UEFI is not set; point it at the uefi-nuwa checkout')
    source = Path(uefi) / SOURCE
    if not source.is_file():
        sys.exit(f'prepare-nuwa-firmware: firmware device tree not found: {source}')
    destination = Path.cwd() / DESTINATION
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    print(f'prepare-nuwa-firmware: source {source}')
    print(f'prepare-nuwa-firmware: staged {destination}')


if __name__ == '__main__':
    main()
