"""P0 r2 (VNOP_READ 配对观测) 回归 + 字段语义表 + 资格化。

在 Windows Python 下运行。输出全部落在 reports/p0-vnop-pair-20261105-r2/：
  regression.json / field-semantics.json / FIELD-SEMANTICS.md /
  qualification.json / README.md
字段语义表与 qualification.json 同轮生成，语义表 SHA 计入候选绑定（AGENTS §6）。
"""
import hashlib
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import flush_trace_inputs as trace  # noqa: E402
import nuwa_launch_context as context  # noqa: E402
import usb_ramdisk_package as transport  # noqa: E402

WORK = R / 'out/p0-vnop-pair-20261105-r2'
INDEP = R / 'out/p0-vnop-pair-20261105-r2-independent'
REPORT = R / 'reports/p0-vnop-pair-20261105-r2'
SOURCE = R / 'package/kernel-mainline/CoarseStages-p0-vnop-pair-r2.S'
P0_SEM = R / 'reports/p0-native-restore-20261105-r1/field-semantics.json'
P0_KERNEL = R / 'out/p0-native-restore-20261105-r1/kernel.macho'
EARLY = R / 'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho'
TRIAGE = R / 'reports/native-restore-20261105/patch-triage.json'

FORMULA = 'draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N; N 为十进制，屏幕后缀为十六进制'
NEW_FIELDS = {
    3: dict(name='vnop_read_entry_magic', kind='arrival-magic',
            meaning='P0 r2 新增：0x7466B10（仅 UIO_READ 路径）入口到达标记，固定 0x56504E52。'
                    '出现 = 已到达 VNOP_READ 参数准备；空白 = 未到达该点。',
            value_source='w1 = movz/movk 立即数 0x56504E52',
            expected='56504E52', unobserved_default='行空白（本候选初始化不绘制该编号）'),
    6: dict(name='vnop_join_w0', kind='return-value',
            meaning='P0 r2 新增：0x7466B24 共同汇合点的 w0（VNOP_READ 返回码或 MAC errno）。'
                    '该点同时被 MAC errno / VNOP_WRITE / swap 路径直达，故必须与 FB03 配对判读。',
            value_source='w1 = w0（汇合点返回值，未经修改）',
            expected='00000000 = 成功；非零 = error', unobserved_default='行空白（本候选初始化不绘制该编号）'),
}
BIG_STAGES = {
    0xfffffff0078e37a8: 'root_wait', 0xfffffff007673098: 'root_return',
    0xfffffff0076732f4: 'root_auth', 0xfffffff0076730e8: 'mount_return',
    0xfffffff00769d2a4: 'init_entry', 0xfffffff00767356c: 'init_loaded',
    0xfffffff00769ce3c: 'exec_entry', 0xfffffff00769bdd8: 'exec_namei',
    0xfffffff00769d624: 'exec_result', 0xfffffff0073c3864: 'el0',
}
KEEP_FUNCTIONAL = {
    0xfffffff0078e331c: 'BSD root selector',
    0xfffffff0084e56a0: 'mapped end', 0xfffffff0084e5710: 'validate_increment',
    0xfffffff0084e5768: 'install_increment', 0xfffffff0084e5740: 'map_permissions',
    0xfffffff00769d230: 'coarse_release_before',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sha_p(path):
    return sha(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_bytes())


def decode_branch(word, pc):
    if word & 0x7c000000 == 0x14000000:
        imm = word & 0x3ffffff
        imm = imm - (1 << 26) if imm & (1 << 25) else imm
        return ('bl' if word & 0x80000000 else 'b', pc + 4 * imm)
    if (word >> 24) & 0xff in (0x34, 0x35, 0xb4, 0xb5):
        kind = 'cbnz' if (word >> 24) & 0xff in (0x35, 0xb5) else 'cbz'
        imm = (word >> 5) & 0x7ffff
        if imm & (1 << 18):
            imm -= 1 << 19
        return (kind, pc + 4 * imm)
    return (None, None)


def parse_writers():
    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    init_start = next(i for i, l in enumerate(lines) if l.strip() == 'trace_1:')
    init_end = next(i for i in range(init_start + 1, len(lines))
                    if lines[i].strip().startswith('.global'))
    label, writers = None, {}
    for i, line in enumerate(lines):
        s = line.strip()
        if s.endswith(':') and not s.startswith('.') and ' ' not in s:
            label = s[:-1]
        if s != 'bl draw':
            continue
        n, w1 = None, None
        for j in range(i - 1, max(-1, i - 7), -1):
            t = lines[j].strip()
            m = re.fullmatch(r'mov w0,#(\d+)', t)
            if m and n is None:
                n = int(m.group(1))
            m1 = re.fullmatch(r'mov w1,(.+)', t) or re.fullmatch(r'movz w1,(.+)', t)
            if m1 and w1 is None:
                w1 = m1.group(1)
            if n is not None and w1 is not None:
                break
        assert n is not None, 'unparsed bl draw at line %d' % (i + 1)
        writers.setdefault(n, []).append(dict(line=i + 1, hook=label, w1=w1,
                                              initialisation=init_start <= i < init_end))
    initial = {}
    for n, items in writers.items():
        for w in items:
            if not w['initialisation']:
                continue
            v = (w['w1'] or '').strip()
            if v.startswith('#'):
                val = v[1:]
                initial.setdefault(n, '00000000' if val == '0' else
                                   ('FFFFFFFF' if val.lower() in ('0xffffffff', '-1')
                                    else '%08X' % int(val, 0)))
            else:
                initial.setdefault(n, '运行时值（%s）' % v)
            break
    return lines, writers, initial


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    build = read(WORK / 'build.json')
    proof = read(WORK / 'kernel-proof.json')
    triage = read(TRIAGE)
    p0_sem = read(P0_SEM)
    delta = build['r2_delta']
    checks = []

    def check(name, condition, evidence):
        assert condition, ('regression failed', name, evidence)
        checks.append(dict(name=name, passed=bool(condition), evidence=evidence))

    kernel = (WORK / 'kernel.macho').read_bytes()
    independent = (INDEP / 'kernel.macho').read_bytes()
    p0_kernel = P0_KERNEL.read_bytes()
    early = EARLY.read_bytes()
    image = (WORK / 'boot-p0-vnop-pair-20261105-r2.img').read_bytes()
    b = trace.builder()
    m, me = b.macho(kernel), b.macho(early)

    def word_at(raw, macho, va, n=4):
        off = b.backed(macho, va, n)
        return raw[off:off + n].hex()

    # 1) 绑定 / 独立重建
    check('kernel_sha_matches_build', sha(kernel) == build['kernel_sha256'], sha(kernel))
    check('image_sha_matches_build', sha(image) == build['image_sha256'], sha(image))
    check('independent_rebuild_byte_identical', kernel == independent, sha(independent))

    # 2) 11 个恢复点仍等于 earlysec
    restore = [(int(r['address'], 16), r['native_from_earlysec'])
               for r in triage['sites'] if r['classification'] == 'observer-or-bridge']
    check('restore_site_count', len(restore) == 11, len(restore))
    bad = [(hex(va), word_at(kernel, m, va), word_at(early, me, va))
           for va, nat in restore if word_at(kernel, m, va) != word_at(early, me, va)]
    check('all_11_restore_sites_equal_earlysec', not bad, bad)
    check('native_bl_vn_rdwr', word_at(kernel, m, 0xfffffff00769bf90) == '7e2af797', '7e2af797')
    check('native_cbnz_w0', word_at(kernel, m, 0xfffffff00769bf94) == '800d0035', '800d0035')

    # 3) 10 大阶段 / 6 功能件
    sy = proof['symbols']
    stage_detail = []
    for va, name in BIG_STAGES.items():
        w = int.from_bytes(bytes.fromhex(word_at(kernel, m, va)), 'little')
        kind, target = decode_branch(w, va)
        stage_detail.append(dict(stage=name, address=hex(va), kind=kind, target=hex(target)))
        check('big_stage_%s_still_hooked' % name,
              kind in ('b', 'bl') and trace.START <= target < trace.START + proof['code_bytes'],
              stage_detail[-1])
    clean = (R / 'out/ufs-check-4-r1-clean/kernel.macho').read_bytes()
    for va, name in KEEP_FUNCTIONAL.items():
        off = b.backed(m, va, 4)
        old = int.from_bytes(clean[off:off + 4], 'little')
        ok, otgt = decode_branch(old, va)
        if ok in ('b', 'bl') and trace.START <= otgt < trace.START + proof['code_bytes']:
            nk, ntgt = decode_branch(int.from_bytes(kernel[off:off + 4], 'little'), va)
            check('functional_%s_rebound' % name,
                  nk in ('b', 'bl') and trace.START <= ntgt < trace.START + proof['code_bytes'],
                  hex(ntgt))
        else:
            check('functional_%s_data_unchanged' % name,
                  kernel[off:off + 4] == clean[off:off + 4],
                  dict(before=clean[off:off + 4].hex(), after=kernel[off:off + 4].hex()))

    # 4) 原生关键路径未被新观测破坏
    check('native_ret_unchanged', word_at(kernel, m, 0xfffffff0074669cc) == 'c0035fd6', 'c0035fd6')
    check('resid_path_unchanged',
          all(word_at(kernel, m, va) == word_at(p0_kernel, m, va)
              for va in (0xfffffff00769bf98, 0xfffffff00769bf9c, 0xfffffff00769bfa0)),
          'resid 三条原生指令与 P0 一致')
    check('legacy_bridge_preserved',
          word_at(kernel, m, 0xfffffff0084d9be4) == word_at(p0_kernel, m, 0xfffffff0084d9be4),
          '0x84D9BE4 不可达字节保留')
    check('p0_mac_read_site_preserved',
          word_at(kernel, m, 0xfffffff007466ad0) == word_at(p0_kernel, m, 0xfffffff007466ad0),
          'FB07 挂点与 P0 一致')

    # 5) 字段编号纪律
    lines, writers, initial = parse_writers()
    for n in (3, 6, 7):
        check('field_%d_single_writer' % n, len(writers.get(n, [])) == 1, writers.get(n))
    check('field3_writer_is_new_hook', writers[3][0]['hook'] == 'p0_vnop_read_entry', writers[3])
    check('field6_writer_is_new_hook', writers[6][0]['hook'] == 'p0_join_point', writers[6])
    check('field7_writer_is_mac_read', writers[7][0]['hook'] == 'p0_mac_read_after', writers[7])
    check('field7_value_is_w0', writers[7][0]['w1'] == 'w0', writers[7][0])
    check('no_check10_retired_ids', not ({21, 22, 23} & set(writers)), sorted(set(writers) & {21, 22, 23}))
    check('all_field_ids_have_semantics',
          set(writers) <= (set(f['field_id_decimal'] for f in p0_sem['fields']) | set(NEW_FIELDS)),
          sorted(set(writers) - set(f['field_id_decimal'] for f in p0_sem['fields']) - set(NEW_FIELDS)))

    # 6) 新挂点字节与分支目标
    sites = delta['new_patch_sites']
    check('new_patch_site_count', len(sites) == 2, len(sites))
    for s in sites:
        va = int(s['address'], 16)
        w = int.from_bytes(bytes.fromhex(word_at(kernel, m, va)), 'little')
        kind, target = decode_branch(w, va)
        check('site_%s_is_branch' % s['symbol'], kind == 'b', dict(word=hex(w), kind=kind))
        check('site_%s_target' % s['symbol'], target == sy[s['symbol']],
              dict(target=hex(target), hook=hex(sy[s['symbol']])))
        check('site_%s_before_native' % s['symbol'], s['before'] == {
            '0xfffffff007466b10': 'e3030091', '0xfffffff007466b24': 'f40300aa'}[s['address']],
            s['before'])

    # 7) 新 hook 机器码：重放原生指令 + 跳回 resume
    cave_lo = delta['cave_range']['file_offset']
    cave = kernel[cave_lo:cave_lo + proof['code_bytes']]
    replay = {
        'p0_vnop_read_entry': dict(word='e3030091', resume=0xfffffff007466b14),
        'p0_join_point': dict(word='f40300aa', resume=0xfffffff007466b28),
    }
    hook_branches = {}
    for name, spec in replay.items():
        start = sy[name] - trace.START
        seg = cave[start:start + 512]
        pos = seg.find(bytes.fromhex(spec['word']))
        check('hook_%s_replays_native_word' % name, pos >= 0 and pos % 4 == 0,
              dict(offset=pos))
        br = []
        if pos >= 0:
            following = int.from_bytes(seg[pos + 4:pos + 8], 'little')
            kind, target = decode_branch(following, sy[name] + pos + 4)
            br.append(dict(kind=kind, target=hex(target)))
            check('hook_%s_resume_target' % name, kind == 'b' and target == spec['resume'],
                  dict(kind=kind, target=hex(target), expected=hex(spec['resume'])))
        hook_branches[name] = br
        # 恢复段在重放之前
        body = SOURCE.read_text(encoding='utf-8').split('.global ' + name, 1)[1]
        before_replay = body.split(
            '    mov x3,sp' if name == 'p0_vnop_read_entry' else '    mov x20,x0', 1)[0]
        check('hook_%s_stack_balanced_before_replay' % name,
              'add sp,sp,#256' in before_replay, '恢复段位于重放之前')

    # 8) 相对 P0 差异范围
    cave_hi = cave_lo + delta['cave_range']['bytes']
    declared = {p['file_offset'] for p in sites}
    actual = [pos for pos in range(0, min(len(p0_kernel), len(kernel)), 4)
              if not (cave_lo <= pos < cave_hi) and p0_kernel[pos:pos + 4] != kernel[pos:pos + 4]]
    check('p0_outside_cave_diff_subset_of_declared', set(actual) <= declared,
          dict(actual=[hex(x) for x in sorted(actual)], declared=[hex(x) for x in sorted(declared)]))
    check('p0_outside_cave_diff_count', len(actual) == delta['p0_outside_cave_diff_words'], len(actual))

    # 9) FAT 回读 / ADT / nonce
    for name, path in (('unixnu.toml', None), ('kernel.macho', WORK / 'kernel.macho'),
                       ('kernel.macho.adt', WORK / 'launch/kernel.macho.adt')):
        rb = WORK / 'fat' / ('readback-' + name)
        check('fat_readback_%s' % name.replace('.', '_'),
              rb.exists() and (path is None or rb.read_bytes() == path.read_bytes()), str(rb))
    fd = transport.ARTIFACT / 'build/FV/SILICIUM_UEFI.fd'
    shim = transport.ARTIFACT / 'shim/shim.bin'
    adt = (WORK / 'launch/kernel.macho.adt').read_bytes()
    nonce = (WORK / 'launch/nonce.bin').read_bytes()
    manifest = (WORK / 'launch/launch-manifest.json').read_bytes()
    try:
        validation = context.validate(adt, WORK / 'kernel.macho', fd, shim,
                                      nonce=nonce, manifest_bytes=manifest)
        check('adt_nonce_validate', True, validation['adt_sha256'])
    except Exception as exc:
        check('adt_nonce_validate', False, repr(exc))
        validation = dict(error=repr(exc))
    check('nonce_is_32_bytes', len(nonce) == 32, len(nonce))
    check('image_bytes_matches_build', len(image) == build['image_bytes'], len(image))

    # ---- 字段语义表 ----
    base_by_n = {f['field_id_decimal']: f for f in p0_sem['fields']}
    fields = []
    for n in sorted(writers):
        label = 'FB%02X' % ((0xFB00 + n) & 0xFF)
        w = writers[n]
        if n in NEW_FIELDS:
            meta = NEW_FIELDS[n]
            entry = dict(field_id_decimal=n, screen_label=label,
                         id_word='0x%04x' % (0xFB00 + n), encoding=FORMULA,
                         name=meta['name'], kind=meta['kind'], meaning=meta['meaning'],
                         value_source=meta['value_source'], expected=meta['expected'],
                         writers=w, writer_count=len(w),
                         unobserved_default=meta['unobserved_default'],
                         default_is_ffffffff=False,
                         visibility_evidence='CHECK10 实机 368 帧作护栏出现并持续到末帧')
        else:
            entry = dict(base_by_n[n])
            entry['writers'] = w
            entry['writer_count'] = len(w)
            entry['encoding'] = FORMULA
            entry['id_word'] = '0x%04x' % (0xFB00 + n)
            entry['screen_label'] = label
        fields.append(entry)
        check('field_%d_encoding_formula' % n,
              entry['id_word'] == '0x%04x' % (0xFB00 + n) and entry['screen_label'] == label,
              dict(id=entry['id_word'], screen=label))

    decision_matrix = [
        dict(FB03='出现', FB06='出现', FB07='任意',
             verdict='VNOP_READ 已调用且返回；后端完成链正常，卡点下移到 exec 续接 / EL0。'),
        dict(FB03='出现', FB06='空白', FB07='00000000',
             verdict='VNOP_READ 已进入但未返回（后端/完成链卡住）；首要嫌疑证实，'
                     '下一步查 APFS/decmpfs/UPL/IOKit 完成事件。'),
        dict(FB03='空白', FB06='出现', FB07='非零',
             verdict='MAC-read 拒绝直跳汇合点，VNOP_READ 未执行；按 FB07 错误码定位 AMFI。'),
        dict(FB03='空白', FB06='出现', FB07='00000000',
             verdict='从 write/swap 或其它直跳路径到汇合点，VNOP_READ 未执行；需回查观测挂点覆盖。'),
        dict(FB03='空白', FB06='空白', FB07='行空白',
             verdict='未到 0x7466B10 且 MAC-read 分派点也未到达；'
                     '含 _vn_rdwr 入口 len<0 早退，与文件系统/存储栈无关。'),
        dict(guard='10 个大阶段全空白 + trace_1 初始化字段也空白',
             verdict='framebuffer 通道或入口未执行，本轮全部读数无效。'),
    ]
    semantics = dict(p0_sem)
    semantics.update(
        schema='Nuwa.FieldSemantics.v2', candidate='P0-VNOP-PAIR r2',
        generated_by='scripts/qualify-p0-vnop-pair-20261105.py',
        generated_at=datetime.now(timezone.utc).isoformat(),
        encoding_formula=FORMULA, generated_by_formula=True,
        image_sha256=build['image_sha256'], kernel_sha256=build['kernel_sha256'],
        observer_source=str(SOURCE.relative_to(R)), observer_source_sha256=sha_p(SOURCE),
        builder_source='scripts/build-p0-vnop-pair-20261105.py',
        builder_sha256=sha_p(R / 'scripts/build-p0-vnop-pair-20261105.py'),
        initialised_ids_decimal=sorted(initial),
        not_drawn_ids_decimal=[21, 22, 23],
        not_drawn_note='CHECK8/10 的 c8_read_return / c10_vn_rdwr_ret 已退役；'
                       'FB03/FB06 在本候选被 P0 r2 配对观测重新使用。',
        fields=fields, decision_matrix=decision_matrix,
        field_id_conflict='无：FB03/FB06/FB07 各 1 个写入源；编号由公式计算，不手工映射。',
        channel_evidence='FB03 入口 magic 0x56504E52 兼作通道有效护栏；'
                         'FB03/FB06 行位在 CHECK10 实机出现过（0000C8A5 / 5A5A5A5A），'
                         '可见性已有实机佐证。若 FB03 空白而 10 个大阶段出现，'
                         '须先核对行位与通道，再解释后端。',
        new_observation_note='本候选相对 P0 只新增 2 个挂点（0x7466B10 / 0x7466B24）与 '
                             '2 个 hook；cave 外其余字节与 P0 逐字节一致。',
        limitations=['静态源码 + 实际交付内核机器码核对；不是实机读数。',
                     'FB03/FB06 的判读依赖「入口/汇合点配对」，单点不得解释成 VNOP_READ 执行过。'])
    sem_path = REPORT / 'field-semantics.json'
    sem_path.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sem_sha = sha_p(sem_path)

    md = ['# P0-VNOP-PAIR r2 字段语义表', '',
          '生成：`scripts/qualify-p0-vnop-pair-20261105.py` · 源码 SHA `%s` · 语义表 SHA `%s`' % (
              sha_p(SOURCE)[:16], sem_sha[:16]),
          '', '编码公式：`%s`' % FORMULA, '',
          '未绘制编号：FB15 / FB16 / FB17（CHECK8/10 退役观测）。FB03 / FB06 在本候选被重新使用。',
          '', '| N | 屏幕 | 字段 | 类型 | 写入源数 | 值来源 | 未观测默认值 | 含义 |',
          '|---:|---|---|---|---:|---|---|---|']
    for f in fields:
        md.append('| %d | %s | %s | %s | %d | %s | %s | %s |' % (
            f['field_id_decimal'], f['screen_label'], f['name'], f['kind'], f['writer_count'],
            f['value_source'].replace('|', '/'), f['unobserved_default'].replace('|', '/'),
            f['meaning'].replace('|', '/')))
    md += ['', '## 全部写入源（逐行）', '']
    for f in fields:
        for w in f['writers']:
            md.append('- %s (N=%d): `:%d` in `%s`, w1 = `%s`' % (
                f['screen_label'], f['field_id_decimal'], w['line'], w['hook'], w['w1']))
    md += ['', '## 判读矩阵', '']
    for d in decision_matrix:
        key = '/'.join('%s=%s' % (k, v) for k, v in d.items() if k != 'verdict')
        md.append('- %s → %s' % (key, d['verdict']))
    (REPORT / 'FIELD-SEMANTICS.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

    regression = dict(schema='Nuwa.P0VnopPairRegression.v1', candidate='P0-VNOP-PAIR r2',
                      kernel_sha256=sha(kernel), independent_kernel_sha256=sha(independent),
                      image_sha256=sha(image), checks=checks,
                      passed=all(c['passed'] for c in checks), case_count=len(checks),
                      new_hook_branches=hook_branches, stage_hooks=stage_detail,
                      adt_validation=validation)
    (REPORT / 'regression.json').write_text(json.dumps(regression, ensure_ascii=False, indent=2) + '\n',
                                            encoding='utf-8')

    qualification = dict(
        schema='Nuwa.OfflineQualification.v1', candidate='P0-VNOP-PAIR r2',
        generated_at=datetime.now(timezone.utc).isoformat(),
        status='OFFLINE_QUALIFIED_AT_CONFIRMATION_GATE',
        kernel_sha256=sha(kernel), image_sha256=sha(image),
        image_path=str(WORK / 'boot-p0-vnop-pair-20261105-r2.img'),
        parent_candidate=dict(candidate='P0-NATIVE-RESTORE r1',
                              kernel_sha256=sha(p0_kernel)),
        field_semantics_sha256=sem_sha, regression_sha256=sha_p(REPORT / 'regression.json'),
        inputs=dict(
            build_json=sha_p(WORK / 'build.json'), kernel_proof=sha_p(WORK / 'kernel-proof.json'),
            observer_source=sha_p(SOURCE), builder=sha_p(R / 'scripts/build-p0-vnop-pair-20261105.py'),
            source_generator=sha_p(R / 'scripts/gen-p0-vnop-pair-source-20261105.py'),
            p0_field_semantics=sha_p(P0_SEM),
            patch_triage=sha_p(TRIAGE), native_earlysec=sha_p(EARLY)),
        regression=dict(case_count=len(checks), passed=all(c['passed'] for c in checks)),
        three_class_inventory=proof['p0_delta']['three_class_inventory'],
        device_gate=dict(
            status='STOPPED', reason='交接文档要求停在实机确认门；用户本轮只授权加观测与新镜像',
            required_before_boot=['新鲜 nuwa/A/TWRP 与 fastboot 目标预检',
                                  '持续录像与实体键恢复条件确认',
                                  '候选镜像 SHA 与未消费状态核验'],
            candidate_consumed=False, device_actions_performed=False,
            partitions_written=False, slot_changed=False, git_committed_or_pushed=False),
        limitations=[
            '离线合格 ≠ 实机通过；FB03/FB06/FB07 与 10 个大阶段均需实机录像逐帧判读。',
            'kernel.macho / fat/unixnu.toml / 内嵌内核字节逐字节可复现；'
            'kernel.macho.adt 含一次性 nonce 且 FAT 含时间戳，boot 镜像每构建必不同，资格绑定精确 SHA。',
            '新观测只加到 2 个挂点；不改变原生错误分支、安全模型或停机门。',
            'FB03/FB06 是配对观测，单点读数不得解释为「VNOP_READ 已执行」。',
        ])
    (REPORT / 'qualification.json').write_text(
        json.dumps(qualification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    readme = ['# P0-VNOP-PAIR r2 · 离线资格', '',
              '2026-11-05 · 在 P0 原生恢复候选上加 VNOP_READ 入口/汇合点配对观测。', '',
              '## 结果', '',
              '- 内核 SHA `%s`' % sha(kernel),
              '- 镜像 SHA `%s`' % sha(image),
              '- 独立重建逐字节一致；回归 %d 项全通过。' % len(checks),
              '- 相对 P0 内核，cave 外差异仅 %d 个字（两个新挂点）。' % len(actual),
              '- 字段语义表 `field-semantics.json` / `FIELD-SEMANTICS.md`，SHA `%s`。' % sem_sha[:16], '',
              '## 新增观测', '']
    readme += ['- `%s` → `%s`（`%s`）：%s' % (s['address'], s['field'], s['symbol'], s['role'])
               for s in sites]
    readme += ['', '字段复用 FB03 / FB06：CHECK10 实机作护栏出现过，行位可见性已验证；'
                   'P0 源码中这两个编号无写入源，无字段编号冲突。FB07 保持 P0 的 MAC-read 标记。', '',
               '## 判读矩阵', '']
    for d in decision_matrix:
        key = '/'.join('%s=%s' % (k, v) for k, v in d.items() if k != 'verdict')
        readme.append('- %s → %s' % (key, d['verdict']))
    readme += ['', '## 实机确认门', '',
               '停在门内。上机前须：新鲜 nuwa/A/TWRP 与 fastboot 目标预检、持续录像与实体键恢复条件确认、'
               '候选镜像 SHA 与未消费状态核验。本轮未操作设备、未写分区、未改槽、未提交/推送。', '',
               '## 边界', '']
    readme += ['- ' + x for x in qualification['limitations']]
    (REPORT / 'README.md').write_text('\n'.join(readme) + '\n', encoding='utf-8')

    print('checks', len(checks), 'passed', all(c['passed'] for c in checks))
    print('kernel', sha(kernel))
    print('image ', sha(image))
    print('field semantics', sem_sha)
    print('report', REPORT.relative_to(R))


if __name__ == '__main__':
    main()
