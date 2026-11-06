#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""菜单与内核日志同屏叠加 / EBS 阶段判定（2026-11-05，离线只读）。

2026-11-05 用户纠正后整体复核并显式撤回上一版结论：上一版把 sheng 的
bp_clear 当成 EBS 的固有行为，断言「EBS 后整屏清黑、菜单被覆盖」，这是错的。
nuwa 的实机视频是菜单与字段/日志叠加；且 EBS 早就过了。

从固定输入重算：
  1. CHECK8/CHECK5/10-24 录像里同屏叠加的直接判读证据；
  2. nuwa draw 只写局部行位、源码无整屏清屏；
  3. sheng 的 bp_clear 是 boot-progress=1/2 控制的可选动作，nuwa 未传；
  4. EBS 之后的逐门实机里程碑（六色带 / 根挂载 / namei / mac_vnode_check_exec）。

不操作设备、不改内核、不构建、不写分区、不提交。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'reports/menu-vs-console-20261105'
OUT.mkdir(parents=True, exist_ok=True)

VIDEO_FORENSICS = R / 'docs/operations/2026-10-24-first-entry-video-forensics.md'
XNU_FIRST_ENTRY = R / 'docs/operations/2026-10-24-xnu-first-entry.md'
OFFICIAL_SEQ = R / 'docs/operations/2026-10-27-official-adaptation-sequence.md'
SHENG_BOARD = R / 'references/sheng-storage-20261105/board.toml'
SHENG_BP = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng/package/BootProgress.c')
SHENG_DISPLAY = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng/package/BootProgressDisplay.h')
SWEET_CONSOLE = Path('D:/Code/PortingiOSLegacy/common/sources/ios-sweet/shim/console.c')
NUWA_IMAGE = R / 'out/p0-vnop-pair-20261105-r2/boot-p0-vnop-pair-20261105-r2.img'
CHECK8_READING = R / 'reports/ufs-check-8-r1/trial/screen-reading.json'
CHECK5_RESULT = R / 'docs/operations/2026-11-03-check5-result-and-main-validation.md'
CHECK10_RESULT = R / 'reports/ufs-check-10-r1/trial/result.md'
ENTRY_PROBE02 = R / 'docs/operations/2026-10-25-entry-probe-02-trial.md'
NUWA_SOURCE = R / 'package/kernel-mainline/CoarseStages-p0-vnop-pair-r2.S'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def anchors(path: Path, patterns: list[str]) -> list[dict]:
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    out = []
    for pat in patterns:
        r = re.compile(pat, re.I)
        for i, l in enumerate(lines):
            if r.search(l):
                out.append(dict(pattern=pat, line=i + 1, text=l.strip()[:190]))
                break
    return out


