"""由 P0 r1 观测源码派生 r3：下钻到 _VNOP_READ 内部分派点 + 三路阳性对照。

只写源码与切片证据，不改内核、不构建、不操作设备。
设计依据 reports/vnop-suspect-and-gap-20261105/README.md 第五节（用户 20:39 批准）；
用户 20:51 追加授权「可以撤掉不需要的 hook」。

撤掉的对象：r2 的 FB03 / FB06 两个已完成使命的观测 hook（r2 实机已给出
FB03=56504E52、FB06=空白、FB07=00000000，结论已固化）。r3 直接由 P0 r1 派生，
故 0x7466B10 / 0x7466B24 保持原生字节，不重发 r2 的 patch。
保留 P0 r1 的 FB07（MAC-read 返回码）、10 个 coarse 大阶段、6 个功能件、
11 个真原生恢复点与 7 个链接对象。

cave 核算：START..RETIRED_END = 5868 B；P0 r1 = 4444 B，余 1424 B；
5 个完整 SAVE/RESTORE 模板约 900 B，余量充足，无需引入共享子程序。
"""
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent
SRC = R / 'package/kernel-mainline/CoarseStages-p0-native-restore-20261105.S'
OUT = R / 'package/kernel-mainline/CoarseStages-p0-vnop-dispatch-r3.S'
EVIDENCE = R / 'reports/p0-vnop-dispatch-20261105-r3/source-generation.json'

# ABI 模板与 P0/r2 的 hook 逐行一致：保存/恢复 x0-x29、x30、NZCV，栈平衡 256 字节。
SAVE = '''    sub sp,sp,#256
    stp x0,x1,[sp,#0]
    stp x2,x3,[sp,#16]
    stp x4,x5,[sp,#32]
    stp x6,x7,[sp,#48]
    stp x8,x9,[sp,#64]
    stp x10,x11,[sp,#80]
    stp x12,x13,[sp,#96]
    stp x14,x15,[sp,#112]
    stp x16,x17,[sp,#128]
    stp x18,x19,[sp,#144]
    stp x20,x21,[sp,#160]
    stp x22,x23,[sp,#176]
    stp x24,x25,[sp,#192]
    stp x26,x27,[sp,#208]
    stp x28,x29,[sp,#224]
    str x30,[sp,#240]
    mrs x9,nzcv
    str x9,[sp,#248]
'''
RESTORE = '''    ldr x9,[sp,#248]
    msr nzcv,x9
    ldp x0,x1,[sp,#0]
    ldp x2,x3,[sp,#16]
    ldp x4,x5,[sp,#32]
    ldp x6,x7,[sp,#48]
    ldp x8,x9,[sp,#64]
    ldp x10,x11,[sp,#80]
    ldp x12,x13,[sp,#96]
    ldp x14,x15,[sp,#112]
    ldp x16,x17,[sp,#128]
    ldp x18,x19,[sp,#144]
    ldp x20,x21,[sp,#160]
    ldp x22,x23,[sp,#176]
    ldp x24,x25,[sp,#192]
    ldp x26,x27,[sp,#208]
    ldp x28,x29,[sp,#224]
    ldr x30,[sp,#240]
    add sp,sp,#256
'''

# 定值（ASCII）：ENTR / EARL / EPIL / GUAR
ENTR = '    movz w1,#0x5452\n    movk w1,#0x454e,lsl #16\n'
EARL = '    movz w1,#0x524c\n    movk w1,#0x4541,lsl #16\n'
EPIL = '    movz w1,#0x494c\n    movk w1,#0x4550,lsl #16\n'
GUAR = '    movz w1,#0x4152\n    movk w1,#0x4755,lsl #16\n'

