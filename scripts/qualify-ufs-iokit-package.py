"""Read the shipped boot image back and bind all offline evidence to its kernel."""
import argparse
import hashlib
import json
import struct
import tomllib
import zlib
from pathlib import Path

import build_xnu_boot_package as package
import flush_trace_inputs as trace
import nuwa_launch_context as context
import ufs_carrier_object_link as overlay
import usb_ramdisk_package as transport

parser = argparse.ArgumentParser()
parser.add_argument('--work', type=Path, required=True)
parser.add_argument('--reproduce', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
work = args.work.resolve()
output = args.output.resolve()
assert not output.exists()
proof = json.loads((work/'build.json').read_bytes())
kernel = (work/'kernel.macho').read_bytes()
image = Path(proof['image_path']).read_bytes()
assert package.sha(kernel) == proof['kernel_sha256']
assert kernel == (args.reproduce/'kernel.macho').read_bytes()
assert package.sha(image) == proof['image_sha256']
assert len(image) == proof['image_bytes'] < 201326592
firmware_size, envelope_size = struct.unpack_from('<II', image, 8)
ramdisk_offset = 4096+((firmware_size+4095) & ~4095)
envelope = image[ramdisk_offset:ramdisk_offset+envelope_size]
assert envelope[:16] == transport.MAGIC
version, header_bytes, fat_bytes, crc = struct.unpack_from('<IIQI', envelope, 16)
assert (version, header_bytes, fat_bytes) == (1, 64, 67108864)
fat = envelope[header_bytes:]
assert len(fat) == fat_bytes and zlib.crc32(fat) == crc
assert fat == (work/'payload.fat').read_bytes()
fd = transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd'
shim = transport.ARTIFACT/'shim/shim.bin'
container = transport.inspect_container(image, transport.STOCK.read_bytes()[:4096],
    shim.read_bytes()+fd.read_bytes(), envelope, 3)
readback = work/'shipped-readback'
readback.mkdir(exist_ok=False)
fatpath = readback/'shipped.fat'
fatpath.write_bytes(fat)
files = {}
for name in ('kernel.macho', 'kernel.macho.adt', 'unixnu.toml'):
    target = readback/name
    overlay.run('mcopy', '-i', overlay.linux(fatpath), '::/EFI/UniXNU/'+
                ('' if name == 'unixnu.toml' else 'Payloads/')+name, overlay.linux(target))
    assert target.read_bytes() == (work/'fat'/name).read_bytes()
    files[name] = package.sha(target.read_bytes())
listing = overlay.run('mdir', '-i', overlay.linux(fatpath), '-/', '::/').decode()
assert 'root-restore' not in listing.lower() and 'apfs' not in listing.lower()
config = tomllib.loads((readback/'unixnu.toml').read_text())
assert len(config['entry']) == 1
assert config['entry'][0]['args'] == '-v nuwa-ufs-metadata=1'
assert 'initrd' not in config['entry'][0]
adt = (readback/'kernel.macho.adt').read_bytes()
tree = context.parse(adt)
assert 'RAMDisk' not in context.properties(context.find(tree, '/chosen/memory-map'))
launch = context.validate(adt, readback/'kernel.macho', fd, shim,
    (work/'launch/nonce.bin').read_bytes(), (work/'launch/launch-manifest.json').read_bytes())
fsck = overlay.run('fsck.fat', '-n', overlay.linux(fatpath)).decode()
model = json.loads((work/'machine-tests.json').read_bytes())
assert model['passed'] and model['kernel_sha256'] == proof['kernel_sha256'] and len(model['tests']) == 10
bootstrap = {}
for case in ('normal', 'occupied-probe', 'bad-topology', 'occupied-fb'):
    result = json.loads((work/('bootstrap-'+case+'.json')).read_bytes())
    assert result['candidate_sha256'] == proof['kernel_sha256'] and result['case'] == case
    assert result['error'] is None and not result['bad_memory'] and result['checks']
    bootstrap[case] = dict(stop=result['nearest'], checks=len(result['checks']))
    if case == 'normal':
        assert result['overlay_checks']['passed'] and result['nearest'] == '_kernel_bootstrap+0x0'
parent = json.loads(Path(proof['parent_build']).read_bytes())
original = (trace.R/parent['candidate']['path']).read_bytes()
B = trace.builder()
macho = B.macho(original)
segment = proof['segment']
allowed = [(c['offset'], c['offset']+len(bytes.fromhex(c['after']))) for c in proof['changes']]
allowed += [(segment['command_offset']+offset, segment['command_offset']+offset+8) for offset in (32, 48)]
code_offset = B.backed(macho, trace.START, proof['code_bytes'])
allowed.append((code_offset, code_offset+proof['code_bytes']))
previous = 0
for first, last in sorted(allowed):
    assert previous <= first and original[previous:first] == kernel[previous:first]
    previous = last
assert original[previous:] == kernel[previous:len(original)]
ci = json.loads((trace.R/'out/ci-iokit-41219744673/run.json').read_text(encoding='utf-8-sig'))
assert ci['conclusion'] == 'success' and ci['headSha'] == 'cd2206df2c52c812a0ac6f65ca4ee58d5c775c4b'
artifact = trace.R/'out/ci-iokit-41219744673.zip'
artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
assert artifact_sha == '6b4a9c9a9854e4d58953e89ad9fd32f55fba5eea61f637ad85e4c809b93819a8'
sources = [trace.R/'scripts'/name for name in ('build-ufs-iokit-mainline.py', 'ufs_carrier_object_link.py',
    'test-ufs-iokit-mainline.py', 'qualify-ufs-iokit-bootstrap.py', 'qualify-ufs-iokit-package.py')]
sources += [trace.R/'package/kernel-mainline/MetadataEntry.S', trace.R/'config/ramblock-ios16-link-contract.json']
report = dict(candidate='KMAIN-1 r1', offline_qualified=True, consumed=False, device_executed=False,
    image_path=proof['image_path'], image_sha256=proof['image_sha256'], image_bytes=len(image),
    kernel_sha256=proof['kernel_sha256'], ci_url=ci['url'], ci_commit=ci['headSha'],
    ci_source_kernel_sha256=proof['ci_source_kernel_sha256'], ci_archive_sha256=proof['ci_archive_sha256'],
    github_artifact_sha256=artifact_sha, container=container, files=files, fsck=fsck, launch=launch,
    kernel_reproduced=True, original_bytes_preserved_outside_declared_changes=True,
    vtables=proof['vtables'], machine_cases=model['tests'], native_startup_model=bootstrap,
    sources={p.relative_to(trace.R).as_posix(): package.sha(p.read_bytes()) for p in sources},
    scope='Offline diagnostic carrier qualification. Production objects plus root-selector observer.',
    remaining=['physical IOKit matching and IOMedia/BSD publication', 'physical block callback read',
               'authenticated UFS root installation and mount', 'EL0 and persistent Data'])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(offline_qualified=True, image_sha256=proof['image_sha256'], image_bytes=len(image))))
