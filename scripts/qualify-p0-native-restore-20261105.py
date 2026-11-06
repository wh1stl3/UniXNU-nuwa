"""P0 原生恢复候选：回归 + 字段语义表 + 资格化（只读，不操作设备）。

在 Windows Python 下运行。输出全部落在 reports/p0-native-restore-20261105-r1/：
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

WORK = R / 'out/p0-native-restore-20261105-r1'
INDEP = R / 'out/p0-native-restore-20261105-r1-independent'
REPORT = R / 'reports/p0-native-restore-20261105-r1'
SOURCE = R / 'package/kernel-mainline/CoarseStages-p0-native-restore-20261105.S'
EARLY = R / 'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho'
CHECK10 = R / 'out/ufs-check-10-r1/kernel.macho'
TRIAGE = R / 'reports/native-restore-20261105/patch-triage.json'

FORMULA = 'draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N; N 为十进制，屏幕后缀为十六进制'

# 每个字段的含义与取值来源。writer 清单、行号与默认值由源码 parse 补全。
FIELD_META = {
    0: ('root_selector_stage', 'flag+return', 'BSD root selector 阶段：初始化 1，storage_load / _native_ufs_register_late / _nuwa_ufs_root_install 的返回值与最终阶段码 w23 均写回此行', 'w1 = 立即数 1/2 / w23 / w0（原生注册调用返回）'),
    1: ('storage_load_result', 'return', 'storage_load 与 _native_ufs_register_late 的返回值', 'w1 = w0（两次 .call 的返回）'),
    2: ('root_install_result', 'return', '_nuwa_ufs_root_install 的返回值', 'w1 = w0（.call 返回）'),
    4: ('root_auth_eauth', 'return', 'FSIOC_KERNEL_ROOTAUTH 返回值；KMAIN-4 实机为 0x50 (EAUTH)，初始化为 FFFFFFFF', 'w1 = rootauth 返回值 / 0xffffffff'),
    5: ('owner_root_accept', 'flag', '严格 owner-root 放行标志；KMAIN-4 实机为 1', 'w1 = 放行结果 / 0xffffffff'),
    7: ('mac_read_return', 'return', 'P0 新增：_vn_rdwr_64 内 mac_vnode_check_read 返回码。0=放行并进入 VNOP_READ 后端；非 0=MAC 拒绝走 0x7466B24；空白=未到达该分派点', 'w1 = w0（bl _mac_vnode_check_read 之后的返回值）'),
    8: ('root_wait', 'flag', 'root_wait 大阶段到达；root_wait hook 写 1', 'w1 = 立即数 1 / 0xffffffff'),
    9: ('root_return', 'flag', 'root_return 大阶段到达', 'w1 = 立即数 1 / 0xffffffff'),
    10: ('mount_return', 'return', '_vfs_mountroot 返回值；0 = 根挂载成功（CHECK5 实机 FB0A=0）', 'w1 = _vfs_mountroot 返回 / 0xffffffff'),
    11: ('init_entry', 'flag', 'load_init_program 入口大阶段', 'w1 = 立即数 1 / 0xffffffff'),
    12: ('root_return_secondary', 'flag', 'root_return hook 的第二个标记', 'w1 = 立即数 1 / 0xffffffff'),
    13: ('init_loaded_or_exec_result', 'flag', 'init_loaded / exec_result 大阶段共用行位', 'w1 = 立即数 1 / 0xffffffff'),
    14: ('el0', 'flag', 'EL0 大阶段标记；各轮实机均 FFFFFFFF（从未实机验收）', 'w1 = 立即数 1 / 0xffffffff'),
    15: ('pmgr_function_anomaly', 'flag', 'pmgr_install 返回值不等于 0x10 时才绘制；正常路径不写', 'w1 = pmgr_install 返回残留值'),
    16: ('exec_milestone_bitmap', 'bitmap', 'coarse_exec_entry / coarse_exec_namei 的里程碑位图（bit0+bit1 => 3）；初始化写 0', 'w1 = 位图值 / 立即数 0'),
    17: ('phase_latch_value', 'value', 'phase_record 在锁存命中时写的一次性值（A0000000 OR phase）', 'w1 = 栈上保存值 / A0000000+phase'),
    18: ('phase_bitmap', 'bitmap', 'phase_record 的 coarse_state 相位位图（A0000000 OR phase）', 'w1 = A0000000 OR phase'),
    19: ('exec_namei_result', 'return', 'exec namei 结果 / 大阶段值', 'w1 = namei 返回 / 0xffffffff'),
    20: ('phase_aux', 'value', 'phase_record 的辅助值（E0000000 OR 保存值）', 'w1 = E0000000 OR 栈上值 / 0xffffffff'),
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
    if (word >> 24) & 0xff in (0x35, 0xb5):  # cbnz
        imm = (word >> 5) & 0x7ffff
        imm = imm - (1 << 19) if imm & (1 << 18) else imm
        return ('cbnz', pc + 4 * imm)
    return (None, None)


def parse_writers():
    """解析全部 bl draw 写入源，并按 N 汇总；同时提取 trace_1 初始化默认值。"""
    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    # trace_1 入口初始化段的范围：从 trace_1: 到下一个 .global，中间的内部标签
    # (pmgr_function_ready / final / resume) 仍属初始化，不能按最近标签排除。
    init_start = next(i for i, l in enumerate(lines) if l.strip() == 'trace_1:')
    init_end = next(i for i in range(init_start + 1, len(lines))
                    if lines[i].strip().startswith('.global'))
    label = None
    writers = {}
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
            m1 = re.fullmatch(r'mov w1,(.+)', t)
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


def build_field_table(writers, initial):
    fields = []
    for n in sorted(writers):
        assert n in FIELD_META, ('field has no semantics', n)
        name, kind, meaning, source = FIELD_META[n]
        # 公式：ID = 0xFB00 + N，屏幕后缀是十六进制的两位；禁止手工映射。
        label = 'FB%02X' % ((0xFB00 + n) & 0xFF)
        fields.append(dict(
            field_id_decimal=n, screen_label=label, id_word='0x%04x' % (0xFB00 + n),
            encoding=FORMULA, name=name, kind=kind, meaning=meaning,
            value_source=source, writers=writers[n], writer_count=len(writers[n]),
            unobserved_default=initial.get(n, '行空白（本候选初始化段不绘制该编号）'),
            default_is_ffffffff=initial.get(n) == 'FFFFFFFF',
        ))
    return fields


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    build = read(WORK / 'build.json')
    proof = read(WORK / 'kernel-proof.json')
    triage = read(TRIAGE)
    delta = build['p0_delta']
    checks = []

    def check(name, condition, evidence):
        assert condition, ('regression failed', name, evidence)
        checks.append(dict(name=name, passed=bool(condition), evidence=evidence))

    kernel = (WORK / 'kernel.macho').read_bytes()
    independent = (INDEP / 'kernel.macho').read_bytes()
    early = EARLY.read_bytes()
    c10 = CHECK10.read_bytes()
    # build.json 在 WSL 下生成，image_path 是 /mnt/d/...；Windows 侧按固定交付路径读取。
    image = (WORK / 'boot-p0-native-restore-20261105-r1.img').read_bytes()
    b = trace.builder()
    m, me = b.macho(kernel), b.macho(early)

    def word_at(raw, macho, va):
        off = b.backed(macho, va, 4)
        return raw[off:off + 4].hex()

    # 1) 内核与镜像绑定、独立重建逐字节一致。
    check('kernel_sha_matches_build', sha(kernel) == build['kernel_sha256'], sha(kernel))
    check('image_sha_matches_build', sha(image) == build['image_sha256'], sha(image))
    check('independent_rebuild_byte_identical', kernel == independent,
          '%s / %s' % (sha(kernel), sha(independent)))

    # 2) 11 个恢复点逐点等于 earlysec 真原生字节。
    restore = [(int(r['address'], 16), r['native_from_earlysec'])
               for r in triage['sites'] if r['classification'] == 'observer-or-bridge']
    check('restore_site_count', len(restore) == 11, len(restore))
    mismatches = [(hex(va), word_at(kernel, m, va), word_at(early, me, va))
                  for va, nat in restore if word_at(kernel, m, va) != word_at(early, me, va)]
    check('all_11_restore_sites_equal_earlysec', not mismatches, mismatches)
    check('native_bl_vn_rdwr', word_at(kernel, m, 0xfffffff00769bf90) == '7e2af797',
          word_at(kernel, m, 0xfffffff00769bf90))
    check('native_cbnz_w0', word_at(kernel, m, 0xfffffff00769bf94) == '800d0035',
          word_at(kernel, m, 0xfffffff00769bf94))

    # 3) 10 个大阶段挂点仍是分支且落在 P0 cave 内。
    cave_lo = delta['cave_range']['file_offset']
    cave_hi = cave_lo + delta['cave_range']['bytes']
    sy = proof['symbols']
    stage_detail = []
    for va, name in BIG_STAGES.items():
        off = b.backed(m, va, 4)
        word = int.from_bytes(kernel[off:off + 4], 'little')
        kind, target = decode_branch(word, va)
        stage_detail.append(dict(stage=name, address=hex(va), kind=kind, target=hex(target)))
        check('big_stage_%s_still_hooked' % name,
              kind in ('b', 'bl') and trace.START <= target < trace.START + proof['code_bytes'],
              stage_detail[-1])

    # 4) 6 个功能件：分支类必须指向 P0 新符号，数据类字节与 CHECK4 clean 相同。
    clean = (R / 'out/ufs-check-4-r1-clean/kernel.macho').read_bytes()
    old_sy = read(R / 'out/ufs-check-4-r1-clean/kernel-proof.json')['symbols']
    cave_old_hi = trace.START + read(R / 'out/ufs-check-4-r1-clean/kernel-proof.json')['code_bytes']
    for va, name in KEEP_FUNCTIONAL.items():
        off = b.backed(m, va, 4)
        old_word = int.from_bytes(clean[off:off + 4], 'little')
        old_kind, old_target = decode_branch(old_word, va)
        if old_kind in ('b', 'bl') and trace.START <= old_target < cave_old_hi:
            new_kind, new_target = decode_branch(int.from_bytes(kernel[off:off + 4], 'little'), va)
            check('functional_%s_rebound_to_p0_cave' % name,
                  new_kind in ('b', 'bl') and trace.START <= new_target < trace.START + proof['code_bytes'],
                  dict(before=clean[off:off + 4].hex(), after=kernel[off:off + 4].hex(),
                       new_target=hex(new_target)))
        else:
            check('functional_%s_data_patch_unchanged' % name,
                  kernel[off:off + 4] == clean[off:off + 4],
                  dict(before=clean[off:off + 4].hex(), after=kernel[off:off + 4].hex()))

    # 5) 原生关键路径与遗留桥接保持。
    check('native_ret_unchanged', word_at(kernel, m, 0xfffffff0074669cc) == 'c0035fd6', 'c0035fd6')
    check('resid_path_unchanged',
          all(word_at(kernel, m, va) == word_at(clean, m, va)
              for va in (0xfffffff00769bf98, 0xfffffff00769bf9c, 0xfffffff00769bfa0)),
          '0x769BF98/A0 三条原生指令')
    check('legacy_bridge_preserved_unreachable',
          word_at(kernel, m, 0xfffffff0084d9be4) == word_at(clean, m, 0xfffffff0084d9be4),
          '0x84D9BE4 字节不变，恢复后不可达')

    # 6) 字段编号：公式、唯一写入源、无冲突。
    lines, writers, initial = parse_writers()
    check('field7_single_writer', len(writers.get(7, [])) == 1, writers.get(7))
    check('field7_writer_is_new_hook', writers[7][0]['hook'] == 'p0_mac_read_after', writers[7])
    check('field7_value_is_w0', writers[7][0]['w1'] == 'w0', writers[7][0])
    check('no_check10_retired_fields',
          not ({3, 6, 21, 22, 23} & set(writers)), sorted(set(writers) & {3, 6, 21, 22, 23}))
    check('all_field_ids_have_semantics', set(writers) <= set(FIELD_META), sorted(set(writers) - set(FIELD_META)))
    fields = build_field_table(writers, initial)
    for f in fields:
        n = f['field_id_decimal']
        check('field_%d_encoding_formula' % n,
              f['id_word'] == '0x%04x' % (0xFB00 + n) and
              f['screen_label'] == 'FB%02X' % ((0xFB00 + n) & 0xFF),
              dict(id=f['id_word'], screen=f['screen_label'],
                   note='由公式生成，非手工映射'))
    check('all_writers_have_line_and_hook',
          all(w['line'] and w['hook'] for items in writers.values() for w in items), 'writer 溯源完整')

    # 7) 新 hook 的 ABI 卫生：源码级逐条断言保存/恢复 x0-x29、x30、NZCV。
    text = SOURCE.read_text(encoding='utf-8')
    hook = text.split('.global p0_mac_read_after', 1)[1]
    pairs = [(2 * i, 2 * i + 1) for i in range(15)]
    hook_lines = hook.splitlines()
    for a, z in pairs:
        check('abi_save_x%d_x%d' % (a, z),
              any('stp x%d,x%d,' % (a, z) in l for l in hook_lines), 'stp x%d,x%d' % (a, z))
        check('abi_restore_x%d_x%d' % (a, z),
              any('ldp x%d,x%d,' % (a, z) in l for l in hook_lines), 'ldp x%d,x%d' % (a, z))
    check('abi_save_x30', 'str x30,[sp,#240]' in hook, 'x30')
    check('abi_restore_x30', 'ldr x30,[sp,#240]' in hook, 'x30')
    check('abi_save_nzcv', 'mrs x9,nzcv' in hook and 'str x9,[sp,#248]' in hook, 'nzcv')
    check('abi_restore_nzcv', 'ldr x9,[sp,#248]' in hook and 'msr nzcv,x9' in hook, 'nzcv')
    check('abi_stack_balanced', 'sub sp,sp,#256' in hook and 'add sp,sp,#256' in hook, 'sp')

    # 8) 新 hook 机器码：cbnz 与两条 b 的落点必须等于原生分派目标。
    hook_va = sy['p0_mac_read_after']
    hook_off = hook_va - trace.START
    cave = kernel[cave_lo:cave_lo + proof['code_bytes']]
    branches = []
    for pos in range(hook_off, min(hook_off + 512, len(cave)), 4):
        word = int.from_bytes(cave[pos:pos + 4], 'little')
        kind, target = decode_branch(word, trace.START + pos)
        if kind:
            branches.append(dict(kind=kind, pc=hex(trace.START + pos), target=hex(target)))
    b_targets = [x['target'] for x in branches if x['kind'] == 'b']
    check('hook_replays_cbnz', any(x['kind'] == 'cbnz' for x in branches), branches)
    check('hook_zero_path_resume', hex(0xfffffff007466ad4) in b_targets, b_targets)
    check('hook_error_path_resume', hex(0xfffffff007466b24) in b_targets, b_targets)
    check('mac_read_site_patched',
          word_at(kernel, m, 0xfffffff007466ad0) != 'a0020035' and
          decode_branch(int.from_bytes(bytes.fromhex(word_at(kernel, m, 0xfffffff007466ad0)), 'little'),
                        0xfffffff007466ad0)[1] == hook_va,
          dict(word=word_at(kernel, m, 0xfffffff007466ad0), hook=hex(hook_va)))

    # 9) FAT 回读（package 阶段生成的 readback 文件）与源字节一致。
    fat_dir = WORK / 'fat'
    for name, path in (('unixnu.toml', None), ('kernel.macho', WORK / 'kernel.macho'),
                       ('kernel.macho.adt', WORK / 'launch/kernel.macho.adt')):
        rb = fat_dir / ('readback-' + name)
        check('fat_readback_%s' % name.replace('.', '_'),
              rb.exists() and (path is None or rb.read_bytes() == path.read_bytes()), str(rb))

    # 10) ADT / nonce 独立复核。
    fd = transport.ARTIFACT / 'build/FV/SILICIUM_UEFI.fd'
    shim = transport.ARTIFACT / 'shim/shim.bin'
    adt = (WORK / 'launch/kernel.macho.adt').read_bytes()
    nonce = (WORK / 'launch/nonce.bin').read_bytes()
    manifest = (WORK / 'launch/launch-manifest.json').read_bytes()
    try:
        validation = context.validate(adt, WORK / 'kernel.macho', fd, shim,
                                      nonce=nonce, manifest_bytes=manifest)
        check('adt_nonce_validate', True, validation['adt_sha256'])
    except Exception as exc:  # 明确记录失败原因，不放宽断言
        check('adt_nonce_validate', False, repr(exc))
        validation = dict(error=repr(exc))
    check('nonce_is_32_bytes', len(nonce) == 32, len(nonce))
    check('image_bytes_matches_build', len(image) == build['image_bytes'], len(image))

    # 11) 差异范围绑定：cave 外差异必须全部落在 build 期声明的 patch 集合内。
    declared = {p['file_offset'] for p in delta['check10_outside_cave_diff']}
    actual = [pos for pos in range(0, min(len(c10), len(kernel)), 4)
              if not (cave_lo <= pos < cave_hi) and c10[pos:pos + 4] != kernel[pos:pos + 4]]
    check('outside_cave_diff_subset_of_declared', set(actual) <= declared,
          dict(actual=[hex(x) for x in sorted(actual)], declared=[hex(x) for x in sorted(declared)]))
    check('outside_cave_diff_count', len(actual) == delta['check10_outside_cave_diff_words'], len(actual))

    # 判读矩阵与语义表。
    decision_matrix = [
        dict(FB07='00000000', verdict='mac_vnode_check_read 放行，已进入 0x7466AD4 之后的 VNOP_READ 后端分派；若后续大阶段仍停在 exec_namei，卡点在 APFS/UPL/后端 I/O。'),
        dict(FB07='非零', verdict='mac_vnode_check_read 返回错误码（即 FB07 值），原生 cbnz 走 0x7466B24 错误汇合；按错误码定位 MAC 策略拒绝原因。'),
        dict(FB07='行空白', verdict='未到达 0x7466AD0 分派点：卡在 _vn_rdwr_64 更早处（含 len<0 早退）或 exec_activate_image 之前。必须结合最后一个出现的大阶段标记定位，不得单独写成「MAC 拒绝」。'),
        dict(guard='10 个大阶段全空白 + trace_1 初始化字段也空白', verdict='framebuffer 通道或入口未执行，本轮全部读数无效，需重新核对通道与入口。'),
    ]
    semantics = dict(
        schema='Nuwa.FieldSemantics.v2', candidate='P0-NATIVE-RESTORE r1',
        generated_by='scripts/qualify-p0-native-restore-20261105.py',
        generated_at=datetime.now(timezone.utc).isoformat(),
        encoding_formula=FORMULA, generated_by_formula=True,
        image_sha256=build['image_sha256'], kernel_sha256=build['kernel_sha256'],
        observer_source=str(SOURCE.relative_to(R)), observer_source_sha256=sha_p(SOURCE),
        builder_source='scripts/build-p0-native-restore-20261105.py',
        builder_sha256=sha_p(R / 'scripts/build-p0-native-restore-20261105.py'),
        initialised_ids_decimal=sorted(initial),
        not_drawn_ids_decimal=[3, 6, 21, 22, 23],
        not_drawn_note='CHECK8/10 的 c8_selfcheck / c8_read_return / c10_vn_rdwr_ret 已退役；这些编号在 P0 无任何 draw 调用，不是本候选的被绘制字段。',
        fields=fields, decision_matrix=decision_matrix,
        field_id_conflict='无：FB07 (N=7) 全候选仅 1 个写入源，见 writers[7]；编号由公式计算，不手工映射。',
        channel_evidence='通道有效性由 trace_1 初始化字段（FB00=00000001、FB04..FB14=FFFFFFFF、FB10=00000000）'
                         '与 10 个大阶段字段共同证明；P0 不含 CHECK8 的 FB03/FB06 自检字段，判读时不得引用它们。',
        limitations=['静态源码 + 实际交付内核机器码核对；不是实机读数。',
                     'FB07 行位可见性沿用 AGENTS §6 对 FB07/FB0F 的既有认定，本轮未在设备上重新验证。'],
    )
    sem_path = REPORT / 'field-semantics.json'
    sem_path.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sem_sha = sha(sem_path.read_bytes())

    md = ['# P0-NATIVE-RESTORE r1 字段语义表', '',
          '生成：`scripts/qualify-p0-native-restore-20261105.py` · 源码 SHA `%s` · 语义表 SHA `%s`' % (
              sha_p(SOURCE)[:16], sem_sha[:16]),
          '', '编码公式：`%s`' % FORMULA, '',
          '未绘制编号：FB03 / FB06 / FB15 / FB16 / FB17（退役的 CHECK8/10 观测，本候选无写入源）。',
          '通道有效性：见 `channel_evidence`；P0 不含 FB03/FB06 自检字段。', '',
          '| N (十进制) | 屏幕 | 字段 | 类型 | 写入源数 | 值来源 | 未观测默认值 | 含义 |',
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
        md.append('- %s → %s' % (d.get('FB07', d.get('guard')), d['verdict']))
    (REPORT / 'FIELD-SEMANTICS.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

    regression = dict(schema='Nuwa.P0Regression.v1', candidate='P0-NATIVE-RESTORE r1',
                      kernel_sha256=sha(kernel), independent_kernel_sha256=sha(independent),
                      image_sha256=sha(image), checks=checks, passed=all(c['passed'] for c in checks),
                      case_count=len(checks), stage_hooks=stage_detail,
                      mac_read_hook_branches=branches, adt_validation=validation)
    (REPORT / 'regression.json').write_text(json.dumps(regression, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    qualification = dict(
        schema='Nuwa.OfflineQualification.v1', candidate='P0-NATIVE-RESTORE r1',
        generated_at=datetime.now(timezone.utc).isoformat(),
        status='OFFLINE_QUALIFIED_AT_CONFIRMATION_GATE',
        kernel_sha256=sha(kernel), image_sha256=sha(image),
        image_path=str(WORK / 'boot-p0-native-restore-20261105-r1.img'),
        field_semantics_sha256=sem_sha, regression_sha256=sha_p(REPORT / 'regression.json'),
        inputs=dict(
            build_json=sha_p(WORK / 'build.json'), kernel_proof=sha_p(WORK / 'kernel-proof.json'),
            observer_source=sha_p(SOURCE), builder=sha_p(R / 'scripts/build-p0-native-restore-20261105.py'),
            source_generator=sha_p(R / 'scripts/gen-p0-observer-source-20261105.py'),
            callsite_verdict=sha_p(R / 'reports/native-restore-20261105/exec-read-callsite.json'),
            patch_triage=sha_p(TRIAGE), native_earlysec=sha_p(EARLY),
            consumed_check10_kernel=sha_p(CHECK10)),
        regression=dict(case_count=len(checks), passed=all(c['passed'] for c in checks)),
        three_class_inventory=delta['three_class_inventory'],
        device_gate=dict(
            status='STOPPED', reason='交接文档要求停在实机确认门，等用户给出设备条件',
            required_before_boot=['新鲜 nuwa/A/TWRP 与 fastboot 目标预检',
                                  '持续录像与实体键恢复条件确认',
                                  '候选镜像 SHA 与未消费状态核验'],
            device_actions_performed=False, partitions_written=False, slot_changed=False,
            git_committed_or_pushed=False),
        limitations=[
            '离线合格 ≠ 实机通过；FB07 与 10 个大阶段均需实机录像逐帧判读。',
            'kernel.macho / fat/unixnu.toml / 内嵌内核字节逐字节可复现；kernel.macho.adt 含一次性 nonce 且 FAT 含时间戳，boot 镜像每构建必不同，资格绑定精确 SHA。',
            'P0 是诊断对照（看原生最远到哪一段），不是「原生应该能跑通」的验证；安全模型未改，permissive 替身未引入。',
        ])
    (REPORT / 'qualification.json').write_text(json.dumps(qualification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    readme = ['# P0 原生恢复候选 · 离线资格', '',
              '2026-11-05 · 未改安全模型、未上机、未提交 git。', '',
              '## 结果', '',
              '- 内核 SHA `%s`' % sha(kernel), '- 镜像 SHA `%s`' % sha(image),
              '- 独立重建逐字节一致；回归 %d 项全通过。' % len(checks),
              '- 字段语义表 `field-semantics.json` / `FIELD-SEMANTICS.md`，SHA `%s`。' % sem_sha[:16], '',
              '## 三分类清单（逐地址绑定）', '',
              '### 1. probe 桥接 / 自建改道（退役，恢复真原生）', '']
    readme += ['- `%s` → `%s`' % (x['address'], x['native']) for x in delta['three_class_inventory']['probe_bridge_retired']]
    readme += ['', '### 2. 功能修复（保留）', '']
    readme += ['- `%s` %s' % (x['address'], x['reason']) for x in delta['three_class_inventory']['functional_kept']]
    readme += ['', '### 3. 必要观测（保留）', '']
    readme += ['- `%s` %s%s' % (x['address'], x.get('stage', ''),
                                ' (FB07=w0)' if x.get('field') else '')
               for x in delta['three_class_inventory']['necessary_observation']]
    readme += ['', '## 实机确认门', '',
               '本轮停在此处。上机前须：新鲜 nuwa/A/TWRP 与 fastboot 目标预检、持续录像与实体键恢复条件确认、候选镜像 SHA 与未消费状态核验。',
               '', '判读先看 10 个大阶段中最后一个出现的标记，再用 FB07 区分：'
                   '`00000000` = MAC-read 放行进入 VNOP_READ 后端；非零 = MAC 拒绝（值即错误码）；空白 = 未到达该分派点。'
                   '空白不得单独写成「MAC 拒绝」或「未返回」。', '',
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