NEW_HOOKS = '''
// ===== r3 新增：_VNOP_READ 内部分派点下钻 + 三路阳性对照 =====
// 设计依据 reports/vnop-suspect-and-gap-20261105/README.md 第五节。
// r2 实机已把嫌疑钉到 0x7466B20 bl _VNOP_READ 内部；本轮下钻到 wrapper 的
// 0x746C688 blr x8（vnode v_op 表间接分派进闭源 apfs 的唯一入口）。
//
// 挂点（原生指令逐字取自 r2 上机内核 1a7ad049…）：
//   H1 0x746C628 sub sp,sp,#0x70      _VNOP_READ 入口（uio_resid 检查之前）
//   H2 0x746C684 add x0,x0,#8        此时 x8 已是 v_op 分派目标（0x746C680 ldr 之后）
//   H3 0x746C68C mov x22,x0          blr x8 返回首条，w0 = vnop 返回码
//   H4 0x7466AC4 mov w0,#0x16        len<0 早退（b 0x7466B5C）
//   H5 0x7466B88 add sp,sp,#0xb0     _vn_rdwr_64 正常返回 epilogue（下一条 ret）
//      注：0x74669C8 是 11 个真原生恢复点之一（CHECK10 c10_vn_rdwr_ret witness），
//      不能覆盖；故改挂 _vn_rdwr_64 函数尾部的 0x7466B88。
//
// 字段重排（全部复用已验证可见行位，不引入首次使用的行号）：
//   FB03 (N=3)  阶段编码：H1=ENTR / H4=EARL / H5=EPIL
//   FB06 (N=6)  分派目标 x8 低 32 位；H1 每次入口重置为 GUAR
//   FB0F (N=15) vnop 返回码 w0；H1 每次入口重置为 GUAR
//   FB07 (N=7)  保留 P0 r1 的 mac_read_return，本轮不改
// H1 在每次 _VNOP_READ 入口同时重置 FB06/FB0F，消除启动早段其它 vnode 读
// 对这两个值字段的污染；最后一次调用的状态即最终读数。
//
// 判读（必须三字段配对，单点不得解释成 vnop 已返回）：
//   ENTR / x8值 / GUAR -> blr x8 已分派且未返回（首要嫌疑进一层，x8 给出目标）
//   ENTR / GUAR / GUAR -> 卡在 _VNOP_READ 分派之前（uio_resid / v_op 表读取）
//   ENTR / x8值 / w0值 -> vnop 已返回，配合 FB07 与 10 大阶段判读卡点下移
//   EARL               -> len<0 早退路径阳性对照
//   EPIL               -> _vn_rdwr 正常返回阳性对照
// 重放原生指令一律放在栈恢复之后，保证 sub/add sp 使用原始 sp。
.global r3_vnop_entry
r3_vnop_entry:
''' + SAVE + ENTR + '''    mov w0,#3
    bl draw
''' + GUAR + '''    mov w0,#6
    bl draw
''' + GUAR + '''    mov w0,#15
    bl draw
''' + RESTORE + '''    sub sp,sp,#0x70
    .jump r3_entry_resume

.global r3_vnop_dispatch
r3_vnop_dispatch:
''' + SAVE + '''    mov w1,w8
    mov w0,#6
    bl draw
''' + RESTORE + '''    add x0,x0,#8
    .jump r3_dispatch_resume

.global r3_vnop_return
r3_vnop_return:
''' + SAVE + '''    mov w1,w0
    mov w0,#15
    bl draw
''' + RESTORE + '''    mov x22,x0
    .jump r3_return_resume

.global r3_early_exit
r3_early_exit:
''' + SAVE + EARL + '''    mov w0,#3
    bl draw
''' + RESTORE + '''    mov w0,#0x16
    .jump r3_early_resume

.global r3_epilogue
r3_epilogue:
''' + SAVE + EPIL + '''    mov w0,#3
    bl draw
''' + RESTORE + '''    add sp,sp,#0xb0
    .jump r3_epilogue_resume
'''

