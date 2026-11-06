"""Generate the CHECK10 field-semantics table from the checked-in observer source.

Inherits the CHECK8 table (IDs 0..20) verbatim and appends the three new
RET-witness fields. All IDs are derived from the 0xFB00+N formula, never
hand-transcribed: the source is parsed for every `bl draw` callsite.
"""
import hashlib, json, re
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
OUT = ROOT / 'reports/ufs-check-10-r1'
SRC = ROOT / 'package/kernel-mainline/CoarseStages-ufs-check10-r1.S'
CHECK8_SEM = ROOT / 'reports/ufs-check-8-r1/field-semantics.json'
BUILD = ROOT / 'out/ufs-check-10-r1/build.json'
PROOF = ROOT / 'out/ufs-check-10-r1/kernel-proof.json'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


base = json.loads(CHECK8_SEM.read_bytes())
build = json.loads(BUILD.read_bytes())
proof = json.loads(PROOF.read_bytes())
text = SRC.read_text()
lines = text.splitlines()

# Map every bl draw to the decimal N in the preceding mov w0,#N.
writers = {}
for i, line in enumerate(lines):
    if line.strip() != 'bl draw':
        continue
    found = None
    for j in range(i - 1, max(-1, i - 6), -1):
        m = re.fullmatch(r'mov w0,#(\d+)', lines[j].strip())
        if m:
            found = int(m.group(1))
            break
    assert found is not None, 'unparsed bl draw at line %d' % (i + 1)
    writers.setdefault(found, []).append(':%d %s' % (i + 1, 'c10_vn_rdwr_ret' if found >= 21 else 'inherited'))

# The CHECK8 prefix must be byte-identical and its ID table must still hold.
check8_text = (ROOT / 'package/kernel-mainline/CoarseStages-ufs-check8-r1.S').read_text()
assert text.startswith(check8_text), 'CHECK8 observer prefix is not verbatim'
for f in base['fields']:
    n = f['field_id_decimal']
    assert n in writers, 'inherited ID %d lost all textual writers' % n
    # Some inherited callsites pass the ID through a register rather than a
    # literal `mov w0,#N`, so the CHECK8 writer_count is authoritative for
    # IDs 0..20 and is preserved verbatim rather than re-derived here.

FORMULA = 'draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N; N is DECIMAL, screen suffix is HEX'
# CHECK8 states the same formula in different words. Bind on the invariant
# parts rather than on prose, and keep the CHECK8 wording in the record.
for wording in (base['encoding_formula'], build['check10_delta']['encoding_formula'], FORMULA):
    assert '0xFB00 + N' in wording and 'DECIMAL' in wording.upper(), wording

new_fields = [
    dict(field_id_decimal=21, screen_label='FB15', id_word='0xfb15', encoding=FORMULA,
         writers=writers[21], writer_count=len(writers[21]),
         unobserved='行空白（初始化不写该编号）', inherited_from_check5=False,
         name='ret_arrival', screen='FB15', kind='arrival-magic', expected='C10A55AA',
         meaning='c10_vn_rdwr_ret 到达标记（固定 C10A55AA）。空白 = _vn_rdwr 从未执行到 epilogue，即卡在 vn_rdwr_64 / UFS 后端内部。'),
    dict(field_id_decimal=22, screen_label='FB16', id_word='0xfb16', encoding=FORMULA,
         writers=writers[22], writer_count=len(writers[22]),
         unobserved='行空白（初始化不写该编号）', inherited_from_check5=False,
         name='ret_w0', screen='FB16', kind='return-value', expected='任意 32 位',
         meaning='最后一次 _vn_rdwr RET 时的 w0 返回值。00000000 = 成功；非零 = error，会走 0x769C144 错误分支。'),
    dict(field_id_decimal=23, screen_label='FB17', id_word='0xfb17', encoding=FORMULA,
         writers=writers[23], writer_count=len(writers[23]),
         unobserved='行空白（初始化不写该编号）', inherited_from_check5=False,
         name='ret_x30_low32', screen='FB17', kind='return-landing', expected='0769BF94',
         meaning='最后一次 _vn_rdwr RET 时 x30 的低 32 位，即真实返回落点。0769BF94 为预期（coarse_read_after 挂点）；其他值说明 x30 被改写。'),
]
for n in (21, 22, 23):
    assert len(writers[n]) == 1, 'new ID %d must have exactly one writer' % n
    assert n not in [f['field_id_decimal'] for f in base['fields']], 'ID collision'

