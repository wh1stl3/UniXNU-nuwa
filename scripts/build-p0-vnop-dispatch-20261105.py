"""P0 r3：由 P0 r1 派生，下钻到 _VNOP_READ 内部分派点 + 三路阳性对照。

在 WSL Ubuntu-22.04 的 python3 下运行：
  python3 scripts/build-p0-vnop-dispatch-20261105.py --work out/p0-vnop-dispatch-20261105-r3

父候选是 P0-NATIVE-RESTORE r1（不是 r2）：用户 20:51 授权撤掉 r2 已完成使命的
FB03 / FB06 两个观测 hook，故 0x7466B10 / 0x7466B24 保持原生字节。
保留 11 点真原生恢复 + 10 大阶段 + 6 功能件 + 7 链接对象 + FB07 MAC-read 标记。

不引入 permissive 替身、不改安全模型、不加停机门、不操作设备、不提交 git。
"""
import argparse
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
P0_DIR = ROOT / 'out/p0-native-restore-20261105-r1'
P0_KERNEL = P0_DIR / 'kernel.macho'
PARENT = ROOT / 'out/ufs-check-4-r1-clean'
SOURCE = ROOT / 'package/kernel-mainline/CoarseStages-p0-vnop-dispatch-r3.S'
SOURCE_GEN = ROOT / 'reports/p0-vnop-dispatch-20261105-r3/source-generation.json'
SUSPECT_EVIDENCE = ROOT / 'reports/vnop-suspect-and-gap-20261105/evidence.json'

SOURCE_SHA = 'aec61be98f0eff863af57df0745f51704775c969894e8e0906bfc146cf08eb2f'
P0_KERNEL_SHA = 'ce75992b9b1e7ef6755a2c0b1be5bc57a47c59052161d7420de3f6e75e4a3d1a'

