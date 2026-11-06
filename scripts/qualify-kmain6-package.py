"""Read the shipped boot image back and bind all offline evidence to its kernel."""
import argparse
import hashlib
import json
import struct
import tempfile
import tomllib
import zlib
import uuid
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
parser.add_argument('--ci-root', type=Path, required=True)
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
readback = Path(tempfile.mkdtemp(prefix='shipped-readback-', dir=work))
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
assert config['entry'][0]['args'] == '-v native-ufs-root=1'
assert 'initrd' not in config['entry'][0]
adt = (readback/'kernel.macho.adt').read_bytes()
tree = context.parse(adt)
assert 'RAMDisk' not in context.properties(context.find(tree, '/chosen/memory-map'))
chosen = context.properties(context.find(tree, '/chosen'))
assert chosen['root-matching'] == (trace.R/'out/ufs-root-chain-r2/chosen-root-matching.bin').read_bytes()
assert 'boot-uuid' not in chosen
launch = context.validate(adt, readback/'kernel.macho', fd, shim,
    (work/'launch/nonce.bin').read_bytes(), (work/'launch/launch-manifest.json').read_bytes())
fsck = overlay.run('fsck.fat', '-n', overlay.linux(fatpath)).decode()
model = json.loads((work/'machine-tests.json').read_bytes())
assert model['passed'] and model['kernel_sha256'] == proof['kernel_sha256'] and len(model['tests']) == 8
coarse = json.loads((work/'coarse-tests.json').read_bytes())
assert coarse['passed'] and coarse['kernel_sha256'] == proof['kernel_sha256'] and len(coarse['tests']) == 20
layout = json.loads((work/'layout-tests.json').read_bytes())
assert layout['passed'] and layout['kernel_sha256'] == proof['kernel_sha256'] and layout['legacy_a_rectangle_untouched'] and layout['short_stride_rejected']
assert coarse['extra_field_pixels'] and coarse['scoped_el0_negative_controls'] and coarse['root_dev_t'] and coarse['exec_result']
for obj in proof['objects']:
    assert package.sha(Path(obj['path']).read_bytes()) == obj['sha256']
assert len(proof['objects']) == 6 and proof['policy']['headers_matched'] == 2
assert not proof['policy']['policy_hash_table_in_boot']
B=trace.builder();final_macho=B.macho(kernel)
policy_address=proof['targets']['_verified_root_policies']
header,size=struct.unpack_from('<QQ',kernel,B.backed(final_macho,policy_address,16))
root_uuid=str(uuid.UUID(bytes=kernel[B.backed(final_macho,header+40,16):][:16])).upper()
assert root_uuid.encode() in chosen['root-matching'] and root_uuid=='DADD93F8-DBBF-4B17-A1DF-0F11E64172F7'
assert proof['owner_root_binding_enabled']
assert proof['mapped_end'] - proof['segment']['va'] < 1024*1024
latch_offset = proof['segment']['fileoff']+proof['targets']['coarse_state']-proof['segment']['va']
assert kernel[latch_offset:] == bytes(4096)
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
ci_root = args.ci_root.resolve()
ci = json.loads((ci_root/'run.json').read_text(encoding='utf-8-sig'))
assert ci['conclusion'] == 'success' and ci['headSha'] == 'd4ad434062e94010b4363aa701785c39c40a25a8'
artifact = ci_root/'artifact.zip'
artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
metadata = json.loads((ci_root/'artifact.json').read_bytes())
assert metadata['workflow_run']['head_sha'] == ci['headSha']
if metadata.get('digest'):
    assert metadata['digest'] == 'sha256:'+artifact_sha
