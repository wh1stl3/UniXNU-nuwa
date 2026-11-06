"""Execute pinned Image4 readers with an ADT-backed, explicitly modeled IOKit boundary.

No kernel/ADT/device writes. OS object lookup, casting and virtual methods are
fixtures; Image4 dispatch, conversion, validation and copying execute real code.
"""
import argparse
import gc
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'out/python-tools'), str(ROOT / 'scripts')]
import unicorn as U
from unicorn.arm64_const import *

spec = importlib.util.spec_from_file_location('probe', ROOT / 'scripts/build-kernel-entry-probe.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
STACK, HEAP, STOP = 0xf00000, 0x1000000, 0xf00000
KEY = 'mix-n-match-prevention-status'
RUNTIME = 0xfffffff005cb14d8
ENTRIES = {'bool': 0xfffffff0046efe7c, 'u32': 0xfffffff0046f0000,
           'u64': 0xfffffff0046f013c, 'digest': 0xfffffff0046f021c}
CACHE = 0xfffffff005cacef8
PMAP_RUNTIME = 0xfffffff005cad070
ADAPTER = 0xfffffff003dc4000


def backed_bytes(raw, macho, address, size):
    at = B.backed(macho, address, size)
    return raw[at:at + size]


def parse_adt(raw):
    nodes = {}

    def node(at, parent):
        if at + 8 > len(raw):
            raise ValueError('Truncated ADT node')
        count, children = struct.unpack_from('<II', raw, at)
        at += 8
        props = {}
        for _ in range(count):
            if at + 36 > len(raw):
                raise ValueError('Truncated ADT property')
            key = raw[at:at + 32].split(b'\0')[0].decode('ascii')
            size = struct.unpack_from('<I', raw, at + 32)[0] & 0x7fffffff
            at += 36
            if at + B.align(size, 4) > len(raw) or key in props:
                raise ValueError('Invalid ADT property bounds/duplicate')
            props[key] = raw[at:at + size]
            at += B.align(size, 4)
        name = props.get('name', b'').split(b'\0')[0].decode('ascii')
        path = parent.rstrip('/') + '/' + name if parent else '/'
        if path in nodes:
            raise ValueError('Duplicate ADT path')
        nodes[path] = props
        for _ in range(children):
            at = node(at, path)
        return at

    end = node(0, '')
    if any(raw[end:]):
        raise ValueError('Nonzero ADT tail')
    return nodes


class Model:
    def __init__(self, raw, macho, nodes, wrong_type=False):
        self.nodes, self.events, self.bad = nodes, [], []
        self.u = u = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
        base = min(s['va'] for s in macho['segments'] if s['size'])
        end = max(s['va'] + s['size'] for s in macho['segments'])
        u.mem_map(base, B.align(end - base))
        u.mem_map(STACK, 0x10000)
        u.mem_map(HEAP, 0x20000)
        u.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
        for s in macho['segments']:
            if s['filesize']:
                u.mem_write(s['va'], raw[s['fileoff']:s['fileoff'] + s['filesize']])
        # Only the following object-boundary calls are modeled, never the
        # Image4 helper/reader, policy results, bzero or memcpy.
        self.hooks = {}
        self.next_object = HEAP + 0x5000
        self.objects = {}
        self.wrong_objects = set()
        self.wrong_type = wrong_type
        self.native_dt_init = macho['symbols']['_SecureDTInit']
        self.native_dt_lookup = macho['symbols']['_SecureDTLookupEntry']
        self.node_vtable, self.data_vtable = HEAP, HEAP + 0x1000
        self.thunks = {name: HEAP + 0x2000 + i * 4 for i, name in
                       enumerate(('property', 'release', 'length', 'bytes'))}
        for name, offset in (('property', 0x118), ('release', 0x28)):
            self.put64(self.node_vtable + offset, self.thunks[name])
        for name, offset in (('length', 0xa0), ('bytes', 0xd8)):
            self.put64(self.data_vtable + offset, self.thunks[name])
        self.hooks.update({v: k for k, v in self.thunks.items()})
        for got, label, expected in (
            (0xfffffff005cab878, 'fromPath', '__ZN15IORegistryEntry8fromPathEPKcPK15IORegistryPlanePcPiPS_'),
            (0xfffffff005cab880, 'safeMetaCast', '__ZN15OSMetaClassBase12safeMetaCastEPKS_PK11OSMetaClass')):
            target = self.get64(got)
            if macho['symbols'].get(expected) != target:
                raise ValueError('Unexpected kernel binding: ' + label)
            self.hooks[target] = label
        # Image4 logging itself needs initialized kernel console/thread state;
        # it is outside the identifier semantics under test.
        self.hooks[0xfffffff0046efe0c] = 'log'
        u.hook_add(U.UC_HOOK_CODE, self.watch)
        u.hook_add(U.UC_HOOK_MEM_INVALID, self.invalid)

    def get64(self, at):
        return struct.unpack('<Q', self.u.mem_read(at, 8))[0]

    def put64(self, at, value):
        self.u.mem_write(at, struct.pack('<Q', value))

    def cstr(self, at):
        return bytes(self.u.mem_read(at, 256)).split(b'\0')[0].decode('ascii')

    def alloc(self, value, vtable):
        at = self.next_object
        self.next_object += 0x100
        if self.next_object >= HEAP + 0x1e000:
            raise ValueError('Object fixture exhausted')
        self.put64(at, vtable)
        self.objects[at] = value
        return at

    def invalid(self, u, access, address, size, value, data):
        self.bad.append([access, hex(address), size])
        return False

    def watch(self, u, pc, size, data):
        if pc == self.native_dt_lookup:
            self.events.append({'secure_dt_lookup': self.cstr(u.reg_read(UC_ARM64_REG_X1))})
        name = self.hooks.get(pc)
        if name is None:
            return
        x0, x1 = u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X1)
        if name == 'fromPath':
            path = self.cstr(x0)
            self.events.append({'lookup': path})
            result = self.alloc(path, self.node_vtable) if path in self.nodes else 0
        elif name == 'property':
            key = self.cstr(x1)
            path = self.objects[x0]
            value = self.nodes[path].get(key)
            self.events.append({'node': path, 'property': key,
                                'length': len(value) if value is not None else None})
            result = self.alloc(value, self.data_vtable) if value is not None else 0
            if self.wrong_type == key and result:
                self.wrong_objects.add(result)
        elif name == 'safeMetaCast':
            result = 0 if self.wrong_type is True or x0 in self.wrong_objects else x0
        elif name == 'length':
            result = len(self.objects[x0])
        elif name == 'bytes':
            value = self.objects[x0]
            if len(value) > 0x1000:
                raise ValueError('Oversized fixture property')
            u.mem_write(HEAP + 0x1f000, value or b'\0')
            result = HEAP + 0x1f000
        else:
            result = 0
        u.reg_write(UC_ARM64_REG_X0, result)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_LR))

    def call(self, entry, args):
        u = self.u
        for reg, value in zip((UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3), args):
            u.reg_write(reg, value)
        u.reg_write(UC_ARM64_REG_SP, STACK + 0x8000)
        u.reg_write(UC_ARM64_REG_LR, STOP)
        u.emu_start(entry, STOP, count=2000000)
        if u.reg_read(UC_ARM64_REG_PC) != STOP or self.bad:
            raise ValueError('Model did not return: ' + str(self.bad))
        return u.reg_read(UC_ARM64_REG_X0)

    def identifier(self, kind, identifier):
        out = STACK + 0x1000
        self.u.mem_write(out, b'\xa5' * 80)
        errno = self.call(ENTRIES[kind], (RUNTIME, 0, identifier, out))
        data = bytes(self.u.mem_read(out, 80))
        return {'errno': errno, 'output_hex': data.hex(), 'events': list(self.events)}

    def install_adapter(self, adapter):
        self.u.mem_map(ADAPTER, B.align(len(adapter)))
        self.u.mem_write(ADAPTER, adapter)
        self.u.mem_write(0xfffffff0046ea000, B.branch(0xfffffff0046ea000, ADAPTER))

    def outer_identifier(self, identifier):
        out = STACK + 0x1000
        self.u.mem_write(out, b'\xa5' * 80)
        errno = self.call(0xfffffff0046e9fe0, (0, 0, identifier, out))
        return {'errno': errno, 'output_hex': bytes(self.u.mem_read(out, 80)).hex()}

    def cached_policy(self, adapter=None):
        # Execute the original chip selection, version-6 instance creation and
        # original IsLockedDown dispatch. The initialized instance bytes are
        # loaded from the input image, rather than invented by the fixture.
        chip = self.call(0xfffffff0046f0f30, ())
        errno = self.call(0xfffffff0046ec264, (chip, CACHE))
        if errno:
            raise ValueError('Real chip-instance creation failed: ' + str(errno))
        self.put64(0xfffffff005caceb8, CACHE)
        self.u.emu_start(0xfffffff0046e9948, 0xfffffff0046e9960, count=100)
        route = self.get64(0xfffffff005cacea8)
        if route != 0xfffffff005cad110:
            raise ValueError('Unexpected runtime selection')
        if adapter is not None:
            self.install_adapter(adapter)
        # Execute the actual initializer's AMNM call and panic edge, including
        # the original panic format and the ARM64 stack-passed variadic errno.
        outcome = {}

        def stop(u, pc, size, data):
            if pc == 0xfffffff0046fa028:
                outcome.update(panic=self.cstr(u.reg_read(UC_ARM64_REG_X0)),
                               errno=self.get64(u.reg_read(UC_ARM64_REG_SP)))
                u.emu_stop()
            elif pc == 0xfffffff0046e99e0:
                outcome.update(panic=None, errno=0)
                u.emu_stop()

        hook = self.u.hook_add(U.UC_HOOK_CODE, stop)
        self.u.reg_write(UC_ARM64_REG_SP, STACK + 0x8000)
        self.u.reg_write(UC_ARM64_REG_X19, PMAP_RUNTIME)
        self.u.reg_write(UC_ARM64_REG_X21, chip)
        self.u.reg_write(UC_ARM64_REG_X20, 0x12345678)
        self.u.reg_write(UC_ARM64_REG_X3, 0xfffffff005cacef0)
        self.u.mem_write(0xfffffff005cacef0, b'\xa5')
        original_sp = self.u.reg_read(UC_ARM64_REG_SP)
        self.u.emu_start(0xfffffff0046e99c4, STOP, count=2000000)
        self.u.hook_del(hook)
        if not outcome or self.bad:
            raise ValueError('Initializer did not reach its original panic/success edge')
        if (self.u.reg_read(UC_ARM64_REG_X19), self.u.reg_read(UC_ARM64_REG_X20),
            self.u.reg_read(UC_ARM64_REG_X21), self.u.reg_read(UC_ARM64_REG_SP)) != (
                PMAP_RUNTIME, 0x12345678, chip, original_sp):
            raise ValueError('Reader clobbered callee-saved registers or stack')
        return {**outcome, 'chip': hex(chip), 'selected_runtime': hex(route),
                'cache_version': int.from_bytes(self.u.mem_read(CACHE, 2), 'little'),
                'cache_missing_mask': hex(self.get64(CACHE + 0x10)),
                'events': list(self.events), 'adapter_in_model_only': adapter is not None,
                'allow_mix_n_match': bytes(self.u.mem_read(0xfffffff005cacef0, 1))[0],
                'callee_saved_and_sp_preserved': True}

    def subsequent_manifest_panic(self, adt):
        tree = 0xe00000
        self.u.mem_map(tree, B.align(len(adt)))
        self.u.mem_write(tree, adt)
        self.call(self.native_dt_init, (tree, len(adt)))
        effective_chip = self.call(0xfffffff0046f126c, ())
        self.put64(0xfffffff005cacec0, effective_chip)
        self.u.reg_write(UC_ARM64_REG_X20, 0xfffffff005cac000)
        outcome = {}

        def stop(u, pc, size, data):
            if pc == 0xfffffff0046fa028:
                outcome['panic'] = self.cstr(u.reg_read(UC_ARM64_REG_X0))
                sp = u.reg_read(UC_ARM64_REG_SP)
                outcome['variadic_values'] = [self.get64(sp), self.get64(sp + 8)]
                u.emu_stop()

        hook = self.u.hook_add(U.UC_HOOK_CODE, stop)
        self.u.emu_start(0xfffffff0046e99e0, STOP, count=2000000)
        self.u.hook_del(hook)
        if self.bad or outcome.get('panic') != 'failed to read boot nonce hash: secure boot level = %#llx: %d':
            raise ValueError('Unexpected subsequent initializer result: ' + str(outcome))
        return {**outcome, 'events': list(self.events),
                'scope': 'Original initializer continuation with baseline native SecureDT; AMNM one only in object fixture'}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--adt', required=True, type=Path)
    cli.add_argument('--output', required=True, type=Path)
    cli.add_argument('--adapter', type=Path, help='Optional compiled model-only compatibility candidate')
    cli.add_argument('--kernel', type=Path,
                     default=ROOT / 'out/kernel-entry-probe-25-vector2/kernel-entry-probe.macho',
                     help='Verify the unchanged shipped donor/provider bytes against the pinned analysis input')
    args = cli.parse_args()
    output = args.output.resolve()
    if output.suffix != '.json' or not any(output.is_relative_to(ROOT / p) for p in ('out', 'reports')):
        raise ValueError('Audit output must be a JSON report under out/ or reports/')
    raw, adt = B.INPUT.read_bytes(), args.adt.read_bytes()
    if B.sha(raw) != B.EXPECTED:
        raise ValueError('Pinned kernel changed')
    macho, nodes = B.macho(raw), parse_adt(adt)
    probe_raw = args.kernel.read_bytes()
    if B.sha(probe_raw) != 'd6f101e4dfb670e7aa44cd6f51d447feb5d433e5c5883152b5a574da1a09479e':
        raise ValueError('This audit is pinned to the PROBE18 donor/provider ABI')
    probe_macho = B.macho(probe_raw)
    preserved = []
    for segment in macho['segments']:
        if segment['name'].startswith(('__PRELINK', '__PLK')) and segment['filesize']:
            before = backed_bytes(raw, macho, segment['va'], segment['filesize'])
            after = backed_bytes(probe_raw, probe_macho, segment['va'], segment['filesize'])
            if before != after:
                raise ValueError('Shipped donor segment changed')
            preserved.append({'name': segment['name'], 'sha256': B.sha(before)})
    locked = macho['symbols']['_SecureDTIsLockedDown']
    if backed_bytes(raw, macho, locked, 8) != bytes.fromhex('00008052c0035fd6'):
        raise ValueError('Native lock-state implementation changed')
    if backed_bytes(raw, macho, locked, 8) != backed_bytes(probe_raw, probe_macho, locked, 8):
        raise ValueError('Shipped lock-state implementation changed')
    if '/chosen' not in nodes or KEY in nodes['/chosen']:
        raise ValueError('This regression audit requires the pinned missing-property baseline')
    cases, checks = {}, []
    variants = [('missing', None, False, 2, 165), ('one', b'\x01\0\0\0', False, 0, 0),
                ('zero', bytes(4), False, 0, 1), ('empty', b'', False, 0, 1),
                ('oversized', bytes(8), False, 84, 165), ('wrong-type', bytes(4), True, 96, 165)]
    for name, value, wrong_type, errno, boolean in variants:
        fixture = {k: dict(v) for k, v in nodes.items()}
        fixture['/chosen'].pop(KEY, None)
        if value is not None:
            fixture['/chosen'][KEY] = value
        model = Model(raw, macho, fixture, wrong_type)
        result = model.identifier('bool', 12)
        if (result['errno'], int(result['output_hex'][:2], 16)) != (errno, boolean):
            raise ValueError((name, result))
        if errno and result['output_hex'] != 'a5' * 80:
            raise ValueError('Error path overwrote its output')
        cases[name] = result
        checks.append({'name': 'IOKit reader ' + name, 'passed': True})
        del model
        gc.collect()
    inventory = {}
    groups = {'u32': (0, 1, 2, 3, 15), 'u64': (4,),
              'bool': (5, 6, 7, 8, 9, 10, 12, 13, 16), 'digest': (11,)}
    for kind, identifiers in groups.items():
        for identifier in identifiers:
            model = Model(raw, macho, nodes)
            inventory[str(identifier)] = {'kind': kind, **model.identifier(kind, identifier)}
            del model
            gc.collect()
    cached_cases = {}
    for name, value in (('shipped', None), ('legal-prevention-one', b'\x01\0\0\0')):
        fixture = {k: dict(v) for k, v in nodes.items()}
        if value is not None:
            fixture['/chosen'][KEY] = value
        model = Model(raw, macho, fixture)
        result = model.cached_policy()
        if result['panic'] != 'failed to get mix-n-match policy: %d' or result['errno'] != 2:
            raise ValueError((name, result))
        if any(e.get('property') == KEY for e in result['events']):
            raise ValueError('Cached pipeline unexpectedly queried AMNM')
        cached_cases[name] = result
        checks.append({'name': 'Original initializer panic through cache: ' + name, 'passed': True})
        del model
        gc.collect()
    descriptors = []
    for i in range(22):
        address = struct.unpack('<Q', backed_bytes(raw, macho, 0xfffffff005cac8c0 + 8 * i, 8))[0]
        data = backed_bytes(raw, macho, address, 0x70)
        identifier, mask = struct.unpack_from('<QQ', data)
        descriptors.append({'address': hex(address), 'identifier': identifier, 'mask': hex(mask)})
    if any(d['identifier'] in (11, 12) for d in descriptors):
        raise ValueError('The pinned instance table now contains CHMH/AMNM')
    checks.append({'name': 'Real 22-entry instance table excludes CHMH and AMNM', 'passed': True})
    adapter_cases = {}
    adapter_controls = {}
    subsequent_panic = None
    if args.adapter:
        adapter = args.adapter.read_bytes()
        if not adapter or len(adapter) > 4096:
            raise ValueError('Invalid adapter extent')
        if backed_bytes(raw, macho, 0xfffffff0046ea000, 4).hex() != '08ae00d0':
            raise ValueError('Displaced Image4 instruction changed')
        for name, value, expected, boolean in (
                ('missing', None, 2, 165), ('one', b'\x01\0\0\0', 0, 0),
                ('zero', bytes(4), 0, 1), ('empty', b'', 0, 1),
                ('oversized', bytes(8), 84, 165), ('wrong-type', bytes(4), 96, 165)):
            fixture = {k: dict(v) for k, v in nodes.items()}
            if value is not None:
                fixture['/chosen'][KEY] = value
            model = Model(raw, macho, fixture, KEY if name == 'wrong-type' else False)
            result = model.cached_policy(adapter)
            if (result['errno'] != expected or bool(result['panic']) != bool(expected)
                    or result['allow_mix_n_match'] != boolean):
                raise ValueError((name, result))
            adapter_cases[name] = result
            checks.append({'name': 'Model-only AMNM adapter ' + name, 'passed': True})
            if name == 'one':
                subsequent_panic = model.subsequent_manifest_panic(adt)
                checks.append({'name': 'Original next BNCH panic reproduced without fabricated manifest input', 'passed': True})
            del model
            gc.collect()
        model = Model(raw, macho, nodes)
        model.cached_policy()
        old = {str(i): model.outer_identifier(i) for i in (5, 6, 7, 8, 9, 10, 13, 16)}
        model.install_adapter(adapter)
        new = {str(i): model.outer_identifier(i) for i in (5, 6, 7, 8, 9, 10, 13, 16)}
        if old != new:
            raise ValueError('Adapter changed a non-AMNM cached identifier')
        adapter_controls['unrelated_cached_identifiers'] = new
        checks.append({'name': 'Eight non-AMNM cached identifiers unchanged', 'passed': True})
        del model
        gc.collect()
        model = Model(raw, macho, nodes)
        tree = 0xe00000
        model.u.mem_map(tree, B.align(len(adt)))
        model.u.mem_write(tree, adt)
        model.call(macho['symbols']['_SecureDTInit'], (tree, len(adt)))
        old = {str(i): model.outer_identifier(i) for i in (5, 6, 7, 8, 9, 10, 12, 13, 16)}
        model.install_adapter(adapter)
        new = {str(i): model.outer_identifier(i) for i in (5, 6, 7, 8, 9, 10, 12, 13, 16)}
        if old != new:
            raise ValueError('Adapter changed the null-cache SecureDT fallback')
        adapter_controls['original_secure_dt_fallback'] = new
        checks.append({'name': 'Nine original SecureDT fallback identifiers unchanged', 'passed': True})
        del model
        gc.collect()
    report = {'scope': __doc__, 'input_sha256': B.sha(raw), 'adt_sha256': B.sha(adt),
              'shipped_probe_kernel_sha256': B.sha(probe_raw), 'preserved_donor_segments': preserved,
              'checks': checks, 'cases': cases, 'inventory': inventory,
              'cached_initializer': cached_cases, 'instance_descriptors': descriptors,
              'adapter_cases': adapter_cases,
              'adapter_controls': adapter_controls,
              'subsequent_initializer': subsequent_panic,
              'adapter_sha256': B.sha(args.adapter.read_bytes()) if args.adapter else None,
              'subsequent_inputs': {
                  'manifest_properties_node_present': '/chosen/manifest-properties' in nodes,
                  'boot_manifest_hash_bytes': len(nodes['/chosen']['boot-manifest-hash'])
                      if 'boot-manifest-hash' in nodes['/chosen'] else None,
                  'manifest_authenticity': 'not established; never substitute an arbitrary digest'},
              'code_evidence': {hex(a): {'bytes': n, 'sha256': B.sha(backed_bytes(raw, macho, a, n))}
                                for a, n in ((0xfffffff0046e98cc, 0x6d0),
                                             (0xfffffff0046e9fe0, 0x16c),
                                             (0xfffffff0046ea9c8, 0xc4),
                                             (0xfffffff0046f07e8, 0xc8))},
              'modeled_boundaries': ['IORegistryEntry::fromPath/getProperty/release',
                                     'OSMetaClassBase::safeMetaCast', 'OSData::getLength/getBytesNoCopy',
                                     'Image4 runtime logging'],
              'policy_selected': False, 'shipped_files_modified': False, 'device_accessed': False,
              'limitations': ['ADT-backed object fixtures; not a live IORegistry snapshot',
                              'No Apple trust chain or manifest authenticity established']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', newline='\n')
    print(json.dumps({'checks': len(checks), 'passed': True,
                      'inventory_errno': {k: v['errno'] for k, v in inventory.items()}}))


if __name__ == '__main__':
    main()