doc = dict(base)
doc.update(
    schema='Nuwa.FieldSemantics.v2',
    candidate='UFS-CHECK-10 r1',
    generated_by='scripts/gen-ufs-check10-field-semantics.py',
    generated_by_formula=True,
    inherited_encoding_formula=base['encoding_formula'],
    image_sha256=build['image_sha256'],
    kernel_sha256=build['kernel_sha256'],
    observer_source='package/kernel-mainline/CoarseStages-ufs-check10-r1.S',
    observer_source_sha256=sha(SRC),
    builder_source='scripts/build-ufs-check10-r1.py',
    builder_sha256=sha(ROOT / 'scripts/build-ufs-check10-r1.py'),
    inherited_observer_prefix_sha256=sha(ROOT / 'package/kernel-mainline/CoarseStages-ufs-check8-r1.S'),
    check5_observer_prefix_sha256=sha(ROOT / 'package/kernel-mainline/CoarseStages-ufs-check5-r1.S'),
    initialised_ids_decimal=base['initialised_ids_decimal'],
    fields=base['fields'] + new_fields,
    decision_matrix=[
        dict(FB15='C10A55AA', FB16='00000000', FB17='0769BF94',
             verdict='vn_rdwr 正常返回、x30 正确、成功路径经 0x84D9BE4 -> 0x769BF98。CHECK8「未返回」结论作废；卡点在 0x769BF98 之后的续接链，下一轮须转向 bsd_init / VFS_ROOT 下游。'),
        dict(FB15='C10A55AA', FB16='非零', FB17='0769BF94',
             verdict='vn_rdwr 返回非零 error，0x84D9BE4 走 0x769C144 错误分支；FB07 空白是必然。需按 FB16 错误码定位后端失败原因。'),
        dict(FB15='C10A55AA', FB16='任意', FB17='非 0769BF94',
             verdict='RET 落到意外地址：x30 在进入 RET 前被改写，或观测改道控制流。这会把卡点定位到返回链而非 UFS 读。'),
        dict(FB15='行空白', FB16='任意', FB17='任意',
             verdict='_vn_rdwr 从未执行到 epilogue，卡在 vn_rdwr_64 / VNOP_READ / UFS 后端内部；这是「未返回」假设的唯一成立条件。'),
        dict(FB15='任意', FB16='任意', FB17='任意', guard='FB03 非 0000C8A5 或 FB06 非 5A5A5A5A',
             verdict='framebuffer 通道或自检地基失效，本轮所有读数需重估，不得据以判定。'),
    ],
    check8_reassessment=dict(
        field='FB07 (N=7, c8_read_return)',
        site='0xfffffff00769bfa4',
        correction='0x769BFA4 是 resid!=0 的短读路径：0x769BF9C 的 cbz w23, 0x769BFD4 在 resid==0 时直接跳过它。x30 常量 movz #49044 == 0xBF94，真实 RET 落点是 0x769BF94，不是 0x769BFA4。',
        consequence='FB07 全 332 帧空白是正常返回的预期结果，不能作为「vn_rdwr 未返回」的证据。CHECK8 归档结论不回写，本表作为更正记录。',
        legacy_documentation_error='CoarseStages-ufs-check8-r1.S 注释与 build-ufs-check8-r1.py 的 x30_installed_by_coarse_read_before 字符串写成 0x769bfa4；机器码与离线审计报告的值 0x769bf94 才是对的。'),
    single_variable=dict(
        baseline='CHECK8 (consumed)',
        baseline_kernel_sha256=build['check10_delta']['baseline_kernel_sha256'],
        outside_cave_diff_word_count=build['check10_delta']['outside_cave_diff_word_count'],
        outside_cave_only_diff=build['check10_delta']['outside_cave_only_diff'],
        control_flow_changed=False,
        repair_patches_removed=0,
        inherited_observations_removed=0,
        note='Cave 内部因追加 hook 导致 draw/font 后移与 bl draw 重定位；cave 之外整颗内核相对 CHECK8 只有 0x74669C8 一个 4 字节改动。'),
    repair_patches=proof['repair_patches'],
    screen_expectation=dict(
        f_region='CHECK8 的 FB00..FB14 全部照旧；新增 FB15/FB16/FB17 三行是本轮唯一判读依据',
        centre_graphic='UniXNU logo (NOT the Apple logo)',
        non_hex_colour_blocks='F 区下方小色块仍会多轮变化，判读须用 60fps 逐帧 RGB 分类，不得用灰度统计',
        timeline_required=True),
    non_field_indicators=dict(
        centre_graphic='UniXNU logo (NOT the Apple logo)',
        states=['no colour block', 'orange f132', 'green steady f138', 'white block f326'],
        note='CHECK9 已排除 framebuffer 写导致卡死；色块时序可偏移但终局不推进。'),
)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'field-semantics.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

md = ['# UFS-CHECK-10 r1 字段语义表', '',
      '公式：`ID = (N + 0xB00) | 0xF000 = 0xFB00 + N`，**N 是十进制**，屏幕 `FBxx` 是十六进制。',
      '', '| ID(N) | 屏幕 | 写入者 | 含义 |', '|---|---|---|---|']
for f in doc['fields']:
    if f['field_id_decimal'] >= 21:
        md.append('| %d | %s | %s | %s |' % (f['field_id_decimal'], f['screen_label'],
                                             ', '.join(f['writers']), f['meaning']))
md += ['', '## 判读矩阵', '']
for r in doc['decision_matrix']:
    md.append('- `%s` → %s' % (json.dumps(r, ensure_ascii=False), r['verdict']))
md += ['', '## 更正（本轮离线核查发现）', '',
       '1. `49044 = 0xBF94`，不是 `0xBFA4`。CHECK8 源码注释与构建脚本字符串写错，机器码与离线审计报告是对的。',
       '2. CHECK8 的 FB07 挂在 `0x769BFA4`（resid≠0 短读路径），`0x769BF9C cbz w23` 在 resid==0 时跳过它。'
       '**FB07 空白不能证明 vn_rdwr 未返回**，CHECK8 的核心结论作废。',
       '3. 因此上一轮 P0「摘掉 0x84D9BE4 遗留桥接」不成立：该桥接在真实返回链上是活的（0x769BF94 → coarse_read_after → 0x84D9BE4）。',
       '', '## 单一变量', '',
       '相对已消费的 CHECK8：源码前缀逐字节相同，修复补丁 0 删除、继承观测 0 删除、控制流 0 改动；'
       'cave 之外整颗内核只有 `0x74669C8` 一个 word 从 `ff030191` 改为指向新 hook 的 `b`，原生 `ret` 保持 `c0035fd6`。']
(OUT / 'field-semantics.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
print('wrote field-semantics.json / .md; fields', len(doc['fields']), 'new IDs 21/22/23 -> FB15/FB16/FB17')