def main():
    inputs = {}
    for k, p in dict(video_forensics=VIDEO_FORENSICS, xnu_first_entry=XNU_FIRST_ENTRY,
                     official_sequence=OFFICIAL_SEQ, sheng_board_toml=SHENG_BOARD,
                     sheng_bootprogress=SHENG_BP, sheng_display=SHENG_DISPLAY,
                     sweet_console=SWEET_CONSOLE, nuwa_image=NUWA_IMAGE,
                     check8_reading=CHECK8_READING, check5_result=CHECK5_RESULT,
                     check10_result=CHECK10_RESULT, entry_probe02=ENTRY_PROBE02,
                     nuwa_source=NUWA_SOURCE).items():
        inputs[k] = dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size)

    video = VIDEO_FORENSICS.read_text(encoding='utf-8', errors='replace')
    timeline = re.findall(r'第 (\d+)[–-]?(\d+)? 秒[^\n]{0,120}', video)
    tl_anchors = anchors(VIDEO_FORENSICS, [
        r'第 57 秒起画面切换到 DarwinBoot',
        r'第 118 秒起绿条出现',
        r'第 123 秒是最后有文字的一帧',
        r'第 124 秒立刻转黑',
        r'绿条只是 ExitBootServices 的瞬时标记',
    ])

    bp = SHENG_BP.read_text(encoding='utf-8', errors='replace')
    disp = SHENG_DISPLAY.read_text(encoding='utf-8', errors='replace')
    sweet = SWEET_CONSOLE.read_text(encoding='utf-8', errors='replace')

    board = SHENG_BOARD.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'"kernel_args"\s*=\s*\[([^\]]*)\]', board)
    sheng_args = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    img = NUWA_IMAGE.read_bytes()
    mm = re.search(rb'args = "([^"]*)"', img)
    nuwa_args = mm.group(1).decode().split() if mm else []

    c8 = json.loads(CHECK8_READING.read_text(encoding='utf-8'))
    visible = c8.get('visual_identification_correction', {}).get('other_visible_elements', [])
    check5 = CHECK5_RESULT.read_text(encoding='utf-8', errors='replace')
    check10 = CHECK10_RESULT.read_text(encoding='utf-8', errors='replace')
    probe02 = ENTRY_PROBE02.read_text(encoding='utf-8', errors='replace')
    src = NUWA_SOURCE.read_text(encoding='utf-8', errors='replace')

    overlay = dict(
        user_observation=('目前拍的视频都是既有内核日志也有 UniXNU 菜单，'
                          '并且内核日志叠加在 UniXNU 菜单上'),
        user_observation_accepted=True,
        check8_same_frame_elements=visible,
        check8_has_menu_and_fields=any('boot entry box' in x for x in visible) and
                                   any('FB field column' in x for x in visible),
        check5_start_frame=next((l.strip() for l in check5.splitlines()
                                 if '起始已是菜单/loader画面' in l), None),
        video_forensics_4_1=('第 120/123 秒（内核输出阶段）logo 区域亮度进一步升高'
                             '（6009/5582 个高亮像素），旧像素仍留在同一位置'),
        video_timeline_47_123='同一 console-text 状态，内容为「DarwinBoot 菜单 + 倒计时 + 内核输出」',
        draw_is_local_only=dict(
            formula=next((l.strip() for l in check10.splitlines()
                          if 'y_px = 576 + 32*N' in l), None),
            source_has_full_screen_clear=any(k in src.lower() for k in
                                             ('memset', 'clear_screen', 'fill_screen')),
            note='draw 只按 y_px=576+32*N 写局部行位；nuwa 源码无整屏清屏。'),
        mechanism=('EBS 之后 XNU 复用同一物理 framebuffer，只在自己的行位写像素；'
                   '固件画的菜单像素留在未被覆盖的区域，于是两者叠加。'
                   '整屏清黑是显式动作（sheng bp_clear / ios-sweet con_clear），'
                   '不是 EBS 的固有行为；nuwa 未传 boot-progress，故不清屏。'),
    )

    ebs = dict(
        question='所以我们还没到「EBS 交接到内核」的阶段？',
        answer='不是。EBS 早就过了；菜单残留在画面上不能当成阶段判据。',
        milestones=[
            dict(gate='ExitBootServices', evidence='2026-10-25 entry-probe-02 六色带中绿条 = DarwinBoot EBS'),
            dict(gate='MMU 开启 / _arm_init', evidence='同轮青条（MMU 后）、白条（进入 _arm_init）'),
            dict(gate='vfs_mountroot', evidence='CHECK5 FB0A=0'),
            dict(gate='launchd namei', evidence='CHECK5 FB13=0'),
            dict(gate='mac_vnode_check_exec', evidence='CHECK5 FB12=A0000005'),
            dict(gate='exec header read / VNOP_READ', evidence='当前卡点，P0-VNOP-PAIR r2 待实机'),
        ],
        probe02_line=next((l.strip() for l in probe02.splitlines()
                           if '六条色带全部出现' in l), None),
        check5_fields=next((l.strip() for l in check5.splitlines()
                            if 'FB09=0' in l), None),
        note=('六色带证明已越过 MMU 开关进入 C 入口；CHECK5 根挂载与 namei 成功。'
              '当前卡在 launchd 的 Mach-O header read / VNOP_READ，属 exec 后段、EL0 之前，'
              '远在 EBS 之后。'),
    )

    ev = dict(
        schema='nuwa/menu-vs-console/2',
        question='为什么内核运行照片看不到菜单；nuwa 视频为何菜单与日志叠加；EBS 到了没有',
        inputs=inputs,
        correction=dict(
            retracted_claims=[
                '「EBS 之后内核侧文本控制台/诊断页接管 framebuffer 并整屏清成黑色」',
                '「菜单像素已被覆盖、两者不会同屏出现」',
                '「照片拍的是 EBS 之后的内核阶段，菜单已被清屏」',
            ],
            reason=('把 sheng BootProgress 的 bp_clear（仅 boot-progress=1/2 时调用）'
                    '误当成 EBS 的通用行为，并据此解释群里那张照片；'
                    'nuwa 实机判读记录显示菜单与字段同屏叠加，推翻该解释。'),
            remaining_valid=('菜单由 DarwinBoot 在 EBS 前绘制、nuwa 与 sheng boot-arg 不同、'
                             '有白字日志不等于启动成功，这三点仍成立。'),
        ),
        answer=('nuwa 实机视频确实是菜单与内核侧字段/日志叠加：EBS 后 XNU 复用同一物理 '
                'framebuffer、只在局部行位写像素，未清屏，固件菜单像素留在未覆盖区域。'
                'EBS 早就过了，当前卡点在 exec 的 VNOP_READ。'
                '群里那张只有黑底白字的照片，更可能是该机器启用了会清屏的诊断页/console，'
                '或拍摄时刻菜单已被后续输出覆盖；本轮未看到原图，不据照片下机制断言。'),
        overlay=overlay,
        ebs_status=ebs,
        stage_boundary=dict(
            menu=dict(component='DarwinBoot (UEFI application)', phase='ExitBootServices 之前',
                      evidence=anchors(VIDEO_FORENSICS, [r'DarwinBoot 的 UniXNU 图形菜单'])),
            handoff=dict(marker='绿条 = kernel entry code ran', phase='ExitBootServices',
                         evidence=anchors(VIDEO_FORENSICS, [r'Exiting boot services'])),
            console=dict(component='XNU text console / sheng BootProgress 诊断页',
                         phase='EBS 之后',
                         evidence=anchors(VIDEO_FORENSICS, [r'App Log Flush : 0 ms'])),
            official_order=anchors(OFFICIAL_SEQ, [r'UEFI.*UniXNU菜单.*DarwinBoot.*内核入口']),
        ),
        nuwa_actual_timeline=dict(
            menu_seconds=[57, 117], ebs_second=118,
            kernel_text_seconds=[118, 123], black_screen_second=124,
            anchors=tl_anchors,
            note=('取自 2026-10-24 实机录像 1fps 抽帧取证。时间线把 47–123 s 归为'
                  '同一个 console-text 状态；§4.1 显示 logo 区域在内核输出阶段亮度'
                  '进一步升高而非消失，支持叠加而非清屏。')),
        clear_screen_evidence=dict(
            sheng_bp_clear_lines=[i + 1 for i, l in enumerate(bp.splitlines()) if 'bp_clear(&display)' in l],
            sheng_boot_progress_arg=anchors(SHENG_BP, [r'PE_parse_boot_argn\("boot-progress"']),
            sheng_display=dict(
                clear_writes_zero='=0;' in disp and 'for(unsigned x=0;x<d->width' in disp,
                white_text='0xffffffff' in bp,
                black_background='bp_line_bg' in disp and 'background' in disp,
                glyph_rows=48,
                note=('BootProgressDisplay.h:13-19 的 bp_clear 把整屏 32-bit 像素写 0（黑）；'
                      'bp_line_bg 用 0xffffffff 白字画 6×14 字模，背景色 0。'
                      'BootProgress.c:502-530 在 boot-progress=1/2 时绑定 framebuffer 并 bp_clear。')),
            sweet_console=dict(
                header=sweet.splitlines()[1].strip() if len(sweet.splitlines()) > 1 else '',
                clears_full_framebuffer='con_clear' in sweet and 'line[x] = bg' in sweet,
                note='ios-sweet/shim/console.c 同样是「ABL splash framebuffer 上的极简文本控制台」，先 con_clear 全屏刷背景。'),
        ),
        boot_arg_comparison=dict(
            sheng_total=len(sheng_args),
            sheng_relevant=[a for a in sheng_args if a in
                            ('-v', 'boot-progress=2', 'sheng-banner=0', 'serial=3',
                             'offline-legacy-gop=1', 'debug=0x14e')],
            nuwa_args=nuwa_args,
            nuwa_has_boot_progress=any(a.startswith('boot-progress') for a in nuwa_args),
            nuwa_has_sheng_banner=any(a.startswith('sheng-banner') for a in nuwa_args),
            note=('nuwa 只传 -v native-ufs-root=1 launchdsuffix=release；'
                  '没有 boot-progress / board page，当前画面是自建 FB 字段与色块，不是文本页。')),
        what_the_photo_might_show=[
            '该机器启用了会整屏清屏的诊断页 / console（如 boot-progress=2 的 bp_clear）',
            '拍摄时刻菜单区域已被后续滚动文本 / 诊断页覆盖',
            '不同设备、不同候选、不同 framebuffer 处理策略',
            '本轮未看到原图，以上为可能性，不是结论',
        ],
        not_evidence_for=[
            '不能据「菜单还在画面上」断言还没到 EBS——菜单是残留像素，不是阶段判据',
            '不能据群里照片断言该机器跳过了菜单或已到 SpringBoard',
            '不能把群里的照片当成本项目实机证据（外部设备、未知固定版本、未知 boot-arg）',
            '不能把「叠加」写成 EBS 未发生或内核未执行',
        ],
        boundaries=[
            '本轮未看到群里那张原始照片，判读基于 nuwa 本地实机判读记录与固定版 sheng 源码/board.toml。',
            '整屏清黑只在显式调用清屏函数时发生；sheng 需 boot-progress=1/2，nuwa 未传。',
            'nuwa 当前 r2 停在实机确认门，未上机；本轮未改内核、未构建、未写分区、未提交。',
        ],
    )
    (OUT / 'evidence.json').write_text(json.dumps(ev, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
    print('timeline anchors:', len(tl_anchors))
    print('overlay menu+fields same frame:', ev['overlay']['check8_has_menu_and_fields'])
    print('draw clears full screen:', ev['overlay']['draw_is_local_only']['source_has_full_screen_clear'])
    print('EBS milestones:', len(ev['ebs_status']['milestones']))
    print('sheng args:', ev['boot_arg_comparison']['sheng_total'],
          '| relevant:', ev['boot_arg_comparison']['sheng_relevant'])
    print('nuwa args:', nuwa_args)
    print('written:', OUT / 'evidence.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
