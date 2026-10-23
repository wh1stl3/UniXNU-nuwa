"""Extract CPU/GIC/PSCI metadata from an existing nuwa FDT, without ADB.

This records Linux binding inputs; it does not emit Apple ADT or board values.
"""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/darwin22-input-contracts/cached-cpu-dt.json'


def main():
    if OUT.exists():
        raise ValueError('Fresh evidence required')
    snapshot = json.loads((ROOT / 'reports/system-volume-audit/android-dt-after-r011.json').read_text())
    path = ROOT / 'out/live-nuwa-dt/android-dt-after-r011/android-live.dtb'
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != snapshot['sha256']:
        raise ValueError('Cached Android FDT differs')
    spec = importlib.util.spec_from_file_location('cached_cpu_fdt_reader', ROOT / 'scripts/audit-trial-boot-inputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    nodes = module.properties(data)
    if b'nuwa' not in nodes['/']['model'].lower() or b'kalama' not in nodes['/']['compatible'].lower():
        raise ValueError('Snapshot hardware identity differs')

    def strings(value):
        return [x.decode('ascii') for x in value.rstrip(b'\0').split(b'\0')] if value else []

    def encoded(props, selected):
        return {k: dict(bytes=len(props[k]), hex=props[k].hex()) for k in selected if k in props}

    cpus, gics, timers, psci = [], [], [], []
    parent = nodes.get('/cpus', {})
    cpu_cells = int.from_bytes(parent.get('#address-cells', bytes.fromhex('00000002')), 'big')
    for node, props in nodes.items():
        compatible = strings(props.get('compatible', b''))
        if node.startswith('/cpus/') and props.get('device_type') == b'cpu\0':
            raw = props.get('reg', b'')
            if len(raw) != cpu_cells * 4:
                raise ValueError('CPU reg cell layout differs')
            cpus.append(dict(node=node, linux_reg=hex(int.from_bytes(raw, 'big')),
                             compatible=compatible, enable_method=strings(props.get('enable-method', b'')),
                             properties=encoded(props, ('reg', 'capacity-dmips-mhz', 'status'))))
        if any(c in ('arm,gic-v3', 'arm,gic-v4') for c in compatible):
            parent_node = node.rsplit('/', 1)[0] or '/'
            bus = nodes[parent_node]
            # DTSpec defaults, not adopted nuwa target values.
            ac = int.from_bytes(bus.get('#address-cells', bytes.fromhex('00000002')), 'big')
            sc = int.from_bytes(bus.get('#size-cells', bytes.fromhex('00000001')), 'big')
            raw = props.get('reg', b'')
            width = (ac + sc) * 4
            if not width or len(raw) % width:
                raise ValueError('GIC reg cell layout differs')
            ranges = [dict(index=i // width, bus_address=hex(int.from_bytes(raw[i:i + ac * 4], 'big')),
                           bytes=int.from_bytes(raw[i + ac * 4:i + width], 'big'))
                      for i in range(0, len(raw), width)]
            translated = []
            # This snapshot's /soc is a direct child of root. Decode its
            # explicit ranges; never treat an absent ranges property as identity.
            if parent_node.rsplit('/', 1)[0] == '' and 'ranges' in bus:
                pac = int.from_bytes(nodes['/'].get('#address-cells', bytes.fromhex('00000002')), 'big')
                mapping = bus['ranges']
                mw = (ac + pac + sc) * 4
                if len(mapping) % mw:
                    raise ValueError('Parent ranges cell layout differs')
                maps = [(int.from_bytes(mapping[i:i + ac * 4], 'big'),
                         int.from_bytes(mapping[i + ac * 4:i + (ac + pac) * 4], 'big'),
                         int.from_bytes(mapping[i + (ac + pac) * 4:i + mw], 'big'))
                        for i in range(0, len(mapping), mw)]
                for region in ranges:
                    address = int(region['bus_address'], 16)
                    matches = [(p + address - c) for c, p, length in maps
                               if c <= address and address - c + region['bytes'] <= length]
                    if len(matches) == 1:
                        translated.append(dict(index=region['index'], physical_address=hex(matches[0]), bytes=region['bytes']))
            gics.append(dict(node=node, compatible=compatible, reg_names=strings(props.get('reg-names', b'')),
                             parent_cells=dict(address=ac, size=sc), reg_ranges=ranges,
                             physical_ranges_from_explicit_root_mapping=translated,
                             declared_redistributor_stride=int.from_bytes(props['redistributor-stride'], 'big') if 'redistributor-stride' in props else None,
                             parent_bus_properties=encoded(bus, ('ranges', '#address-cells', '#size-cells')),
                             properties=encoded(props, ('#interrupt-cells', '#redistributor-regions', 'redistributor-stride', 'interrupts'))))
        if any(c.startswith('arm,armv8-timer') for c in compatible):
            timers.append(dict(node=node, compatible=compatible,
                               declared_clock_frequency=int.from_bytes(props['clock-frequency'], 'big') if 'clock-frequency' in props else None,
                               properties=encoded(props, ('interrupts', 'interrupt-parent', 'clock-frequency', 'always-on'))))
        if any(c.startswith('arm,psci') for c in compatible):
            psci.append(dict(node=node, compatible=compatible, method=strings(props.get('method', b''))))
    if not cpus or not gics or not timers or not psci:
        raise ValueError('Required cached hardware metadata not found')
    report = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='Existing Android FDT snapshot only; no new device reads or target ADT generated',
                  source=dict(path=str(path.relative_to(ROOT)), sha256=snapshot['sha256'],
                              original_observation='reports/system-volume-audit/android-dt-after-r011.json'),
                  cpus=cpus, gics=gics, timers=timers, psci=psci,
                  apple_consumer_contract=dict(cpu_device_type='cpu plus NUL, exactly4bytes', cpu_reg='consumer reads first little-endian u32; physical-ID mapping must be qualified',
                                               arm_io_ranges_bytes=24, intc_reg_bytes=32,
                                               intc_compatible='arm,gic-v3 plus NUL, exactly11bytes'),
                  todo=['Qualify GICD/GICR selection and runtime ownership before any Apple reg/ranges emission',
                        'Qualify MPIDR/physical-ID mapping against XNU CPU registration',
                        'Counter frequency, interrupt delivery and PSCI runtime behavior remain unverified',
                        'Do not infer candidate ABL x0 tree from this Android snapshot'],
                  device_accessed=False, adt_generated=False, board_feed_changed=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(cpu_count=len(cpus), gic_nodes=[x['node'] for x in gics],
                         timer_nodes=[x['node'] for x in timers], psci=psci, adt_generated=False), indent=2))


if __name__ == '__main__':
    main()
