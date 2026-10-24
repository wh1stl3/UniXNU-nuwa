"""Independently decode and audit a nuwa Apple-format DT.

The decoder is written separately from scripts/make-nuwa-adt.py on purpose: a
checker that reuses the generator's encoder can only prove the encoder is
self-consistent, not that the bytes match the Apple node encoding XNU and
DarwinBoot actually parse. This one walks the blob with its own bounded cursor
and records the byte offset of every property, then asserts the structural
invariants DarwinBoot.c and ArmDTPlatform.cpp enforce.

Structural checks only. Board values are reported, not hard-coded here, so this
file does not become a second copy of the board constants.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MAX_BLOB = 1024 * 1024
MAX_NODES = 4096
MAX_DEPTH = 64
REQUIRED_NODES = ('/device-tree/chosen', '/device-tree/cpus', '/device-tree/arm-io',
                  '/device-tree/defaults', '/device-tree/options')
NVRAM_KEYS = ('nvram-bank-size', 'nvram-bank-count', 'nvram-current-bank', 'nvram-proxy-data')
MEMORY_MAP_KEYS = ('RAMDisk', 'PackedRAMDisk', 'TrustCache', 'GpuAddon')
OWED_MIN, OWED_MAX, OWED_STEP = 0x10000000, 0x200000000, 0x200000


def decode(blob):
    """Bounded walk over Apple node encoding; returns {path: {props, offsets}}."""
    if len(blob) > MAX_BLOB:
        raise ValueError('oversized ADT (%d bytes)' % len(blob))
    nodes = {}
    cursor = 0

    def read(n):
        nonlocal cursor
        if cursor + n > len(blob):
            raise ValueError('truncated ADT at %d (+%d)' % (cursor, n))
        chunk = blob[cursor:cursor + n]
        cursor += n
        return chunk

    def walk(prefix, depth):
        nonlocal cursor
        if depth > MAX_DEPTH:
            raise ValueError('ADT deeper than %d' % MAX_DEPTH)
        if cursor + 8 > len(blob):
            raise ValueError('node header at %d crosses the end' % cursor)
        count, children = struct.unpack('<II', read(8))
        if count == 0:
            # Every node must at least carry its own 'name' property.
            raise ValueError('node at depth %d has no properties' % depth)
        if count > 1024 or children > 256:
            raise ValueError('implausible counts (%d props, %d children)' % (count, children))
        props, offsets = {}, {}
        for _ in range(count):
            if cursor + 36 > len(blob):
                raise ValueError('property header at %d crosses the end' % cursor)
            raw = read(32)
            if b'\0' not in raw:
                raise ValueError('unterminated property name at %d' % (cursor - 36))
            name = raw.split(b'\0', 1)[0].decode('ascii', 'strict')
            if not name:
                raise ValueError('empty property name at %d' % (cursor - 36))
            if name in props:
                raise ValueError('duplicate property %r' % name)
            length = struct.unpack('<I', read(4))[0]
            if length > MAX_BLOB - cursor:
                raise ValueError('property %r length %d crosses the end' % (name, length))
            offsets[name] = cursor
            props[name] = read(length)
            pad = (4 - length % 4) % 4
            if pad:
                if read(pad) != bytes(pad):
                    raise ValueError('non-zero padding after %r' % name)
        name_bytes = props.get('name')
        if name_bytes is None:
            raise ValueError('node at depth %d has no name property' % depth)
        if not name_bytes.endswith(b'\0') or b'\0' in name_bytes[:-1] or b'/' in name_bytes:
            raise ValueError('malformed node name %r' % name_bytes)
        name = name_bytes[:-1].decode('ascii', 'strict')
        if depth == 0:
            if name != 'device-tree':
                raise ValueError('root node is %r, expected device-tree' % name)
            path = '/device-tree'
        else:
            if not name:
                raise ValueError('empty child name under %s' % prefix)
            path = prefix + '/' + name
        if path in nodes:
            raise ValueError('duplicate path %s' % path)
        if len(nodes) >= MAX_NODES:
            raise ValueError('more than %d nodes' % MAX_NODES)
        nodes[path] = {'properties': props, 'offsets': offsets}
        for _ in range(children):
            walk(path, depth + 1)

    walk('', 0)
    if cursor != len(blob):
        raise ValueError('%d trailing bytes after the root node' % (len(blob) - cursor))
    return nodes


def u32(value):
    return struct.unpack('<I', value)[0] if len(value) == 4 else None


def u64(value):
    return struct.unpack('<Q', value)[0] if len(value) == 8 else None


def s(value):
    return value[:-1].decode('ascii', 'strict') if value.endswith(b'\0') else None


def audit(nodes):
    checks, failures, notes = [], [], []

    def check(name, ok, detail=''):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})
        if not ok:
            failures.append(name)
        return ok

    def note(name, ok, detail=''):
        # Conditions DarwinBoot tolerates but a bring-up reviewer should see.
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail, 'advisory': True})
        if not ok:
            notes.append('%s: %s' % (name, detail))
        return ok

    for path in REQUIRED_NODES:
        check('required node %s' % path, path in nodes,
              'ArmDTPlatform::configure() rejects the tree without it')

    chosen = nodes.get('/device-tree/chosen', {}).get('properties', {})
    check('chosen has a 64-byte random-seed',
          len(chosen.get('random-seed', b'')) == 64,
          'DarwinBoot/XNU entropy seed')
    check('chosen supplies a usable CHRP NVRAM proxy',
          len(chosen.get('nvram-bank-size', b'')) == 4 and len(chosen.get('nvram-proxy-data', b'')) > 0,
          'ArmDTPlatform::hasNVRAMProxy() requires both')
    check('chosen carries osenvironment', s(chosen.get('osenvironment', b'')) in ('main', 'recoveryos', 'ramdisk'),
          'reported %r' % s(chosen.get('osenvironment', b'')))

    dram_base = u64(chosen.get('dram-base', b''))
    dram_size = u64(chosen.get('dram-size', b''))
    check('dram-base and dram-size are 64-bit', dram_base is not None and dram_size is not None,
          'base=%s size=%s' % (hex(dram_base) if dram_base is not None else None,
                               hex(dram_size) if dram_size is not None else None))
    if dram_base is not None and dram_size is not None:
        check('dram window is 4 KiB aligned and non-empty',
              dram_base % 0x1000 == 0 and dram_size > 0 and dram_size % 0x1000 == 0,
              '%#x + %#x' % (dram_base, dram_size))

    window = chosen.get('darwinboot-memory-size')
    if window is not None:
        request = u64(window)
        check('darwinboot-memory-size is 8 bytes',
              request is not None, 'len=%d' % len(window))
        if request is not None:
            check('owned window is 256 MiB..8 GiB in 2 MiB steps',
                  OWED_MIN <= request <= OWED_MAX and request % OWED_STEP == 0,
                  '%#x' % request)
            if dram_size:
                check('owned window fits the advertised DRAM size',
                      request <= dram_size, '%#x <= %#x' % (request, dram_size))

    memory_map = nodes.get('/device-tree/chosen/memory-map', {}).get('properties', {})
    for key in MEMORY_MAP_KEYS:
        if key in memory_map:
            check('memory-map placeholder %s is 16 bytes' % key,
                  len(memory_map[key]) == 16, 'DarwinBoot writes address+size here')
    # DarwinBoot.c:224-227 refuses a tree that carries both: KeepPacked is set by
    # PackedRAMDisk, and a second ramdisk placeholder then fails the parse.
    check('RAMDisk and PackedRAMDisk are not both present',
          not ('RAMDisk' in memory_map and 'PackedRAMDisk' in memory_map),
          'DarwinBoot rejects the tree when both are declared')
    note('memory-map declares at least one sidecar placeholder',
         any(key in memory_map for key in MEMORY_MAP_KEYS),
         'present keys: %s (legal only when the payload carries no sidecar)'
         % (', '.join(k for k in MEMORY_MAP_KEYS if k in memory_map) or 'none'))

    fixups = chosen.get('text-fixups')
    if fixups is not None:
        entries = [e for e in fixups.split(b'\0') if e]
        check('text-fixups is NUL-separated and terminated',
              fixups.endswith(b'\0'), '%d entries' % len(entries))

    cpu_paths = [path for path in nodes if path.startswith('/device-tree/cpus/') and path.count('/') == 3]
    check('cpus has at least one core', bool(cpu_paths), '%d core(s)' % len(cpu_paths))
    boot = [p for p in cpu_paths if u32(nodes[p]['properties'].get('reg', b'')) == 0]
    check('exactly one CPU has reg 0 (the boot CPU)', len(boot) == 1, 'found %d' % len(boot))
    for path in cpu_paths:
        props = nodes[path]['properties']
        check('%s reports a 32-bit timebase-frequency' % path,
              u32(props.get('timebase-frequency', b'')) is not None,
              '%s Hz' % u32(props.get('timebase-frequency', b'')))
    if len(cpu_paths) > 1:
        check('more than one CPU requires /psci', '/device-tree/psci' in nodes,
              'secondary start needs it')

    arm_io = nodes.get('/device-tree/arm-io', {}).get('properties', {})
    ranges = arm_io.get('ranges', b'')
    check('arm-io declares one ranges tuple', len(ranges) == 24, 'len=%d' % len(ranges))
    if len(ranges) == 24:
        child, base, size = struct.unpack('<QQQ', ranges)
        check('arm-io ranges child address is zero', child == 0, '%#x' % child)
        intc = nodes.get('/device-tree/arm-io/intc', {}).get('properties', {})
        check('intc matches arm,gic-v3', b'arm,gic-v3' in intc.get('compatible', b''),
              'compatible=%r' % intc.get('compatible', b'')[:16])
        reg = intc.get('reg', b'')
        check('intc reg is two base/size pairs', len(reg) == 32, 'len=%d' % len(reg))
        if len(reg) == 32:
            values = struct.unpack('<4Q', reg)
            inside = all(values[0] + values[1] <= size and values[2] + values[3] <= size
                         for _ in (0,))
            check('intc windows sit inside the arm-io ranges window', inside,
                  'dist=%#x+%#x redist=%#x+%#x window=%#x..%#x'
                  % (values[0], values[1], values[2], values[3], base, base + size))

    return checks, failures, notes


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--adt', type=Path, required=True, help='ADT blob to audit')
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    args = cli.parse_args()

    target = args.output.resolve()
    if not target.is_relative_to(ROOT / 'reports') or target.exists():
        raise ValueError('fresh report under reports/ required')

    blob = args.adt.read_bytes()
    nodes = decode(blob)
    checks, failures, notes = audit(nodes)

    paths = sorted(nodes)
    report = {
        'scope': 'offline structural audit of an Apple-format DT; not a boot, not a QEMU run',
        'adt': str(args.adt),
        'adt_bytes': len(blob),
        'adt_sha256': hashlib.sha256(blob).hexdigest(),
        'node_count': len(nodes),
        'node_paths': paths,
        'chosen_sha256_properties': {
            key: (hashlib.sha256(value).hexdigest() if key != 'random-seed' else '<fresh seed, not compared>')
            for key, value in sorted(nodes['/device-tree/chosen']['properties'].items())
            if key.startswith('nvram-')
        },
        'checks': checks,
        'failures': failures,
        'advisories': notes,
        'status': 'structural_audit_passed' if not failures else 'structural_audit_failed',
        'not_proven': [
            'that firmware can allocate the advertised or requested window',
            'that XNU accepts this tree at boot (no kernel execution yet)',
            'that any driver binds these nodes on hardware',
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('nodes: %d, checks: %d, failures: %d, advisories: %d, status: %s'
          % (len(nodes), len(checks), len(failures), len(notes), report['status']))
    for advisory in notes:
        print('  advisory:', advisory)
    if failures:
        for name in failures:
            print('  FAILED:', name)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
