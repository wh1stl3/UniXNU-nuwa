"""P0 r2：在 P0 原生恢复候选上追加 VNOP_READ 入口 / 汇合点配对观测。

在 WSL Ubuntu-22.04 的 python3 下运行：
  python3 scripts/build-p0-vnop-pair-20261105.py --work out/p0-vnop-pair-20261105-r2

复用 P0 构建链（11 点真原生恢复 + 10 大阶段 + 6 功能件 + FB07 MAC-read 标记），
只新增 2 个挂点与 2 个 hook。不引入 permissive 替身、不改安全模型、不加停机门。
不操作设备、不提交 git。
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
P0_DIR = ROOT / 'out/p0-native-restore-20261105-r1'
P0_KERNEL = ROOT / 'out/p0-native-restore-20261105-r1/kernel.macho'
PARENT = ROOT / 'out/ufs-check-4-r1-clean'
SOURCE = ROOT / 'package/kernel-mainline/CoarseStages-p0-vnop-pair-r2.S'
SOURCE_GEN = ROOT / 'reports/p0-vnop-pair-20261105-r2/source-generation.json'
HYPOTHESIS = ROOT / 'reports/apfs-vs-hfs-stack-20261105/evidence.json'

SOURCE_SHA = '23743213d7a490b281ab5ef2b04bd776c85d354fa3dfd09d3ad5f91016d24dff'
P0_KERNEL_SHA = 'ce75992b9b1e7ef6755a2c0b1be5bc57a47c59052161d7420de3f6e75e4a3d1a'

RESUME_ENTRY = 0xfffffff007466b14
RESUME_JOIN = 0xfffffff007466b28
SITES = (
    dict(name='p0_vnop_read_entry', address=0xfffffff007466b10,
         native='e3030091', native_semantics='mov x3,sp',
         field_n=3, field_label='FB03', role='VNOP_READ 入口到达'),
    dict(name='p0_join_point', address=0xfffffff007466b24,
         native='f40300aa', native_semantics='mov x20,x0',
         field_n=6, field_label='FB06', role='共同汇合点 w0'),
)
NEW_TARGETS = dict(p0_vnop_read_resume=RESUME_ENTRY, p0_join_resume=RESUME_JOIN)


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

# 新 hook 用 .jump <target>；把两个 resume 绝对地址注入 P0 的 targets 字典。
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
    assert sha(P0_KERNEL.read_bytes()) == P0_KERNEL_SHA, 'P0 kernel SHA changed'

    # 第一步：跑 P0 构建链（新源码已包含 2 个 hook，但尚未挂到内核上）。
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
    # cave 允许范围要覆盖 P0 与 CHECK10 的 cave 长度（含残留字节）。
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
                            symbol=s['name'], role='vnop-read-pair-observation',
                            field=s['field_label']))
        proof['changes'].append(dict(address=hex(va), offset=at,
                                     before=s['native'], after=after.hex(),
                                     reason='P0 r2 %s (%s)' % (s['role'], s['field_label'])))

    # 相对 P0 内核：差异必须全部落在 cave 范围 + 2 个新挂点。
    allowed = [(cave_lo, cave_hi)] + [(p['file_offset'], p['file_offset'] + 4) for p in patches]
    check = bytearray(out)
    for lo, hi in allowed:
        check[lo:hi] = raw_p0[lo:hi]
    assert check == raw_p0, 'bytes changed outside declared ranges vs P0'
    outside = []
    for pos in range(0, min(len(raw_p0), len(out)), 4):
        if cave_lo <= pos < cave_hi:
            continue
        if raw_p0[pos:pos + 4] != out[pos:pos + 4]:
            outside.append(dict(file_offset=pos, p0=raw_p0[pos:pos + 4].hex(),
                                r2=out[pos:pos + 4].hex()))
    assert {x['file_offset'] for x in outside} == {p['file_offset'] for p in patches}, \
        ('unexpected P0->r2 outside-cave diff', outside[:8])

    # 原生关键路径仍与 P0 一致（确认没碰 MAC / 恢复点）。
    for va in (0xfffffff0074669c8, 0xfffffff0074669cc, 0xfffffff00769bf90,
               0xfffffff00769bf94, 0xfffffff00769d110, 0xfffffff007466ad0):
        at = b.backed(m, va, 4)
        assert out[at:at + 4] == raw_p0[at:at + 4], ('P0 semantic site changed', hex(va))

    proof.update(
        schema='Nuwa.P0VnopPair.v1',
        kernel_sha256=sha(out), source_sha256=sha(SOURCE.read_bytes()),
        observer_source=str(SOURCE.relative_to(ROOT)),
        builder_source='scripts/build-p0-vnop-pair-20261105.py',
        parent_candidate=dict(path='out/p0-native-restore-20261105-r1/kernel.macho',
                              sha256=P0_KERNEL_SHA),
        r2_delta=dict(
            purpose='在 P0 上加 VNOP_READ 入口/汇合点配对观测，区分「后端未返回」与「MAC-read 直跳汇合点」',
            design_reference='reports/apfs-vs-hfs-stack-20261105/README.md 4.4',
            source_generation=str(SOURCE_GEN.relative_to(ROOT)),
            hypothesis_evidence=str(HYPOTHESIS.relative_to(ROOT)),
            user_authorization='用户 2026-11-05 明确要求「在当前实机候选上加这轮观测 出新镜像」',
            new_patch_sites=patches,
            cave_range=dict(file_offset=cave_lo, bytes=cave_hi - cave_lo),
            allowed_file_ranges=allowed,
            all_bytes_outside_declared_ranges_unchanged_vs_p0=True,
            p0_outside_cave_diff_words=len(outside),
            p0_outside_cave_diff=outside,
            field_visibility='FB03/FB06 在 CHECK10 实机作护栏出现并持续到末帧，行位可见性已验证；'
                             'P0 源码中这两个编号无写入源',
            field_conflict_check=dict(n3_writers=1, n6_writers=1, n7_writers=1),
            decision_matrix=[
                dict(FB03='出现', FB06='出现', verdict='VNOP_READ 已调用且返回，卡点下移'),
                dict(FB03='出现', FB06='空白', verdict='VNOP_READ 已进入但未返回，后端/完成链卡住'),
                dict(FB03='空白', FB06='出现', verdict='直跳汇合点，VNOP_READ 未执行；结合 FB07 判 MAC errno'),
                dict(FB03='空白', FB06='空白', verdict='未到 0x7466B10，卡在 MAC-read 或更前'),
            ],
            control_flow='新增 2 个 b 到 cave 的观测挂点；各 hook 保存恢复 x0-x29/x30/NZCV、'
                         '重放被替换的原生指令、跳回下一条；不改原生错误分支',
            security_model_changed=False, stop_gate_added=False,
            repair_patches_removed=0, observations_added=2),
    )
    obs = proof['p0_delta']['three_class_inventory']['necessary_observation']
    for s in SITES:
        obs.append(dict(address=hex(s['address']), stage=s['name'],
                        field=s['field_label'], reason=s['role']))
    (work / 'kernel.macho').write_bytes(out)
    (work / 'kernel-proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    (work / 'build.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print('kernel', sha(out), 'bytes', len(out))
    print('new patch sites', len(patches), '| outside-cave diffs vs P0', len(outside))
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
    menu = (PARENT / 'fat/unixnu.toml').read_text().replace('UFS-CHECK-4 r1', 'P0-VNOP-PAIR r2')
    assert 'P0-VNOP-PAIR r2' in menu
    run('mformat', '-C', '-F', '-T', '131072', '-v', 'NUWAXNU', '-N', '584E5558', '-i', fatpath, '::')
    for d in ('::/EFI', '::/EFI/UniXNU', '::/EFI/UniXNU/Payloads'):
        run('mmd', '-i', fatpath, d)
    for name, data, dest in [
        ('unixnu.toml', menu.encode(), '::/EFI/UniXNU/unixnu.toml'),
        ('kernel.macho', (work / 'kernel.macho').read_bytes(), '::/EFI/UniXNU/Payloads/kernel.macho'),
        ('kernel.macho.adt', (work / 'launch/kernel.macho.adt').read_bytes(),
         '::/EFI/UniXNU/Payloads/kernel.macho.adt'),
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
    path = work / 'boot-p0-vnop-pair-20261105-r2.img'
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
