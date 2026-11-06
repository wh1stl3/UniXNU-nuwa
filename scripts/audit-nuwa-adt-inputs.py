"""Tie every board constant in scripts/make-nuwa-adt.py back to the live nuwa FDT.

The generator claims its constants come from the phone. This walks the captured
FDT itself (no dtc, no libfdt) and reports, per constant, what the tree actually
says. A mismatch is a failure, not a note: if the FDT and the generator disagree,
one of them is wrong and neither may be shipped silently.

Read-only over an observation blob already committed under docs/inherited/ or
out/. This does not touch the phone and does not emit any bootable artifact.
"""
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FDT_MAGIC = 0xD00DFEED
MAX_BLOB = 32 * 1024 * 1024
MAX_DEPTH = 64


def load_generator():
    """Import the generator only for its pinned constants; main() stays unrun."""
    spec = importlib.util.spec_from_file_location('make_nuwa_adt', ROOT / 'scripts/make-nuwa-adt.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_fdt(blob):
    """Minimal FDT reader: returns (root_name, {path: {prop: bytes}})."""
    if len(blob) > MAX_BLOB:
        raise ValueError('oversized FDT (%d bytes)' % len(blob))
    # struct fdt_header: magic, totalsize, off_dt_struct, off_dt_strings,
    # off_mem_rsvmap, version, last_comp_version, boot_cpuid_phys,
    # size_dt_strings, size_dt_struct (all big-endian u32).
    magic, total, off_struct, off_strings = struct.unpack_from('>4I', blob, 0)
    version, _last_comp, _boot_cpuid, string_bytes, struct_bytes = struct.unpack_from('>5I', blob, 20)
    if magic != FDT_MAGIC:
        raise ValueError('not an FDT (magic %#x)' % magic)
    if total > len(blob) or version < 16:
        raise ValueError('unexpected FDT header (total=%d version=%d)' % (total, version))
    if off_struct + struct_bytes > total or off_strings + string_bytes > total:
        raise ValueError('FDT block outside the blob')

    nodes = {}
    stack = []
    cursor = off_struct
    while cursor < off_struct + struct_bytes:
        tag = struct.unpack_from('>I', blob, cursor)[0]
        cursor += 4
        if tag == 1:  # BEGIN_NODE
            end = blob.index(b'\0', cursor)
            name = blob[cursor:end].decode('ascii')
            cursor = (end + 4) & ~3
            stack.append({'name': name, 'props': {}})
            if len(stack) > MAX_DEPTH:
                raise ValueError('FDT deeper than %d' % MAX_DEPTH)
        elif tag == 2:  # END_NODE
            node = stack.pop()
            path = '/'.join([entry['name'] for entry in stack] + [node['name']]).replace('//', '/')
            path = '/' + path.lstrip('/')
            if path in nodes:
                raise ValueError('duplicate FDT path %s' % path)
            nodes[path] = node['props']
        elif tag == 3:  # PROP
            length, name_offset = struct.unpack_from('>II', blob, cursor)
            cursor += 8
            if name_offset >= string_bytes or cursor + length > off_struct + struct_bytes:
                raise ValueError('malformed FDT property at %d' % cursor)
            name = blob[off_strings + name_offset:blob.index(b'\0', off_strings + name_offset)].decode('ascii')
            if not stack:
                raise ValueError('FDT property outside any node')
            stack[-1]['props'][name] = blob[cursor:cursor + length]
            cursor = (cursor + length + 3) & ~3
        elif tag == 4:  # NOP
            continue
        elif tag == 9:  # END
            break
        else:
            raise ValueError('unknown FDT tag %d at %d' % (tag, cursor - 4))
    if stack:
        raise ValueError('%d unclosed FDT nodes' % len(stack))
    return nodes


def u32(raw):
    return struct.unpack('>I', raw)[0] if raw is not None and len(raw) == 4 else None


def text(raw):
    return raw.split(b'\0')[0].decode('ascii') if raw else None


def find(nodes, predicate):
    """First (path, props) whose properties satisfy predicate."""
    for path in sorted(nodes):
        if predicate(nodes[path]):
            return path, nodes[path]
    return None, None


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--fdt', type=Path, required=True,
                     help='live nuwa FDT, e.g. out/live-nuwa-dt/android-dt-after-r011/android-live.dtb')
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    args = cli.parse_args()

    target = args.output.resolve()
    if not target.is_relative_to(ROOT / 'reports') or target.exists():
        raise ValueError('fresh report under reports/ required')

    gen = load_generator()
    blob = args.fdt.read_bytes()
    nodes = parse_fdt(blob)

    rows, failures = [], []

    def compare(name, expected, actual, evidence):
        ok = expected == actual

        def show(value):
            return '%#x' % value if isinstance(value, int) else value

        rows.append({'constant': name, 'generator': show(expected), 'fdt': show(actual),
                     'evidence': evidence, 'match': ok})
        if not ok:
            failures.append('%s: generator=%s fdt=%s' % (name, show(expected), show(actual)))

    # timebase: the FDT arch timer's clock-frequency, not a guessed SM8xxx value.
    timer_path, timer = find(nodes, lambda p: b'arm,armv8-timer' in p.get('compatible', b''))
    compare('TIMEBASE', gen.TIMEBASE, u32(timer.get('clock-frequency')) if timer else None,
            '%s clock-frequency' % timer_path)

    # GIC: the live FDT's two base/size pairs and the redistributor stride.
    gic_path, gic = find(nodes, lambda p: b'arm,gic-v3' in p.get('compatible', b'')
                         and len(p.get('reg', b'')) == 16)
    reg = gic.get('reg') if gic else None
    if reg and len(reg) == 16:
        dist_base, dist_size, redist_base, redist_size = struct.unpack('>4I', reg)
        compare('GIC_DIST', gen.GIC_DIST, dist_base, '%s reg[0]' % gic_path)
        compare('GIC_DIST_SIZE', gen.GIC_DIST_SIZE, dist_size, '%s reg[1]' % gic_path)
        compare('GIC_REDIST', gen.GIC_REDIST, redist_base, '%s reg[2]' % gic_path)
        compare('GIC_REDIST_SIZE', gen.GIC_REDIST_SIZE, redist_size, '%s reg[3]' % gic_path)
        stride = gic.get('redistributor-stride', b'')
        stride_value = struct.unpack('>2I', stride)[1] if len(stride) == 8 else None
        compare('GIC_REDIST_STRIDE', gen.GIC_REDIST_STRIDE, stride_value,
                '%s redistributor-stride' % gic_path)

    # CPU topology: the FDT numbers cores by Affinity1 in the node reg.
    # Only direct /cpus/cpu@N children count; cpu@0/l2-cache/... is not a core.
    cpu_paths = [path for path in nodes
                 if path.startswith('/cpus/cpu@') and '/' not in path.split('cpu@', 1)[1]]
    cpu_regs = sorted(int(path.split('cpu@', 1)[1], 16) for path in cpu_paths)
    rows.append({'constant': 'CPU_AFFINITY1', 'generator': 'passed via --cpu-regs',
                 'fdt': ['%#x' % value for value in cpu_regs],
                 'evidence': '%d /cpus/cpu@N nodes' % len(cpu_paths), 'match': None})

    # psci conduit. The live tree nests it under /soc, not at the root.
    psci_path, psci = find(nodes, lambda p: b'arm,psci' in p.get('compatible', b''))
    if psci is not None:
        compare('PSCI_METHOD', 'smc', text(psci.get('method')),
                '%s method (generator default)' % psci_path)
    else:
        failures.append('PSCI_METHOD: no arm,psci node in the live FDT')

    # UFS host window: first reg pair of the ufshc node.
    ufs_path, ufs = find(nodes, lambda p: b'ufshc' in p.get('compatible', b''))
    ufs_reg = ufs.get('reg') if ufs else None
    if ufs_reg and len(ufs_reg) >= 8:
        hc_base, hc_size = struct.unpack('>2I', ufs_reg[:8])
        compare('UFS_HC', gen.UFS_HC, hc_base, '%s reg[0]' % ufs_path)
        compare('UFS_HC_SIZE', gen.UFS_HC_SIZE, hc_size, '%s reg[1]' % ufs_path)

    # DRAM: coalesce adjacent /memory entries into contiguous runs first. The live
    # tree splits one 9 GiB run into two adjacent reg pairs, so "largest single
    # entry" would misreport the bank. Which run XNU must advertise is still a
    # decision (D-001); this only reports what the tree says.
    memory = nodes.get('/memory', {})
    memory_reg = memory.get('reg', b'')
    banks = []
    for index in range(0, len(memory_reg) - 15, 16):
        base_hi, base_lo, size_hi, size_lo = struct.unpack('>4I', memory_reg[index:index + 16])
        banks.append({'base': (base_hi << 32) | base_lo, 'size': (size_hi << 32) | size_lo})
    runs = []
    for bank in sorted(banks, key=lambda item: item['base']):
        if runs and bank['base'] <= runs[-1]['base'] + runs[-1]['size']:
            end = max(runs[-1]['base'] + runs[-1]['size'], bank['base'] + bank['size'])
            runs[-1]['size'] = end - runs[-1]['base']
            runs[-1]['banks'] += 1
        else:
            runs.append({'base': bank['base'], 'size': bank['size'], 'banks': 1})
    largest = max(runs, key=lambda run: run['size']) if runs else None
    compare('DRAM_BASE', gen.DRAM_BASE,
            largest['base'] if largest else None,
            '/memory reg: %d entries coalesce into %d run(s), largest is %d entries'
            % (len(banks), len(runs), largest['banks'] if largest else 0))
    rows.append({'constant': 'DRAM_RUN_SPAN',
                 'generator': 'passed via --dram-size',
                 'fdt': '%#x' % largest['size'] if largest else None,
                 'evidence': 'largest contiguous /memory run (%d entries)'
                             % (largest['banks'] if largest else 0),
                 'match': None})

    root_model = text(nodes.get('/', {}).get('model'))
    root_compatible = [part for part in (nodes.get('/', {}).get('compatible', b'') or b'').split(b'\0') if part]
    rows.append({'constant': 'ROOT_MODEL', 'generator': 'nuwa-first-boot',
                 'fdt': root_model, 'evidence': '/ model (label only)', 'match': None})
    rows.append({'constant': 'ROOT_COMPATIBLE',
                 'generator': gen.ROOT_COMPATIBLE.split(b'\0')[0].decode(),
                 'fdt': [part.decode() for part in root_compatible],
                 'evidence': '/ compatible; ArmDTPlatform::configure() does not match this property',
                 'match': None})

    report = {
        'scope': 'known-value reconciliation between the generator constants and the captured nuwa FDT',
        'fdt': str(args.fdt),
        'fdt_bytes': len(blob),
        'fdt_sha256': hashlib.sha256(blob).hexdigest(),
        'fdt_node_count': len(nodes),
        'generator_sha256': hashlib.sha256((ROOT / 'scripts/make-nuwa-adt.py').read_bytes()).hexdigest(),
        'comparisons': rows,
        'failures': failures,
        'status': 'constants_match_live_fdt' if not failures else 'constants_differ_from_live_fdt',
        'not_proven': [
            'that a matching FDT value is also the right Apple-side value for XNU',
            'that the largest /memory bank is the window firmware can allocate',
            'anything about a boot: no kernel or firmware ran',
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    matched = sum(1 for row in rows if row['match'] is True)
    print('comparisons: %d (%d exact), failures: %d, status: %s'
          % (len(rows), matched, len(failures), report['status']))
    for failure in failures:
        print('  MISMATCH:', failure)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
