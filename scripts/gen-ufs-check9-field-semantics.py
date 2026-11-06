"""Generate CHECK9 field semantics from the source by the 0xFB00+N formula.

CHECK9 is a zero-draw control: every inherited callsite still calls draw, but
draw is a single `ret`. Therefore EVERY field is expected to be blank. A blank
F region is the PASS condition, not a failure. The screen verdict comes from
the non-field RGB colour-block timeline below the F region.
"""
import hashlib, json, re
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
SRC = ROOT/'package/kernel-mainline/CoarseStages-ufs-check9-r1.S'
CHECK5 = ROOT/'package/kernel-mainline/CoarseStages-ufs-check5-r1.S'
OUT = ROOT/'reports/ufs-check-9-r1'
PROOF = ROOT/'out/ufs-check-9-r1/build.json'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

assert SRC.read_bytes() == CHECK5.read_bytes(), 'CHECK9 source must equal CHECK5'
proof = json.loads(PROOF.read_bytes())
lines = SRC.read_text().splitlines()
label = None
writers = {}
bl_count = 0
for i, line in enumerate(lines, 1):
    s = line.strip()
    m = re.match(r'^([A-Za-z_$][\w$.]*):', s)
    if m:
        label = m.group(1)
    if s != 'bl draw':
        continue
    bl_count += 1
    n = None
    for j in range(i-2, max(-1, i-8), -1):
        mm = re.fullmatch(r'mov\s+w0,#(\d+)', lines[j].strip())
        if mm:
            n = int(mm.group(1)); break
    assert n is not None, ('unparsed draw ID at line', i)
    writers.setdefault(n, []).append(':{} {}'.format(i, label))
assert bl_count == 37, ('unexpected draw callsite count', bl_count)

initialised = [4,5,8,9,10,11,12,13,14,15,20]
fields = []
for n in sorted(set(writers) | set(initialised)):
    fields.append(dict(
        field_id_decimal=n,
        screen_label='FB%02X' % n,
        id_word=hex(0xFB00+n),
        encoding='draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N; N is DECIMAL, screen suffix is HEX',
        writers=writers.get(n, []),
        writer_count=len(writers.get(n, [])),
        inherited_from_check5=True,
        initialised=n in initialised,
        visible_in_check9=False,
        expected_screen='整行空白（zero-draw：draw 体为 ret+nops，任何编号都不写 framebuffer）'))
ids = [f['field_id_decimal'] for f in fields]
assert len(ids) == len(set(ids)), 'duplicate field ID'
assert next(f for f in fields if f['field_id_decimal']==10)['screen_label']=='FB0A'
assert next(f for f in fields if f['field_id_decimal']==16)['screen_label']=='FB10'

sem = dict(
    schema='Nuwa.FieldSemantics.v3.zero-draw',
    candidate='UFS-CHECK-9 r1',
    generated_by='scripts/gen-ufs-check9-field-semantics.py scanning CHECK9 source',
    generated_by_formula=True,
    encoding_formula='ID_word = (N + 0xB00) | 0xF000 = 0xFB00 + N, N DECIMAL; screen label FB%02X uses HEX(N)',
    image_sha256=proof['image_sha256'],
    kernel_sha256=proof['kernel_sha256'],
    observer_source=str(SRC.relative_to(ROOT)).replace('/', '\\'),
    observer_source_sha256=sha(SRC),
    builder_source='scripts/build-ufs-check9-r1.py',
    builder_sha256=sha(ROOT/'scripts/build-ufs-check9-r1.py'),
    inherited_observer_prefix_sha256=sha(CHECK5),
    zero_draw=True,
    draw_body_pattern=proof['check9_delta']['draw_body_pattern'],
    draw_callsites_retained=bl_count,
    framebuffer_writes_executed=0,
    screen_expectation=dict(
        f_region='ALL rows blank for the entire recording. This is the expected zero-draw signature, not a fault.',
        interpretation_rule='Never read a blank/uninitialised F row as a phase marker in CHECK9. There are no field values.',
        verdict_channel='60fps per-frame RGB classification of the small colour blocks BELOW the F region'),
    inherited_id_sanity=dict(
        FB0A='(N=10) _vfs_mountroot return; CHECK5/6/7/8 measured 00000000 = mount succeeded',
        FB10='(N=16) exec milestone bitmap; CHECK5/6/7/8 measured 00000003; NOT ESRCH, NOT mount failure',
        FB12='(N=18) phase field; A0000005 = phase 5 coarse_read_before',
        warning='These historical values are NOT visible in CHECK9. They are recorded only to prevent re-introducing the decimal/hex misreading.'),
    non_field_indicators=dict(
        rule='AGENTS.md section 6: non-field status must be recorded per frame with RGB classification; do not interpret as kernel phase without a semantic table',
        baseline='UFS-CHECK-8 r1, 60fps, 332 frames',
        states=[
            dict(state='no_colour', frames='f0-126', rgb='none', time_s='0.00-2.10'),
            dict(state='orange', frames='f132-137', rgb='f132', time_s='2.20-2.28'),
            dict(state='green_steady', frames='f138-325', rgb='f138', time_s='2.30-5.42'),
            dict(state='white_blocks_full_bright', frames='f326-330', time_s='5.43-5.50')],
        centre_graphic='UniXNU logo (NOT the Apple logo)',
        verdict_matrix=dict(
            progresses='colour blocks advance to a NEW state, or a post-logo UI appears => observer screen writes are the stall cause; re-evaluate all prior root-cause verdicts',
            unchanged='same four-state timeline and same stall => framebuffer writes excluded; next suspect is hook control flow / inherited x30 defect / genuine UFS read hang',
            f_region_has_any_digit='zero-draw was NOT applied; candidate or image is wrong -> abort, no verdict')),
    initialised_ids_decimal=initialised,
    fields=fields)

