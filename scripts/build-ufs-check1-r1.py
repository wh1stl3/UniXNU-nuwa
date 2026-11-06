"""Bind the exact CI NativeUfs objects to the qualified iOS16 carrier and package it.

The CI source kernel and this donor-prelinked boot carrier are distinct outputs.
No physical root installation or device action is performed by this builder.
"""
import argparse
import importlib.util
import json
import struct
import zlib
from pathlib import Path

import build_xnu_boot_package as package
import flush_trace_inputs as trace
import nuwa_launch_context as context
import ufs_carrier_object_link as overlay
import usb_ramdisk_package as transport

ROOT = trace.R
PARENT_SHA = '1449dc8b6b9b71345fa5f1731e85c12b0a8a46f9334e350a963fb86011aa17e4'
SITE = 0xfffffff0078e331c
SOURCE = ROOT/'package/kernel-mainline/CoarseStages-ufs-check-r1.S'


def adr(pc, target, register):
    distance = target-pc
    assert -(1 << 20) <= distance < (1 << 20)
    return struct.pack('<I', 0x10000000 | (distance & 3) << 29 |
                       ((distance >> 2) & 0x7ffff) << 5 | register)


def symbols(path):
    lines = overlay.run('llvm-nm', '--defined-only', overlay.linux(path)).decode().splitlines()
    return {line.split()[2]: int(line.split()[0], 16)+overlay.BIAS
            for line in lines if len(line.split()) == 3}


def compile_observer(work, targets):
    display = (ROOT/'package/ufs-r1/Status-r2.S').read_text().split('\ndraw:\n')[1]
    display = display.replace('scratch_page:\n    adrp x9,.\nscratch_offset:\n    add x9,x9,#0',
                              '    .addr x9,scratch').replace('add x0,x0,#0x100', 'add x0,x0,#0xb00')
    display = display.replace('add x10,x10,#384', 'add x10,x10,#1,lsl #12\n    add x10,x10,#256').replace('cmp x11,#4096', 'mov x12,#5504\n    cmp x11,x12')
    source = SOURCE.read_text()+'\ndraw:\n'+display
    lines = []
    fixups = []
    for line in source.splitlines():
        instruction = line.strip().split()
        if instruction and instruction[0] in ('.call', '.jump', '.addr'):
            label = 'fixup_'+str(len(fixups))
            fixups.append((label, instruction[0], instruction[1]))
            lines.extend((label+':', '    b .'))
            if instruction[0] == '.addr' and instruction[1].split(',')[1] == 'pmgr_vtable':
                lines.extend(['    nop']*3)
            elif instruction[0] == '.addr' and instruction[1].split(',')[1] in ('rootvnode','rootdev','vnop_lookup_desc'):
                lines.append('    nop')
        else:
            lines.append(line)
    code, local = trace.compile_code('\n'.join(lines)+'\n', work/'observer')
    code = bytearray(code)
    for label, kind, operand in fixups:
        pc = local[label]
        if kind == '.addr':
            register, name = operand.split(',')
            word = (b'' if name in ('rootvnode','rootdev','vnop_lookup_desc') else adr(pc, targets[name], int(register[1:]))) if name != 'pmgr_vtable' else b''.join(struct.pack('<I', (0xd2800000 if j == 0 else 0xf2800000) | j << 21 | ((targets[name] >> (j*16)) & 65535) << 5 | int(register[1:])) for j in range(4))
            if name in ('rootvnode','rootdev','vnop_lookup_desc'):
                reg = int(register[1:]); target = targets[name]
                delta = ((target & ~4095) - (pc & ~4095)) >> 12
                assert -(1 << 20) <= delta < (1 << 20)
                word = struct.pack('<II',0x90000000 | (delta & 3) << 29 | ((delta >> 2) & 0x7ffff) << 5 | reg,
                    0x91000000 | (target & 4095) << 10 | reg << 5 | reg)
        else:
            word = trace.builder().branch(pc, targets[operand])
            if kind == '.call':
                word = struct.pack('<I', int.from_bytes(word, 'little') | 0x80000000)
        code[pc-trace.START:pc-trace.START+len(word)] = word
    assert trace.START+len(code) <= trace.RETIRED_END
    return code, local