PATCH_SITES = [
    dict(name='r3_vnop_entry', address='0xfffffff00746c628', native='ffc301d1',
         native_semantics='sub sp,sp,#0x70', resume='0xfffffff00746c62c',
         fields=['FB03=ENTR', 'FB06=GUAR', 'FB0F=GUAR'],
         role='_VNOP_READ 入口到达 + 值字段重置'),
    dict(name='r3_vnop_dispatch', address='0xfffffff00746c684', native='e0230091',
         native_semantics='add x0,x0,#8', resume='0xfffffff00746c688',
         fields=['FB06=w8'], role='记录 v_op 分派目标 x8 低 32 位'),
    dict(name='r3_vnop_return', address='0xfffffff00746c68c', native='f60300aa',
         native_semantics='mov x22,x0', resume='0xfffffff00746c690',
         fields=['FB0F=w0'], role='blr x8 返回首条，记录 vnop 返回码'),
    dict(name='r3_early_exit', address='0xfffffff007466ac4', native='c0028052',
         native_semantics='mov w0,#0x16', resume='0xfffffff007466ac8',
         fields=['FB03=EARL'], role='len<0 早退路径阳性对照'),
    dict(name='r3_epilogue', address='0xfffffff007466b88', native='ffc30291',
         native_semantics='add sp,sp,#0xb0', resume='0xfffffff007466b8c',
         fields=['FB03=EPIL'], role='_vn_rdwr_64 正常返回 epilogue 阳性对照'),
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    src = SRC.read_text(encoding='utf-8')
    out = src + NEW_HOOKS
    OUT.write_text(out, encoding='utf-8')
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    # 证据一律用文件实际字节（Windows 下 write_text 会转 CRLF），与 build 脚本断言同源。
    out_bytes = OUT.read_bytes()

    # 前缀逐字节一致：r3 = P0 r1 + 5 个 hook，不含 r2 的 2 个 hook。
    assert out.startswith(src), 'P0 r1 prefix must be byte-identical'
    assert 'p0_vnop_read_entry' not in out and 'p0_join_point' not in out, \
        'r2 hooks must not be inherited'
    assert 'p0_mac_read_after' in out, 'P0 r1 FB07 hook must survive'
    for n in (3, 6):
        assert src.count('mov w0,#%d\n' % n) == 0, \
            'P0 r1 prefix must not use FB%02X' % n
    assert out.count('mov w0,#3\n') == 3, 'FB03 needs 3 writers (H1/H4/H5)'
    assert out.count('mov w0,#6\n') == 2, 'FB06 needs 2 writers (H1 reset/H2)'
    assert out.count('mov w0,#15\n') == 3, 'FB0F needs 3 writers (init/H1 reset/H3)'
    assert out.count('mov w0,#7\n') == 1, 'FB07 must stay unique'
    for s in PATCH_SITES:
        assert ('.global ' + s['name']) in out, ('missing hook', s['name'])
    for name in ('r3_vnop_entry', 'r3_vnop_dispatch', 'r3_vnop_return',
                 'r3_early_exit', 'r3_epilogue'):
        body = out.split('.global ' + name, 1)[1]
        for line in SAVE.strip().splitlines():
            assert line in body, (name, 'missing save', line)
        for line in RESTORE.strip().splitlines():
            assert line in body, (name, 'missing restore', line)
    # 重放指令与 resume 目标逐 hook 核对
    replays = {
        'r3_vnop_entry': ('sub sp,sp,#0x70', 'r3_entry_resume'),
        'r3_vnop_dispatch': ('add x0,x0,#8', 'r3_dispatch_resume'),
        'r3_vnop_return': ('mov x22,x0', 'r3_return_resume'),
        'r3_early_exit': ('mov w0,#0x16', 'r3_early_resume'),
        'r3_epilogue': ('add sp,sp,#0xb0', 'r3_epilogue_resume'),
    }
    for name, (insn, resume) in replays.items():
        body = out.split('.global ' + name, 1)[1].split('.global ', 1)[0]
        assert insn in body, (name, 'missing replay', insn)
        assert '.jump ' + resume in body, (name, 'missing resume', resume)

    EVIDENCE.write_text(json.dumps(dict(
        schema='Nuwa.P0VnopDispatchSource.v1', date='2026-11-05',
        input=str(SRC.relative_to(R)), input_sha256=sha(src.encode()),
        output=str(OUT.relative_to(R)), output_sha256=sha(out_bytes),
        output_bytes=len(out_bytes), prefix_verbatim=True,
        input_file_sha256=sha(SRC.read_bytes()),
        parent_candidate='P0-NATIVE-RESTORE r1 (not r2)',
        withdrawn_hooks=[
            dict(name='p0_vnop_read_entry', field='FB03', address='0xfffffff007466b10',
                 reason='r2 实机已给出 56504E52，结论固化；其入口语义由 r3 H1 更靠后的挂点承担'),
            dict(name='p0_join_point', field='FB06', address='0xfffffff007466b24',
                 reason='r2 实机 FB06 空白，结论固化；其返回语义由 r3 H3 更直接的挂点承担'),
        ],
        withdrawal_authorization='用户 2026-11-05 20:51「可以撤掉不需要的 hook」',
        retained=['P0 r1 FB07 mac_read_return', '10 coarse milestones',
                  '6 functional patches', '11 restored native sites', '7 linked objects'],
        new_hooks=[s['name'] for s in PATCH_SITES],
        patch_sites=PATCH_SITES,
        field_layout=dict(
            FB03=dict(n=3, role='阶段编码 ENTR/EARL/EPIL', writers=3,
                      visibility='CHECK10 实机护栏 0000C8A5，已验证可见'),
            FB06=dict(n=6, role='v_op 分派目标 x8 低 32 位；H1 重置 GUAR', writers=2,
                      visibility='CHECK10 实机护栏 5A5A5A5A，已验证可见'),
            FB0F=dict(n=15, role='vnop 返回码 w0；H1 重置 GUAR', writers=3,
                      visibility='CHECK10/CHECK8 记为空白行位，已验证可见；'
                                 'P0 r1 trace_1 初始化另有 1 个写入源，会被 H1 覆盖'),
            FB07=dict(n=7, role='MAC-read 返回码（P0 r1 继承）', writers=1,
                      visibility='r2 实机 00000000，已验证可见'),
        ),
        constants=dict(ENTR='0x454E5452', EARL='0x4541524C',
                       EPIL='0x4550494C', GUAR='0x47554152'),
        decision_matrix=[
            dict(FB03='ENTR', FB06='x8 值', FB0F='GUAR',
                 verdict='blr x8 已分派且未返回；x8 给出 APFS vnop 目标地址'),
            dict(FB03='ENTR', FB06='GUAR', FB0F='GUAR',
                 verdict='卡在 _VNOP_READ 分派之前（uio_resid 检查或 v_op 表读取）'),
            dict(FB03='ENTR', FB06='x8 值', FB0F='w0 值',
                 verdict='vnop 已返回，配合 FB07 与 10 大阶段判读卡点下移'),
            dict(FB03='EARL', verdict='len<0 早退路径阳性对照命中'),
            dict(FB03='EPIL', verdict='_vn_rdwr 正常 epilogue 阳性对照命中'),
        ],
        cave_budget=dict(total=5868, p0_r1_code_bytes=4444,
                         r2_code_bytes=4792, remaining_from_p0_r1=1424,
                         estimated_five_hooks_bytes=900),
        abi_saved_restored=['x0-x29', 'x30', 'NZCV', 'sp 256 字节平衡'],
        limitations=['仅生成源码，未编译；符号地址由构建脚本重算。',
                     'H2 挂在 0x746C684 而非 0x746C680：后者执行前 x8 仍是 v_op 偏移，'
                     '取不到函数指针；0x746C688 是 blr，重放会破坏 x30，故取下一条。',
                     'H1 在每次 _VNOP_READ 入口重置 FB06/FB0F，早段调用不会污染末态。',
                     'H5 不挂 0x74669C8：该地址是 11 个真原生恢复点之一'
                     '（CHECK10 c10_vn_rdwr_ret epilogue witness），改挂 _vn_rdwr_64 尾部 0x7466B88。',
                     '本脚本只写源码与切片证据，不改内核、不构建、不操作设备。'],
    ), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('wrote', OUT.relative_to(R), len(out_bytes), 'bytes')
    print('source sha', sha(out_bytes))
    print('writers N3/N6/N15/N7 =', out.count('mov w0,#3\n'),
          out.count('mov w0,#6\n'), out.count('mov w0,#15\n'),
          out.count('mov w0,#7\n'))
    print('evidence', EVIDENCE.relative_to(R))


if __name__ == '__main__':
    main()
