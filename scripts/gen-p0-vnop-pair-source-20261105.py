"""由 P0 观测源码派生 r2：追加 VNOP_READ 入口 / 汇合点配对观测。

只写源码与切片证据，不改内核、不构建、不操作设备。
设计依据 reports/apfs-vs-hfs-stack-20261105/README.md 第 4.4 节。
"""
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent
SRC = R / 'package/kernel-mainline/CoarseStages-p0-native-restore-20261105.S'
OUT = R / 'package/kernel-mainline/CoarseStages-p0-vnop-pair-r2.S'
EVIDENCE = R / 'reports/p0-vnop-pair-20261105-r2/source-generation.json'

# ABI 模板与 P0 的 hook 一致：保存/恢复 x0-x29、x30、NZCV，栈平衡 256 字节。
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

NEW_HOOKS = '''
// ===== P0 r2 新增：VNOP_READ 入口 / 汇合点配对观测 =====
// 设计依据 reports/apfs-vs-hfs-stack-20261105/README.md 4.4。
// 挂点 0x7466B10：原生 mov x3,sp，位于 cbz w22,0x7466AF0 的 UIO_READ 分支，
//   且是 tbnz w20,#0x15 / cbz w0 的跳转目标；只有 read 路径经过。
// 挂点 0x7466B24：原生 mov x20,x0，是 MAC errno / VNOP_WRITE / swap / VNOP_READ
//   四条路径共用的汇合点，故单点不能证明 VNOP_READ 执行过，必须配对。
// FB03 (N=3) = 入口到达 magic 0x56504E52；FB06 (N=6) = 汇合点 w0。
// 两个行位在 CHECK10 实机作护栏出现（0000C8A5 / 5A5A5A5A），可见性已验证；
// P0 源码中这两个编号无任何写入源，因此没有字段编号冲突。
// 判读四态：
//   FB03 出现 + FB06 出现 -> VNOP_READ 已调用且返回，卡点在更下游
//   FB03 出现 + FB06 空白 -> VNOP_READ 已进入但未返回（后端/完成链卡住）
//   FB03 空白 + FB06 出现 -> 直跳汇合点（MAC errno 等），VNOP_READ 未执行
//   两者全空              -> 未到 0x7466B10，结合 FB07 判 MAC-read 或更早
// 重放原生指令放在栈恢复之后，保证 mov x3,sp 使用原始 sp。
.global p0_vnop_read_entry
p0_vnop_read_entry:
''' + SAVE + '''    movz w1,#0x4e52
    movk w1,#0x5650,lsl #16
    mov w0,#3
    bl draw
''' + RESTORE + '''    mov x3,sp
    .jump p0_vnop_read_resume

.global p0_join_point
p0_join_point:
''' + SAVE + '''    mov w1,w0
    mov w0,#6
    bl draw
''' + RESTORE + '''    mov x20,x0
    .jump p0_join_resume
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    src = SRC.read_text(encoding='utf-8')
    out = src + NEW_HOOKS
    OUT.write_text(out, encoding='utf-8')
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)

    # 字段编号纪律：本候选全量写入源由公式生成，禁止复用已占用编号。
    assert out.count('mov w0,#3\n') == 1, 'FB03 must have exactly one writer'
    assert out.count('mov w0,#6\n') == 1, 'FB06 must have exactly one writer'
    assert out.count('mov w0,#7\n') == 1, 'FB07 (inherited MAC-read) must stay unique'
    assert src.count('mov w0,#3\n') == 0 and src.count('mov w0,#6\n') == 0, \
        'P0 prefix must not already use FB03/FB06'
    for name in ('p0_vnop_read_entry', 'p0_join_point', 'p0_mac_read_after',
                 'coarse_release_before', 'phase_record'):
        assert (name + ':\n') in out, ('missing hook', name)
    assert out.startswith(src), 'P0 prefix must be byte-identical'
    assert out.count('.jump p0_vnop_read_resume') == 1
    assert out.count('.jump p0_join_resume') == 1
    # ABI 卫生：两个新 hook 的保存/恢复段必须与 P0 模板逐行一致。
    for name in ('p0_vnop_read_entry', 'p0_join_point'):
        body = out.split('.global ' + name, 1)[1]
        for line in SAVE.strip().splitlines():
            assert line in body, (name, 'missing save', line)
        for line in RESTORE.strip().splitlines():
            assert line in body, (name, 'missing restore', line)

    EVIDENCE.write_text(json.dumps(dict(
        schema='Nuwa.P0VnopPairSource.v1', date='2026-11-05',
        input=str(SRC.relative_to(R)), input_sha256=sha(src.encode()),
        output=str(OUT.relative_to(R)), output_sha256=sha(out.encode()),
        output_bytes=len(out.encode()), prefix_verbatim=True,
        new_hooks=['p0_vnop_read_entry', 'p0_join_point'],
        patch_sites=[
            dict(address='0xfffffff007466b10', native='e3030091',
                 native_semantics='mov x3,sp', hook='p0_vnop_read_entry',
                 resume='0xfffffff007466b14', field_decimal=3, field_label='FB03',
                 value='固定 magic 0x56504E52', role='VNOP_READ 入口到达'),
            dict(address='0xfffffff007466b24', native='f40300aa',
                 native_semantics='mov x20,x0', hook='p0_join_point',
                 resume='0xfffffff007466b28', field_decimal=6, field_label='FB06',
                 value='w0（VNOP_READ 返回码或 MAC errno）', role='共同汇合点'),
        ],
        field_visibility_evidence='CHECK10 实机 368 帧中 FB03/FB06 作为护栏出现并持续到末帧'
                                  '（reports/ufs-check-10-r1/field-semantics.json、trial-plan.md:45-47）',
        field_conflict_check=dict(n3_writers=1, n6_writers=1, n7_writers=1,
                                  prefix_n3=0, prefix_n6=0,
                                  formula='draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N'),
        abi_saved_restored=['x0-x29', 'x30', 'NZCV', 'sp 256 字节平衡'],
        decision_matrix=[
            dict(FB03='出现', FB06='出现', verdict='VNOP_READ 已调用且返回，后端完成链正常，卡点下移'),
            dict(FB03='出现', FB06='空白', verdict='VNOP_READ 已进入但未返回，后端/完成链卡住（首要嫌疑证实）'),
            dict(FB03='空白', FB06='出现', verdict='直跳汇合点，VNOP_READ 未执行；结合 FB07 判 MAC errno'),
            dict(FB03='空白', FB06='空白', verdict='未到 0x7466B10，卡在 MAC-read 或更前'),
        ],
        limitations=['仅生成源码，未编译；符号地址由构建脚本重算。',
                     '本脚本只写源码与切片证据，不改内核、不构建、不操作设备。'],
    ), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('wrote', OUT.relative_to(R), len(out.encode()), 'bytes')
    print('FB03/FB06/FB07 writers',
          out.count('mov w0,#3\n'), out.count('mov w0,#6\n'), out.count('mov w0,#7\n'))
    print('evidence', EVIDENCE.relative_to(R))


if __name__ == '__main__':
    main()
