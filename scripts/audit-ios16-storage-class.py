"""Identify the actual iOS16 storage class from native code; never emit aliases."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import read_dispatch_audit as A

ROOT = A.ROOT
KERNEL = ROOT / 'out/trial-boot/xnu-entry-probe-54-strategy-r4/readback-kernel.macho'
EXPECTED = '2bceb55856bf1a6159855c1de7783261275a9949562d6adc549281df3245fad1'
MASK = (1 << 64) - 1


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(raw):
    image = A.B.macho(raw)
    names = image['symbols']
    reverse = {}
    for name, va in names.items():
        reverse.setdefault(va, []).append(name)
    plan = json.loads(A.PLAN.read_bytes())
    extents = {e['segment']: e for e in plan['extents'] if e['module'] == 'com.apple.iokit.IOStorageFamily'}

    def read(va, size):
        at = A.B.backed(image, va, size)
        return raw[at:at + size]

    def instructions(va, size):
        return list(A.CS.disasm(read(va, size), va))

    def address_pair(first, second, reg):
        require(first.mnemonic == 'adrp' and first.op_str.startswith(reg + ', '), 'Expected ADRP ' + reg)
        require(second.mnemonic == 'add' and second.op_str.startswith(reg + ', ' + reg + ', '), 'Expected ADD ' + reg)
        return (first.operands[1].imm + second.operands[2].imm) & MASK

    def target(va, name):
        record = A.stub(raw, image, va)
        require(record is not None and record['target'] == names[name], 'Import thunk mismatch: ' + name)
        return record

    text = extents['__TEXT_EXEC']
    code = instructions(text['va'], text['size'])
    # Identify name/parent/size directly from the class constructor calls.
    constructors = []
    for index, ins in enumerate(code[:-6]):
        if ins.mnemonic != 'adrp' or not ins.op_str.startswith('x1, '):
            continue
        following = code[index + 1]
        if following.mnemonic != 'add' or not following.op_str.startswith('x1, x1, '):
            continue
        string = address_pair(ins, following, 'x1')
        text_data = extents['__TEXT']
        if not text_data['va'] <= string < text_data['va'] + text_data['size'] - 21:
            continue
        if read(string, 21) != b'IOBlockStorageDevice\0':
            continue
        seq = code[index:index + 6]
        require(seq[2].mnemonic == 'adrp' and seq[2].op_str.startswith('x2, '), 'Parent ADRP')
        require(seq[3].mnemonic == 'ldr' and seq[3].op_str.startswith('x2, [x2'), 'Parent load')
        slot = (seq[2].operands[1].imm + seq[3].operands[1].mem.disp) & MASK
        require(struct.unpack('<Q', read(slot, 8))[0] == names['__ZN9IOService10gMetaClassE'], 'Parent identity')
        require(seq[4].mnemonic == 'mov' and seq[4].op_str.startswith('w3, '), 'Class size argument')
        require(seq[5].mnemonic == 'bl', 'Metaclass constructor call')
        thunk = target(seq[5].operands[0].imm & MASK, '__ZN11OSMetaClassC2EPKcPKS_j')
        static_meta = None
        if index >= 2 and code[index-2].mnemonic == 'adrp' and code[index-2].op_str.startswith('x0, '):
            static_meta = address_pair(code[index-2], code[index-1], 'x0')
        constructors.append(dict(pc=hex(ins.address), instance_size=seq[4].operands[1].imm,
                                 static_meta=static_meta, parent_slot=hex(slot), thunk=thunk,
                                 instructions=[A.record(i) for i in seq]))
    require(len(constructors) == 3, 'Expected three matching native metaclass constructors')
    sizes = {c['instance_size'] for c in constructors}
    require(len(sizes) == 1, 'Inconsistent native class sizes')
    statics = [c['static_meta'] for c in constructors if c['static_meta'] is not None]
    require(len(statics) == 1, 'Unique static class initializer required')
    meta = statics[0]
    getters = []
    for index, ins in enumerate(code[:-2]):
        if ins.mnemonic == 'adrp' and ins.op_str.startswith('x0, ') and code[index+1].mnemonic == 'add' and code[index+2].mnemonic == 'ret':
            if address_pair(ins, code[index+1], 'x0') == meta:
                getters.append(ins.address)
    const = extents['__DATA_CONST']
    blob = read(const['va'], const['size'])
    service = names['__ZTV9IOService'] + 16
    service_first = list(struct.unpack('<12Q', read(service, 96)))
    tables = []
    for at in range(16, len(blob)-96, 8):
        ptr = list(struct.unpack_from('<12Q', blob, at))
        if ptr[7] in getters and blob[at-16:at] == bytes(16) and all(ptr[i] == service_first[i] for i in (2,3,4,5,6,8,9,10,11)):
            tables.append(const['va'] + at)
    require(len(tables) == 1, 'Unique actual storage dispatch required')
    table = tables[0]
    pointers = []
    for index in range(256):
        ptr = struct.unpack('<Q', read(table + index * 8, 8))[0]
        if ptr == 0:
            break
        require(ptr in reverse or text['va'] <= ptr < text['va'] + text['size'], 'Unknown vtable target')
        pointers.append(ptr)
    require(len(pointers) >= 150 and len(pointers) < 256, 'Vtable boundary')
    require(read(pointers[0], 4) == read(pointers[1], 4) == bytes.fromhex('200020d4'), 'Abstract destructor traps')
    destructor = pointers[0] - 4
    branch = instructions(destructor, 4)[0]
    require(branch.mnemonic == 'b', 'Base destructor tailcall')
    d2 = target(branch.operands[0].imm & MASK, '__ZN9IOServiceD2Ev')
    protected = []
    for index, ins in enumerate(code[:-7]):
        seq = code[index:index+8]
        if [i.mnemonic for i in seq] != ['stp','mov','bl','adrp','add','str','ldp','ret']:
            continue
        if not seq[3].op_str.startswith('x8, ') or not seq[4].op_str.startswith('x8, x8, '):
            continue
        if address_pair(seq[3],seq[4],'x8') == table:
            require(seq[5].op_str == 'x8, [x0]', 'Constructor vptr store')
            c2 = target(seq[2].operands[0].imm & MASK, '__ZN9IOServiceC2EPK11OSMetaClass')
            protected.append(dict(pc=hex(ins.address), thunk=c2, instructions=[A.record(i) for i in seq]))
    require(len(protected) == 1, 'Unique protected constructor')
    return dict(class_name='IOBlockStorageDevice', instance_size=next(iter(sizes)), metaclass=hex(meta),
        vtable=hex(table-16), method_count=len(pointers), metaclass_constructors=constructors,
        protected_constructor=protected[0], base_destructor=dict(pc=hex(destructor), thunk=d2),
        methods=[dict(slot=i, target=hex(v), native_names=reverse.get(v, [])) for i,v in enumerate(pointers)],
        pure_virtual_count=pointers.count(names['___cxa_pure_virtual']),
        live_metadata_verified=False, public_header_abi_verified=False, aliases_emitted=False,
        scope='Static actual-target class identity and dispatch; not complete ABI or runtime registration')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    out = args.output.resolve()
    require(not out.exists() and out.is_relative_to(ROOT/'reports'), 'Fresh reports directory')
    raw = KERNEL.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTED, 'Current kernel identity')
    require(hashlib.sha256(A.PLAN.read_bytes()).hexdigest() == A.PLAN_SHA, 'Prelink identity')
    result = audit(raw)
    image = A.B.macho(raw)
    cases = [('parent', int(result['metaclass_constructors'][0]['parent_slot'],16), bytes(8)),
             ('size', int(result['metaclass_constructors'][0]['pc'],16)+16, bytes.fromhex('03208052')),
             ('destructor',int(result['base_destructor']['pc'],16),bytes.fromhex('c0035fd6')),
             ('vtable',int(result['vtable'],16)+16+2*8,bytes(8))]
    tests = []
    for name, va, replacement in cases:
        mutated=bytearray(raw); offset=A.B.backed(image,va,len(replacement));mutated[offset:offset+len(replacement)]=replacement
        try:
            audit(bytes(mutated))
        except ValueError as error:
            tests.append(dict(name=name,rejected=True,reason=str(error)))
        else:
            raise ValueError('Mutation accepted: '+name)
    result.update(kernel_sha256=EXPECTED, negative_tests=tests, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    out.mkdir(parents=True)
    (out/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'audit-script.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:result[k] for k in ('instance_size','metaclass','vtable','method_count','pure_virtual_count','negative_tests')}))


if __name__ == '__main__':
    main()
