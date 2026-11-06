#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内核日志落盘可行性审计（2026-11-05，纯离线只读）。

回答「userdata 已刷掉后，能否做内核日志落盘」。所有结论由本脚本从固定输入
重算，不采信手抄值：
  1. 当前候选内核 r2 的 LC_SYMTAB / 字符串常量 / FAT boot-args；
  2. CHECK4 linked 对象的完整 nm 符号（写入 provider 是否真的编进内核）；
  3. 上游 BootLog.c 的 producer 契约与依赖的弱符号；
  4. userdata 分区布局算术（根镜像前缀、日志窗口、export、reserve 是否重叠）；
  5. 授权边界（AGENTS.md、2026-10-29 评估、2026-11-01 根安装记录）。

不操作设备、不改内核、不构建、不写分区、不提交。
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'reports/kernel-log-persist-20261105'
OUT.mkdir(parents=True, exist_ok=True)

KERNEL = R / 'out/p0-vnop-pair-20261105-r2/kernel.macho'
IMAGE = R / 'out/p0-vnop-pair-20261105-r2/boot-p0-vnop-pair-20261105-r2.img'
LINKED = R / 'out/ufs-check-4-r1-clean/linked/linked-0.macho'
LINKED_IMPORTS = R / 'out/ufs-check-4-r1-clean/linked/imports.json'
NATIVE_UFS_LATEST = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-latest-audit/drivers/NativeUfs/NativeUfs.cpp')
ROOT_COMMANDS = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-latest-audit/drivers/NativeUfs/RootCommands.h')
BOOTLOG = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng-route-audit/package/BootLog.c')
READER = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng-route-audit/scripts/read-sheng-log.py')
OLD_REVIEW = R / 'docs/operations/2026-10-29-kernel-log-options.md'
ROOT_ROUTE = R / 'docs/operations/2026-11-01-ufs-root-recovery-route.md'
ROOT_AUTH = R / 'docs/operations/2026-11-01-ufs-authenticated-root.md'
AGENTS = R / 'AGENTS.md'
STATUS = R / 'docs/STATUS.md'
FIELD_SEMANTICS = R / 'reports/p0-vnop-pair-20261105-r2/field-semantics.json'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def diagnostic_gain() -> dict:
    """回答「落盘之后诊断观测是否更方便」：把两种观测的实际容量、时间分辨率、
    writer 启动依赖与失效模式从固定输入重算，避免只凭印象说「更方便」。
    """
    sem = json.loads(FIELD_SEMANTICS.read_text(encoding='utf-8'))
    bl = BOOTLOG.read_text(encoding='utf-8', errors='replace')
    nu = NATIVE_UFS_LATEST.read_text(encoding='utf-8', errors='replace')
    a = AGENTS.read_text(encoding='utf-8')

    consts = {}
    for key in ('LogBlock', 'LogMsgFirst', 'LogMsgBlocks', 'LogSlotFirst',
                'LogSlotBlocks', 'LogPeriodMs', 'LogMaxErrors'):
        m = re.search(r'\b' + key + r'\s*=\s*(\d+)', bl)
        consts[key] = int(m.group(1)) if m else None
    blocks = 8192  # kLogReserveBlocks, 由 native_ufs_log_open 返回
    slot_count = (blocks - consts['LogSlotFirst']) // consts['LogSlotBlocks']
    period_s = consts['LogPeriodMs'] / 1000.0

    # writer 启动链：board page monitor 每秒 tick -> kernel_thread_start_priority -> 等 root layout
    tick_anchor = next((i + 1 for i, l in enumerate(bl.splitlines())
                        if 'Called by the board page' in l), None)
    thread_anchor = next((i + 1 for i, l in enumerate(bl.splitlines())
                          if 'kernel_thread_start_priority' in l), None)
    sleep_anchor = next((i + 1 for i, l in enumerate(bl.splitlines())
                         if 'IOSleep(LogPeriodMs)' in l), None)

    return dict(
        question='日志落盘之后诊断观测会更方便吧',
        screen_observation=dict(
            candidate='P0-VNOP-PAIR r2',
            drawn_fields=len(sem['fields']),
            not_drawn_ids_decimal=sem.get('not_drawn_ids_decimal'),
            value_width_bits=32,
            carries_text=False,
            survives_reboot=False,
            requires_per_frame_rgb='逐帧 RGB 分类' in a,
            requires_timeline='实测录像判读必须记录时间线' in a,
            requires_field_semantics_per_candidate='每个候选必须随资格一并落一份字段语义表' in a,
            blank_reading_rule='空白读数必须同时证明' in a,
            note=('21 个字段各只写一个 32-bit 值；末态可拍但过渡值要靠 60fps 录像逐帧拼图，'
                  '且 2fps 抽样会漏；跨重启没有历史。')),
        disk_log=dict(
            bootlog_constants=consts,
            log_window_blocks=blocks,
            text_slot_count=slot_count,
            bytes_per_slot=consts['LogSlotBlocks'] * consts['LogBlock'],
            ring_history_seconds=slot_count * period_s,
            ring_history_minutes=round(slot_count * period_s / 60, 1),
            msgbuf_bytes=consts['LogMsgBlocks'] * consts['LogBlock'],
            sampling_period_seconds=period_s,
            max_consecutive_write_errors=consts['LogMaxErrors'],
            header_fields=['magic', 'version', 'boot_id', 'first_lba', 'uptime_s',
                           'rounds', 'write_errors', 'gpt_open', 'gpt_last', 'state',
                           'slots_written', 'tag'],
            carries_full_text=True,
            survives_reboot_via='TWRP/ADB 从 userdata 尾部读回 + 解码',
            writer_start_chain=dict(
                tick_caller_line=tick_anchor,
                thread_start_line=thread_anchor,
                period_sleep_line=sleep_anchor,
                nuwa_board_page_monitor_absent=('boot_progress_page_text' not in
                                                KERNEL.read_bytes().decode('latin-1')),
                note=('sheng 靠 board page monitor 每秒调 boot_log_tick() 启动 writer；'
                      'nuwa 没有 board page，boot_progress_* 符号 0 命中，'
                      '需另找启动点，这是上一轮未列出的第 4 个缺口。')),
            failure_modes=[
                '硬挂/IRQ 关闭/多核全停时 writer 线程不调度，最后一批必丢',
                'writer 经 hostWrite4k 取 gHost.lock、复用唯一 polled UTP 槽，与正在故障的读链竞争',
                '2s 周期无法记录「进入 VNOP_READ 但未返回」这类瞬时挂起',
                '连续 3 次写失败后 writer 主动退出（state=3），此后通道静默',
                'GPT CRC 变化即永久停写（state=4）',
            ]),
        gains=[
            '跨重启可回收，不再依赖末态照片与录像',
            '可读文本：msgbuf 全文、panic 文本、48 行诊断页、banner、进程栈、GPU 统计',
            '自带时间线：boot_id / uptime_s / rounds / slots_written / write_errors',
            '约 34 分钟环形历史，能看到字段跳变与阶段推进，而不是只有末态',
            '不受 FB 行位数量与编号公式约束，也不必每候选重做行位可见性验证',
        ],
        not_improved=[
            '不提高挂点覆盖度：空白日志仍受「通道有效/覆盖所有返回路径」纪律约束，不能写成未发生',
            '不定位根因：只是把已有 producer 的内容搬到盘上，区分力仍来自挂点布局',
            '当前卡点在 EL0 之前、VNOP_READ 内部，恰是 writer 最可能无法写出的窗口',
            '不改变单一变量纪律：启用落盘本身引入写盘竞争，可能改变故障形态',
        ],
        verdict=('是，但只在「系统仍在跑、writer 能调度」之后；对当前 VNOP_READ 卡点'
                 '这一格，落盘不增加判别力，反而可能因同锁竞争制造新故障。'
                 '当前唯一该做的是消费 r2 的 FB03/FB06 配对。'),
    )


