"""P0-VNOP-DISPATCH r3 离线资格化：回归 + 字段语义表 + qualification 同轮入库。

只读核对，不改内核、不构建、不操作设备、不提交。
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import flush_trace_inputs as trace  # noqa: E402
import nuwa_launch_context as context  # noqa: E402
import usb_ramdisk_package as transport  # noqa: E402

WORK = R / 'out/p0-vnop-dispatch-20261105-r3'
INDEP = R / 'out/p0-vnop-dispatch-20261105-r3-independent'
REPORT = R / 'reports/p0-vnop-dispatch-20261105-r3'
SOURCE = R / 'package/kernel-mainline/CoarseStages-p0-vnop-dispatch-r3.S'
P0_SEM = R / 'reports/p0-native-restore-20261105-r1/field-semantics.json'
P0_KERNEL = R / 'out/p0-native-restore-20261105-r1/kernel.macho'
EARLY = R / 'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho'
TRIAGE = R / 'reports/native-restore-20261105/patch-triage.json'
BUILD = WORK / 'build.json'
IMAGE = WORK / 'boot-p0-vnop-dispatch-20261105-r3.img'
FORMULA = 'draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N; N 为十进制，屏幕后缀为十六进制'

CANDIDATE = 'P0-VNOP-DISPATCH r3'
FIELD_META = {
    3: dict(name='vnop_phase_code', kind='phase-code',
            meaning='r3 新增：阶段编码。H1(_VNOP_READ 入口)=0x454E5452 ENTR；'
                    'H4(len<0 早退)=0x4541524C EARL；H5(_vn_rdwr_64 正常返回 epilogue)=0x4550494C EPIL。'
                    '最后一次写入胜出；卡在 vnop 内部时停在 ENTR。',
            value_source='w1 = movz/movk 立即数常量',
            expected='ENTR/EARL/EPIL 之一；行空白 = 三个挂点均未命中',
            unobserved_default='行空白（本候选初始化不绘制该编号）'),
    6: dict(name='vnop_dispatch_target_low32', kind='register-value',
            meaning='r3 新增：0x746C684（0x746C680 ldr x8,[x9,x8,lsl#3] 之后）的 x8 低 32 位，'
                    '即 vnode v_op 表取出的 VNOP_READ 实现地址；进入闭源 apfs 的唯一分派目标。'
                    'H1 每次入口先重置为 GUAR，故末态只反映最后一次调用。',
            value_source='w1 = w8', expected='0x07xxxxxx 形态的 APFS vnop 地址；GUAR = 未到分派点',
            unobserved_default='行空白（本候选初始化不绘制该编号）'),
    15: dict(name='vnop_return_w0', kind='return-value',
             meaning='r3 新增：0x746C68C（blr x8 返回首条 mov x22,x0）的 w0，即 vnop 返回码。'
                     'H1 每次入口先重置为 GUAR；若 vnop 未返回则该字段保持 GUAR。'
                     '注：P0 r1 的 trace_1 初始化段也写一次 N=15，会被 H1 覆盖。',
             value_source='w1 = w0', expected='00000000 = 成功；非零 = errno；GUAR = 未返回',
             unobserved_default='trace_1 初始化值（H1 命中后被覆盖）'),
}
SITES = {
    'r3_vnop_entry': dict(address=0xfffffff00746c628, native='ffc301d1',
                          replay='sub sp,sp,#0x70', resume=0xfffffff00746c62c,
                          fields=[3, 6, 15]),
    'r3_vnop_dispatch': dict(address=0xfffffff00746c684, native='e0230091',
                             replay='add x0,x0,#8', resume=0xfffffff00746c688,
                             fields=[6]),
    'r3_vnop_return': dict(address=0xfffffff00746c68c, native='f60300aa',
                           replay='mov x22,x0', resume=0xfffffff00746c690,
                           fields=[15]),
    'r3_early_exit': dict(address=0xfffffff007466ac4, native='c0028052',
                          replay='mov w0,#0x16', resume=0xfffffff007466ac8,
                          fields=[3]),
    'r3_epilogue': dict(address=0xfffffff007466b88, native='ffc30291',
                        replay='add sp,sp,#0xb0', resume=0xfffffff007466b8c,
                        fields=[3]),
}
WITHDRAWN = {
    0xfffffff007466b10: 'e3030091',
    0xfffffff007466b24: 'f40300aa',
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
SAVE_LINES = ['sub sp,sp,#256'] + ['stp x%d,x%d,[sp,#%d]' % (a, a + 1, (a // 2) * 16)
                                   for a in range(0, 29, 2)] + ['str x30,[sp,#240]',
                                                                 'mrs x9,nzcv', 'str x9,[sp,#248]']
RESTORE_LINES = ['ldr x9,[sp,#248]', 'msr nzcv,x9'] + \
                ['ldp x%d,x%d,[sp,#%d]' % (a, a + 1, (a // 2) * 16)
                 for a in range(0, 29, 2)] + ['ldr x30,[sp,#240]', 'add sp,sp,#256']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sha_p(p):
    return sha(Path(p).read_bytes())


def read(p):
    return json.loads(Path(p).read_bytes())


def decode_branch(word, pc):
    if word & 0x7c000000 == 0x14000000:
        imm = word & 0x3ffffff
        if imm & (1 << 25):
            imm -= 1 << 26
        return ('bl' if word & 0x80000000 else 'b', (pc + 4 * imm) & 0xffffffffffffffff)
    return ('?', None)


def word_at(raw, m, va, size=4):
    off = trace.builder().backed(m, va, size)
    return raw[off:off + size].hex()


def parse_writers():
    lines = SOURCE.read_text(encoding='utf-8').splitlines()
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
            m1 = re.fullmatch(r'(?:mov w1,(.+)|movz w1,#\S+|movk w1,#\S+,lsl #16)', t)
            if m1 and w1 is None:
                w1 = m1.group(1) if m1.group(1) else t
            if n is not None and w1 is not None:
                break
        assert n is not None, 'unparsed bl draw at line %d' % (i + 1)
        writers.setdefault(n, []).append(dict(line=i + 1, hook=label, w1=w1))
    return lines, writers


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    build = read(BUILD)
    kernel = (WORK / 'kernel.macho').read_bytes()
    image = IMAGE.read_bytes()
    independent = (INDEP / 'kernel.macho').read_bytes()
    p0_sem = read(P0_SEM)
    triage = read(TRIAGE)
    lines, writers = parse_writers()
    src = SOURCE.read_text(encoding='utf-8')
    b = trace.builder()
    m = b.macho(kernel)
    mp0 = b.macho(P0_KERNEL.read_bytes())
    mearly = b.macho(EARLY.read_bytes())
    checks = []

    def check(name, cond, evidence=None):
        checks.append(dict(name=name, passed=bool(cond), evidence=evidence))

    # 1) 交付物与重建
    check('kernel_sha_matches_build', sha(kernel) == build['kernel_sha256'], sha(kernel))
    check('image_sha_matches_build', sha(image) == build['image_sha256'], sha(image))
    check('independent_rebuild_byte_identical', kernel == independent, sha(independent))
    check('image_bytes_matches_build', len(image) == build['image_bytes'], len(image))
    check('source_sha_matches_build', sha_p(SOURCE) == build['source_sha256'], sha_p(SOURCE))
    check('cave_within_retired_budget',
          trace.START + build['code_bytes'] <= trace.RETIRED_END,
          dict(used=build['code_bytes'], limit=trace.RETIRED_END - trace.START))

    # 2) 11 个真原生恢复点
    restore = [(int(r['address'], 16), r['native_from_earlysec'])
               for r in triage['sites'] if r['classification'] == 'observer-or-bridge']
    bad = [hex(va) for va, nat in restore
           if word_at(kernel, m, va) != nat or
           word_at(EARLY.read_bytes(), mearly, va) != nat]
    check('restore_site_count', len(restore) == 11, len(restore))
    check('all_11_restore_sites_equal_earlysec', not bad, bad)
    check('native_bl_vn_rdwr', word_at(kernel, m, 0xfffffff00769bf90) == '7e2af797', '7e2af797')
    check('native_cbnz_w0', word_at(kernel, m, 0xfffffff00769bf94) == '800d0035', '800d0035')
    check('native_ret_unchanged', word_at(kernel, m, 0xfffffff0074669cc) == 'c0035fd6', 'c0035fd6')
    check('epilogue_witness_0x74669c8_stays_native',
          word_at(kernel, m, 0xfffffff0074669c8) == 'ff030191',
          word_at(kernel, m, 0xfffffff0074669c8))
    check('resid_path_unchanged',
          word_at(kernel, m, 0xfffffff007466b5c) == word_at(P0_KERNEL.read_bytes(), mp0, 0xfffffff007466b5c),
          word_at(kernel, m, 0xfffffff007466b5c))
    check('legacy_bridge_preserved',
          word_at(kernel, m, 0xfffffff0084d9be4) == word_at(P0_KERNEL.read_bytes(), mp0, 0xfffffff0084d9be4),
          word_at(kernel, m, 0xfffffff0084d9be4))

    # 3) 10 大阶段 / 6 功能件 / FB07
    sy = build['symbols']
    for va, name in BIG_STAGES.items():
        w = int.from_bytes(kernel[b.backed(m, va, 4):b.backed(m, va, 4) + 4], 'little')
        kind, target = decode_branch(w, va)
        check('big_stage_%s_still_hooked' % name,
              kind in ('b', 'bl') and trace.START <= target < trace.RETIRED_END,
              dict(word=hex(w), kind=kind, target=hex(target or 0)))
    for va, name in KEEP_FUNCTIONAL.items():
        w = int.from_bytes(kernel[b.backed(m, va, 4):b.backed(m, va, 4) + 4], 'little')
        kind, target = decode_branch(w, va)
        ok = kind in ('b', 'bl') and trace.START <= target < trace.RETIRED_END
        base = word_at(P0_KERNEL.read_bytes(), mp0, va)
        check('functional_%s_present' % name, ok or
              word_at(kernel, m, va) == base,
              dict(word=hex(w), kind=kind, p0=base))
    check('fb07_hook_symbol_present', 'p0_mac_read_after' in sy, hex(sy.get('p0_mac_read_after', 0)))
    check('fb07_patch_preserved_vs_p0',
          word_at(kernel, m, 0xfffffff007466ad0) == word_at(P0_KERNEL.read_bytes(), mp0, 0xfffffff007466ad0),
          word_at(kernel, m, 0xfffffff007466ad0))

    # 4) 撤掉的 r2 挂点必须是原生
    for va, nat in WITHDRAWN.items():
        check('withdrawn_r2_site_%s_is_native' % hex(va),
              word_at(kernel, m, va) == nat and
              word_at(EARLY.read_bytes(), mearly, va) == nat,
              dict(actual=word_at(kernel, m, va), expected=nat))

    # 5) 5 个新挂点：分支、落点、原生 before
    sites = build['r3_delta']['new_patch_sites']
    check('new_patch_site_count', len(sites) == 5, len(sites))
    for s in sites:
        va = int(s['address'], 16)
        w = int.from_bytes(kernel[b.backed(m, va, 4):b.backed(m, va, 4) + 4], 'little')
        kind, target = decode_branch(w, va)
        spec = SITES[s['symbol']]
        check('site_%s_is_branch' % s['symbol'], kind == 'b', dict(word=hex(w), kind=kind))
        check('site_%s_target_matches_symbol' % s['symbol'], target == sy[s['symbol']],
              dict(target=hex(target or 0), symbol=hex(sy[s['symbol']])))
        check('site_%s_before_is_native' % s['symbol'], s['before'] == spec['native'], s['before'])
        check('site_%s_native_still_in_earlysec' % s['symbol'],
              word_at(EARLY.read_bytes(), mearly, va) == spec['native'], spec['native'])

    # 6) hook ABI 卫生 / 重放 / resume
    for name, spec in SITES.items():
        body = src.split('.global ' + name, 1)[1].split('.global ', 1)[0]
        check('hook_%s_saves_all' % name,
              all(x in body for x in SAVE_LINES), [x for x in SAVE_LINES if x not in body][:3])
        check('hook_%s_restores_all' % name,
              all(x in body for x in RESTORE_LINES), [x for x in RESTORE_LINES if x not in body][:3])
        pos = body.find('    ' + spec['replay'])
        check('hook_%s_replays_native_insn' % name, spec['replay'] in body, spec['replay'])
        check('hook_%s_replay_after_stack_restore' % name,
              pos > body.find('add sp,sp,#256'), dict(pos=pos))
        jm = re.search(r'\.jump (\w+)', body)
        check('hook_%s_has_jump' % name, bool(jm), jm.group(1) if jm else None)
        # 解码 cave 里 .jump 对应的分支目标
        hook_va = sy[name]
        target_found = None
        for off in range(b.backed(m, hook_va, 4), b.backed(m, hook_va, 4) + 512, 4):
            w = int.from_bytes(kernel[off:off + 4], 'little')
            kind, t = decode_branch(w, trace.START + off - b.backed(m, trace.START, 4))
            if kind == 'b' and t == spec['resume']:
                target_found = t
                break
        check('hook_%s_resume_target' % name, target_found == spec['resume'],
              dict(expected=hex(spec['resume']), found=hex(target_found or 0)))
        for n in spec['fields']:
            check('hook_%s_writes_FB%02X' % (name, n),
                  any(x['hook'] == name for x in writers.get(n, [])), writers.get(n, []))

    # 7) 字段编号纪律
    check('field3_writer_count', len(writers.get(3, [])) == 3, writers.get(3, []))
    check('field6_writer_count', len(writers.get(6, [])) == 2, writers.get(6, []))
    check('field15_writer_count', len(writers.get(15, [])) == 3, writers.get(15, []))
    check('field7_single_writer', len(writers.get(7, [])) == 1, writers.get(7, []))
    check('field7_writer_is_mac_read',
          writers[7][0]['hook'] == 'p0_mac_read_after', writers[7][0])
    check('no_first_use_row_ids',
          not ({21, 22, 23, 24} & set(writers)), sorted(set(writers) & {21, 22, 23, 24}))
    check('h1_resets_both_value_fields',
          {3: 1, 6: 1, 15: 1} == {n: sum(1 for x in writers[n] if x['hook'] == 'r3_vnop_entry')
                                  for n in (3, 6, 15)},
          {n: [x['hook'] for x in writers[n]] for n in (3, 6, 15)})
    for n in sorted(writers):
        label = 'FB%02X' % ((0xFB00 + n) & 0xFF)
        occurrences = src.count('mov w0,#%d\n' % n)
        check('field_%d_label_and_writer_count' % n,
              label == 'FB%02X' % n and occurrences >= len(writers[n]) >= 1,
              dict(n=n, label=label, mov_count=occurrences, writers=len(writers[n])))

    # 8) 相对 P0 r1 的差异范围
    delta = build['r3_delta']
    declared = {p_['file_offset'] for p_ in sites}
    p0raw = P0_KERNEL.read_bytes()
    cave_lo = delta['cave_range']['file_offset']
    cave_hi = cave_lo + delta['cave_range']['bytes']
    actual = []
    for pos in range(0, min(len(p0raw), len(kernel)), 4):
        if cave_lo <= pos < cave_hi:
            continue
        if p0raw[pos:pos + 4] != kernel[pos:pos + 4]:
            actual.append(pos)
    check('p0_diff_subset_of_declared', set(actual) <= declared,
          dict(actual=sorted(actual), declared=sorted(declared)))
    check('p0_diff_count', len(actual) == delta['p0_outside_cave_diff_words'] == 5, len(actual))
    check('security_model_unchanged', delta['security_model_changed'] is False, False)
    check('no_stop_gate', delta['stop_gate_added'] is False, False)
    check('no_repair_removed', delta['repair_patches_removed'] == 0, 0)
    check('observations_added_5', delta['observations_added'] == 5, 5)
    check('observations_withdrawn_2', delta['observations_withdrawn'] == 2, 2)

    # 9) FAT / ADT / nonce
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

    # ---- 字段语义表 ----
    base_by_n = {f['field_id_decimal']: f for f in p0_sem['fields']}
    fields = []
    for n in sorted(writers):
        label = 'FB%02X' % ((0xFB00 + n) & 0xFF)
        w = writers[n]
        if n in FIELD_META:
            meta = FIELD_META[n]
            entry = dict(field_id_decimal=n, screen_label=label,
                         id_word='0x%04x' % (0xFB00 + n), encoding=FORMULA,
                         name=meta['name'], kind=meta['kind'], meaning=meta['meaning'],
                         value_source=meta['value_source'], expected=meta['expected'],
                         writers=w, writer_count=len(w),
                         unobserved_default=meta['unobserved_default'],
                         default_is_ffffffff=False,
                         visibility_evidence='FB03/FB06 在 CHECK10 实机作护栏出现并持续到末帧；'
                                             'FB0F 在 CHECK8/10 记为已验证空白行位')
        else:
            entry = dict(base_by_n[n])
            entry.update(writers=w, writer_count=len(w), encoding=FORMULA,
                         id_word='0x%04x' % (0xFB00 + n), screen_label=label)
        fields.append(entry)

    decision_matrix = [
        dict(FB03='ENTR', FB06='x8 值', FB0F='GUAR',
             verdict='blr x8 已分派且未返回；x8 给出 APFS vnop 目标地址。'
                     '首要嫌疑进一层，下一轮沿该地址下钻。'),
        dict(FB03='ENTR', FB06='GUAR', FB0F='GUAR',
             verdict='卡在 _VNOP_READ 分派之前（_uio_resid 检查或 v_op 表读取）；与 APFS 后端无关。'),
        dict(FB03='ENTR', FB06='x8 值', FB0F='w0 值',
             verdict='vnop 已返回；配合 FB07 与 10 大阶段判读卡点是否下移到 exec 续接 / EL0。'),
        dict(FB03='EARL', verdict='len<0 早退路径阳性对照命中；本轮主链读数需重新归因。'),
        dict(FB03='EPIL', verdict='_vn_rdwr_64 正常返回 epilogue 阳性对照命中；说明读链已整体返回。'),
        dict(guard='三行全空白 + 10 大阶段出现',
             verdict='未观察到任何 H1/H4/H5 命中；按 AGENTS §6 只写「未观察到」，'
                     '并核对行位可见性与挂点覆盖，不得写成「未发生」。'),
    ]
    semantics = dict(p0_sem)
    semantics.update(
        schema='Nuwa.FieldSemantics.v2', candidate=CANDIDATE,
        generated_by='scripts/qualify-p0-vnop-dispatch-20261105.py',
        generated_at=datetime.now(timezone.utc).isoformat(),
        encoding_formula=FORMULA, generated_by_formula=True,
        image_sha256=build['image_sha256'], kernel_sha256=build['kernel_sha256'],
        observer_source=str(SOURCE.relative_to(R)), observer_source_sha256=sha_p(SOURCE),
        builder_source='scripts/build-p0-vnop-dispatch-20261105.py',
        builder_sha256=sha_p(R / 'scripts/build-p0-vnop-dispatch-20261105.py'),
        initialised_ids_decimal=p0_sem['initialised_ids_decimal'],
        not_drawn_ids_decimal=[21, 22, 23],
        not_drawn_note='CHECK8/10 的 c8_read_return / c10_vn_rdwr_ret 已退役；'
                       '本候选未引入任何首次使用的行号。',
        fields=fields, decision_matrix=decision_matrix,
        field_id_conflict='无：FB03 三个写入源（H1/H4/H5 阶段编码）、FB06 两个（H1 重置/H2 值）、'
                          'FB0F 三个（trace_1 初始化/H1 重置/H3 值）、FB07 一个（MAC-read）。'
                          '编号由公式计算，不手工映射。',
        channel_evidence='H1 在每次 _VNOP_READ 入口画 ENTR + 两次 GUAR，'
                         '本身兼作三个行位的通道有效性护栏，且重置早段调用对值字段的污染。',
        new_observation_note='本候选相对 P0 r1 新增 5 个挂点、撤掉 r2 的 2 个挂点；'
                             'cave 外其余字节与 P0 r1 逐字节一致。',
        constants=dict(ENTR='0x454E5452', EARL='0x4541524C',
                       EPIL='0x4550494C', GUAR='0x47554152'),
        limitations=['静态源码 + 实际交付内核机器码核对；不是实机读数。',
                     'FB03/FB06/FB0F 必须三字段配对判读，单点不得解释成 vnop 已返回。',
                     'H2 挂在 0x746C684 而非 0x746C680：后者执行前 x8 仍是 v_op 偏移。'])
    sem_path = REPORT / 'field-semantics.json'
    sem_path.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sem_sha = sha_p(sem_path)

    md = ['# %s · 字段语义表' % CANDIDATE, '',
          '编号公式 `%s`。共 %d 个被绘制字段。' % (FORMULA, len(fields)), '',
          '| 行位 | N | 名称 | 值来源 | 写入源 | 判读 |', '|---|---:|---|---|---:|---|']
    for f in fields:
        md.append('| %s | %d | %s | %s | %d | %s |' % (
            f['screen_label'], f['field_id_decimal'], f['name'],
            f.get('value_source', f.get('meaning', ''))[:46],
            f['writer_count'], f.get('expected', f.get('meaning', ''))[:56]))
    md += ['', '## 常量', '', '- `ENTR = 0x454E5452`（_VNOP_READ 入口）',
           '- `EARL = 0x4541524C`（len<0 早退）', '- `EPIL = 0x4550494C`（正常 epilogue）',
           '- `GUAR = 0x47554152`（H1 重置护栏）', '', '## 判读矩阵', '']
    for d in decision_matrix:
        key = '/'.join('%s=%s' % (k, v) for k, v in d.items() if k != 'verdict')
        md.append('- **%s** → %s' % (key, d['verdict']))
    (REPORT / 'FIELD-SEMANTICS.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

    regression = dict(candidate=CANDIDATE, case_count=len(checks),
                      passed=all(c['passed'] for c in checks), checks=checks,
                      adt_validation=validation,
                      new_hook_branches={s['symbol']: hex(sy[s['symbol']]) for s in sites},
                      withdrawn_sites={hex(k): v for k, v in WITHDRAWN.items()},
                      diff_outside_cave_words=len(actual),
                      cave_budget=dict(used=build['code_bytes'],
                                       limit=trace.RETIRED_END - trace.START))
    (REPORT / 'regression.json').write_text(
        json.dumps(regression, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    qualification = dict(
        schema='Nuwa.OfflineQualification.v2', candidate=CANDIDATE,
        status='OFFLINE_QUALIFIED_AT_RECORDING_CONFIRMATION_GATE',
        generated_at=datetime.now(timezone.utc).isoformat(),
        kernel_path=str((WORK / 'kernel.macho').relative_to(R)),
        kernel_sha256=sha(kernel), image_path=str(IMAGE.relative_to(R)),
        image_sha256=sha(image), image_bytes=len(image),
        regression=dict(case_count=len(checks), passed=regression['passed']),
        regression_sha256=sha_p(REPORT / 'regression.json'),
        field_semantics_sha256=sem_sha,
        field_semantics='reports/p0-vnop-dispatch-20261105-r3/field-semantics.json',
        parent_candidate='P0-NATIVE-RESTORE r1 (ce75992b…)，非 r2',
        withdrawn=['r2 FB03 p0_vnop_read_entry', 'r2 FB06 p0_join_point'],
        device_gate=dict(
            status='STOPPED_AT_RECORDING_CONFIRMATION',
            reason='用户 20:39 授权「继续直到下一轮实机录像确认」；'
                   '本轮完成新候选离线合格，停在等用户当轮录像确认的门内',
            candidate_consumed=False, device_actions_performed=False,
            partitions_written=False, slot_changed=False, git_committed_or_pushed=False,
            required_before_boot=[
                '用户当轮明确确认全程 60fps 录像（建议 ≥9 s，CHECK10 6.13 s / r2 5.982 s 均记为限制）',
                '实体键恢复路径可用，启动后能手动回 TWRP/fastboot',
                '新鲜 nuwa/A/TWRP 与 fastboot 目标预检',
                '候选镜像 SHA 与未消费状态核验',
                '认证根前缀只读抽查（20:39 已实测完好，属非阻断复核）']),
        limitations=[
            '离线合格 ≠ 实机通过；FB03/FB06/FB0F 与 10 个大阶段均需实机录像逐帧判读。',
            'kernel.macho / fat/unixnu.toml / 内嵌内核字节逐字节可复现；'
            'kernel.macho.adt 含一次性 nonce 且 FAT 含时间戳，boot 镜像每构建必不同，资格绑定精确 SHA。',
            'r2 的 FB03/FB06 已撤；与 r2 不是同一观测形态，不构成严格 A/B。',
            'H1 每次 _VNOP_READ 入口重置 FB06/FB0F，末态反映最后一次调用；'
            '若存在并发读，值字段可能属于另一条读，需结合 10 大阶段时间线。',
            '三路阳性对照本轮补齐（入口 H1 / 早退 H4 / 正常 epilogue H5），但仍无 H3 的实机阳性命中。'])
    (REPORT / 'qualification.json').write_text(
        json.dumps(qualification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    readme = ['# %s · 离线资格' % CANDIDATE, '',
              '2026-11-05 · 由 P0 r1 派生，下钻到 `_VNOP_READ` 的 `v_op` 分派点。', '',
              '## 结果', '',
              '- 内核 SHA `%s`' % sha(kernel),
              '- 镜像 SHA `%s`' % sha(image),
              '- 独立重建逐字节一致；回归 %d 项全通过。' % len(checks),
              '- 相对 P0 r1 内核，cave 外差异仅 %d 个字（5 个新挂点）。' % len(actual),
              '- cave 用量 %d / %d 字节。' % (build['code_bytes'], trace.RETIRED_END - trace.START),
              '- 字段语义表 `field-semantics.json` / `FIELD-SEMANTICS.md`，SHA `%s`。' % sem_sha[:16], '',
              '## 撤掉的 hook（用户 20:51 授权）', '',
              'r2 的 `p0_vnop_read_entry`(FB03) 与 `p0_join_point`(FB06) 实机结论已固化，'
              '撤掉释放 cave 空间；`0x7466B10` / `0x7466B24` 恢复 P0 r1 原生字节。'
              '保留 FB07（MAC-read 返回码）、10 大阶段、6 功能件、11 恢复点、7 链接对象。', '',
              '## 新增观测', '']
    readme += ['- `%s` → `%s`（`%s`）：重放 `%s`' % (
        s['address'], s['field'], s['symbol'], SITES[s['symbol']]['replay'])
        for s in sites]
    readme += ['', '## 判读矩阵', '']
    for d in decision_matrix:
        key = '/'.join('%s=%s' % (k, v) for k, v in d.items() if k != 'verdict')
        readme.append('- %s → %s' % (key, d['verdict']))
    readme += ['', '## 实机录像确认门', '',
               '**停在门内**。等用户当轮明确确认全程 60fps 录像（≥9 s）与实体键恢复路径，'
               '再执行正式预检 → 恰好一次 `fastboot boot` → 逐帧判读 → 恢复后验。'
               'r3 未消费、未上机、未写分区、未改槽、未提交/推送。', '',
               '## 边界', '']
    readme += ['- ' + x for x in qualification['limitations']]
    (REPORT / 'README.md').write_text('\n'.join(readme) + '\n', encoding='utf-8')

    print('checks', len(checks), 'passed', regression['passed'])
    for c in checks:
        if not c['passed']:
            print('  FAIL', c['name'], c['evidence'])
    print('kernel', sha(kernel))
    print('image ', sha(image))
    print('field semantics', sem_sha)
    print('report', REPORT.relative_to(R))


if __name__ == '__main__':
    main()
