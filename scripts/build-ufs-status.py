"""Build and verify the read-only XNU UFS handoff survey in the proven iOS16 carrier."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import build_xnu_boot_package as package
import flush_trace_inputs as trace
import usb_ramdisk_package as transport
from ufs_status_context import API

ROOT = package.ROOT
SITE = 0xfffffff0076729e0
PARENT = '1449dc8b6b9b71345fa5f1731e85c12b0a8a46f9334e350a963fb86011aa17e4'
SOURCE = ROOT / 'package/ufs-r1/Status.S'


def build_kernel(work, source=SOURCE):
    parent = trace.read(trace.BASE / 'build.json')
    raw = (ROOT / parent['candidate']['path']).read_bytes()
    assert package.sha(raw) == PARENT
    trace.P.verify_bytes(parent, raw)
    builder = trace.builder()
    macho = builder.macho(raw)
    assert macho['symbols']['_bsd_init'] == SITE
    implementation = macho['symbols']['_ml_io_map_with_prot']
    code, symbols = trace.compile_code(source.read_text(), work)
    code = bytearray(code)
    assert trace.START == symbols['trace_1']
    assert trace.START + len(code) <= trace.RETIRED_END
    scratch = int(parent['probe']['symbols']['probe_scratch'], 16)
    pc = symbols['scratch_page']
    delta = (scratch >> 12) - (pc >> 12)
    assert -(1 << 20) <= delta < (1 << 20)
    struct.pack_into('<I', code, pc-trace.START,
                     0x90000009 | (delta & 3) << 29 | ((delta >> 2) & 0x7ffff) << 5)
    struct.pack_into('<I', code, symbols['scratch_offset']-trace.START,
                     0x91000129 | (scratch & 0xfff) << 10)
    call = symbols['map_call'] - trace.START
    code[call:call+4] = builder.branch(symbols['map_call'], implementation)
    if 'alloc_call' in symbols:
        table = macho['symbols']['__ZTV24IOBufferMemoryDescriptor'] + 16
        for slot, name in [(0x28,'__ZNK8OSObject7releaseEv'),
                           (0x98,'__ZN25IOGeneralMemoryDescriptor18getPhysicalSegmentEyPyj'),
                           (0x148,'__ZN24IOBufferMemoryDescriptor14getBytesNoCopyEv')]:
            assert struct.unpack_from('<Q', raw, builder.backed(macho,table+slot))[0] == macho['symbols'][name]
        task = macho['symbols']['_kernel_task']
        pc = symbols['task_page']
        delta = (task >> 12) - (pc >> 12)
        assert -(1 << 20) <= delta < (1 << 20) and task % 8 == 0
        struct.pack_into('<I',code,pc-trace.START,0x90000009 | (delta & 3)<<29 | ((delta>>2)&0x7ffff)<<5)
        struct.pack_into('<I',code,symbols['task_load']-trace.START,0xf9400120 | ((task & 4095)//8)<<10)
        pc = symbols['alloc_call']
        code[pc-trace.START:pc-trace.START+4] = builder.branch(pc,macho['symbols']['__ZN24IOBufferMemoryDescriptor17inTaskWithOptionsEP4taskjmm'])
    offset = builder.backed(macho, trace.START, len(code))
    site = builder.backed(macho, SITE)
    assert raw[site:site+4].hex() == 'f9603914'
    patched = bytearray(raw)
    patched[offset:offset+len(code)] = code
    patched[site:site+4] = builder.branch(SITE, trace.START)
    (work/'resolved.bin').write_bytes(code)
    (work/'symbols.json').write_text(json.dumps(symbols))
    kernel = work/'kernel.macho'
    kernel.write_bytes(patched)
    return kernel, dict(parent_sha256=PARENT, site=hex(SITE), map_function=hex(implementation),
                        source_sha256=package.sha(source.read_bytes()), code_sha256=package.sha(code),
                        code_bytes=len(code), scratch=hex(scratch), kernel_sha256=package.sha(patched))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--revision', type=int, choices=(1, 2), default=1)
    parser.add_argument('--smmu', action='store_true')
    parser.add_argument('--context-bank', action='store_true')
    parser.add_argument('--dma-buffer', action='store_true')
    parser.add_argument('--queue-dry', action='store_true')
    parser.add_argument('--queue-cycle', action='store_true')
    parser.add_argument('--queue-bind', action='store_true')
    parser.add_argument('--nop', action='store_true')
    parser.add_argument('--power-read', action='store_true')
    parser.add_argument('--layout-read', action='store_true')
    args = parser.parse_args()
    if sum((args.context_bank, args.smmu, args.dma_buffer, args.queue_dry, args.queue_cycle, args.queue_bind, args.nop, args.power_read, args.layout_read)) > 1:
        parser.error('select one survey')
    work = args.work.resolve()
    assert work.is_relative_to(ROOT/'out') and not work.exists()
    source = SOURCE if args.revision == 1 else SOURCE.with_name("Status-r2.S")
    title = f'NUWA UFS-R1 r{args.revision}'
    filename = f'boot-ufs-r1-r{args.revision}.img'
    entry = 'XNU read-only UFS host status'
    if args.smmu:
        source = SOURCE.with_name('Smmu.S')
        title = 'NUWA UFS-R2 r1'
        filename = 'boot-ufs-r2-r1.img'
        entry = 'XNU read-only UFS DMA stream survey'
    if args.context_bank:
        source = SOURCE.with_name('Context.S')
        title = 'NUWA UFS-R3 r1'
        filename = 'boot-ufs-r3-r1.img'
        entry = 'XNU read-only UFS context bank'
    if args.dma_buffer:
        source = SOURCE.with_name('Dma.S')
        title = 'NUWA UFS-R4 r1'
        filename = 'boot-ufs-r4-r1.img'
        entry = 'XNU UFS DMA buffer admission'
    if args.queue_dry:
        source = SOURCE.with_name('QueueDry.S')
        title = 'NUWA UFS-R5 r1'
        filename = 'boot-ufs-r5-r1.img'
        entry = 'XNU UFS queue and read descriptor admission'
    if args.queue_cycle:
        source = SOURCE.with_name('QueueCycle.S')
        title = 'NUWA UFS-R6 r1'
        filename = 'boot-ufs-r6-r1.img'
        entry = 'XNU UFS legacy list stop and restore'
    if args.queue_bind:
        source = SOURCE.with_name('QueueBind.S')
        title = 'NUWA UFS-R7 r1'
        filename = 'boot-ufs-r7-r1.img'
        entry = 'XNU stopped transfer-list base round trip'
    if args.nop:
        source = SOURCE.with_name('Nop.S')
        title = 'NUWA UFS-R8 r1'
        filename = 'boot-ufs-r8-r1.img'
        entry = 'XNU UFS LU0 read ladder'
    if args.power_read:
        source = SOURCE.with_name('PowerRead.S')
        title = 'NUWA UFS-R9 r1'
        filename = 'boot-ufs-r9-r1.img'
        entry = 'XNU UFS power mode and LU0 read'
    if args.layout_read:
        source = SOURCE.with_name('LayoutRead.S')
        title = 'NUWA UFS-R10 r1'
        filename = 'boot-ufs-r10-r1.img'
        entry = 'XNU UFS physical root-window layout'
    kernel, proof = build_kernel(work, source)
    fd = transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd'
    shim = transport.ARTIFACT/'shim/shim.bin'
    stock = transport.STOCK.read_bytes()
    assert [package.sha(p.read_bytes()) for p in (fd, shim)] == [package.FD_SHA, package.SHIM_SHA]
    assert package.sha(stock) == transport.STOCK_SHA
    disk = ROOT/'out/root-mainline-v29/restore/restore-payload.bin'
    base = ROOT/'out/exec-probe46-progress/launch/base.adt'
    report = ROOT/'reports'/work.name
    report.mkdir(exist_ok=True)
    launch = work/'launch'
    validator = API
    context_script = 'ufs_status_context.py'
    if args.dma_buffer:
        from ufs_dma_context import API as validator
        context_script = 'ufs_dma_context.py'
    if args.queue_dry:
        from ufs_queue_context import API as validator
        context_script = 'ufs_queue_context.py'
    if args.queue_cycle:
        from ufs_cycle_context import API as validator
        context_script = 'ufs_cycle_context.py'
    if args.queue_bind:
        from ufs_bind_context import API as validator
        context_script = 'ufs_bind_context.py'
    if args.nop:
        from ufs_nop_context import API as validator
        context_script = 'ufs_nop_context.py'
    if args.power_read:
        from ufs_power_context import API as validator
        context_script = 'ufs_power_context.py'
    if args.layout_read:
        from ufs_layout_context import API as validator
        context_script = 'ufs_layout_context.py'
    subprocess.run([sys.executable, '-B', str(ROOT/'scripts'/context_script),
                    '--base-adt', base, '--kernel', kernel, '--fd', fd, '--shim', shim,
                    '--ramdisk', disk, '--work', launch, '--output', report/'launch.json',
                    '--root-output', report/'root-policy.json'], check=True)
    adt = (launch/'kernel.macho.adt').read_bytes()
    validator.validate(adt, kernel, fd, shim, disk, (launch/'nonce.bin').read_bytes())
    package.UNIXNU_TOML = package.UNIXNU_TOML.replace('NUWA XNU FIRST ENTRY - ANALYSIS BUILD',title).replace('Enter UniXNU iOS 16 kernel (analysis prelink)',entry).replace('args = "-v"', 'args = "-v rd=md0"\ninitrd = "Payloads/root-restore.apfs"')
    staging = work/'fat'
    staging.mkdir()
    fatpath = work/'payload.fat'
    package.build_fat(staging, fatpath, adt, kernel.read_bytes(), disk.read_bytes())
    fat = fatpath.read_bytes()
    envelope = transport.MAGIC + struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat)) + fat
    firmware = shim.read_bytes() + fd.read_bytes()
    image = transport.compose(stock[:4096], firmware, envelope, 3)
    path = work/filename
    path.write_bytes(image)
    transport.inspect_container(path.read_bytes(),stock[:4096],firmware,envelope,3)
    proof.update(image_path=path.relative_to(ROOT).as_posix(), image_bytes=len(image),
                 image_sha256=package.sha(image), adt_sha256=package.sha(adt),
                 fat_sha256=package.sha(fat), device_run=False)
    (report/'build.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(path, proof['image_sha256'])


if __name__ == '__main__':
    main()