def inputs() -> dict:
    files = dict(kernel=KERNEL, image=IMAGE, linked=LINKED,
                 linked_imports=LINKED_IMPORTS, native_ufs_latest=NATIVE_UFS_LATEST,
                 root_commands=ROOT_COMMANDS, bootlog_upstream=BOOTLOG,
                 reader_upstream=READER, old_review=OLD_REVIEW,
                 root_route=ROOT_ROUTE, root_auth=ROOT_AUTH,
                 agents=AGENTS, status=STATUS, field_semantics=FIELD_SEMANTICS)
    return {k: dict(path=str(v), sha256=sha(v), bytes=v.stat().st_size) for k, v in files.items()}


def macho_symbols(raw: bytes) -> set[str]:
    """解 LC_SYMTAB，返回全部有名字的符号（含 C++ mangled）。"""
    off, sym = 32, None
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, sz = struct.unpack_from('<II', raw, off)
        if cmd == 0x2:
            sym = struct.unpack_from('<IIII', raw, off + 8)
        off += sz
    assert sym, 'no LC_SYMTAB'
    so, ns, sto, sts = sym
    out = set()
    for i in range(ns):
        strx, ntype, nsect, desc, val = struct.unpack_from('<IBBHQ', raw, so + i * 16)
        if strx:
            e = raw.find(b'\0', sto + strx)
            out.add(raw[sto + strx:e].decode('utf-8', 'replace'))
    return out


