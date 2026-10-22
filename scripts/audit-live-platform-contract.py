"""Compare a captured nuwa Android FDT with the exact linked driver sources.

Reports observations only. Never emit ADT, board configuration or images.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--fdt', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports'):
        raise ValueError('Report must stay under reports/')
    raw = args.fdt.read_bytes()
    spec = importlib.util.spec_from_file_location('dt_parser', ROOT / 'scripts/audit-trial-boot-inputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    nodes = module.properties(raw)
    if b'nuwa' not in nodes['/']['model'].lower() or b'kalama' not in nodes['/']['compatible'].lower():
        raise ValueError('Not a nuwa/kalama FDT')
    audit = json.loads((ROOT / 'reports/kernel-ci/39793231214/driver-archives/audit.json').read_text())
    sources = []
    terms = ('/arm-io', '/psci', 'sizeof (regions)', 'sizeof (bus)', 'getLength () == 11',
             'kSgiPpiEnable', 'cntv', 'cntfrq', 'getBytesNoCopy', 'required /cpus')
    for name in ('ArmCpu', 'ArmDTPlatform'):
        source = Path('D:/Code/PortingiOS/common/sources/UniXNU/drivers') / name / (name + '.cpp')
        data = source.read_bytes()
        expected = next(item for item in audit['components'] if item['component'] == name)['source_sha256']
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Read-only driver differs from actual CI source')
        sources.append({'component': name, 'path': str(source), 'sha256': expected,
                        'contract_lines': [{'line': index, 'text': line}
                                           for index, line in enumerate(data.decode().splitlines(), 1)
                                           if any(term in line for term in terms)]})
    selected = []
    for path, properties in nodes.items():
        compatible = properties.get('compatible', b'')
        cpu = properties.get('device_type') == b'cpu\0'
        if not (cpu or any(value in compatible.split(b'\0') for value in (
                b'arm,gic-v3', b'arm,armv8-timer', b'arm,psci-1.0'))):
            continue
        keep = {name: {'hex': value.hex(), 'bytes': len(value)}
                for name, value in properties.items() if name in (
                    'compatible', 'reg', 'method', 'enable-method', 'status', 'interrupts',
                    'redistributor-stride', 'clock-frequency', 'device_type')}
        item = {'android_node': path, 'properties': keep}
        if 'reg' in properties:
            parent = nodes[path.rsplit('/', 1)[0] or '/']
            a = int.from_bytes(parent.get('#address-cells', b'\0\0\0\2'), 'big') * 4
            s = int.from_bytes(parent.get('#size-cells', b'\0\0\0\1'), 'big') * 4
            width = a + s
            data = properties['reg']
            if a <= 0 or width <= 0 or len(data) % width:
                raise ValueError('Malformed platform reg cells')
            item['decoded_reg_from_parent_cells'] = [
                {'address': hex(int.from_bytes(data[i:i+a], 'big')),
                 'size': hex(int.from_bytes(data[i+a:i+width], 'big'))}
                for i in range(0, len(data), width)]
        selected.append(item)
    link = json.loads((ROOT / 'reports/kernel-ci/39793231214/platform-link/audit.json').read_text())
    kernel_path = ROOT / 'out/kernel-ci/39793231214/nuwa-8796-source/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped'
    kernel = kernel_path.read_bytes()
    if hashlib.sha256(kernel).hexdigest() != link['kernel_sha256']:
        raise ValueError('Kernel does not match the linked driver report')
    parser_path = Path('D:/Code/PortingiOS/common/sources/UniXNU/kits/NativePrelink/native_prelink.py')
    inspection = json.loads((ROOT / 'reports/kernel-ci/39793231214/kernel-inspection.json').read_text())
    if hashlib.sha256(parser_path.read_bytes()).hexdigest() != inspection['parser_sha256']:
        raise ValueError('NativePrelink parser changed')
    spec = importlib.util.spec_from_file_location('fixed_native_parser', parser_path)
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)
    image = parser_module.macho(kernel)
    addresses = [address for address, names in parser_module.exports(kernel, image).items()
                 if '_gIOKernelConfigTables' in names]
    if len(addresses) != 1:
        raise ValueError('Expected one kernel catalogue pointer')
    offset = parser_module.backed_offset(image['segments'], addresses[0], 8, len(kernel))
    pointer, = struct.unpack_from('<Q', kernel, offset)
    offset = parser_module.backed_offset(image['segments'], pointer, 1, len(kernel))
    end = kernel.index(b'\0', offset, offset + 65536)
    parser_module.backed_offset(image['segments'], pointer, end - offset + 1, len(kernel))
    catalogue = kernel[offset:end].decode('ascii')
    if not all("= " + name + ";" in catalogue for name in ('ArmCpu', 'ArmDTPlatform')):
        raise ValueError('Actual kernel catalogue lacks platform personalities')
    report = {'scope': 'Android hardware evidence and linked-source contract, not ADT/runtime validation',
              'fdt_path': str(args.fdt), 'fdt_sha256': hashlib.sha256(raw).hexdigest(),
              'exact_linked_driver_sources': sources, 'android_nodes': selected,
              'actual_build_runtime_arguments': [value for value in link['make_arguments']
                                                 if 'ARCH_TIMER' in value or 'BOOT_PROGRESS' in value],
              'actual_kernel_catalogue': {'kernel_sha256': link['kernel_sha256'],
                                          'file_offset': offset, 'text': catalogue,
                                          'runtime_matching': 'unverified'},
              'gaps': ['No nuwa candidate ADT generated or validated',
                       'Android FDT big-endian cells must not be copied as Apple ADT native-endian values',
                       'Driver expects /arm-io/intc and /psci, not Android /soc node paths',
                       'No EL/PSCI/GIC/timer hardware execution evidence',
                       'No provider/boot-progress/watchdog runtime qualification'],
              'device_executed': False, 'board_modified': False, 'adt_generated': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'platform_nodes': len(selected), 'sources_match_ci': True}))


if __name__ == '__main__':
    main()
