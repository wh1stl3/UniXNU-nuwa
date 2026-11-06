#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交流群「内核运行照片」判读（2026-11-05，用户提供原图，离线只读）。

用户提供原图后逐行转录，判定它是不是 XNU / UniXNU 启动画面。
结论：这是 Linux 内核启动日志，不是 XNU；因此「看不到 UniXNU 菜单」
不是 EBS 清屏或阶段问题，而是这条启动链根本没经过 UniXNU 菜单。

复核项：
  1. 图中 Linux 专有串在 xnu-8796 源码树里命中数应为 0；
  2. framebuffer 数字自洽（640*1136*4 == 0x2c6000，linelength == 640*4）；
  3. sheng 临时 Linux 日志读取器的 CMDLINE 与图中 console=tty0 对照；
  4. 输入 SHA（含原图）绑定。

不操作设备、不改内核、不构建、不写分区、不提交。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'reports/photo-linux-console-20261105'
OUT.mkdir(parents=True, exist_ok=True)
PHOTO = R / 'out/photo-evidence-20261105/original.jpg'
XNU = Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')
MENU_REPORT = R / 'reports/menu-vs-console-20261105/README.md'
LINUX_LOG_INIT = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng-route-audit/package/linux-log/init')
LINUX_LOG_BUILD = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng-route-audit/package/linux-log/build-linux-log-boot.py')
OFFICIAL_REVIEW = R / 'docs/operations/2026-10-22-official-site-route-review.md'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# 逐行转录（图片 1080x1920；个别字符受分辨率限制标 uncertain）。
TRANSCRIPT = [
    'console [tty0] enabled',
    'bootconsole [uart0] disabled',
    'Calibrating delay loop (skipped) preset value.. 200.00 BogoMIPS (lpj=1000000)',
    'pid_max: default: 32768 minimum: 301',
    'Mount-cache hash table entries: 2048 (order: 1, 8192 bytes)',
    'Mountpoint-cache hash table entries: 2048 (order: 1, 8192 bytes)',
    'CPU: Testing write buffer coherency: ok',
    'Setting up static identity map for 0x80008200 - 0x80008258',
    'devtmpfs: initialized',
    'clocksource: jiffies: mask: 0xffffffff max_cycles: 0xffffffff, max_idle_ns: 19112604462750000 ns',
    'futex hash table entries: 256 (order: -1, 3072 bytes)',
    'NET: Registered protocol family 16',
    'DMA: preallocated 256 KiB pool for atomic coherent allocations',
    'usbcore: registered new interface driver usbfs',
    'usbcore: registered new interface driver hub',
    'usbcore: registered new device driver usb',
    'Advanced Linux Sound Architecture Driver Initialized.',
    'Bluetooth: Core ver 2.21',
    'NET: Registered protocol family 31',
    'Bluetooth: HCI device and connection manager initialized',
    'Bluetooth: HCI socket layer initialized',
    'Bluetooth: L2CAP socket layer initialized',
    'Bluetooth: SCO socket layer initialized',
    'clocksource: Switched to clocksource apple-1c',
    'es, mapped to 0xfe00000',
    'simple-framebuffer bf700000.framebuffer: framebuffer at 0xbf700000, 0x2c6000 byt',
    'Console: switching to colour frame buffer device 80x71',
    'simple-framebuffer bf700000.framebuffer: format=a8r8g8b8, mode=640x1136x32, line',
    'length=2560',
    'simple-framebuffer bf700000.framebuffer: fb0: simplefb registered!',
    'Block layer SCSI generic (bsg) driver version 0.4 loaded (major 253)',
    'io scheduler noop registered',
    'io scheduler deadline registered',
    'io scheduler cfq registered (default)',
    'apple-s518950x-gpio 3fa00000.gpio: apple-gpio: 232 pins, 8 groups',
    'mousedev: PS/2 mouse device common for all mice',
    'usbcore: registered new interface driver usbhid',
    'usbhid: USB HID core driver',
    'input: buttons as /devices/platform/buttons/input/input0',
    'rtc0: unable to open rtc device (rtc0)',
    'ALSA device list:',
    '  No soundcards found.',
    'Warning: unable to open an initial console.',
    'Freeing unused kernel memory: 1420K',
    '-',
]