verified = json.loads((ci_root/'nuwa-8796-source/reports/verified-ufs/audit.json').read_bytes())
assert verified['passed'] and verified['archive_sha256'] == proof['verified_ufs_archive_sha256']
assert verified['verified_root_enabled'] and verified['inherited_vtable_verified']
assert kernel[trace.builder().backed(trace.builder().macho(kernel),0xfffffff0046fe7a4,4):][:4] == bytes.fromhex('f50300f9')
sources = [trace.R/'scripts'/name for name in ('build-ufs-kmain6-r1.py', 'prepare-kmain2-r2.py', 'test-kmain4-r1-stages.py', 'ufs_carrier_object_link.py',
    'test-kmain4-r1-mainline.py', 'qualify-ufs-iokit-bootstrap.py', 'qualify-kmain4-r1-package.py')]
sources += [trace.R/'scripts/audit_ios16_pmgr.py',trace.R/'scripts/test-kmain4-pmgr.py']
sources += [trace.R/'package/kernel-mainline/CoarseStages-exec-r1.S', trace.R/'config/ramblock-ios16-link-contract.json', trace.R/'config/ufs-ios16-verified-root-ci.json', trace.R/'package/verified-root/NuwaUfsPolicyRead.h', trace.R/'scripts/ci/build-verified-ufs.py', trace.R/'package/verified-root/NativeUfsRootAuth.cpp', trace.R/'package/verified-root/NuwaRootBinding.h', trace.R/'tests/ufs-root-binding.cpp']
pmgr = json.loads((work/'pmgr-tests.json').read_bytes())
assert pmgr['passed'] and pmgr['kernel_sha256'] == proof['kernel_sha256']
binding=json.loads((trace.R/'out/apfs-root-identity-r1/root-binding.json').read_bytes())
assert binding['passed'] and binding['mount_identity_and_iocount_cases']==9 and binding['media_provider_cases']==10
binding_sources={name.replace('\\','/'):value for name,value in binding['sources'].items()}
for name in ('package/verified-root/NuwaRootBinding.h','tests/ufs-root-binding.cpp'):
    assert binding_sources[name] == package.sha((trace.R/name).read_bytes())
assert 'NativeUfsRootAuth.o' in verified['objects']
init=json.loads((work/'exec-tests.json').read_bytes())
assert init['passed'] and init['kernel_sha256']==proof['kernel_sha256'] and len(init['tests'])==33
assert layout['all_19_rows_checked']
report = dict(exec_boundary_tests=init, root_binding_host=binding, root_binding_private_adapter_compiled=True, pmgr=pmgr, candidate='KMAIN-6 r1', offline_qualified=True, deployable=False, required_root_installed=False, persistent_recovery_verified=False, consumed=False, device_executed=False,
    image_path=proof['image_path'], image_sha256=proof['image_sha256'], image_bytes=len(image),
    kernel_sha256=proof['kernel_sha256'], ci_url=ci['url'], ci_commit=ci['headSha'],
    ci_source_kernel_sha256=proof['ci_source_kernel_sha256'], ci_archive_sha256=proof['ci_archive_sha256'],
    github_artifact_sha256=artifact_sha, container=container, files=files, fsck=fsck, launch=launch,
    kernel_reproduced=True, original_bytes_preserved_outside_declared_changes=True,
    vtables=proof['vtables'], machine_cases=model['tests'], coarse_stage_tests=coarse, display_layout=layout, native_startup_model=bootstrap, authenticated_driver_and_local_policy_linked=True, deployment_preconditions_met=False, root_image_required=proof['root_image_required'], verified_ufs=verified,
    sources={p.relative_to(trace.R).as_posix(): package.sha(p.read_bytes()) for p in sources},
    scope='Offline boot-package qualification with real CI authenticated NativeUfs and compact local trusted policies. No device execution or root installation.',
    remaining=['new candidate physical init boundaries', 'full BSD strategy read closure',
               'fresh trial recovery conditions; installed-root evidence tracked separately', 'SystemOS mount binding', 'EL0 and persistent Data'])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(offline_qualified=True, image_sha256=proof['image_sha256'], image_bytes=len(image))))
