#!/usr/bin/env python3
"""Compile the explicitly non-runnable AMNM stage-one native archive."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, default=Path.cwd())
    p.add_argument('--config', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--font-dir', type=Path)
    a = p.parse_args()
    tree = a.tree.resolve()
    config = a.config or tree.parent / '.config'
    if 'CONFIG_XNU_NUWA_AMNM_OBSERVER=y' not in config.read_text().splitlines():
        print('AMNM disabled; no outputs touched')
        return
    src = tree / 'kits/nuwa/diagnostics'
    if not (src / 'amnm-observer.S').is_file():
        src = Path(os.environ['UNIXNU_DEVICE']) / 'package/diagnostics'
    font = a.font_dir or Path(os.environ['UNIXNU_DEVICE']).parent / 'uefi-nuwa/Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib'
    assert (font / 'Font.h').is_file(), font
    toolchain = Path(os.environ.get('UNIXNU_TOOLCHAIN', '/opt/unixnu-linux'))
    clang = os.environ.get('CROSS_CLANG', str(toolchain / 'llvm/bin/clang'))
    libtool = str(Path(os.environ.get('CLT_PREFIX', str(toolchain / 'CommandLineTools/usr'))) / 'bin/libtool')
    out = a.out or tree / 'build/nuwa-amnm-observer'
    out.mkdir(parents=True, exist_ok=True)
    objects = []
    binding_file = os.environ.get('AMNM_BINDINGS_JSON')
    binding_source = src / 'amnm-stage1-bindings.S'
    if binding_file:
        binding = json.loads(Path(binding_file).read_text())
        source = Path(binding['prelink']['path'])
        assert hashlib.sha256(source.read_bytes()).hexdigest() == binding['prelink']['sha256']
        sites = binding['sites']
        symbols = {'amnm_input_continue': int(sites['input'], 16)+4,
                   'amnm_store_continue': int(sites['store'], 16)+4,
                   'amnm_branch_zero': int(sites['branch_zero'], 16),
                   'amnm_branch_nonzero': int(sites['branch_nonzero'], 16),
                   'amnm_entry_continue': int(sites['entry'], 16)+4,
                   'amnm_precall_continue': int(sites['precall_blr'], 16),
                   'amnm_precall_return': int(sites['return'], 16),
                   'amnm_return_binding': int(sites['return'], 16),
                   'amnm_reader_binding': int(sites['reader'], 16),
                   'amnm_flag_binding': int(sites['flag'], 16)}
        binding_source = out / 'amnm-stage2-bindings.S'
        binding_source.write_text('/* derived stage-two absolute symbols; verify final prelink */\n' + ''.join(
            f'.globl _{name}\n.set _{name}, 0x{value:x}\n' for name, value in symbols.items()))
    for source in (src / 'amnm-observer.S', src / 'amnm-record.c', src / 'amnm-panic-screen.c', binding_source):
        name = source.name
        obj = out / (Path(name).stem + '.o')
        cmd = [clang, '-target', 'arm64-apple-ios16.0', '-march=armv8.1-a+lse',
               '-O2', '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-Werror']
        if name == 'amnm-panic-screen.c':
            cmd += ['-include', str(src / 'amnm-native-symbols.h'), '-I', str(font)]
        cmd += ['-c', str(source), '-o', str(obj)]
        print('+ ' + ' '.join(map(str, cmd)), flush=True)
        subprocess.run(cmd, check=True)
        objects.append(obj)
    cmd = [libtool, '-static', '-o', str(out / 'libNuwaAmnmObserver.a'), *map(str, objects)]
    print('+ ' + ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    print(('STAGE 2 BINDINGS REQUIRE FINAL-LAYOUT AUDIT' if binding_file else 'STAGE 1 TRAP PLACEHOLDERS') + ': NOT A DEVICE CANDIDATE', flush=True)

if __name__ == '__main__':
    main()