OUT.mkdir(parents=True, exist_ok=True)
(OUT/'field-semantics.json').write_text(json.dumps(sem, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

md = ['# UFS-CHECK-9 r1 字段语义表（zero-draw 对照）', '',
      '## 本轮没有字段值', '',
      'CHECK9 的观测源与 CHECK5 逐字节相同，全部 37 个 `bl draw` 调用点都在；',
      '但 `draw` 函数体被替换为 `ret` + 54 个 `nop`，不写 framebuffer、不执行 `dsb sy`。',
      '**F 区全片空白是本轮的预期签名，不是故障、不是「未到达」。**',
      '编号按 `0xFB00 + N` 生成，`N` 为十进制，屏幕 `FBxx` 的 `xx` 是十六进制。', '',
      '| 编号 N | 屏幕 | 写入源数 | CHECK9 预期 |', '|---|---|---|---|']
for f in fields:
    md.append('| {} | {} | {} | 恒空白 |'.format(f['field_id_decimal'], f['screen_label'], f['writer_count']))
md += ['', '## 历史编号防误读（本轮不可见）', '',
       '- `FB0A` (N=10) = `_vfs_mountroot` 返回值，CHECK5/6/7/8 实测 `00000000`，根挂载成功。',
       '- `FB10` (N=16) = exec 里程碑位图，实测 `00000003`，**不是 ESRCH、不是挂载失败**。',
       '- `FB12` (N=18) = phase 字段，`A0000005` 是 phase 5 `coarse_read_before`。', '',
       '## 判读通道：F 区下方色块（60fps 逐帧 RGB）', '',
       '| 状态 | 帧 | 时间 |', '|---|---|---|',
       '| 无色 | f0-126 | 0.00-2.10s |', '| 橙 | f132-137 | 2.20-2.28s |',
       '| 绿稳态 | f138-325 | 2.30-5.42s |', '| 白块全亮 | f326-330 | 5.43-5.50s |', '',
       '画面中央是 **UniXNU logo**，不是 Apple logo。', '',
       '| 观察 | 结论 |', '|---|---|',
       '| 色块推进到第 5 态 / 出现 logo 之后的 UI | 观测写屏就是卡点成因，前几轮根因结论全部重估 |',
       '| 四态时间线与 CHECK8 一致、仍停住 | 排除 framebuffer 写；下一步查 hook 控制流 / 继承的 x30 缺陷 / 真实 UFS 读挂死 |',
       '| F 区出现任何数字 | zero-draw 未生效，候选或镜像错误，中止判读 |', '']
(OUT/'field-semantics.md').write_text('\n'.join(md), encoding='utf-8')
print('generated', OUT/'field-semantics.json', sha(OUT/'field-semantics.json'))
print('fields', len(fields), 'draw callsites', bl_count)
