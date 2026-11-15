#!/usr/bin/env python3
"""Component-only mechanical checks. No native link, prelink or device use."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

sys.dont_write_bytecode = True


def inspect_object(path):
    data = path.read_bytes()
    magic, cpu, subtype, kind, count, size, flags, reserved = struct.unpack_from('<8I', data)
    assert (magic, cpu, subtype, kind) == (0xfeedfacf, 0x100000c, 0, 1)
    sections, symbols = {}, {}
    relocations, symbol_names = [], []
    offset = 32
    for _ in range(count):
        command, length = struct.unpack_from('<2I', data, offset)
        if command == 0x19:  # LC_SEGMENT_64
            nsects = struct.unpack_from('<I', data, offset + 64)[0]
            for index in range(nsects):
                p = offset + 72 + index * 80
                name, segment, address, length_s, fileoff, align, reloc, nreloc, sflags, *_ = struct.unpack_from('<16s16sQQ8I', data, p)
                name = name.rstrip(b'\0').decode()
                sections[name] = dict(segment=segment.rstrip(b'\0').decode(), address=address,
                                      size=length_s, flags=sflags, relocations=nreloc)
                if name == '__text':
                    words = struct.unpack_from('<3I', data, fileoff)
                    # Exactly ADRP x0 / ADD x0,x0,#imm / B .: no SP use, stores,
                    # calls, RET, allocation, init or shared scratch instructions.
                    assert length_s == 12
                    assert words[0] & 0x9f00001f == 0x90000000
                    assert words[1] & 0xffc003ff == 0x91000000
                    assert words[2] == 0x14000000
                    assert sflags & 0x80000400 == 0x80000400
                    for j in range(nreloc):
                        address_r, bits = struct.unpack_from('<iI', data, reloc + j * 8)
                        relocations.append(dict(offset=address_r, symbol_index=bits & 0xffffff,
                                                pcrel=(bits >> 24) & 1, length=(bits >> 25) & 3,
                                                external=(bits >> 27) & 1, type=bits >> 28))
                elif name == '__cstring':
                    assert sflags & 0xff == 2  # S_CSTRING_LITERALS, __TEXT intent
                    assert data[fileoff:fileoff + length_s] == b'DIAG: PMAP initializer normal epilogue reached; STOP\0'
        elif command == 2:  # LC_SYMTAB
            symoff, nsyms, stroff, strsize = struct.unpack_from('<4I', data, offset + 8)
            for index in range(nsyms):
                string, typ, section, desc, value = struct.unpack_from('<IBBHQ', data, symoff + index * 16)
                name = data[stroff + string:data.index(b'\0', stroff + string)].decode()
                symbol_names.append(name)
                assert typ & 0x0e != 0, f'undefined symbol: {name}'
                symbols[name] = dict(type=typ, section=section, value=value)
        offset += length
    assert set(sections) == {'__text', '__cstring'}  # no init/data/termination section
    expected = {'_nuwa_pmap_ret_observer', '_nuwa_pmap_ret_observer_renderer_branch', '_nuwa_pmap_ret_observer_message'}
    assert {name for name, sym in symbols.items() if sym['type'] & 1} == expected
    assert symbols['_nuwa_pmap_ret_observer']['value'] == 0
    assert symbols['_nuwa_pmap_ret_observer_renderer_branch']['value'] == 8
    for relocation in relocations:
        index = relocation.pop('symbol_index')
        assert index < len(symbol_names), f'relocation symbol index out of range: {index}'
        relocation['target'] = symbol_names[index]
    message = '_nuwa_pmap_ret_observer_message'
    assert sorted(relocations, key=lambda item: item['offset']) == [
        dict(offset=0, pcrel=1, length=2, external=1, type=3, target=message),
        dict(offset=4, pcrel=0, length=2, external=1, type=4, target=message),
    ]  # ARM64 PAGE21 / PAGEOFF12, 4-byte instruction fields, defined message target
    assert symbols[message]['type'] == 0x0f  # external N_SECT, not an undefined reference
    assert symbols[message]['section'] == list(sections).index('__cstring') + 1
    assert symbols[message]['value'] == sections['__cstring']['address']
    return dict(header='arm64 MH_OBJECT', sections=sections, symbols=symbols,
                relocations=relocations, undefined=[])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True, help='read-only UniXNU base')
    parser.add_argument('--out', type=Path, required=True, help='dedicated empty evidence directory')
    args = parser.parse_args()
    device = Path(__file__).resolve().parents[1]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.base.resolve() / 'scripts'))
    from unixnu.config import parse_config
    from unixnu.kernel import xnu_env
    baseline = parse_config((device / 'configs/nuwa_defconfig').read_text())
    diagnostic = parse_config((device / 'configs/nuwa_pmap_ret_defconfig').read_text())
    common = parse_config((args.base / 'profiles/arch/arm64/configs/common.config').read_text())
    assert common['XNU_BUILD_ARCHIVES'] is True
    assert all(diagnostic[key] == value for key, value in baseline.items())
    assert diagnostic['XNU_NUWA_PMAP_RET_OBSERVER'] is True
    tree = out / 'tree'
    tree.mkdir()
    class Context:
        def need_config(self):
            return diagnostic
    ctx = Context()
    ctx.tree = tree
    flags = xnu_env(ctx)['XNU_EXTRA_LD_ARCHIVES']
    assert flags.split() == [
        f'-Wl,-force_load,{tree}/build/nuwa-pmap-ret-observer/libNuwaPmapRetObserver.a',
        '-Wl,-u,_nuwa_pmap_ret_observer',
        f'-Wl,-map,{tree}/build/nuwa-pmap-ret-observer/native-link.map']
    script = device / 'scripts/build-nuwa-pmap-ret-observer.py'
    env = dict(os.environ, UNIXNU_DEVICE=str(device))
    config = out / '.config'
    commands = []
    def run(extra=(), environment=env):
        command = [sys.executable, str(script), *extra]
        result = subprocess.run(command, cwd=tree, env=environment, text=True, capture_output=True)
        commands.append(dict(cwd=str(tree), argv=command, exit=result.returncode,
                             stdout=result.stdout, stderr=result.stderr))
        assert result.returncode == 0, result.stderr
    config.write_text('CONFIG_XNU_NUWA_PMAP_RET_OBSERVER=n\n')
    run(['--clang', '/nonexistent', '--libtool', '/nonexistent'])
    assert not list(tree.iterdir())
    config.write_text('# No diagnostic switch; environment must not enable it.\n')
    run(['--clang', '/nonexistent'], dict(env, XNU_NUWA_PMAP_RET_OBSERVER='1'))
    assert not list(tree.iterdir())
    config.write_text((device / 'configs/nuwa_pmap_ret_defconfig').read_text())
    run()  # Actual recipe cwd + UNIXNU_DEVICE fallback
    component = tree / 'build/nuwa-pmap-ret-observer'
    obj = component / 'pmap-ret-observer.o'
    report = inspect_object(obj)
    archive = component / 'libNuwaPmapRetObserver.a'
    result = subprocess.run(['/usr/bin/llvm-ar', 't', str(archive)], check=True, text=True, capture_output=True)
    assert result.stdout.splitlines() == ['pmap-ret-observer.o']
    extracted = subprocess.run(['/usr/bin/llvm-ar', 'p', str(archive), 'pmap-ret-observer.o'], check=True, capture_output=True)
    assert extracted.stdout == obj.read_bytes()
    # Normal assembled package mapping, without UNIXNU_DEVICE fallback.
    mapped = tree / 'kits/nuwa'
    mapped.parent.mkdir()
    mapped.symlink_to(device / 'package', target_is_directory=True)
    clean_env = {key: value for key, value in env.items() if key != 'UNIXNU_DEVICE'}
    run(['--out', str(out / 'mapped-component')], clean_env)
    assert (out / 'mapped-component/pmap-ret-observer.o').read_bytes() == obj.read_bytes()
    before = {p.name: p.read_bytes() for p in component.iterdir()}
    config.write_text('# CONFIG_XNU_NUWA_PMAP_RET_OBSERVER is not set\n')
    run()
    assert before == {p.name: p.read_bytes() for p in component.iterdir()}
    config.write_text('CONFIG_XNU_NUWA_PMAP_RET_OBSERVER=y\nCONFIG_XNU_NUWA_PMAP_RET_OBSERVER=n\n')
    run(['--out', str(out / 'disabled-output')])
    assert not (out / 'disabled-output').exists()
    report.update(status='self-checked', link_flags=flags, archive=str(archive), commands=commands,
                  checks=['config parser and tree expansion', 'disabled empty/stale outputs unchanged',
                          'enabled recipe and package mapping', 'archive member byte identity',
                          'exact instruction whitelist and local relocations', 'no undefined/init/runtime calls'])
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