SITES = (
    dict(name='r3_vnop_entry', address=0xfffffff00746c628, native='ffc301d1',
         native_semantics='sub sp,sp,#0x70', field='FB03/FB06/FB0F',
         role='_VNOP_READ 入口 + 值字段重置'),
    dict(name='r3_vnop_dispatch', address=0xfffffff00746c684, native='e0230091',
         native_semantics='add x0,x0,#8', field='FB06',
         role='记录 v_op 分派目标 x8 低 32 位'),
    dict(name='r3_vnop_return', address=0xfffffff00746c68c, native='f60300aa',
         native_semantics='mov x22,x0', field='FB0F',
         role='blr x8 返回首条 w0'),
    dict(name='r3_early_exit', address=0xfffffff007466ac4, native='c0028052',
         native_semantics='mov w0,#0x16', field='FB03', role='len<0 早退阳性对照'),
    dict(name='r3_epilogue', address=0xfffffff007466b88, native='ffc30291',
         native_semantics='add sp,sp,#0xb0', field='FB03',
         role='_vn_rdwr_64 正常返回 epilogue 阳性对照'),
)
NEW_TARGETS = dict(
    r3_entry_resume=0xfffffff00746c62c,
    r3_dispatch_resume=0xfffffff00746c688,
    r3_return_resume=0xfffffff00746c690,
    r3_early_resume=0xfffffff007466ac8,
    r3_epilogue_resume=0xfffffff007466b8c,
)
# 撤掉的 r2 挂点必须保持 P0 r1 原生字节
WITHDRAWN = (
    dict(address=0xfffffff007466b10, native='e3030091', semantics='mov x3,sp'),
    dict(address=0xfffffff007466b24, native='f40300aa', semantics='mov x20,x0'),
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_p0():
    spec = importlib.util.spec_from_file_location(
        'p0_builder', ROOT / 'scripts/build-p0-native-restore-20261105.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


p0 = load_p0()
p0.SOURCE = SOURCE
p0.SOURCE_SHA = SOURCE_SHA
_orig_read = p0.read


def _read_with_resumes(path):
    d = _orig_read(path)
    if isinstance(d, dict) and isinstance(d.get('targets'), dict):
        for k, v in NEW_TARGETS.items():
            d['targets'].setdefault(k, v)
    return d


p0.read = _read_with_resumes


def run(*args):
    return subprocess.check_output([str(x) for x in args], stderr=subprocess.STDOUT)


def native_path(value):
    value = str(value).replace('\\', '/')
    return Path('/mnt/' + value[0].lower() + value[2:]) if len(value) > 2 and value[1] == ':' else Path(value)


def build(work):
    assert work.resolve().is_relative_to(ROOT / 'out')
    assert sha(SOURCE.read_bytes()) == SOURCE_SHA, 'source SHA changed'
    assert sha(P0_KERNEL.read_bytes()) == P0_KERNEL_SHA, 'P0 r1 kernel SHA changed'
    assert SOURCE_GEN.exists() and SUSPECT_EVIDENCE.exists(), 'evidence missing'

    # 第一步：跑 P0 r1 构建链（新源码已含 5 个 hook，但尚未挂到内核上）。
    proof = p0.build(work)
    sy = proof['symbols']
    for s in SITES:
        assert s['name'] in sy, ('hook symbol missing', s['name'])
    assert proof['code_bytes'] == len((work / 'observer/trace.bin').read_bytes()), \
        'observer code length mismatch'

    b = trace.builder()
    raw_p0 = P0_KERNEL.read_bytes()
    raw = (work / 'kernel.macho').read_bytes()
    m = b.macho(raw)
    out = bytearray(raw)
    cave_lo = b.backed(m, trace.START, proof['code_bytes'])
    p0_proof = json.loads((P0_DIR / 'kernel-proof.json').read_text(encoding='utf-8'))
    c10_proof = json.loads((ROOT / 'out/ufs-check-10-r1/kernel-proof.json').read_text(encoding='utf-8'))
    cave_hi = cave_lo + max(proof['code_bytes'], p0_proof['code_bytes'], c10_proof['code_bytes'])

    patches = []
    for s in SITES:
        va = s['address']
        at = b.backed(m, va, 4)
        assert raw[at:at + 4].hex() == s['native'], (hex(va), 'native word changed')
        after = b.branch(va, sy[s['name']])
        assert len(after) == 4
        out[at:at + 4] = after
        patches.append(dict(address=hex(va), file_offset=at,
                            before=s['native'], after=after.hex(),
                            symbol=s['name'], role='vnop-dispatch-observation',
                            field=s['field']))
        proof['changes'].append(dict(address=hex(va), offset=at,
                                     before=s['native'], after=after.hex(),
                                     reason='P0 r3 %s (%s)' % (s['role'], s['field'])))

    # 相对 P0 r1 内核：差异必须全部落在 cave 范围 + 5 个新挂点。
    allowed = [(cave_lo, cave_hi)] + [(p_['file_offset'], p_['file_offset'] + 4) for p_ in patches]
    check = bytearray(out)
    for lo, hi in allowed:
        check[lo:hi] = raw_p0[lo:hi]
    assert check == raw_p0, 'bytes changed outside declared ranges vs P0 r1'
    outside = []
    for pos in range(0, min(len(raw_p0), len(out)), 4):
        if cave_lo <= pos < cave_hi:
            continue
        if raw_p0[pos:pos + 4] != out[pos:pos + 4]:
            outside.append(dict(file_offset=pos, p0=raw_p0[pos:pos + 4].hex(),
                                r3=out[pos:pos + 4].hex()))
    assert {x['file_offset'] for x in outside} == {p_['file_offset'] for p_ in patches}, \
        ('unexpected P0->r3 outside-cave diff', outside[:8])

    # 撤掉的 r2 挂点必须等于 P0 r1 原生字节。
    for w in WITHDRAWN:
        at = b.backed(m, w['address'], 4)
        assert out[at:at + 4].hex() == w['native'], ('withdrawn hook not native', hex(w['address']))
    # MAC-read / 原生恢复点等关键路径与 P0 r1 一致。
    for va in (0xfffffff00769bf90, 0xfffffff00769bf94, 0xfffffff00769d110,
               0xfffffff007466ad0, 0xfffffff0074669c8, 0xfffffff0074669cc):
        at = b.backed(m, va, 4)
        assert out[at:at + 4] == raw_p0[at:at + 4], ('P0 semantic site changed', hex(va))

    proof.update(
        schema='Nuwa.P0VnopDispatch.v1',
        kernel_sha256=sha(out), source_sha256=sha(SOURCE.read_bytes()),
        observer_source=str(SOURCE.relative_to(ROOT)),
        builder_source='scripts/build-p0-vnop-dispatch-20261105.py',
        parent_candidate=dict(path='out/p0-native-restore-20261105-r1/kernel.macho',
                              sha256=P0_KERNEL_SHA),
        r3_delta=dict(
            purpose='把 r2 实机证实的「VNOP_READ 已进入未返回」下钻到 v_op 分派点 x8 与 vnop 返回码',
            design_reference='reports/vnop-suspect-and-gap-20261105/README.md 第五节',
            source_generation=str(SOURCE_GEN.relative_to(ROOT)),
            suspect_evidence=str(SUSPECT_EVIDENCE.relative_to(ROOT)),
            user_authorization='用户 2026-11-05 20:39「批准 继续直到下一轮实机录像确认」；'
                               '20:51「可以撤掉不需要的 hook」',
            withdrawn_hooks=[dict(address=hex(w['address']), native=w['native'],
                                  semantics=w['semantics'],
                                  reason='r2 实机结论已固化，撤掉以释放 cave 空间')
                             for w in WITHDRAWN],
            new_patch_sites=patches,
            cave_range=dict(file_offset=cave_lo, bytes=cave_hi - cave_lo),
            allowed_file_ranges=allowed,
            all_bytes_outside_declared_ranges_unchanged_vs_p0=True,
            p0_outside_cave_diff_words=len(outside),
            p0_outside_cave_diff=outside,
            field_visibility='FB03/FB06 在 CHECK10 实机作护栏出现并持续到末帧；'
                             'FB0F 在 CHECK8/CHECK10 记为已验证空白行位；FB07 在 r2 实机 00000000。'
                             '未引入任何首次使用的行号。',
            field_conflict_check=dict(n3_writers=3, n6_writers=2, n15_writers=3, n7_writers=1),
            decision_matrix=[
                dict(FB03='ENTR', FB06='x8 值', FB0F='GUAR',
                     verdict='blr x8 已分派且未返回；x8 给出 APFS vnop 目标地址'),
                dict(FB03='ENTR', FB06='GUAR', FB0F='GUAR',
                     verdict='卡在 _VNOP_READ 分派之前（uio_resid 检查或 v_op 表读取）'),
                dict(FB03='ENTR', FB06='x8 值', FB0F='w0 值',
                     verdict='vnop 已返回，卡点下移；配合 FB07 与 10 大阶段判读'),
                dict(FB03='EARL', verdict='len<0 早退路径阳性对照命中'),
                dict(FB03='EPIL', verdict='_vn_rdwr 正常 epilogue 阳性对照命中'),
            ],
            control_flow='5 个 b 到 cave 的观测挂点；各 hook 保存恢复 x0-x29/x30/NZCV、'
                         '重放被替换的原生指令、跳回下一条；不改原生错误分支',
            security_model_changed=False, stop_gate_added=False,
            repair_patches_removed=0, observations_added=5, observations_withdrawn=2,
            cave_budget=dict(total=trace.RETIRED_END - trace.START,
                             used=proof['code_bytes'],
                             headroom=trace.RETIRED_END - trace.START - proof['code_bytes']),
        ),
    )
    obs = proof['p0_delta']['three_class_inventory']['necessary_observation']
    for s in SITES:
        obs.append(dict(address=hex(s['address']), stage=s['name'],
                        field=s['field'], reason=s['role']))
    (work / 'kernel.macho').write_bytes(out)
    (work / 'kernel-proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    (work / 'build.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print('kernel', sha(out), 'bytes', len(out))
    print('new patch sites', len(patches), '| outside-cave diffs vs P0 r1', len(outside))
    print('cave', proof['code_bytes'], '/', trace.RETIRED_END - trace.START)
    return proof


def package(work, proof):
    fd = transport.ARTIFACT / 'build/FV/SILICIUM_UEFI.fd'
    shim = transport.ARTIFACT / 'shim/shim.bin'
    stock = native_path(transport.STOCK).read_bytes()
    assert [sha(p_.read_bytes()) for p_ in (fd, shim)] == [transport.FD_SHA, transport.SHIM_SHA]
    assert sha(stock) == transport.STOCK_SHA
    base = work / 'base.adt'
    base.write_bytes((PARENT / 'base.adt').read_bytes())
    launch = context.create(base, work / 'kernel.macho', fd, shim, work / 'launch')
    staging = work / 'fat'
    staging.mkdir()
    fatpath = work / 'payload.fat'
    menu = (PARENT / 'fat/unixnu.toml').read_text().replace('UFS-CHECK-4 r1', 'P0-VNOP-DISPATCH r3')
    assert 'P0-VNOP-DISPATCH r3' in menu
    run('mformat', '-C', '-F', '-T', '131072', '-v', 'NUWAXNU', '-N', '584E5558', '-i', fatpath, '::')
    for d in ('::/EFI', '::/EFI/UniXNU', '::/EFI/UniXNU/Payloads'):
        run('mmd', '-i', fatpath, d)
    for name, data, dest in [
        ('unixnu.toml', menu.encode(), '::/EFI/UniXNU/unixnu.toml'),
        ('kernel.macho', (work / 'kernel.macho').read_bytes(), '::/EFI/UniXNU/Payloads/kernel.macho'),
        ('kernel.macho.adt', (work / 'launch/kernel.macho.adt').read_bytes(),
         '::/EFI/UniXNU/Payloads/kernel.macho.adt'),
    ]:
        p_ = staging / name
        p_.write_bytes(data)
        os.utime(p_, (315532800, 315532800))
        run('mcopy', '-m', '-i', fatpath, p_, dest)
        back = staging / ('readback-' + name)
        run('mcopy', '-i', fatpath, dest, back)
        assert back.read_bytes() == data, ('FAT readback mismatch', name)
    fat = fatpath.read_bytes()
    envelope = transport.MAGIC + struct.pack('<IIQI28x', 1, 64, len(fat), zlib.crc32(fat)) + fat
    fw = shim.read_bytes() + fd.read_bytes()
    image = transport.compose(stock[:4096], fw, envelope, 3)
    transport.inspect_container(image, stock[:4096], fw, envelope, 3)
    path = work / 'boot-p0-vnop-dispatch-20261105-r3.img'
    path.write_bytes(image)
    proof.update(image_path=str(path), image_sha256=sha(image), image_bytes=len(image), launch=launch)
    (work / 'build.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print(path, sha(image))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--kernel-only', action='store_true')
    a = p.parse_args()
    proof = build(a.work.resolve())
    if not a.kernel_only:
        package(a.work.resolve(), proof)
