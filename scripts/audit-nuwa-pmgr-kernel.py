#!/usr/bin/env python3
"""Final PMGR link/startup ABI audit and bounded real-code execution.

No full IOKit model. Mode prefixes stop at OSKext load; lifecycle success is
explicitly not claimed. Outputs stay in the isolated build directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import importlib.util


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--python-tools', type=Path, required=True)
    a = p.parse_args()
    out = a.build.resolve()
    assert out.is_relative_to(ROOT / 'out')
    sys.path.insert(0, str(a.python_tools))
    import capstone as C
    import unicorn as U
    from unicorn import arm64_const as R
    B = load(ROOT / 'scripts/build-nuwa-pmgr-kernel.py', 'pmgr_kernel_build_helpers')
    P = load(ROOT / 'scripts/build-nuwa-platform-power.py', 'pmgr_kernel_provider_helpers')
    provenance = json.loads((out / 'provenance.json').read_text())
    old_renderer = json.loads((ROOT / 'out/pthread-renderer-20261112-r1/renderer-manifest.json').read_text())
    renderer_sources = old_renderer['source_provenance']
    for entry in [*renderer_sources.values(), old_renderer['font']]:
        assert sha(Path(entry['path']).read_bytes()) == entry.get('raw_sha256', entry.get('sha256'))
    assert sha((ROOT / 'scripts/build-nuwa-pmap-ret-diagnostic.py').read_bytes()) == '819a99e6da4796e45a25171b3f6b1e35535c7442d0e77c2ae915e28029bf0506'
    for key in ('native', 'native_map', 'prelink', 'archive', 'output', 'source', 'patch', 'isolated_source', 'provider_object', 'provider_report'):
        entry = provenance[key]
        assert sha(Path(entry['path']).read_bytes()) == entry['sha256'], key
    for entry in provenance['reused_link_inputs']:
        assert sha(Path(entry['path']).read_bytes()) == entry['sha256'], entry['path']
    final = (out / 'kernel.macho').read_bytes()
    pristine = (out / 'prelink.macho').read_bytes()
    native = (out / 'native.macho').read_bytes()
    ns = B.names(final)
    final_info = B.macho(final)
    symbol_command = next(at for cmd, at, _ in final_info['commands'] if cmd == 2)
    symoff, nsyms, stroff, _ = struct.unpack_from('<4I', final, symbol_command+8)
    local_names = {}
    for i in range(nsyms):
        ix, kind, _, _, address = struct.unpack_from('<IBBHQ', final, symoff+i*16)
        if kind & 0xe0 or not kind & 0x0e:
            continue
        name = final[stroff+ix:final.index(b'\0', stroff+ix)].decode()
        local_names.setdefault(name, set()).add(address)
    # ld localizes weak inline methods; these remain genuine N_SECT definitions.
    for name, addresses in local_names.items():
        if len(addresses) == 1:
            ns.setdefault(name, next(iter(addresses)))
    segments = B.macho(final)['segments']
    obj = Path(provenance['provider_object']['path']).read_bytes()
    P.verify_late(obj)
    late_info = B.macho(obj)
    init_section = next(s for seg in late_info['segments'] for s in seg['sections'] if s['name'] == '__mod_init_func')
    assert init_section['size'] == 0
    bindings = json.loads((out / 'original-bindings.json').read_text())
    assert len(bindings) == 8
    canonical = ROOT / 'out/nuwa-platform-power-20261113-r2'
    assert sha((canonical / 'libNuwaPlatformPower.a').read_bytes()) == '568885fd698489843701907e5d8216f3c9b377c678a2d6710bd8652bad93d29e'
    canonical_object = B.subprocess.check_output(['/usr/bin/llvm-ar', 'p', str(canonical / 'libNuwaPlatformPower.a'), 'original-bindings.o'])
    assert sha(canonical_object) == '98c02ab274fd83a6a90a7c61dde043a6d6ddf78380698844977cb0afa7e44e26'
    canonical_values = B.names(canonical_object)
    reviewed = json.loads((canonical / 'build-report.json').read_text())
    assert {n: hex(v) for n, v in canonical_values.items() if n in bindings} == reviewed['bindings']
    donor = Path(provenance['donor']['path']).read_bytes()
    _, donor_pmgr = B.module(donor, 'com.apple.driver.ApplePMGR')
    _, final_pmgr = B.module(final, 'com.apple.driver.ApplePMGR')
    for name, entry in bindings.items():
        target = int(entry['final_va'], 16)
        assert ns[name] == target
        seg, = [s for s in donor_pmgr['segments'] if s['name'] == entry['segment']]
        assert seg['va']+int(entry['offset'], 16) == int(entry['donor_va'], 16)
        assert int(entry['donor_va'], 16)+entry['slide'] == target
        assert any(s['va'] <= target < s['va']+s['size'] for s in final_pmgr['segments'])
        if seg['initprot'] & 4:
            assert B.read(final, target, 32) == B.read(donor, int(entry['donor_va'], 16), 32)
    # All 325 final slots must resolve to the exact object's relocated symbol.
    sym_at = next(at for cmd, at, _ in late_info['commands'] if cmd == 2)
    syms, count, strings, _ = struct.unpack_from('<4I', obj, sym_at+8)
    symbols = []
    for i in range(count):
        ix, kind, sect, desc, address = struct.unpack_from('<IBBHQ', obj, syms+i*16)
        symbols.append((obj[strings+ix:obj.index(b'\0', strings+ix)].decode(), address, kind))
    vtable = next(va for name, va, _ in symbols if name == '__ZTV17NuwaPlatformPower')
    relocation_names = {}
    for seg in late_info['segments']:
        for sec in seg['sections']:
            if not sec['va'] <= vtable < sec['va']+sec['size']:
                continue
            at, nreloc = struct.unpack_from('<2I', obj, sec['command_offset']+56)
            for i in range(nreloc):
                offset, bits = struct.unpack_from('<2I', obj, at+i*8)
                if bits >> 27 & 1 and bits >> 28 == 0 and bits >> 25 & 3 == 3:
                    relocation_names[sec['va']+offset] = symbols[bits & 0xffffff][0]
    table = ns['__ZTV17NuwaPlatformPower']+16
    slots = []
    for i in range(325):
        name = relocation_names[vtable+16+i*8]
        actual, = struct.unpack('<Q', B.read(final, table+i*8, 8))
        assert actual == ns[name], (i, name, hex(actual), hex(ns[name]))
        if i in (312, 313):
            assert '9ApplePMGR' in name
        elif 168 <= i <= 324:
            assert '17NuwaPlatformPower' in name
        elif i not in (0, 1, 7):
            inherited, = struct.unpack('<Q', B.read(final, ns['__ZTV6IOPMGR']+16+i*8, 8))
            assert actual == inherited, ('native IOPMGR slot', i)
        slots.append(dict(slot=i, symbol=name, target=hex(actual)))
    assert vtable+16+325*8 not in relocation_names
    initializer = ns[P.INIT_NAME]
    auto_initializers = []
    for seg in segments:
        for sec in seg['sections']:
            if sec['name'] == '__mod_init_func':
                values = struct.unpack('<'+'Q'*(sec['size']//8), B.read(final, sec['va'], sec['size']))
                auto_initializers.extend(values)
    assert initializer not in auto_initializers
    md = C.Cs(C.CS_ARCH_ARM64, C.CS_MODE_ARM)
    md.detail = True
    md.skipdata = True

    def disasm(address, size):
        return list(md.disasm(B.read(final, address, size), address))

    def lines(code):
        return [f'{x.address:#x}: {x.mnemonic} {x.op_str}' for x in code]

    def branch_target(ins):
        return ins.operands[0].imm & ((1 << 64)-1)

    def stub(address):
        code = disasm(address, 12)
        assert [x.mnemonic for x in code] == ['adrp', 'ldr', 'br']
        pointer = (code[0].operands[1].imm + code[1].operands[1].mem.disp) & ((1 << 64)-1)
        target, = struct.unpack('<Q', B.read(final, pointer, 8))
        return dict(stub=hex(address), pointer=hex(pointer), target=hex(target),
                    names=B.exports(final, B.macho(final)).get(target, []), instructions=lines(code))

    hook_name, = [n for n in ns if 'IOPlatformExpertDevice' in n and 'startIOServiceMatching' in n]
    hook = ns[hook_name]
    hook_code = disasm(hook, 0x90)
    callsite, = [x.address for x in hook_code if x.mnemonic == 'bl' and branch_target(x) == ns['_nuwa_pmgr_run']]
    all_pmgr_calls, all_init_calls = [], []
    for seg in segments:
        if not seg['initprot'] & 4 or not seg['filesize']:
            continue
        data = B.read(final, seg['va'], seg['filesize'])
        for offset in range(0, len(data)-3, 4):
            word, = struct.unpack_from('<I', data, offset)
            if word & 0xfc000000 != 0x94000000:
                continue
            immediate = word & 0x3ffffff
            if immediate & 0x2000000:
                immediate -= 0x4000000
            target = seg['va']+offset+immediate*4
            if target == ns['_nuwa_pmgr_run']:
                all_pmgr_calls.append(seg['va']+offset)
            if target == initializer:
                all_init_calls.append(seg['va']+offset)
    assert all_pmgr_calls == [callsite], all_pmgr_calls
    run_start = ns['_nuwa_pmgr_run']
    run_end = min(v for v in ns.values() if run_start < v and v < run_start+0x2000)
    assert len(all_init_calls) == 1 and run_start <= all_init_calls[0] < run_end
    # Preserve original executable bytes modulo the emitter's explicit pointer
    # bindings. This checks the final image, after renderer installation too.
    prelink = json.loads((out / 'prelink.json').read_text())
    previous = json.loads((ROOT / 'out/pthread-normal-prelink-20261112-r4/work/kernel/kernel.json').read_text())
    assert prelink['components'] == previous['components']
    assert prelink['slide'] == previous['slide']
    for binding in prelink['bindings']:
        at = B.backed_offset(segments, binding['new_site'], 8, len(final))
        assert struct.unpack_from('<Q', final, at)[0] == binding['new_target']
    exec_checks = []
    for identifier in ('com.apple.driver.ApplePMGR', 'com.apple.kec.pthread',
                       'com.apple.driver.AppleMobileFileIntegrity', 'com.apple.security.sandbox'):
        _, old_module = B.module(donor, identifier)
        _, new_module = B.module(final, identifier)
        total = 0
        for old_seg in old_module['segments']:
            if not old_seg['initprot'] & 4 or not old_seg['filesize']:
                continue
            new_seg, = [s for s in new_module['segments'] if s['name'] == old_seg['name']]
            expected = bytearray(B.read(donor, old_seg['va'], old_seg['filesize']))
            for binding in prelink['bindings']:
                if old_seg['va'] <= binding['site'] < old_seg['va']+old_seg['filesize']:
                    struct.pack_into('<Q', expected, binding['site']-old_seg['va'], binding['new_target'])
            assert B.read(final, new_seg['va'], new_seg['filesize']) == bytes(expected), identifier
            total += len(expected)
        exec_checks.append(dict(module=identifier, bytes=total, unchanged_except_declared_pointer_relocations=True))
    # Source-relative donor anchors are translated through actual module segment
    # placement; the report retains old/new addresses rather than assuming VAs.
    old_carrier = (ROOT / 'out/pthread-renderer-20261112-r1/renderer-baseline.macho').read_bytes()
    assert sha(old_carrier) == 'e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d'

    def va(old, owner):
        _, om = B.module(old_carrier, owner)
        _, nm = B.module(final, owner)
        seg, = [s for s in om['segments'] if s['va'] <= old < s['va']+s['size']]
        new, = [s for s in nm['segments'] if s['name'] == seg['name']]
        return new['va']+old-seg['va']

    sandbox, amfi = 'com.apple.security.sandbox', 'com.apple.driver.AppleMobileFileIntegrity'
    anchors = {}
    for name, old, owner, size in (
        ('sandbox_kmod_start', 0xfffffff0054ba258, sandbox, 0x120),
        ('sandbox_amfi_call', 0xfffffff0054bcd80, sandbox, 0x180),
        ('amfi_policy_entry', 0xfffffff004704320, amfi, 0xc0),
        ('amfi_policy_setup', 0xfffffff004703c54, amfi, 0x3c0),
        ('policy_callback', 0xfffffff004706f34, amfi, 0x60),
        ('pmgr_worker', 0xfffffff0046fe6cc, amfi, 0xc0),
        ('pmgr_wait', 0xfffffff0046fe730, amfi, 0xb0)):
        address = va(old, owner)
        anchors[name] = dict(old_va=hex(old), new_va=hex(address), module=owner, instructions=lines(disasm(address, size)))
    sandbox_stub = stub(va(0xfffffff0054e3ca4, sandbox))
    assert sandbox_stub['pointer'] == hex(va(0xfffffff005ef85b0, sandbox))
    assert int(sandbox_stub['target'], 16) == va(0xfffffff004704320, amfi)
    sandbox_entry, _ = B.module(final, sandbox)
    kmod_start, = struct.unpack('<Q', B.read(final, sandbox_entry['_PrelinkKmodInfo']+180, 8))
    assert kmod_start == va(0xfffffff0054ba258, sandbox)
    sandbox_start = disasm(kmod_start, 12)
    start_pointer = (sandbox_start[0].operands[1].imm + sandbox_start[1].operands[2].imm) & ((1 << 64)-1)
    actual_start, = struct.unpack('<Q', B.read(final, start_pointer, 8))
    assert actual_start == va(0xfffffff0054bcd80, sandbox)
    assert branch_target(disasm(actual_start+12, 4)[0]) == int(sandbox_stub['stub'], 16)
    assert branch_target(disasm(va(0xfffffff004704328, amfi), 4)[0]) == va(0xfffffff004703c54, amfi)
    policy_store = disasm(va(0xfffffff004703ed4, amfi), 12)
    assert [x.mnemonic for x in policy_store] == ['adrp', 'add', 'stp'], lines(policy_store)
    callback = (policy_store[0].operands[1].imm + policy_store[1].operands[2].imm) & ((1 << 64)-1)
    assert callback == va(0xfffffff004706f34, amfi)
    assert policy_store[2].operands[2].mem.disp == 0x50
    reg_call = disasm(va(0xfffffff004703fa4, amfi), 4)[0]
    assert reg_call.mnemonic == 'bl'
    policy_register = stub(branch_target(reg_call))
    assert '_mac_policy_register' in policy_register['names']
    callback_code = disasm(callback, 0x60)
    thread_calls = [x for x in callback_code if x.mnemonic == 'bl']
    thread_bindings = [stub(branch_target(x)) for x in thread_calls]
    assert any('_kernel_thread_start' in b['names'] for b in thread_bindings)
    worker_argument = disasm(va(0xfffffff004706f5c, amfi), 20)
    assert worker_argument[0].mnemonic == 'adrp' and worker_argument[1].mnemonic == 'add'
    worker = (worker_argument[0].operands[1].imm + worker_argument[1].operands[2].imm) & ((1 << 64)-1)
    assert worker == va(0xfffffff0046fe6cc, amfi)
    assert '_kernel_thread_start' in stub(branch_target(worker_argument[-1]))['names']
    wait_binding = stub(va(0xfffffff004717f9c, amfi))
    assert '__ZN9IOService22waitForMatchingServiceEP12OSDictionaryy' in wait_binding['names']
    source = Path(provenance['isolated_source']['path']).read_text()
    method = source.split('IOPlatformExpertDevice::startIOServiceMatching(void)', 1)[1].split('\n}', 1)[0]
    assert method.count('nuwa_pmgr_run(this);') == 1
    assert method.index('IOWorkLoop::workLoop()') < method.index('nuwa_pmgr_run(this);') < method.index('registerService();')
    provider_source = (ROOT / 'package/NuwaPlatformPower.cpp').read_text()
    assert 'getPlatform(' not in provider_source and 'IOService *publicationParent' in provider_source
    assert 'memcpy(&bound, reinterpret_cast<const char *>(nub) + 0x88' in provider_source
    source_snapshots = []
    for relative, first, last in (
        ('osfmk/kern/startup.c', 685, 795),
        ('pexpert/arm/pe_init.c', 390, 414),
        ('iokit/Kernel/IOStartIOKit.cpp', 135, 198),
        ('bsd/kern/bsd_init.c', 621, 634),
        ('security/mac_process.c', 194, 211),
        ('security/mac_policy.h', 5788, 5806)):
        path = B.TREE / '.cache/xnu-work' / relative
        text = path.read_text()
        source_snapshots.append(dict(path=str(path), sha256=sha(path.read_bytes()),
                                     lines=[f'{i}: {line}' for i, line in enumerate(text.splitlines(), 1) if first <= i <= last]))
    startup_text = (B.TREE / '.cache/xnu-work/osfmk/kern/startup.c').read_text()
    order = [startup_text.index(text) for text in ('PE_init_iokit();', 'mac_policy_initmach();',
             'OSKextRemoveKextBootstrap();', 'machine_lockdown();', 'PE_lockdown_iokit();', 'bsd_init();')]
    assert order == sorted(order)
    # Incremental real-code checks: no invented IOKit success stubs.
    halt, stack = 0x30000000, 0x30100000
    obs = ns['_nuwa_pmgr_observation']

    def machine():
        uc = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
        for seg in segments:
            if not seg['size']:
                continue
            first, last = seg['va'] & ~0xfff, (seg['va']+seg['size']+0xfff) & ~0xfff
            # Segments are page-aligned and disjoint. Map each extent once;
            # thousands of individual QEMU regions have unnecessary host cost.
            uc.mem_map(first, last-first)
            if seg['filesize']:
                uc.mem_write(seg['va'], final[seg['fileoff']:seg['fileoff']+seg['filesize']])
        uc.mem_map(halt, 0x1000)
        uc.mem_map(stack, 0x10000)
        uc.reg_write(R.UC_ARM64_REG_SP, stack+0xf000)
        uc.reg_write(R.UC_ARM64_REG_X30, halt)
        uc.reg_write(R.UC_ARM64_REG_X0, 0x12345678)  # borrowed, untouched before OSKext
        return uc

    cases = []
    uc = machine()
    for present, mode, prior_stage in ((False, 0, 0), (True, 0, 0), (True, 4, 0),
                                       (True, 1, 0), (True, 2, 0), (True, 3, 0), (True, 2, 4)):
        uc.mem_write(obs, bytes(128))
        uc.reg_write(R.UC_ARM64_REG_SP, stack+0xf000)
        uc.reg_write(R.UC_ARM64_REG_X30, halt)
        uc.reg_write(R.UC_ARM64_REG_X0, 0x12345678)
        uc.mem_write(obs, struct.pack('<Q', prior_stage))
        stopped = []

        def hook(uc, pc, size, _):
            if pc == ns['_PE_parse_boot_argn']:
                assert bytes(uc.mem_read(uc.reg_read(R.UC_ARM64_REG_X0), 10)) == b'nuwa-pmgr\0'
                uc.mem_write(uc.reg_read(R.UC_ARM64_REG_X1), struct.pack('<I', mode))
                uc.reg_write(R.UC_ARM64_REG_X0, int(present))
                uc.reg_write(R.UC_ARM64_REG_PC, uc.reg_read(R.UC_ARM64_REG_X30))
            elif pc == ns['_OSKextLoadKextWithIdentifier']:
                stopped.append('before_actual_OSKext_load')
                uc.emu_stop()
        handle = uc.hook_add(U.UC_HOOK_CODE, hook)
        uc.emu_start(run_start, halt, count=2000)
        uc.hook_del(handle)
        observation = struct.unpack('<16Q', bytes(uc.mem_read(obs, 128)))
        expected_load = present and mode in (1, 2, 3) and not prior_stage
        assert bool(stopped) == expected_load
        if expected_load:
            assert observation[0] == 1 and observation[15] == mode
        else:
            assert uc.reg_read(R.UC_ARM64_REG_PC) == halt and observation[0] == prior_stage
        cases.append(dict(kind='real entry instructions; boot-arg parser mocked; OSKext not executed',
                          present=present, mode=mode, prior_stage=prior_stage, observation=list(observation),
                          stopped=stopped or ['returned'], passed=True))
    # Execute the actual final vtable's slot-170 implementation to its panic.
    refusal, = struct.unpack('<Q', B.read(final, table+170*8, 8))
    uc.mem_write(obs, bytes(128))
    uc.reg_write(R.UC_ARM64_REG_SP, stack+0xf000)
    uc.reg_write(R.UC_ARM64_REG_X30, halt)
    stopped = []

    def panic_hook(uc, pc, size, _):
        if pc == ns['_panic']:
            stopped.append('actual_guard_reached_panic_entry')
            uc.emu_stop()
    uc.hook_add(U.UC_HOOK_CODE, panic_hook)
    uc.emu_start(refusal, halt, count=2000)
    observation = struct.unpack('<16Q', bytes(uc.mem_read(obs, 128)))
    assert stopped and observation[0] == 0x100+170 and observation[1] != 0
    cases.append(dict(kind='real slot170 refusal instructions to panic entry; not full mode3 lifecycle',
                      observation=list(observation), passed=True))
    # Final donor nub methods dispatch through the newly linked provider table.
    mock = 0x30200000
    uc.mem_map(mock, 0x40000)
    nub = mock+0x38000
    uc.mem_write(mock, struct.pack('<Q', table))
    uc.mem_write(nub+0x88, struct.pack('<Q', mock))
    for name, expected in (('_nuwa_original_pmgr_nub_read', 0xffffffff),
                           ('_nuwa_original_pmgr_nub_write', mock)):
        uc.reg_write(R.UC_ARM64_REG_SP, stack+0xf000)
        uc.reg_write(R.UC_ARM64_REG_X30, halt)
        uc.reg_write(R.UC_ARM64_REG_X0, nub)
        uc.reg_write(R.UC_ARM64_REG_X1, 0xffffffff)
        before = bytes(uc.mem_read(mock, 0x40000))
        uc.emu_start(ns[name], halt, count=100)
        assert uc.reg_read(R.UC_ARM64_REG_PC) == halt
        assert uc.reg_read(R.UC_ARM64_REG_X0) == expected
        assert bytes(uc.mem_read(mock, 0x40000)) == before
        cases.append(dict(kind='real final nub/AON instructions via final 325-slot table; mock object storage only',
                          symbol=name, x0=hex(expected), memory_unchanged=True, passed=True))
    render = json.loads((out / 'renderer-manifest.json').read_text())
    allowed = bytearray(len(final))
    assert len(pristine) == len(final)
    for patch in render['patches']:
        at, size = patch['fileoff'], patch['size']
        assert sha(pristine[at:at+size]) == patch['before_sha256']
        assert sha(final[at:at+size]) == patch['after_sha256']
        allowed[at:at+size] = b'\1'*size
    assert all(a == b or allowed[i] for i, (a, b) in enumerate(zip(pristine, final)))
    startup = dict(anchors=anchors, sandbox_stub=sandbox_stub,
                   sandbox_start_pointer=hex(start_pointer), sandbox_start_target=hex(actual_start),
                   worker_argument=lines(worker_argument), source_snapshots=source_snapshots,
                   policy_store=lines(policy_store), policy_register=policy_register,
                   thread_imports=thread_bindings, wait_import=wait_binding,
                   root_hook=lines(hook_code), callsite=hex(callsite),
                   ordering='bootstrap InitIOKit -> MAC policy registration -> lockdown -> root workloop/PMGR '
                            '-> original root registerService -> bsd_init -> mac_cred_label_associate_kernel '
                            '-> registered callback -> kernel_thread_start -> PMGR worker; static, not device execution')
    (out / 'startup-audit.json').write_text(json.dumps(dict(status='self-checked; static ordering',
        kernel_sha256=sha(final), startup=startup), indent=2)+'\n')
    result = dict(status='self-checked; pending directed deep review and independent verifier',
                  kernel_sha256=sha(final), native_sha256=sha(native), bindings=bindings,
                  donor_pointer_rebindings_checked=len(prelink['bindings']),
                  renderer_inputs_reused=renderer_sources, font_reused=old_renderer['font'],
                  vtable_slots=slots, class_size=0x36968, nub_size=0x740, provider_to_nub_offset=0x88,
                  metaclass_identity='parent binds original ApplePMGR::gMetaClass; runtime equality checks retained',
                  initializer_manual_call=hex(all_init_calls[0]), auto_init_absent=True,
                  single_root_call=hex(callsite), original_executable_checks=exec_checks,
                  startup=startup, executed_cases=cases, all_passed=True,
                  lifecycle_executed=dict(mode1_cleanup=False, mode2_publication=False, mode3_full_path=False,
                                          slot170_refusal_to_panic=True),
                  pthread_runtime_qualified=False, no_hardware_or_mmio_claim=True,
                  sources={str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in (
                      ROOT / 'scripts/build-nuwa-pmgr-kernel.py', Path(__file__),
                      ROOT / 'package/NuwaPlatformPower.cpp', ROOT / 'patches/xnu/8796-nuwa-pmgr-root-publication.patch')})
    (out / 'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    manifest = dict(status=result['status'], kernel=B.record(out / 'kernel.macho'), native=B.record(out / 'native.macho'),
                    map=B.record(out / 'native-link.map'), prelink_manifest=B.record(out / 'prelink.json'),
                    provenance=B.record(out / 'provenance.json'), audit=B.record(out / 'audit.json'),
                    startup=B.record(out / 'startup-audit.json'),
                    bindings=B.record(out / 'original-bindings.json'), renderer=B.record(out / 'renderer-manifest.json'),
                    chmh_rebind_required=True, pthread_runtime_qualified=False, device_approved=False)
    (out / 'kernel.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(kernel=manifest['kernel'], bindings=8, slots=325, executed=len(cases), all_passed=True), indent=2))


if __name__ == '__main__':
    main()
