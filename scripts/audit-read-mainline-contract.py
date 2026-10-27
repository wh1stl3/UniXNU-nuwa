"""Read-only pinned registration/driver audit; no execution or device claims."""
import argparse
import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('read_contract_builder', ROOT/'scripts/build-kernel-entry-probe.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
REGISTRATION = 0xfffffff005f48ef8
EMISSION_SHA = 'e10770f6a5f85a1430494114a136ba801f4ab062a9af1ba09408f60feb9fc5f2'
PUBLIC = {
    'apple-oss-distributions-xnu-bsd-sys-decmpfs.h': 'de165f10f5ee333a0c2ed69d49a5e81cdaeb0e394ee270a036f76248f970713d',
    'apple-oss-distributions-xnu-bsd-kern-decmpfs.c': '549649080ce3791c2edbf8471dca05fb22340eaa06715ca221e82dbf5a28082a',
    'UniXNU-ArmCpu-ArmCpu.cpp': '3c87b3bd617be5582a6a24ff797c359497ee9feaa702ee883ecee4270db21c9f',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists() and a.output.resolve().is_relative_to(ROOT/'reports')
    raw = B.INPUT.read_bytes()
    assert B.sha(raw) == B.EXPECTED
    b = json.loads(a.build.read_bytes())
    candidate = (ROOT/b['candidate']['path']).read_bytes()
    assert B.sha(candidate) == b['candidate']['sha256']
    m, cm = B.macho(raw), B.macho(candidate)
    plan_raw = (ROOT/'out/earlysec-2026-10-24/emission.json').read_bytes()
    assert B.sha(plan_raw) == EMISSION_SHA
    plan = json.loads(plan_raw)
    source_records = []
    for name, digest in PUBLIC.items():
        path = ROOT/'out/probe31-public-research'/name
        assert B.sha(path.read_bytes()) == digest
        source_records.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=digest))
    # AArch64 natural ABI: int at0, 4-byte padding, pointer slots at8..40.
    table = raw[B.backed(m, REGISTRATION, 48):B.backed(m, REGISTRATION, 48)+48]
    assert table == candidate[B.backed(cm, REGISTRATION, 48):B.backed(cm, REGISTRATION, 48)+48]
    version = struct.unpack_from('<I', table)[0]
    assert version in (1, 3), version
    fields = []
    for index, name in enumerate(('validate','adjust_fetch','fetch','free_data','get_flags'), 1):
        address = struct.unpack_from('<Q', table, index*8)[0]
        applicable = version == 3 or name != 'get_flags'
        extents = [e for e in plan['extents'] if e['va'] <= address < e['va']+e['size']]
        bindings = [e for e in plan['bindings'] if e.get('new_site') == REGISTRATION+index*8]
        if applicable and address:
            assert len(extents) == 1 and extents[0]['segment'] == '__TEXT_EXEC', (name, hex(address), extents)
            assert len(bindings) == 1 and bindings[0]['new_target'] == address, (name, bindings)
            at = B.backed(m, address, 16)
            cat = B.backed(cm, address, 16)
            assert raw[at:at+16] == candidate[cat:cat+16]
        fields.append(dict(name=name, offset=index*8, address=hex(address), applicable=applicable,
                           extent=extents, bindings=bindings))
    assert next(f for f in fields if f['name']=='fetch')['address'] != '0x0'
    counters = {}
    for name in ('_armcpu_timer_interrupts','_armcpu_ipi_interrupts','_armcpu_irq_phase','_armcpu_irq_id'):
        address = m['symbols'].get(name)
        counters[name] = hex(address) if address is not None else None
    result = dict(scope=__doc__, candidate_sha256=B.sha(candidate), native_input_sha256=B.EXPECTED,
                  emission_sha256=EMISSION_SHA, source_sha256=B.sha(Path(__file__).read_bytes()),
                  public_sources=source_records, registration_address=hex(REGISTRATION),
                  registration_version=version, registration_file_bytes_unchanged=True,
                  fields=fields, driver_counter_symbols=counters,
                  device_accessed=False, runtime_callback_invoked=False,
                  limitations=['Photographed pointer is not a live registration-table memory dump',
                               'Static target provenance does not prove callback ABI execution or return',
                               'Counter symbols and driver source do not prove interrupt delivery',
                               'No filesystem lock, cache, decompression or UFS execution test'])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(registration=hex(REGISTRATION), version=version, slots=fields, counters=counters)))


if __name__ == '__main__':
    main()