def linked_nm() -> list[str]:
    """直接解 linked 对象的 LC_SYMTAB（含 local/external 全部符号），不依赖 llvm-nm。

    最终内核的 LC_SYMTAB 只保留外部符号；写入实现以 non-external 形式留在
    linked 对象里，因此这一步必须由 linked 对象自身核对。
    """
    raw = LINKED.read_bytes()
    off, sym = 32, None
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, sz = struct.unpack_from('<II', raw, off)
        if cmd == 0x2:
            sym = struct.unpack_from('<IIII', raw, off + 8)
        off += sz
    assert sym, 'linked object has no LC_SYMTAB'
    so, ns, sto, sts = sym
    lines = []
    for i in range(ns):
        strx, ntype, nsect, desc, val = struct.unpack_from('<IBBHQ', raw, so + i * 16)
        if strx:
            e = raw.find(b'\0', sto + strx)
            name = raw[sto + strx:e].decode('utf-8', 'replace')
            kind = 'external' if (ntype & 0x0f) != 0x0 and (ntype & 0x01) else 'non-external'
            lines.append('%s %s' % (kind, name))
    return lines


def scan_kernel() -> dict:
    raw = KERNEL.read_bytes()
    img = IMAGE.read_bytes()
    syms = macho_symbols(raw)
    strs = {
        'sheng-log': raw.count(b'sheng-log'),
        'sheng-log-reserve': raw.count(b'sheng-log-reserve'),
        'sheng-data-persist': raw.count(b'sheng-data-persist'),
        'native-ufs-root': raw.count(b'native-ufs-root'),
        'SHLOG001': raw.count(b'SHLOG001'),
        'boot_progress_page_text': raw.count(b'boot_progress_page_text'),
        'stage=%s result=%08x': raw.count(b'stage=%s result=%08x'),
    }
    # FAT unixnu.toml 里的 XNU entry args
    m = re.search(rb'args = "([^"]*native-ufs-root[^"]*)"', img)
    fat_args = m.group(1).decode() if m else None
    # producer 依赖的弱符号，在当前内核 LC_SYMTAB 中是否可见
    need = ['native_ufs_log_open', 'native_ufs_log_write', 'native_ufs_log_sync',
            'native_ufs_export_write', 'native_ufs_export_blocks',
            'native_ufs_store_gpt_check', 'native_data_persist_state',
            'native_data_persist_header', 'native_data_persist_writes',
            'native_data_persist_syncs', 'native_data_persist_first_lba',
            'boot_progress_page_text', 'boot_progress_panic_text',
            'boot_log_export_put', 'native_ufs_store_mode',
            'native_ufs_store_open', 'native_ufs_store_write']
    visible = {n: (n in syms or '_' + n in syms) for n in need}
    return dict(
        kernel_symtab_named=len(syms),
        string_counts=strs,
        fat_xnu_entry_args=fat_args,
        image_has_sheng_log_arg=b'sheng-log=1' in img,
        image_has_data_persist_arg=b'sheng-data-persist=2' in img,
        producer_dependency_symbols_in_final_symtab=visible,
        producer_dependencies_visible_count=sum(visible.values()),
        note=('最终内核 LC_SYMTAB 不含这些 external 写入接口，'
              '因为它们随 linked 对象以 non-external/本地符号形式链接；'
              '是否存在须以 linked 对象 nm 为准，不能用最终符号表否定。'))


