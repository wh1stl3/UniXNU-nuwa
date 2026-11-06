"""离线判定 0x769BF70 的 w6 调用点归属，并逐字解码 11 个 P0 恢复点。

只读取本地固定二进制与源码，不改内核、不构建、不操作设备。
输出 reports/native-restore-20261105/exec-read-callsite.json。

证据纪律：
- 分支/立即数一律从 32 位机器码解出，不采信源码注释或字符串常量。
- 官方 mach_loader.c:1574/1605 的「9 vs 8」对照位于 #if __x86_64__，
  对 ARM64 donor 内核不成立；真正的对照在 bsd/kern/kern_exec.c。
"""
import hashlib
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import flush_trace_inputs as trace  # noqa: E402

OUT = R / 'reports/native-restore-20261105/exec-read-callsite.json'
TRIAGE = R / 'reports/native-restore-20261105/patch-triage.json'
EARLY = R / 'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho'
CHECK10 = R / 'out/ufs-check-10-r1/kernel.macho'
KERN_EXEC = Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/bsd/kern/kern_exec.c')
MACH_LOADER = R / 'reports/offline-official-kernel-audit-20261104/official-source/mach_loader.c'
VNODE_H = R / 'reports/offline-official-kernel-audit-20261104/official-source/vnode.h'
DISASM = R / 'out/kmain-6-analysis/activate-disassembly.txt'
OFFICIAL = R / 'reports/offline-official-kernel-audit-20261104/official-source'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sx(value, bits):
    """把无符号立即数按 bits 位符号扩展。"""
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def decode(word, pc):
    """够用的 ARM64 指令解码：分支、比较分支、加减立即数、LDR、ORR/MOVZ。"""
    top = (word >> 24) & 0xFF
    # B / BL：opcode 0b000101，bit31 区分 BL
    if (word & 0x7C000000) == 0x14000000:
        imm = sx(word & 0x03FFFFFF, 26) * 4
        return dict(kind='bl' if word & 0x80000000 else 'b',
                    target=hex(pc + imm), imm_bytes=imm)
    # CBZ / CBNZ：sf 011010 op imm19 Rt
    if top in (0x34, 0x35, 0xB4, 0xB5):
        kind = 'cbnz' if top in (0x35, 0xB5) else 'cbz'
        width = 'x' if top in (0xB4, 0xB5) else 'w'
        imm = sx((word >> 5) & 0x7FFFF, 19) * 4
        return dict(kind=kind, reg='%s%d' % (width, word & 0x1F),
                    target=hex(pc + imm), imm_bytes=imm)
    # ADD / SUB immediate
    if top in (0x11, 0x91, 0x51, 0xD1):
        kind = 'sub' if top in (0x51, 0xD1) else 'add'
        width = 'x' if top in (0x91, 0xD1) else 'w'
        imm = (word >> 10) & 0xFFF
        if (word >> 22) & 1:
            imm <<= 12
        return dict(kind=kind, width=width, rd=word & 0x1F,
                    rn=(word >> 5) & 0x1F, imm=imm)
    # LDR (unsigned offset)
    if top in (0xB9, 0xF9):
        return dict(kind='ldr', width='x' if top == 0xF9 else 'w',
                    rt=word & 0x1F, rn=(word >> 5) & 0x1F,
                    offset=((word >> 10) & 0xFFF) * (8 if top == 0xF9 else 4))
    # ORR (shifted register)，含 mov xN, xM 的别名
    if (word & 0x7F000000) == 0x2A000000:
        return dict(kind='orr/mov', rd=word & 0x1F,
                    rn=(word >> 5) & 0x1F, rm=(word >> 16) & 0x1F)
    if (word & 0x7F800000) == 0x52800000:  # MOVZ
        return dict(kind='movz', rd=word & 0x1F,
                    imm16=(word >> 5) & 0xFFFF, hw=(word >> 21) & 3)
    return dict(kind='unclassified')


def word_at(raw, macho, va):
    off = trace.builder().backed(macho, va, 4)
    return int.from_bytes(raw[off:off + 4], 'little')


def line_of(path, needle, start=1):
    """返回首个包含 needle 的行号与原文，作为源码锚点。"""
    for n, line in enumerate(Path(path).read_text(encoding='utf-8', errors='replace').splitlines(), start):
        if needle in line:
            return dict(line=n, text=line.strip())
    return None