LINUX_ONLY = [
    'BogoMIPS', 'devtmpfs', 'usbcore', 'io scheduler cfq',
    'Mount-cache hash table', 'Advanced Linux Sound Architecture',
    'Freeing unused kernel memory', 'simple-framebuffer',
    'Registered protocol family', 'Bluetooth: Core ver',
    'pid_max: default: 32768 minimum: 301',
    'Setting up static identity map',
]

XNU_ONLY = ['UniXNU', 'Darwin', 'AppleARMPlatform', 'SecurityLock',
            'IOKit', 'mach_kernel', 'BSD root', 'AppleMobileFileIntegrity']


def main():
    inputs = {}
    for k, p in dict(photo=PHOTO, xnu_source_tree=XNU, menu_report=MENU_REPORT,
                     sheng_linux_log_init=LINUX_LOG_INIT,
                     sheng_linux_log_build=LINUX_LOG_BUILD,
                     official_review=OFFICIAL_REVIEW).items():
        if p.is_dir():
            files = list(p.rglob('*'))
            n = len([f for f in files if f.is_file()])
            inputs[k] = dict(path=str(p), kind='directory', file_count=n)
        else:
            inputs[k] = dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size)

    # 在 XNU 源码树里搜 Linux 专有串（限定源码/头文件后缀，避免二进制噪声）
    hits = {}
    exts = {'.c', '.h', '.cpp', '.hpp', '.s', '.S', '.inc', '.defs', '.strings', '.plist'}
    for s in LINUX_ONLY:
        n = 0
        for f in XNU.rglob('*'):
            if not f.is_file() or f.suffix not in exts:
                continue
            try:
                if s.lower() in f.read_text(encoding='utf-8', errors='replace').lower():
                    n += 1
            except OSError:
                pass
        hits[s] = n

    build = LINUX_LOG_BUILD.read_text(encoding='utf-8', errors='replace')
    cmdline = re.search(r"CMDLINE\s*=\s*(.+)", build)
    init = LINUX_LOG_INIT.read_text(encoding='utf-8', errors='replace')
    review = OFFICIAL_REVIEW.read_text(encoding='utf-8', errors='replace')

    fb = dict(width=640, height=1136, depth=32,
              linelength=2560, bytes=0x2c6000,
              computed_bytes=640 * 1136 * 4,
              computed_linelength=640 * 4,
              bytes_match=640 * 1136 * 4 == 0x2c6000,
              linelength_match=640 * 4 == 2560)

    ev = dict(
        schema='nuwa/photo-linux-console/1',
        question='交流群发的「内核运行照片」为什么看不到 UniXNU 菜单，只有黑底白字日志',
        inputs=inputs,
        photo=dict(sha256=sha(PHOTO), pixels='1080x1920',
                   archived_at='out/photo-evidence-20261105/original.jpg'),
        verdict=('这是 Linux 内核启动日志，不是 XNU / UniXNU 启动画面。'
                 '看不到 UniXNU 菜单不是 EBS 清屏或阶段交接问题，'
                 '而是这条启动链根本没经过 DarwinBoot / UniXNU 菜单。'),
        transcript=TRANSCRIPT,
        linux_only_strings_in_photo=LINUX_ONLY,
        linux_only_strings_xnu_source_hits=hits,
        all_linux_strings_absent_from_xnu=all(v == 0 for v in hits.values()),
        xnu_only_strings_in_photo=[s for s in XNU_ONLY
                                   if any(s.lower() in l.lower() for l in TRANSCRIPT)],
        no_unixnu_ui_in_photo=dict(
            logo=False, menu_box=False, countdown=False, green_bar=False,
            note='整幅画面只有白字文本，无 UniXNU logo、菜单框、倒计时或绿条残留。'),
        framebuffer_arithmetic=fb,
        hardware_clues=dict(
            resolution='640x1136x32（iPhone 5/5s/SE 类面板）',
            framebuffer_phys='0xbf700000，simple-framebuffer',
            gpio='apple-gpio: 232 pins, 8 groups；设备树节点 s5l8950x / 3fa00000.gpio',
            identity_map='0x80008200 - 0x80008258（32-bit ARM 内核典型 identity map）',
            clocksource='apple-1c（转录可能有个别字符偏差）',
            conclusion=('硬件线索指向 Apple A 系列 SoC 上的 Linux 移植，'
                        '与 nuwa / sheng 的 SM8550 不符；'
                        '具体机型与内核版本未核实，不据此断言项目来源。')),
        fails_to_reach_userspace=dict(
            last_lines=['Warning: unable to open an initial console.',
                        'Freeing unused kernel memory: 1420K', '-'],
            note=('这两行是 Linux 内核初始化末尾；initial console 打不开，'
                  '说明连 Linux 自己也没进入用户态，不是「成功运行的系统」。')),
        sheng_linux_log_reader=dict(
            cmdline=cmdline.group(1) if cmdline else None,
            init_mounts=re.findall(r'mount -t (\w+)', init),
            reads_userdata_tail='dd if=/dev/$P of=/run/log.bin bs=4096 skip=$((B - 8192)) count=8192' in init,
            offers_usb_cdc='acm.usb0' in init,
            official_note=next((l.strip() for l in review.splitlines()
                                if '独立Linux阶段' in l), None),
            comparison=('图中 console [tty0] / bootconsole [uart0] / devtmpfs 与该读取器'
                        ' CMDLINE 的 console=tty0、init 的 devtmpfs 挂载同类；'
                        '但图中出现大量 KERN_INFO 级输出，与 loglevel=4 不完全一致，'
                        '且 apple-gpio / 640x1136 不是 SM8550 特征。'
                        '机制同类、不能凭这一张无来源照片断言就是该镜像。')),
        implications=[
            '这张照片不能用于判断 nuwa 是否经过 EBS，也不能当作 UniXNU 的实机阶段证据。',
            '前两轮把群里那张照片当成 XNU 画面来讨论「清屏 / 叠加 / 阶段」，前提不成立，需整体撤回该部分。',
            'nuwa 自己的视频是 UniXNU 菜单与 FB 字段叠加（用户上一轮纠正，已确认），与这张群图是两类东西。',
            '项目里「临时启动 Linux 读 userdata 尾部日志」确实是独立启动链、不经过 UniXNU 菜单，机制上可解释同类画面。',
        ],
        boundaries=[
            '原图由用户提供，已归档并绑定 SHA；未看到该照片的拍摄设备、固定版本、boot-arg 或镜像来源。',
            '转录受 1080x1920 照片分辨率限制，个别行（clocksource / gpio 型号 / simplefb 折行）可能有字符偏差，不作精确版本断言。',
            '本轮未改内核、未构建、未上机、未写分区、未提交 git。',
        ],
    )
    (OUT / 'evidence.json').write_text(json.dumps(ev, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
    print('photo sha:', sha(PHOTO)[:16])
    print('linux-only strings in XNU source:', hits)
    print('all absent:', ev['all_linux_strings_absent_from_xnu'])
    print('XNU-only strings in photo:', ev['xnu_only_strings_in_photo'])
    print('framebuffer arithmetic:', fb['bytes_match'], fb['linelength_match'])
    print('sheng reader cmdline:', ev['sheng_linux_log_reader']['cmdline'])
    print('written:', OUT / 'evidence.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