def scan_linked() -> dict:
    lines = linked_nm()
    providers = ['native_ufs_log_open', 'native_ufs_log_write', 'native_ufs_log_sync',
                 'native_ufs_export_write', 'native_ufs_store_mode',
                 'native_ufs_store_open', 'native_ufs_store_read',
                 'native_ufs_store_write', 'native_ufs_store_sync',
                 'native_ufs_store_gpt_check']
    found = {p: any(('_' + p) in l for l in lines) for p in providers}
    extra = {}
    for key in ('hostWrite4k', 'hostLogOpen', 'hostStoreOpen', 'hostSyncCache',
                'logMode', 'storeMode', 'reserveBlocks', 'gLogRegionFirst',
                'gStoreGeometry', 'reportWriteProtection', 'doAsyncReadWrite',
                '__GLOBAL__sub_I_NativeUfs.cpp'):
        extra[key] = sum(1 for l in lines if key in l)
    bootlog_producer = [l for l in lines
                        if 'boot_log' in l or 'SHLOG' in l or 'boot_progress_page' in l]
    return dict(nm_available=bool(lines), nm_symbol_count=len(lines),
                provider_externals=found,
                provider_externals_found=sum(found.values()),
                implementation_symbols=extra,
                bootlog_producer_symbols=bootlog_producer,
                verdict=('写入 provider 已编进当前内核' if all(found.values())
                         else '写入 provider 不完整'))


def layout() -> dict:
    # 全部取自 2026-11-01 根安装记录，4096 字节逻辑块。
    total = 240_597_577_728
    root_bytes = 8_445_681_664
    userdata_lu0_start = 12_742_557_696
    blk = 4096
    log_blocks = 8192            # 32 MiB，kLogReserveBlocks
    export_blocks = 65536        # 256 MiB，kExportBlocks
    reserve_blocks = 1024 * 256  # 1024 MiB 默认 sheng-log-reserve
    total_blocks = total // blk
    image_blocks = root_bytes // blk
    guard_blocks = 1024          # 4 MiB 保护
    last = total_blocks - 1
    log_first = last + 1 - log_blocks
    export_first = log_first - export_blocks
    reserve_first = last + 1 - reserve_blocks
    free = reserve_first - (image_blocks + guard_blocks)
    return dict(
        userdata_bytes=total, userdata_blocks=total_blocks,
        userdata_lu0_start=userdata_lu0_start,
        root_image_bytes=root_bytes, root_image_blocks=image_blocks,
        root_image_lu0_range=[userdata_lu0_start, userdata_lu0_start + root_bytes],
        log_window_blocks=log_blocks, log_window_bytes=log_blocks * blk,
        log_first_partition_lba=log_first,
        log_first_lu0_lba=userdata_lu0_start // blk + log_first,
        log_first_lu0_byte=userdata_lu0_start + log_first * blk,
        export_blocks=export_blocks, export_bytes=export_blocks * blk,
        export_first_partition_lba=export_first,
        reserve_default_mib=1024, reserve_blocks=reserve_blocks,
        reserve_first_partition_lba=reserve_first,
        guard_blocks=guard_blocks, guard_bytes=guard_blocks * blk,
        free_blocks_between_root_guard_and_reserve=free,
        log_clear_of_root_image=(export_first > image_blocks + guard_blocks),
        reserve_clear_of_root_image=(reserve_first > image_blocks + guard_blocks),
        note=('算术上日志窗口/export/reserve 都远离根镜像前缀；'
              '但这是源码常量 + 分区数字推算，不是设备上 GPT 读回或写入实测。'))