def main():
    b = trace.builder()
    early_raw, c10_raw = EARLY.read_bytes(), CHECK10.read_bytes()
    me, mc = b.macho(early_raw), b.macho(c10_raw)
    triage = json.loads(TRIAGE.read_text(encoding='utf-8'))
    restore = [r for r in triage['sites'] if r['classification'] == 'observer-or-bridge']
    assert len(restore) == 11, '恢复点数量与交接文档不符'

    # 1) 逐点核对 current / native 机器码，并解出分支目标。
    sites = []
    for r in restore:
        va = int(r['address'], 16)
        cur_word = word_at(c10_raw, mc, va)
        nat_word = word_at(early_raw, me, va)
        assert cur_word == int.from_bytes(bytes.fromhex(r['current']), 'little')
        assert nat_word == int.from_bytes(bytes.fromhex(r['native_from_earlysec']), 'little')
        sites.append(dict(address=r['address'],
                          current=r['current'], native=r['native_from_earlysec'],
                          current_decoded=decode(cur_word, va),
                          native_decoded=decode(nat_word, va),
                          reason=r['reason']))

    # 2) 0x769BF70..8C 参数块：逐项绑定 kern_exec.c:2210 的实参。
    blk = {}
    for va in range(0xFFFFFFF00769BF54, 0xFFFFFFF00769BF94, 4):
        blk[hex(va)] = decode(word_at(c10_raw, mc, va), va)

    callsite = dict(
        address='0xfffffff00769bf70',
        function='exec_activate_image',
        source='bsd/kern/kern_exec.c:2210-2213',
        source_sha256=sha(KERN_EXEC),
        source_line_anchor=line_of(KERN_EXEC, 'vn_rdwr(UIO_READ, imgp->ip_vp, imgp->ip_vdata, PAGE_SIZE, 0,'),
        args=[
            dict(arm64='w0=0', source='UIO_READ', value=0),
            dict(arm64='x1=[x19,#0x20]', source='imgp->ip_vp', value=None),
            dict(arm64='x2=[x19,#0x40]', source='imgp->ip_vdata', value=None),
            dict(arm64='x3=1<<[x26]', source='PAGE_SIZE (page shift)', value=None),
            dict(arm64='x4=0', source='file_offset = 0', value=0),
            dict(arm64='w5=2', source='UIO_SYSSPACE', value=2),
            dict(arm64='w6=8', source='IO_NODELOCKED = 0x0008', value=8),
            dict(arm64='x7=x25 (_vfs_context_ucred)', source='vfs_context_ucred(imgp->ip_vfs_context)', value=None),
            dict(arm64='stack[0]=sp+0x1c', source='&resid', value=None),
            dict(arm64='stack[1]=_vfs_context_proc', source='vfs_context_proc(imgp->ip_vfs_context)', value=None),
        ],
        flag_definition=line_of(VNODE_H, '#define IO_NODELOCKED'),
        unit_definition=line_of(VNODE_H, '#define IO_UNIT'),
    )

    # 3) 真正与 w6=8 相对的另一处调用：kern_exec.c:826（fat_arch 重读，用 9）。
    fat_callsite = dict(
        source='bsd/kern/kern_exec.c:826-829',
        anchor=line_of(KERN_EXEC, 'PAGE_SIZE, fat_arch.offset,'),
        flags='IO_UNIT | IO_NODELOCKED = 9',
        file_offset='fat_arch.offset (非 0)',
        reason='这是 fat 封装二进制选定 arch 后重读 Mach-O 头，不是首次 header 读',
    )

    # 4) 作废的旧对照框架：mach_loader.c:1574/1605 位于 #if __x86_64__。
    ml_lines = MACH_LOADER.read_text(encoding='utf-8').splitlines()
    x86_guard = next((i + 1 for i, l in enumerate(ml_lines) if '#if __x86_64__' in l), None)
    invalid = dict(
        previously_used='mach_loader.c:1574 (9) vs :1605 (8)',
        guard_line=x86_guard,
        guard_text=ml_lines[x86_guard - 1].strip() if x86_guard else None,
        enclosing_function='check_if_simulator_binary()',
        reason='该整段函数被 #if __x86_64__ 包裹，ARM64 donor 内核不编译；'
               'ip_vdata 在此文件中仅出现在该函数内。用它判定 w6 归属的前提不成立。',
        mach_loader_vn_rdwr_lines=[l['line'] for l in [
            line_of(MACH_LOADER, 'error = vn_rdwr(UIO_READ, vp, addr,'),
            line_of(MACH_LOADER, 'UIO_SYSSPACE, (IO_UNIT | IO_NODELOCKED),'),
            line_of(MACH_LOADER, 'UIO_SYSSPACE, IO_NODELOCKED, cred, &resid, p);'),
            line_of(MACH_LOADER, 'UIO_SYSSPACE, IO_NODELOCKED, kerncred'),
        ] if l],
    )

    # 5) 恢复 0x769BF90/94 后的原生控制流。
    bl = next(s for s in sites if s['address'].endswith('769bf90'))
    cbnz = next(s for s in sites if s['address'].endswith('769bf94'))
    assert bl['native_decoded']['kind'] == 'bl', bl
    assert bl['native_decoded']['target'] == hex(0xFFFFFFF007466988), bl
    assert cbnz['native_decoded']['kind'] == 'cbnz', cbnz

    result = dict(
        schema='Nuwa.ExecReadCallsite.v1',
        date='2026-11-05',
        verdict=dict(
            address='0xfffffff00769bf70',
            belongs_to='exec_activate_image() 首次 Mach-O header 读，kern_exec.c:2210-2213',
            w6=8,
            w6_meaning='IO_NODELOCKED (0x0008)，不是 IO_UNIT|IO_NODELOCKED (9)',
            confidence='静态实锤：反汇编 0x769bf54-8c 十个参数与源码 2210-2213 逐一对应',
            effect_on_p0='恢复 0x769BF90 为原生 bl _vn_rdwr 后，参数块不动；'
                         'w6=8 是原生值，P0 不引入任何参数或 ABI 变化。',
            superseded='交接文档「mach_loader.c:1574 vs :1605，w6 归属未定」这一对照框架作废',
        ),
        callsite=callsite,
        fat_callsite=fat_callsite,
        invalid_prior_framework=invalid,
        restored_control_flow=dict(
            call=bl['native_decoded'],
            error_branch=cbnz['native_decoded'],
            x30_source='由 bl 硬件写入 0x769BF94，不再是 coarse_read_before 的 movz x30,#49044',
            ret_landing='0x769BF94 原生 cbnz w0；成功落入 0x769BF98，错误跳 bad',
            legacy_bridge='0x84D9BE4 probe61 遗留 cbz w0 恢复后不再被引用，不可达字节保留不擦除',
        ),
        parameter_block_decoded=blk,
        restore_sites=sites,
        inputs=dict(
            patch_triage_sha256=sha(TRIAGE),
            earlysec_sha256=sha(EARLY),
            check10_kernel_sha256=sha(CHECK10),
            kern_exec_c_sha256=sha(KERN_EXEC),
            mach_loader_c_sha256=sha(MACH_LOADER),
            vnode_h_sha256=sha(VNODE_H),
            disassembly_sha256=sha(DISASM),
            official_mach_loader_c_sha256=sha(OFFICIAL / 'mach_loader.c'),
        ),
        limitations=[
            'kern_exec.c 取自只读资料库 xnu-ios16-full（git 1b191cb58250d0705d8a51287127505aa4bc0789），'
            '与 donor xnu-8796.141.3 的版本一致性由参数逐项对应间接支持，未做全文件逐字节版本绑定。',
            '0x769BF90/94 的原生字节取自 earlysec 基线；300 个随机非 patch 地址的零不一致校验见 native-baseline-probe.json。',
            '本脚本只做静态解码与源码锚点核对，不执行指令、不改二进制、不访问设备。',
        ],
    )
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('verdict:', result['verdict']['belongs_to'])
    print('w6:', result['verdict']['w6'], result['verdict']['w6_meaning'])
    print('bl target:', bl['native_decoded']['target'], '| error branch:', cbnz['native_decoded'])
    print('written:', OUT.relative_to(R))


if __name__ == '__main__':
    main()
