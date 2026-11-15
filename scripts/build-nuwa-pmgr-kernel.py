#!/usr/bin/env python3
"""Isolated PMGR root-publication native relink + donor pthread prelink + renderer.

Replay recorded compile/link inputs; never mutate the recorded native tree or
official checkout. The device patch is opt-in here, not in the normal series.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tomllib

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = Path('/mnt/d/Code/PortingiOS/UniXNU')
OLD = Path('/root/nuwa-pmap-ret-native-20261111/build-result.json')
REC = json.loads(OLD.read_text())
TREE = Path(REC['work']) / 'tree'
OBJ = TREE / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837'
sys.path.insert(0, str(TREE / 'kits/NativePrelink'))
from native_prelink import macho, exports, backed_offset, unserialize_xml
from emit_prelink import emit


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(path):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path.read_bytes()))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def names(raw):
    return {name: va for va, ns in exports(raw, macho(raw)).items() for name in ns}


def read(raw, va, size):
    at = backed_offset(macho(raw)['segments'], va, size, len(raw))
    return raw[at:at+size]


def info(raw):
    seg = next(s for s in macho(raw)['segments'] if s['name'] == '__PRELINK_INFO')
    return unserialize_xml(read(raw, seg['va'], seg['filesize']))


def module(raw, identifier):
    entry = next(e for e in info(raw)['_PrelinkInfoDictionary'] if e['CFBundleIdentifier'] == identifier)
    at = backed_offset(macho(raw)['segments'], entry['_PrelinkExecutableLoadAddr'], 32, len(raw))
    return entry, macho(raw, at)


def compile_replay(source, output, compile_record, run):
    rec = json.loads(compile_record.read_text().strip().rstrip(','))
    args = list(rec['arguments'])
    args[args.index(rec['file'])] = str(source)
    args[args.index('-o')+1] = str(output)
    args += ['-iquote', str(Path(rec['file']).parent)]
    run('compile-' + output.stem, args, cwd=rec['directory'])


def renderer(out, prelink, native_path, linkmap, run):
    B = load(ROOT / 'scripts/build-nuwa-pmap-ret-diagnostic.py', 'pmgr_renderer_helpers')
    reader = load(TREE / 'kits/XnuPrelink/native_prelink.py', 'pmgr_renderer_reader')
    raw, native_raw = prelink.read_bytes(), native_path.read_bytes()
    image, native = B.Image(reader, raw), B.Image(reader, native_raw)
    # Existing start.o and its source are reused; new map proves padding ownership.
    padding = B.padding_provenance(REC, native, image, linkmap.read_text(encoding='latin-1'))
    observer = B.validate_observer(image)
    assert image.word(observer[1]) == 0x14000000
    pmap = B.discover_pmap(image)
    assert image.word(pmap['ret']) == 0xd65f03c0
    os.environ['UNIXNU_UEFI'] = str(ROOT.parent / 'uefi-nuwa')
    os.environ['PATH'] = '/usr/bin:/bin'
    patcher = load(BASE / 'scripts/patch-xnu-entry-probe.py', 'pmgr_renderer_patcher')
    patcher.load_segments(raw)
    ns = patcher.rebase(prelink, raw)
    sites = [(patcher.ENTRY_VA, 1, {'target': patcher.START_FIRST_CPU}),
             (patcher.MMU_ENABLE_VA, 2, {'target': patcher.MMU_ENABLE_VA+4})]
    start = max(patcher.CAVES[stage] for _, stage, _ in sites) + patcher.CAVE_SIZE
    assert patcher.PANIC_CAVE_END == int(padding['vector'], 16)-16
    work = out / 'renderer'
    work.mkdir()
    code, address, entry = patcher.assemble_c(BASE / 'scripts/xnu-panic-screen.c', start, work, ns)
    common = patcher.panic_common_entry(work, code, address)
    assert address == entry == start and address+len(code) <= patcher.PANIC_CAVE_END
    final, changes = bytearray(raw), []

    def put(label, va, data, expected):
        image.span(va, len(data), 5)
        at = image.offset(va, len(data))
        assert image.read(va, len(data)) == expected, label
        final[at:at+len(data)] = data
        changes.append(dict(label=label, va=hex(va), fileoff=at, size=len(data),
                            before_sha256=sha(expected), after_sha256=sha(data)))

    for site, stage, target in sites:
        bar_dir = out / ('bar-' + str(stage))
        bar_dir.mkdir()
        bar = patcher.assemble(patcher.SOURCES[stage], patcher.CAVES[stage], target, bar_dir)
        assert len(bar) <= patcher.CAVE_SIZE
        put('bar-' + str(stage), patcher.CAVES[stage], bar, bytes(len(bar)))
        expected = B.branch(site, patcher.START_FIRST_CPU) if stage == 1 else 0xd5181000
        assert native.word(site) == expected
        put('hook-' + str(stage), site, struct.pack('<I', B.branch(site, patcher.CAVES[stage])), struct.pack('<I', expected))
    put('renderer', address, code, bytes(len(code)))
    for name, target in (('_panic', entry), ('_panic_trap_to_debugger', common)):
        site = image.symbols[name]
        assert native.read(site, 4) == image.read(site, 4)
        put(name, site, struct.pack('<I', B.branch(site, target)), image.read(site, 4))
    changed = B.check_differences(raw, bytes(final), [(c['fileoff'], c['size']) for c in changes])
    target = out / 'kernel.macho'
    target.write_bytes(final)
    result = dict(input=record(prelink), output=record(target), patches=changes, changed_bytes=changed,
                  padding=padding, observer=observer, pmap=pmap, renderer_entry=hex(entry), common_entry=hex(common))
    (out / 'renderer-manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    return target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--reuse-provider', type=Path, help='reuse this work item\'s compiled provider, source SHA must match')
    a = p.parse_args()
    out = a.out.resolve()
    assert out.is_relative_to(ROOT / 'out') and not out.exists(), 'require fresh device out/'
    out.mkdir(parents=True)
    env = dict(os.environ, DARWIN_TRIPLE='arm64-apple-ios17.0',
               CROSS_CLANG='/opt/unixnu-linux/llvm/bin/clang',
               CROSS_EXTRA_FLAGS='-mllvm -disable-atexit-based-global-dtor-lowering',
               PYTHONDONTWRITEBYTECODE='1')
    env['PATH'] = '/opt/unixnu-linux/CommandLineTools/usr/bin:/opt/unixnu-linux/bin:' + env.get('PATH', '')
    commands = []

    def run(label, command, cwd=ROOT):
        command = [str(x) for x in command]
        log = out / (label + '.log')
        with log.open('wb') as stream:
            result = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(label=label, argv=command, cwd=str(cwd), exit=result.returncode, log=str(log)))
        (out / 'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
        if result.returncode:
            errors = [line for line in log.read_text(errors='replace').splitlines() if 'error:' in line]
            print(errors[0] if errors else log.read_text(errors='replace')[-2000:])
            raise SystemExit(f'{label}: exit {result.returncode}; {log}')

    assert subprocess.check_output(['git', '-C', str(BASE), 'rev-parse', 'HEAD'], text=True).strip() == REC['base_revision']
    for key in ('native', 'link_map', 'config', 'kernelcache', 'pristine_prelink'):
        assert record(Path(REC[key]['path']))['sha256'] == REC[key]['sha256'], key
    source_record = json.loads((Path(REC['work']) / 'xnu-inputs.json').read_text())
    for patch in source_record['patches']:
        assert sha(Path(patch['path']).read_bytes()) == patch['sha256'], patch['path']
    assert subprocess.check_output(['git', '-C', source_record['source'], 'rev-parse', 'HEAD'], text=True).strip() == source_record['commit']
    old_carrier = ROOT / 'out/pthread-renderer-20261112-r1/renderer-baseline.macho'
    carrier = old_carrier.read_bytes()
    assert sha(carrier) == 'e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d'
    abi = json.loads((ROOT / 'out/nuwa-platform-power-20261113-r2/build-report.json').read_text())
    donor = Path(REC['kernelcache']['path']).read_bytes()
    board = tomllib.loads((ROOT / 'board.toml').read_text())
    # Resolve inherited prelink fields from the pinned OS profile.
    prior = json.loads((ROOT / 'out/pthread-normal-prelink-20261112-r4/work/kernel/kernel.json').read_text())
    slide = prior['slide']
    roots = board['os_overrides']['ios-16.7.16-20H392']['kernel']['prelink']['roots']
    assert roots.count('com.apple.kec.pthread') == 1 and slide == -0x1000000
    # Re-derive every binding from the exact donor component + segment offset.
    # Old carrier addresses identify reviewed offsets only; never copy them as
    # final link values. Require matching component extents and the donor slide.
    _, old_mod = module(carrier, 'com.apple.driver.ApplePMGR')
    _, donor_mod = module(donor, 'com.apple.driver.ApplePMGR')
    bindings, anchors = {}, {}
    for name, value in abi['bindings'].items():
        address = int(value, 16)
        seg, = [s for s in old_mod['segments'] if s['va'] <= address < s['va']+s['size']]
        new, = [s for s in donor_mod['segments'] if s['name'] == seg['name']]
        offset = address-seg['va']
        assert new['size'] == seg['size'] and seg['va'] == new['va']+slide
        target = new['va']+offset+slide
        if seg['initprot'] & 4:
            assert read(carrier, address, 32) == read(donor, new['va']+offset, 32)
        bindings[name] = target
        anchors[name] = dict(module='com.apple.driver.ApplePMGR', segment=seg['name'], offset=hex(offset),
                             donor_va=hex(new['va']+offset), slide=slide, final_va=hex(target))
    assert len(bindings) == 8
    (out / 'original-bindings.json').write_text(json.dumps(anchors, indent=2)+'\n')
    asm = out / 'original-bindings.S'
    asm.write_text(''.join(f'.globl {name}\n.set {name}, {va:#x}\n' for name, va in bindings.items()))
    run('original-bindings', ['/opt/unixnu-linux/llvm/bin/clang-24', '--target=arm64-apple-ios17.0', '-c', asm, '-o', out / 'original-bindings.o'])
    provider = a.reuse_provider.resolve() if a.reuse_provider else out / 'provider'
    if a.reuse_provider:
        report = json.loads((provider / 'build-report.json').read_text())
        assert report['source_sha256'] == sha((ROOT / 'package/NuwaPlatformPower.cpp').read_bytes())
        assert report['archive_sha256'] == sha((provider / 'libNuwaPlatformPower.a').read_bytes())
    else:
        run('provider', ['/home/wh1stl3/.local/bin/python3.11', '-B', ROOT / 'scripts/build-nuwa-platform-power.py', '--out', provider])
    # Only the compiled late object is carried forward; its old absolute member
    # is discarded and replaced by the donor-derived bindings above.
    archive = out / 'libNuwaPlatformPower.a'
    run('provider-archive', ['/usr/bin/llvm-ar', 'rcs', archive, provider / 'NuwaPlatformPower.late.o', out / 'original-bindings.o'])
    isolated = out / 'tree'
    source = isolated / 'iokit/Kernel/IOPlatformExpert.cpp'
    source.parent.mkdir(parents=True)
    source.write_bytes((TREE / '.cache/xnu-work/iokit/Kernel/IOPlatformExpert.cpp').read_bytes())
    patch = ROOT / 'patches/xnu/8796-nuwa-pmgr-root-publication.patch'
    run('device-patch', ['/usr/bin/patch', '--batch', '--forward', '-p1', '-i', patch], cwd=isolated)
    platform_obj = out / 'IOPlatformExpert.cpo'
    compile_replay(source, platform_obj, OBJ / 'iokit/DEVELOPMENT/IOPlatformExpert.cpo.json', run)
    files = (OBJ / 'link.filelist').read_text().splitlines()
    old_obj = str(OBJ / 'iokit/DEVELOPMENT/IOPlatformExpert.cpo')
    assert files.count(old_obj) == 1
    new_files = [str(platform_obj) if f == old_obj else f for f in files]
    filelist = out / 'link.filelist'
    filelist.write_text('\n'.join(new_files)+'\n')
    linkdir = OBJ / 'mach.development.bcm2837.link'
    command = shlex.split((OBJ / '.LDFLAGS').read_text().rstrip('\0\n'))
    libcc = command.pop()
    assert libcc.endswith('/libcc_kext.a')
    archives = shlex.split((linkdir / 'mach.development.bcm2837.linkarchives').read_text())
    linkmap = out / 'native-link.map'
    archives = [f'-Wl,-map,{linkmap}' if x.startswith('-Wl,-map,') else x for x in archives]
    native = out / 'native.macho'
    command += ['-filelist', str(filelist), 'version.o', 'lastkerneldataconst.o', 'lastkernelconstructor.o', 'nonlto.o',
                '-o', str(native), libcc] + archives + [f'-Wl,-force_load,{archive}']
    run('native-link', command, cwd=OBJ)
    native_raw = native.read_bytes()
    ns = names(native_raw)
    for name, va in bindings.items():
        assert ns[name] == va, name
    # Official emitter independently checks all new native/component collisions
    # and resolves donor->native imports against this actual native layout.
    prelinked, manifest = emit(native_raw, donor, roots, slide)
    pristine = out / 'prelink.macho'
    pristine.write_bytes(prelinked)
    (out / 'prelink.json').write_text(json.dumps(manifest, indent=2)+'\n')
    final = renderer(out, pristine, native, linkmap, run)
    inputs = []
    for f in files + ['version.o', 'lastkerneldataconst.o', 'lastkernelconstructor.o', 'nonlto.o']:
        path = Path(f) if Path(f).is_absolute() else OBJ / f
        inputs.append(record(path))
    for arg in archives + [libcc]:
        path = arg.removeprefix('-Wl,-force_load,')
        if Path(path).is_file():
            inputs.append(record(Path(path)))
    result = dict(status='self-checked; no device approval', argv=sys.argv, source_record=record(OLD),
                  base_revision=REC['base_revision'], xnu_source_inputs=source_record,
                  original_native=REC['native'], original_map=REC['link_map'], config=REC['config'], donor=REC['kernelcache'],
                  source=record(ROOT / 'package/NuwaPlatformPower.cpp'), patch=record(patch),
                  isolated_source=record(source), platform_object=record(platform_obj),
                  provider_object=record(provider / 'NuwaPlatformPower.late.o'),
                  provider_report=record(provider / 'build-report.json'),
                  reused_link_inputs=inputs, link_flags=record(OBJ / '.LDFLAGS'),
                  native=record(native), native_map=record(linkmap), prelink=record(pristine),
                  archive=record(archive), bindings=anchors, output=record(final),
                  commands=commands, pthread_runtime_qualified=False, chmh_rebind_required=True,
                  initializer='manual only; late object __mod_init_func disabled',
                  limits='No full IOKit execution, hardware, FAT/outer, executor or device run.')
    (out / 'provenance.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(output=result['output'], native=result['native'], archive=result['archive']), indent=2))


if __name__ == '__main__':
    main()
