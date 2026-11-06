"""P0 原生恢复候选：恢复 11 个自建改道/观测桥接为真原生，保留大阶段观测。

在 WSL Ubuntu-22.04 的 python3 下运行（编译/打包工具均为 WSL 原生命令）：
  python3 scripts/build-p0-native-restore-20261105.py --work out/p0-native-restore-20261105-r1

设计（reports/native-restore-20261105/README.md）：
- 基线 out/ufs-check-4-r1-clean/kernel.macho（已含 NativeUfs 链接对象与修复补丁）。
- 11 个 observer-or-bridge 恢复 earlysec 真原生字节，不取 build.json before。
- 保留 10 个 coarse 大阶段、6 个功能件、7 个 linked 对象原样。
- 新增 1 个 MAC-read 返回标记（0x7466AD0 -> p0_mac_read_after，FB07）。
- 不改安全模型、不加停机门、不操作设备、不提交 git。
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    from pip._vendor import tomli as tomllib
    sys.modules['tomllib'] = tomllib

import flush_trace_inputs as trace
import nuwa_launch_context as context
import usb_ramdisk_package as transport

ROOT = trace.R
PARENT = ROOT / 'out/ufs-check-4-r1-clean'
EARLY = ROOT / 'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho'
CHECK10_KERNEL = ROOT / 'out/ufs-check-10-r1/kernel.macho'
CHECK10_PROOF = ROOT / 'out/ufs-check-10-r1/kernel-proof.json'
SOURCE = ROOT / 'package/kernel-mainline/CoarseStages-p0-native-restore-20261105.S'
TRIAGE = ROOT / 'reports/native-restore-20261105/patch-triage.json'
SOURCE_GEN_EVIDENCE = ROOT / 'reports/native-restore-20261105/p0-observer-source.json'
CALL_SITE_EVIDENCE = ROOT / 'reports/native-restore-20261105/exec-read-callsite.json'

KERNEL_SHA = '551a0cf621b5fca221be267ae25aba142d5aaa904cccdd5310dfb53b88474ec3'
IMAGE_SHA = '0a37f98ea65c14f80cb446aff89cff0e51184f983e723e50705a7ec701514257'
EARLY_SHA = '1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6'
CHECK10_SHA = 'da23791bdecc5b4381c76114b3f9f1275719aef4f34307657841e5e22fbf4b28'
SOURCE_SHA = 'f5c8642fcf48acddc5ffb6d5a0d515f06d5ad47ab169dbefb0c22480d6493f95'
TRIAGE_SHA = 'cd9377d38e2adbf1375f786dc947c97019e13dbffb7f62b4375058cc9802ed98'

# 新增观测：_vn_rdwr_64 内 mac_vnode_check_read 返回后的原生错误分派点。
MAC_READ_SITE = 0xfffffff007466ad0
MAC_READ_NATIVE = 'a0020035'          # cbnz w0,0xfffffff007466b24
MAC_READ_RESUME_ZERO = 0xfffffff007466ad4
MAC_READ_RESUME_ERROR = 0xfffffff007466b24
MAC_READ_FIELD_N = 7                  # draw: 0xFB00+7 = FB07
MAC_READ_HOOK = 'p0_mac_read_after'

BIG_STAGES = {
    0xfffffff0078e37a8: 'root_wait', 0xfffffff007673098: 'root_return',
    0xfffffff0076732f4: 'root_auth', 0xfffffff0076730e8: 'mount_return',
    0xfffffff00769d2a4: 'init_entry', 0xfffffff00767356c: 'init_loaded',
    0xfffffff00769ce3c: 'exec_entry', 0xfffffff00769bdd8: 'exec_namei',
    0xfffffff00769d624: 'exec_result', 0xfffffff0073c3864: 'el0',
}
KEEP_FUNCTIONAL = {
    0xfffffff0078e331c: 'BSD root selector',
    0xfffffff0084e56a0: 'mapped end / prelink adaptation',
    0xfffffff0084e5710: 'validate_increment',
    0xfffffff0084e5768: 'install_increment',
    0xfffffff0084e5740: 'map_permissions',
    0xfffffff00769d230: 'coarse_release_before (publishes ip_new_thread)',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def native_path(value):
    value = str(value).replace('\\', '/')
    return Path('/mnt/' + value[0].lower() + value[2:]) if len(value) > 2 and value[1] == ':' else Path(value)


def run(*args):
    return subprocess.check_output([str(x) for x in args], stderr=subprocess.STDOUT)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def compile_code(text, work):
    """WSL 原生工具链；入口用 trace_1，与 flush_trace_inputs 默认一致。"""
    work.mkdir(parents=True, exist_ok=False)
    (work / 'trace.S').write_text(text)
    run('/usr/bin/clang', '--target=aarch64-none-elf', '-c', work / 'trace.S', '-o', work / 'trace.o')
    run('/usr/bin/ld.lld', '-Ttext=' + hex(trace.START), '-e', 'trace_1',
        work / 'trace.o', '-o', work / 'trace.elf')
    run('/usr/bin/llvm-objcopy', '-O', 'binary', '--only-section=.text',
        work / 'trace.elf', work / 'trace.bin')
    nm = run('/usr/bin/llvm-nm', '--defined-only', work / 'trace.elf').decode()
    sy = {s[2]: int(s[0], 16) for line in nm.splitlines() if len(s := line.split()) == 3}
    return (work / 'trace.bin').read_bytes(), sy


def word_at(raw, macho, va):
    off = trace.builder().backed(macho, va, 4)
    return raw[off:off + 4].hex()


def branch_target(word, pc):
    imm = word & 0x3ffffff
    imm = imm - (1 << 26) if imm & (1 << 25) else imm
    return pc + 4 * imm


def build(work):
    assert work.resolve().is_relative_to(ROOT / 'out')
    work.mkdir(parents=True, exist_ok=False)
    b = trace.builder()
    raw = (PARENT / 'kernel.macho').read_bytes()
    early = EARLY.read_bytes()
    c10 = CHECK10_KERNEL.read_bytes()
    assert sha(raw) == KERNEL_SHA
    assert sha((PARENT / 'boot-ufs-check-4-r1.img').read_bytes()) == IMAGE_SHA
    assert sha(early) == EARLY_SHA
    assert sha(c10) == CHECK10_SHA
    assert sha(SOURCE.read_bytes()) == SOURCE_SHA
    assert sha(TRIAGE.read_bytes()) == TRIAGE_SHA
    prior = read(PARENT / 'kernel-proof.json')
    m, me = b.macho(raw), b.macho(early)
    triage = read(TRIAGE)
    restore = [(int(r['address'], 16), r['native_from_earlysec'])
               for r in triage['sites'] if r['classification'] == 'observer-or-bridge']
    assert len(restore) == 11
    # 恢复目标一律从 earlysec 独立重算，不采信 triage 的手抄值。
    for va, nat in restore:
        assert word_at(early, me, va) == nat, (hex(va), 'triage native mismatch')
    restore_addrs = {va for va, _ in restore}

    compiler = module('check4_compiler', ROOT / 'scripts/build-ufs-check4-r1.py')
    trace.compile_code = compile_code
    oldcode, oldsy = compiler.compile_observer(work / 'parent-reproduction', prior['targets'])
    off = b.backed(m, trace.START, len(oldcode))
    assert oldsy == prior['symbols'] and oldcode == raw[off:off + len(oldcode)]
    assert len(oldcode) == prior['code_bytes']

    compiler.SOURCE = SOURCE
    targets = dict(prior['targets'])
    targets.update(p0_mac_read_resume=MAC_READ_RESUME_ZERO,
                   p0_mac_read_error_target=MAC_READ_RESUME_ERROR)
    code, sy = compiler.compile_observer(work, targets)
    assert MAC_READ_HOOK in sy and 'draw' in sy
    assert trace.START + len(code) <= trace.RETIRED_END
    # FB07 全候选只有一个写入源（按 AGENTS §6 字段编号纪律）。
    source_text = SOURCE.read_text()
    assert source_text.count('mov w0,#%d\n' % MAC_READ_FIELD_N) == 1

    out = bytearray(raw)
    out[off:off + len(code)] = code
    entries = {v: k for k, v in oldsy.items() if not k.startswith(('fixup_', '$'))}
    patches = []
    fullchanges = copy.deepcopy(prior['changes'])
    by_addr = {}
    for c in fullchanges:
        by_addr.setdefault(int(c['address'], 16), []).append(c)

    # 重算所有指向旧 cave 的分支；11 个恢复点跳过，稍后统一写原生字节。
    for change in fullchanges:
        address = int(change['address'], 16)
        at = b.backed(m, address, 4)
        word = int.from_bytes(raw[at:at + 4], 'little')
        if word & 0x7c000000 != 0x14000000:
            continue
        target = branch_target(word, address)
        if not trace.START <= target < trace.START + len(oldcode):
            continue
        if address in restore_addrs:
            continue
        assert target in entries, (hex(address), hex(target))
        label = entries[target]
        assert label in sy, ('P0 cave dropped live symbol', hex(address), label)
        after = b.branch(address, sy[label])
        if word & 0x80000000:
            after = struct.pack('<I', int.from_bytes(after, 'little') | 0x80000000)
        out[at:at + 4] = after
        patches.append(dict(address=hex(address), file_offset=at,
                            before=raw[at:at + 4].hex(), after=after.hex(),
                            symbol=label, role='big-stage-or-function-hook'))
        change['after'] = after.hex()

    # 11 个恢复点：写 earlysec 真原生字节。3 个在 CHECK4 clean 里本就原生，记为 NO-OP。
    restore_records = []
    for va, nat in restore:
        at = b.backed(m, va, 4)
        before = raw[at:at + 4].hex()
        out[at:at + 4] = bytes.fromhex(nat)
        restore_records.append(dict(address=hex(va), file_offset=at,
                                    before=before, after=nat,
                                    action='RESTORE' if before != nat else 'NO-OP already-native',
                                    source='earlysec 1aeebf13…'))
        patches.append(dict(address=hex(va), file_offset=at, before=before,
                            after=nat, role='restore-true-native'))
        for c in by_addr.get(va, []):
            c['after'] = nat

    # 新增唯一观测挂点。
    at = b.backed(m, MAC_READ_SITE, 4)
    assert raw[at:at + 4].hex() == MAC_READ_NATIVE, 'MAC-read dispatch word changed'
    mac_after = b.branch(MAC_READ_SITE, sy[MAC_READ_HOOK])
    out[at:at + 4] = mac_after
    patches.append(dict(address=hex(MAC_READ_SITE), file_offset=at,
                        before=MAC_READ_NATIVE, after=mac_after.hex(),
                        symbol=MAC_READ_HOOK, role='necessary-observation'))
    fullchanges.append(dict(address=hex(MAC_READ_SITE), offset=at,
                            before=MAC_READ_NATIVE, after=mac_after.hex(),
                            reason='P0 MAC-read 返回标记 (FB07 = w0)'))

    # 结构性断言：10 个大阶段仍挂到新 cave；6 个功能件字节未变；原生关键路径不变。
    written = {int(p['address'], 16): p for p in patches}
    for va, name in BIG_STAGES.items():
        assert va in written, ('big-stage hook lost', name, hex(va))
        w = int.from_bytes(bytes.fromhex(written[va]['after']), 'little')
        assert w & 0x7c000000 == 0x14000000, (name, 'not a branch')
        assert trace.START <= branch_target(w, va) < trace.START + len(code), (name, 'target outside P0 cave')
    # 功能件分两类：指向 cave 的 hook 分支必须重算到 P0 新符号（字节会变，语义不变）；
    # 非分支的数据补丁必须逐字节保持 CHECK4 clean 原值。
    for va, name in KEEP_FUNCTIONAL.items():
        at = b.backed(m, va, 4)
        old_word = int.from_bytes(raw[at:at + 4], 'little')
        old_target = branch_target(old_word, va)
        if old_word & 0x7c000000 == 0x14000000 and trace.START <= old_target < trace.START + len(oldcode):
            label = entries[old_target]
            assert label in sy, ('functional hook symbol dropped', name, label)
            new_word = int.from_bytes(out[at:at + 4], 'little')
            assert new_word & 0x7c000000 == 0x14000000, (name, 'functional branch lost')
            assert branch_target(new_word, va) == sy[label], (name, 'functional hook rebound elsewhere')
        else:
            assert out[at:at + 4].hex() == raw[at:at + 4].hex(), (name, 'functional data patch changed')
    assert word_at(out, m, 0xfffffff0074669cc) == 'c0035fd6', 'native RET changed'
    for va in (0xfffffff00769bf98, 0xfffffff00769bf9c, 0xfffffff00769bfa0):
        assert word_at(out, m, va) == word_at(raw, m, va), ('resid path changed', hex(va))
    assert word_at(out, m, 0xfffffff0084d9be4) == word_at(raw, m, 0xfffffff0084d9be4), 'legacy bridge must remain (unreachable)'
    assert word_at(out, m, 0xfffffff00769bf90) == '7e2af797', 'native bl _vn_rdwr not restored'
    assert word_at(out, m, 0xfffffff00769bf94) == '800d0035', 'native cbnz w0 not restored'

    # 允许改动范围：cave + 所有 4 字节写入点；其余字节必须与 CHECK4 clean 相同。
    cave_hi = off + max(len(oldcode), len(code), read(CHECK10_PROOF)['code_bytes'])
    allowed = [(off, cave_hi)] + [(p['file_offset'], p['file_offset'] + 4) for p in patches]
    check = bytearray(out)
    for start, end in allowed:
        check[start:end] = raw[start:end]
    assert check == raw, 'bytes changed outside declared ranges'

    # 相对已消费 CHECK10 内核的差异字节范围（逐 4 字节枚举，全部落在声明范围内）。
    outside = []
    for pos in range(0, min(len(c10), len(out)), 4):
        if off <= pos < cave_hi:
            continue
        if c10[pos:pos + 4] != out[pos:pos + 4]:
            outside.append(dict(file_offset=pos, check10=c10[pos:pos + 4].hex(),
                                p0=out[pos:pos + 4].hex()))
    outside_set = {x['file_offset'] for x in outside}
    patch_set = {p['file_offset'] for p in patches}
    # P0 保留 CHECK10 观测源码的前缀，前缀内 10 个大阶段符号地址不变，
    # 因此这些挂点重算后的分支字与 CHECK10 相同（NO-OP 重绑定）。
    # 允许的结论是「差异必须全部落在已声明的 patch 集合内」，而非两者相等。
    assert outside_set <= patch_set, (
        'unexpected CHECK10->P0 outside-cave diff',
        'diff-not-in-patches', [hex(x) for x in sorted(outside_set - patch_set)[:12]])
    noop_rebound = [hex(x) for x in sorted(patch_set - outside_set)]

    three_classes = dict(
        probe_bridge_retired=[dict(address=hex(va), native=nat,
                                   classification='observer-or-bridge')
                              for va, nat in restore],
        functional_kept=[dict(address=hex(va), reason=name) for va, name in KEEP_FUNCTIONAL.items()]
        + [dict(address='linked-in-candidate x7', reason='NativeUfs 链接对象原样保留 (CHECK4 linked/)')],
        necessary_observation=[dict(address=hex(va), stage=name) for va, name in BIG_STAGES.items()]
        + [dict(address=hex(MAC_READ_SITE), stage='mac_read_return', field='FB07', value='w0')],
    )

    proof = copy.deepcopy(prior)
    proof.update(
        schema='Nuwa.P0NativeRestore.v1',
        parent_build=str(native_path(prior['parent_build'])),
        kernel_sha256=sha(out), source_sha256=sha(SOURCE.read_bytes()),
        observer_source=str(SOURCE.relative_to(ROOT)),
        builder_source='scripts/build-p0-native-restore-20261105.py',
        code_bytes=len(code), symbols=sy, changes=fullchanges,
        objects=[dict(path=str(native_path(x['path'])), sha256=x['sha256']) for x in prior['objects']],
        p0_delta=dict(
            native_reference=dict(path=str(EARLY.relative_to(ROOT)), sha256=EARLY_SHA),
            consumed_baseline=dict(path=str(CHECK10_KERNEL.relative_to(ROOT)), sha256=CHECK10_SHA),
            triage_sha256=TRIAGE_SHA,
            observer_source_generation=str(SOURCE_GEN_EVIDENCE.relative_to(ROOT)),
            callsite_verdict=str(CALL_SITE_EVIDENCE.relative_to(ROOT)),
            restored_sites=restore_records,
            restored_count=len(restore),
            already_native_noop=[r['address'] for r in restore_records if r['action'].startswith('NO-OP')],
            new_observation=dict(address=hex(MAC_READ_SITE), native_word=MAC_READ_NATIVE,
                                 hook=MAC_READ_HOOK, hook_address=hex(sy[MAC_READ_HOOK]),
                                 field_decimal_n=MAC_READ_FIELD_N, field_label='0xFB07',
                                 field_value_source='w0 = mac_vnode_check_read 返回码',
                                 resume_w0_zero=hex(MAC_READ_RESUME_ZERO),
                                 resume_w0_nonzero=hex(MAC_READ_RESUME_ERROR),
                                 field_id_formula='draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N'),
            big_stages_kept={hex(k): v for k, v in BIG_STAGES.items()},
            functional_kept={hex(k): v for k, v in KEEP_FUNCTIONAL.items()},
            control_flow='恢复 0x769BF90 为原生 bl _vn_rdwr，x30 由硬件写入 0x769BF94；'
                         '0x769BF94 恢复原生 cbnz w0,0x769C144；参数块 w6=8 (IO_NODELOCKED) 不动',
            security_model_changed=False, stop_gate_added=False, repair_patches_removed=0,
            three_class_inventory=three_classes,
            cave_range=dict(file_offset=off, bytes=cave_hi - off),
            allowed_file_ranges=allowed,
            all_bytes_outside_declared_ranges_unchanged=True,
            check10_outside_cave_diff_words=len(outside),
            check10_outside_cave_diff=outside,
            check10_noop_rebound_patch_offsets=noop_rebound,
            check10_diff_subset_of_declared_patches=True,
            purpose='诊断对照：撤掉自建改道与细粒度观测桥接，看原生 header-read 链最远能跑到哪一段；'
                    '保留 10 个大阶段观测 + 1 个 MAC-read 返回标记以区分 MAC 返回与 VNOP_READ 后端。'),
    )
    (work / 'kernel.macho').write_bytes(out)
    save(work / 'kernel-proof.json', proof)
    save(work / 'build.json', proof)
    print('kernel', sha(out), 'bytes', len(out))
    print('restored', len(restore), '| outside-cave diffs vs CHECK10', len(outside))
    return proof


def package(work, proof):
    fd = transport.ARTIFACT / 'build/FV/SILICIUM_UEFI.fd'
    shim = transport.ARTIFACT / 'shim/shim.bin'
    stock = native_path(transport.STOCK).read_bytes()
    assert [sha(p.read_bytes()) for p in (fd, shim)] == [transport.FD_SHA, transport.SHIM_SHA]
    assert sha(stock) == transport.STOCK_SHA
    base = work / 'base.adt'
    base.write_bytes((PARENT / 'base.adt').read_bytes())
    launch = context.create(base, work / 'kernel.macho', fd, shim, work / 'launch')
    staging = work / 'fat'
    staging.mkdir()
    fatpath = work / 'payload.fat'
    menu = (PARENT / 'fat/unixnu.toml').read_text().replace('UFS-CHECK-4 r1', 'P0-NATIVE-RESTORE r1')
    assert 'P0-NATIVE-RESTORE r1' in menu
    run('mformat', '-C', '-F', '-T', '131072', '-v', 'NUWAXNU', '-N', '584E5558', '-i', fatpath, '::')
    for d in ('::/EFI', '::/EFI/UniXNU', '::/EFI/UniXNU/Payloads'):
        run('mmd', '-i', fatpath, d)
    for name, data, dest in [
        ('unixnu.toml', menu.encode(), '::/EFI/UniXNU/unixnu.toml'),
        ('kernel.macho', (work / 'kernel.macho').read_bytes(), '::/EFI/UniXNU/Payloads/kernel.macho'),
        ('kernel.macho.adt', (work / 'launch/kernel.macho.adt').read_bytes(), '::/EFI/UniXNU/Payloads/kernel.macho.adt'),
    ]:
        p = staging / name
        p.write_bytes(data)
        os.utime(p, (315532800, 315532800))
        run('mcopy', '-m', '-i', fatpath, p, dest)
        back = staging / ('readback-' + name)
        run('mcopy', '-i', fatpath, dest, back)
        assert back.read_bytes() == data, ('FAT readback mismatch', name)
    fat = fatpath.read_bytes()
    envelope = transport.MAGIC + struct.pack('<IIQI28x', 1, 64, len(fat), zlib.crc32(fat)) + fat
    fw = shim.read_bytes() + fd.read_bytes()
    image = transport.compose(stock[:4096], fw, envelope, 3)
    transport.inspect_container(image, stock[:4096], fw, envelope, 3)
    path = work / 'boot-p0-native-restore-20261105-r1.img'
    path.write_bytes(image)
    proof.update(image_path=str(path), image_sha256=sha(image), image_bytes=len(image), launch=launch)
    save(work / 'build.json', proof)
    print(path, sha(image))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--kernel-only', action='store_true')
    a = p.parse_args()
    proof = build(a.work.resolve())
    if not a.kernel_only:
        package(a.work.resolve(), proof)