def build_kernel(work, artifact, linker):
    work.mkdir(parents=True, exist_ok=False)
    archive_audit = json.loads((artifact/'reports/ramblock-archive/audit.json').read_bytes())
    link_audit = json.loads((artifact/'reports/ramblock-link/audit.json').read_bytes())
    contract = json.loads((ROOT/'config/ramblock-ios16-link-contract.json').read_bytes())
    assert archive_audit['passed'] and link_audit['passed'] and link_audit['final_source_link']
    for name in ('compile', 'runtime', 'route', 'metadata'):
        pinned = contract['ufs_'+name+'_patch']
        assert archive_audit['ufs_provider'][name+'_patch'] == pinned
        assert package.sha((ROOT/pinned['path']).read_bytes()) == pinned['sha256']
    assert link_audit['contract_sha256'] == package.sha((ROOT/'config/ramblock-ios16-link-contract.json').read_bytes())
    source_kernel = artifact/'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped'
    assert package.sha(source_kernel.read_bytes()) == link_audit['kernel_sha256']
    assert package.sha((artifact/archive_audit['archive']).read_bytes()) == archive_audit['archive_sha256']
    parent = trace.read(trace.BASE/'build.json')
    raw = (ROOT/parent['candidate']['path']).read_bytes()
    assert package.sha(raw) == PARENT_SHA
    trace.P.verify_bytes(parent, raw)
    builder = trace.builder()
    macho = builder.macho(raw)
    assert macho['symbols']['_IOFindBSDRoot'] == SITE
    verified = json.loads((artifact/'reports/verified-ufs/audit.json').read_bytes())
    assert verified['passed'] and verified['verified_root_enabled'] and verified['inherited_vtable_verified']
    assert verified['contract_sha256'] == package.sha((ROOT/'config/ufs-ios16-verified-root-ci.json').read_bytes())
    verified_archive = artifact/'build/verified-ufs/libNativeUfs.verified.a'
    assert package.sha(verified_archive.read_bytes()) == verified['archive_sha256']
    objects = [artifact/'build/verified-ufs'/name for name in ('NativeUfs.late.o', 'NativeUfsLateInit.o', 'verified_root.o', 'xnu_crypto.o', 'NativeUfsRootAuth.o', 'NuwaUfsReadProbe.o')]
    for obj in objects:
        assert package.sha(obj.read_bytes()) == verified['objects'][obj.name]
        archived = overlay.run('llvm-ar', 'p', overlay.linux(verified_archive), obj.name)
        assert archived == obj.read_bytes(), obj.name
    policy = ROOT/'out/ufs-policy-storage-r1/CompactRootPolicy.o'
    policy_audit = json.loads((policy.parent/'compact-link.json').read_bytes())
    assert policy_audit['passed'] and package.sha(policy.read_bytes()) == policy_audit['compact_object_sha256']
    objects.append(policy)
    chunks = overlay.link(raw, objects, work/'linked', linker, '_native_ufs_register_late')
    linked_symbols = symbols(work/'linked/linked-0.macho')
    text_start = min(address for (seg, sec), (address, data) in chunks.items() if seg == '__TEXT')
    const_start = min(address for (seg, sec), (address, data) in chunks.items() if seg == '__DATA_CONST')
    data_start = min(address for (seg, sec), (address, data) in chunks.items() if seg == '__DATA')
    end = (max(address+len(data) for address, data in chunks.values())+4095) & ~4095
    coarse_state = end
    end += 4096  # Dedicated zero-initialized RW/NX first-visit latches.
    targets = dict(linked_symbols)
    storage_load = [v for k, v in macho['symbols'].items() if 'OSKext' in k and 'loadKextWithIdentifierEPKc' in k]
    assert len(storage_load) == 1
    targets['storage_load'] = storage_load[0]
    targets.update(scratch=int(parent['probe']['symbols']['probe_scratch'], 16),
                   old_end=0xfffffff0084ea000, old_data=0xfffffff0084e7000,
                   driver_text=text_start, driver_const=const_start, driver_data=data_start,
                   validate_compare=0xfffffff0084e5714, install_compare=0xfffffff0084e576c,
                   old_rx=0xfffffff0084e574c, old_rw=0xfffffff0084e5758,
                   old_set_leaf=0xfffffff0084e5760, root_resume=SITE+4)
    targets.update(exec_entry_old=0xfffffff0084da038,exec_namei_target=0xfffffff0084ce804,exec_namei_resume=0xfffffff00769cf54,exec_lookup_old=0xfffffff00746c228,exec_apfs_entry_old=0xfffffff0051a1f6c,vnop_lookup_desc=0xfffffff0079fdbb0,exec_vnop_return_old=0xfffffff007441330,exec_vnop_zero=0xfffffff0074414a8,exec_namei_enter_old=0xfffffff0074401c8,exec_apfs_call1_target=0xfffffff0051b5478,exec_apfs_return1_zero=0xfffffff0051a22dc,exec_apfs_return1_error=0xfffffff0051a26e4,exec_apfs_call2_target=0xfffffff005196680,exec_apfs_return2_zero=0xfffffff0051a2340,exec_apfs_return2_error=0xfffffff0051a23f8,exec_apfs_locked_old=0xfffffff0051a2280,exec_apfs_lock_old=0xfffffff00525ec64,exec_lookup_zero=0xfffffff007440500,
        coarse_state=coarse_state,
        root_wait_resume=0xfffffff0078e37ac, root_wait_target=0xfffffff0078652c8,
        rootvnode=macho['symbols']['_rootvnode'], rootdev=macho['symbols']['_rootdev'],
        root_auth_zero=0xfffffff0076732f8, root_auth_resume=0xfffffff007673418,
        root_return_zero=0xfffffff0076730cc, root_return_resume=0xfffffff00767309c,
        mount_return_zero=0xfffffff007673114, mount_return_resume=0xfffffff0076730ec,
        init_entry_resume=0xfffffff00769d2a8, init_loaded_resume=0xfffffff007673570, el0_resume=0xfffffff0073c3868)
    assert targets['root_wait_target'] == macho['symbols']['__ZN9IOService14waitForServiceEP12OSDictionaryP13mach_timespec']
    import audit_ios16_pmgr as pmgr
    targets.update(pmgr.audit(raw, work/'pmgr-abi.json'))
    targets.update(s_query_before_target=0xfffffff00523561c,n_read_lock=0xfffffff00525ec64,n_neighbor_after_next=0xfffffff005234d64,n_neighbor_error=0xfffffff005234ec8,n_node_release=0xfffffff005240cb4,n_release_after_next=0xfffffff005234d78,s_query_after_target=0xfffffff0051f7270,s_query_after_branch=0xfffffff0051f75b0)
    targets['ufs_probe_bind']=linked_symbols['_nuwa_ufs_probe_bind']
    code, local = compile_observer(work, targets)
    assert len(code) <= trace.RETIRED_END-trace.START, "Observer exceeds retired code cave"
    segment = macho['segments'][-1]
    assert segment['name'] == '__NUWA_PROBE' and segment['fileoff']+segment['filesize'] == len(raw)
    assert segment['va']+segment['size'] <= text_start < const_start < data_start < end
    assert end-segment['va'] < 0x100000 and segment['va'] >> 21 == (end-1) >> 21
    patched = bytearray(raw)+bytes(segment['fileoff']+end-segment['va']-len(raw))
    for key, (address, data) in chunks.items():
        at = segment['fileoff']+address-segment['va']
        assert at >= len(raw) and not any(patched[at:at+len(data)])
        patched[at:at+len(data)] = data
    changes = []

    def replace(address, before, after, reason):
        offset = builder.backed(macho, address, len(after))
        assert raw[offset:offset+len(after)] == before, (hex(address), reason)
        patched[offset:offset+len(after)] = after
        changes.append(dict(address=hex(address), offset=offset, before=before.hex(), after=after.hex(), reason=reason))

    replace(0xfffffff00769d4e0, bytes.fromhex('edf73814'), bytes.fromhex('ff8302d1'), 'retire old at_path entry drawing; native stack allocation')
    replace(SITE, bytes.fromhex('ffc302d1'), builder.branch(SITE, trace.START), 'BSD root selector observer')
    replace(0xfffffff0084e56a0, bytes.fromhex('144b0210'), adr(0xfffffff0084e56a0, end, 20), 'mapped end')
    for address, name, before in ((0xfffffff0084e5710, 'validate_increment', 'f7064091'),
                                   (0xfffffff0084e5768, 'install_increment', 'f7064091'),
                                   (0xfffffff0084e5740, 'map_permissions', '0cc60010')):
        replace(address, bytes.fromhex(before), builder.branch(address, local[name]), name)
    for address, before, name in (
        (0xfffffff0078e37a8, 'c806fe97', 'root_wait'),
        (0xfffffff007673098, 'a0010034', 'root_return'),
        (0xfffffff0076732f4, '20090035', 'root_auth'),
        (0xfffffff0076730e8, '76653914', 'mount_return'),
        (0xfffffff00769d2a4, '44f83814', 'init_entry'),
        (0xfffffff00767356c, '282100f0', 'init_loaded'),
        (0xfffffff0073c3864, 'f30303aa', 'el0'),
        (0xfffffff00769d624, 'c0035fd6', 'exec_result'),
        (0xfffffff00769ce3c, '7ff43814', 'exec_entry'),
        (0xfffffff00769bdd8, '8bca3814', 'exec_namei'),
        (0xfffffff007441328, 'c0ab0094', 'exec_lookup'),
        (0xfffffff0051a1f68, 'ff0305d1', 'exec_apfs_entry'),
        (0xfffffff00769bdd4, 'fd90f697', 'exec_namei_enter'),
        (0xfffffff0051a233c, 'e0050035', 'exec_apfs_return2'),
        (0xfffffff0084db290, '00000014', 'exec_hold'),
        (0xfffffff0051f7268, 'edf80094', 's_query_before'),
        (0xfffffff0051f726c, '201a0034', 's_query_after'),
        (0xfffffff00744132c, 'e00b0034', 'exec_vnop_return')):
        replace(address, bytes.fromhex(before), builder.branch(address, local['coarse_'+name]),
                'first-visit coarse milestone: '+name)
    assert raw[builder.backed(macho, 0xfffffff0046fe7a4, 4):builder.backed(macho, 0xfffffff0046fe7a4, 4)+4] == bytes.fromhex('f50300f9')
    # Reuse existing first-panic tile: red 1024x64 banner at (0,128).
    # No new panic hook, polling, allocation, or normal-path framebuffer writes.
    for address, before, after in (
        (0xfffffff0084e51cc, 0xd280420b, 0xd280100b),
        (0xfffffff0084e51d4, 0x91060129, 0x91000129),
        (0xfffffff0084e51d8, 0x52801fec, 0x5280000c),
        (0xfffffff0084e51dc, 0x72bff28c, 0x72bfffeC),
        (0xfffffff0084e51e0, 0xd280040d, 0xd280080d),
        (0xfffffff0084e51e4, 0xd280060e, 0xd280400e),
        (0xfffffff0084e51f8, 0xd1060129, 0xd1400529)):
        replace(address, struct.pack('<I', before), struct.pack('<I', after), 'existing panic tile becomes red banner')
    offset = builder.backed(macho, trace.START, len(code))
    patched[offset:offset+len(code)] = code
    for offset in (32, 48):
        struct.pack_into('<Q', patched, segment['command_offset']+offset, end-segment['va'])
    candidate = work/'kernel.macho'
    candidate.write_bytes(patched)
    new_macho = builder.macho(patched)
    assert new_macho['segments'][:-1] == macho['segments'][:-1]
    assert patched[builder.backed(macho, macho['symbols']['_bsd_init']):][:4] == raw[builder.backed(macho, macho['symbols']['_bsd_init']):][:4]
    # Every virtual method resolves to its actual object definition or a bound
    # carrier implementation. Do not inherit the CI kernel's different addresses.
    spec = importlib.util.spec_from_file_location('link_contract', ROOT/'scripts/ci/build-ramblock-kernel.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    vtables = []
    for cls in ('NativeUfs', 'NativeUfsBlock'):
        methods = helper.vtable(objects[0], cls)
        assert len(methods) == (190 if cls == 'NativeUfsBlock' else 168), (cls, len(methods))
        base = linked_symbols['__ZTV'+str(len(cls))+cls]+16
        parent_class = 'IOService' if cls == 'NativeUfs' else 'IOBlockStorageDevice'
        parent_table = linked_symbols.get('__ZTV'+str(len(parent_class))+parent_class,
                                         macho['symbols'].get('__ZTV'+str(len(parent_class))+parent_class))
        assert parent_table is not None
        inherited = 0
        for i, name in enumerate(methods):
            actual = struct.unpack_from('<Q', patched, builder.backed(new_macho, base+i*8))[0]
            assert actual == linked_symbols[name], (cls, i, name)
            if not name.startswith(('__ZN'+str(len(cls))+cls, '__ZNK'+str(len(cls))+cls)):
                original = struct.unpack_from('<Q', raw, builder.backed(macho, parent_table+16+i*8))[0]
                assert actual == original, (cls, i, 'carrier parent virtual ABI')
                inherited += 1
        vtables.append(dict(classname=cls, slots=len(methods), inherited_carrier_slots=inherited))
    proof = dict(schema='nuwa.native-ufs-carrier.v1', parent_build=str(trace.BASE/'build.json'),
                 parent_sha256=PARENT_SHA, kernel_sha256=package.sha(patched), site=hex(SITE),
                 ci_source_kernel_sha256=link_audit['kernel_sha256'], ci_archive_sha256=archive_audit['archive_sha256'],
                 contract_sha256=link_audit['contract_sha256'],
                 source_sha256=package.sha(SOURCE.read_bytes()), code_bytes=len(code), changes=changes,
                 symbols=local, targets=targets, segment=segment, mapped_end=end, vtables=vtables,
                 chunks=[dict(segment=k[0], section=k[1], address=a, bytes=len(d), sha256=package.sha(d))
                         for k, (a, d) in chunks.items()],
                 objects=[dict(path=str(p), sha256=package.sha(p.read_bytes())) for p in objects],
                 device_run=False, root_mount=False, ci_source_kernel_is_boot_carrier=False, verified_ufs_archive_sha256=verified['archive_sha256'], policy=policy_audit, root_image_required=policy_audit['root_image_sha256'], deployment_preconditions_met=False, owner_root_binding_enabled=True, removed_observation=['GPT metadata polling', 'AMFI AON return hook', 'per-block timing and progress polling'])
    (work/'kernel-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    return candidate, proof


def make_package(work, kernel, proof):
    fd = transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd'
    shim = transport.ARTIFACT/'shim/shim.bin'
    stock = transport.STOCK.read_bytes()
    assert [package.sha(p.read_bytes()) for p in (fd, shim)] == [package.FD_SHA, package.SHIM_SHA]
    assert package.sha(stock) == transport.STOCK_SHA
    tree = context.parse((ROOT/'out/exec-probe46-progress/launch/base.adt').read_bytes())
    memory_map = context.find(tree, '/chosen/memory-map')
    memory_map['properties'] = [p for p in memory_map['properties'] if p[0] != 'RAMDisk']
    chosen = context.find(tree, '/chosen')
    assert not any(p[0] in ('root-matching','boot-uuid') for p in chosen['properties'])
    matching = (ROOT/'out/ufs-root-chain-r2/chosen-root-matching.bin').read_bytes()
    assert package.sha(matching) == '573b453c2217f68c5fdd692111b047141a1cb982f0700d5d93374e349306bc68'
    chosen['properties'].append(('root-matching', 0, matching))
    base = work/'base.adt' 
    base.write_bytes(context.encode(tree))
    launch = context.create(base, kernel, fd, shim, work/'launch')
    adt = (work/'launch/kernel.macho.adt').read_bytes()
    package.UNIXNU_TOML = package.UNIXNU_TOML.replace('NUWA XNU FIRST ENTRY - ANALYSIS BUILD', 'NUWA UFS-CHECK-1 r1').replace(
        'Enter UniXNU iOS 16 kernel (analysis prelink)', 'iOS16 authenticated UFS root').replace(
        'args = "-v"', 'args = "-v native-ufs-root=1"')
    staging = work/'fat'
    staging.mkdir()
    fatpath = work/'payload.fat'
    package.build_fat(staging, fatpath, adt, kernel.read_bytes(), None)
    fat = fatpath.read_bytes()
    envelope = transport.MAGIC+struct.pack('<IIQI28x', 1, 64, len(fat), zlib.crc32(fat))+fat
    firmware = shim.read_bytes()+fd.read_bytes()
    image = transport.compose(stock[:4096], firmware, envelope, 3)
    path = work/'boot-ufs-check-1-r1.img'
    path.write_bytes(image)
    transport.inspect_container(path.read_bytes(), stock[:4096], firmware, envelope, 3)
    proof.update(image_path=str(path), image_sha256=package.sha(image), image_bytes=len(image), launch=launch)
    (work/'build.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(path, proof['image_sha256'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--linker', type=Path, required=True)
    parser.add_argument('--kernel-only', action='store_true')
    args = parser.parse_args()
    work = args.work.resolve()
    assert work.is_relative_to(ROOT/'out')
    kernel, proof = build_kernel(work, args.artifact.resolve(), args.linker.resolve())
    if not args.kernel_only:
        make_package(work, kernel, proof)