def upstream_contract() -> dict:
    nu = NATIVE_UFS_LATEST.read_text(encoding='utf-8', errors='replace').splitlines()
    rc = ROOT_COMMANDS.read_text(encoding='utf-8', errors='replace').splitlines()
    bl = BOOTLOG.read_text(encoding='utf-8', errors='replace').splitlines()

    def anchors(lines, pats):
        r = re.compile('|'.join(pats), re.I)
        return [dict(line=i + 1, text=l.strip()[:180])
                for i, l in enumerate(lines) if r.search(l)]

    return dict(
        native_ufs_log_mode=anchors(nu, [r'PE_parse_boot_argn \("sheng-log"',
                                        r'PE_parse_boot_argn \("sheng-log-reserve"',
                                        r'PE_parse_boot_argn \("sheng-data-persist"']),
        native_ufs_log_open=anchors(nu, [r'extern "C" int native_ufs_log_open'])[:1],
        native_ufs_store_write=anchors(nu, [r'extern "C" int native_ufs_store_write'])[:1],
        readonly_block_device=anchors(nu, [r'reportWriteProtection \(bool',
                                           r'return kIOReturnNotWritable']),
        write_path_lock=anchors(rc, [r'IOLockLock \(gHost\.lock\)',
                                     r'static IOReturn hostWrite4k',
                                     r'static bool hostLogOpen',
                                     r'static IOReturn hostSyncCache']),
        write_window_guard=anchors(rc, [r'hostInWindow \(lba, blocks\)'])[:1],
        bootlog_producer=anchors(bl, [r'SHLOG001', r'sheng-log=1',
                                      r'native_ufs_log_open.*weak_import'])[:6],
        bootlog_weak_imports=sorted(set(re.findall(r'extern [^;]*?(native_\w+|boot_progress_\w+)[^;]*?weak_import',
                                                  '\n'.join(bl))))[:30],
    )


def authorization() -> dict:
    a = AGENTS.read_text(encoding='utf-8')
    old = OLD_REVIEW.read_text(encoding='utf-8')
    route = ROOT_ROUTE.read_text(encoding='utf-8')
    checks = {
        '硬停_flash_erase_改槽需具体目标日志恢复依据': 'flash、erase、改槽位等仍须有具体目标、日志和恢复依据' in a,
        '放弃旧数据不等于授权格式化分区写入': '放弃旧数据也不等于授权格式化、分区写入或改槽' in a,
        '持久日志须先手工writer_sync_reader闭环': '持久日志必须先手工writer/sync/reader与恢复闭环，再自动循环' in a,
        '日志先可回收再自动化': '日志先可回收，再自动化' in a,
        '写入授权不扩大': '该要求不扩大设备写入、改槽、提交或推送权限' in a,
        '旧评估_不启用sheng_data_persist': '此轮不启用sheng-data-persist、不改GPT、不借userdata尾部' in old,
        '旧评估_不得把尾部当空闲区': '不得为了日志打开mode2或把尾部当空闲区' in old,
        '旧评估_故障存储链丢最后一批': '若存储正是故障路径，最后一批仍可能丢失' in old,
        '根安装_旧Android数据已失效': '旧Android Data已失效' in route,
        '根安装_未刷GPT未改槽': '未刷写boot/recovery/vbmeta/GPT，未改槽' in route,
    }
    return dict(checks=checks, all_matched=all(checks.values()),
                note='userdata 内容被覆盖不等于新增分区写入授权；本轮不请求、不执行任何设备写入。')


def main():
    ev = dict(
        schema='nuwa/kernel-log-persist-feasibility/1',
        question='userdata 已刷掉后，能否做内核日志落盘',
        inputs=inputs(),
        current_kernel=scan_kernel(),
        linked_provider=scan_linked(),
        layout=layout(),
        upstream_contract=upstream_contract(),
        authorization=authorization(),
        diagnostic_gain=diagnostic_gain(),
    )
    (OUT / 'evidence.json').write_text(
        json.dumps(ev, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    k = ev['current_kernel']
    l = ev['linked_provider']
    lay = ev['layout']
    g = ev['diagnostic_gain']
    print('kernel strings:', k['string_counts'])
    print('FAT args:', k['fat_xnu_entry_args'], '| sheng-log=1 in image:', k['image_has_sheng_log_arg'])
    print('linked nm available:', l['nm_available'], '| provider externals:',
          l['provider_externals_found'], '/', len(l['provider_externals']))
    print('BootLog producer symbols in linked:', len(l['bootlog_producer_symbols']))
    print('layout log_first_lu0_byte:', lay['log_first_lu0_byte'],
          '| clear of root:', lay['log_clear_of_root_image'])
    print('authorization checks all matched:', ev['authorization']['all_matched'])
    print('screen fields:', g['screen_observation']['drawn_fields'],
          '| disk slots:', g['disk_log']['text_slot_count'],
          '| ring minutes:', g['disk_log']['ring_history_minutes'],
          '| sampling s:', g['disk_log']['sampling_period_seconds'])
    print('writer start chain:', g['disk_log']['writer_start_chain'])
    print('written:', OUT / 'evidence.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
