"""Qualify CHECK5 shipped bytes and explicit scoped reuse of CHECK4 evidence."""
import argparse, collections, json, struct, sys, uuid, zlib
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location('check5_build',Path(__file__).with_name('build-ufs-check5-r1.py'))
B5=importlib.util.module_from_spec(spec);sys.modules['check5_build']=B5;spec.loader.exec_module(B5)
from check5_build import *

p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--reproduce',type=Path,required=True);p.add_argument('--report-dir',type=Path,required=True);a=p.parse_args()
w=a.work.resolve();r=a.report_dir.resolve();r.mkdir(parents=True,exist_ok=True)
output=r/'offline-qualification-final.json';assert not output.exists()
proof=read(w/'build.json');kernel=(w/'kernel.macho').read_bytes();image=Path(proof['image_path']).read_bytes()
assert sha(kernel)==proof['kernel_sha256'] and sha(image)==proof['image_sha256'] and len(image)==proof['image_bytes']==70266880
assert kernel==(a.reproduce/'kernel.macho').read_bytes()
assert proof['symbols']==read(a.reproduce/'kernel-proof.json')['symbols']
parent=(PARENT/'kernel.macho').read_bytes();assert sha(parent)==KERNEL_SHA
assert sha((PARENT/'boot-ufs-check-4-r1.img').read_bytes())==IMAGE_SHA
old=read(PARENT/'kernel-proof.json');delta=proof['check5_delta'];b=trace.builder();m=b.macho(kernel)
assert b.macho(parent)['segments']==m['segments'] and len(kernel)==len(parent)
masked=bytearray(kernel)
for start,end in delta['allowed_file_ranges']:masked[start:end]=parent[start:end]
assert masked==parent
for change in delta['callers']:
 at=change['file_offset'];assert kernel[at:at+4].hex()==change['after'] and parent[at:at+4].hex()==change['before']
 address=int(change['address'],16);word=struct.unpack_from('<I',kernel,at)[0];imm=word&0x3ffffff
 if imm&(1<<25):imm-=1<<26
 assert address+4*imm==proof['symbols'][change['symbol']]
assert proof['targets']==old['targets'] and proof['chunks']==old['chunks'] and proof['vtables']==old['vtables']
for chunk in proof['chunks']:
 at=b.backed(m,chunk['address'],chunk['bytes']);assert sha(kernel[at:at+chunk['bytes']])==chunk['sha256']
for obj in proof['objects']:assert sha(Path(obj['path']).read_bytes())==obj['sha256']
assert len(proof['objects'])==7
state=b.backed(m,proof['targets']['coarse_state']);assert kernel[state:]==bytes(4096)

priorfile=ROOT/'reports/ufs-check-4-r1/offline-qualification-final.json';prior=read(priorfile)
assert prior['offline_qualified'] and prior['kernel_sha256']==KERNEL_SHA and prior['image_sha256']==IMAGE_SHA
for path,digest in prior['sources'].items():assert sha((ROOT/path).read_bytes())==digest,('changed inherited source',path)
for path,digest in prior['supporting_reports'].items():assert sha((ROOT/native_path(path)).read_bytes())==digest,('changed inherited report',path)

fwsize,envsize=struct.unpack_from('<II',image,8);start=4096+((fwsize+4095)&~4095);envelope=image[start:start+envsize]
assert envelope[:16]==transport.MAGIC
version,header,fatsize,crc=struct.unpack_from('<IIQI',envelope,16);fat=envelope[header:]
assert (version,header,fatsize)==(1,64,67108864) and len(fat)==fatsize and zlib.crc32(fat)==crc
assert fat==(w/'payload.fat').read_bytes()
fd=transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd';shim=transport.ARTIFACT/'shim/shim.bin';stock=native_path(transport.STOCK).read_bytes()
assert sha(stock)==transport.STOCK_SHA and sha(fd.read_bytes())==transport.FD_SHA and sha(shim.read_bytes())==transport.SHIM_SHA
container=transport.inspect_container(image,stock[:4096],shim.read_bytes()+fd.read_bytes(),envelope,3)
back=w/'qualified-readback';back.mkdir();fatpath=back/'shipped.fat';fatpath.write_bytes(fat);files={}
for name in ('kernel.macho','kernel.macho.adt','unixnu.toml'):
 target=back/name;run('mcopy','-i',fatpath,'::/EFI/UniXNU/'+('' if name=='unixnu.toml' else 'Payloads/')+name,target)
 assert target.read_bytes()==(w/'fat'/name).read_bytes();files[name]=sha(target.read_bytes())
assert files['kernel.macho']==proof['kernel_sha256']
listing=run('mdir','-i',fatpath,'-/','::/').decode();assert 'apfs' not in listing.lower() and 'root-restore' not in listing.lower()
fsck=run('fsck.fat','-n',fatpath).decode()
menu=(back/'unixnu.toml').read_text();config=tomllib.loads(menu)
assert len(config['entry'])==1 and config['entry'][0]['args']=='-v native-ufs-root=1 launchdsuffix=release' and 'initrd' not in config['entry'][0]
assert menu.replace('UFS-CHECK-5 r1','UFS-CHECK-4 r1')==(PARENT/'fat/unixnu.toml').read_text()
adt=(back/'kernel.macho.adt').read_bytes();tree=context.parse(adt);chosen=context.properties(context.find(tree,'/chosen'))
assert 'RAMDisk' not in context.properties(context.find(tree,'/chosen/memory-map')) and 'boot-uuid' not in chosen
assert chosen['root-matching']==(ROOT/'out/ufs-root-chain-r2/chosen-root-matching.bin').read_bytes()
header_address,policy_size=struct.unpack_from('<QQ',kernel,b.backed(m,proof['targets']['_verified_root_policies'],16))
root_uuid=str(uuid.UUID(bytes=kernel[b.backed(m,header_address+40,16):][:16])).upper()
assert root_uuid=='DADD93F8-DBBF-4B17-A1DF-0F11E64172F7' and root_uuid.encode() in chosen['root-matching']
assert proof['owner_root_binding_enabled'] and proof['policy']==old['policy'] and not proof['policy']['policy_hash_table_in_boot']
assert (w/'base.adt').read_bytes()==(PARENT/'base.adt').read_bytes()
assert (w/'launch/nonce.bin').read_bytes()!=(PARENT/'launch/nonce.bin').read_bytes()
launch=context.validate(adt,back/'kernel.macho',fd,shim,(w/'launch/nonce.bin').read_bytes(),(w/'launch/launch-manifest.json').read_bytes())

tests={}
for path,count,key in [(r/'tests-qualified/target-lifetime.json',7,'cases'),(r/'tests-qualified/native-el0-restore.json',4,'cases'),
 (r/'tests-qualified/native-helpers.json',14,'cases'),(r/'tests-qualified/native-continuation.json',20,'cases'),
 (w/'coarse-tests.json',20,'tests'),(w/'machine-tests.json',8,'tests')]:
 report=read(path);assert report['passed'] and report['kernel_sha256']==proof['kernel_sha256'] and len(report[key])==count
 tests[str(path.relative_to(ROOT))]=dict(sha256=sha(path.read_bytes()),cases=count)
for path in (w/'layout-tests.json',r/'tests-qualified/regression-binding.json'):
 report=read(path);assert report['passed'] and report['kernel_sha256']==proof['kernel_sha256'];tests[str(path.relative_to(ROOT))]=dict(sha256=sha(path.read_bytes()))
assert read(w/'layout-tests.json')['legacy_a_rectangle_untouched'] and read(w/'layout-tests.json')['short_stride_rejected']
assert read(w/'coarse-tests.json')['exec_return_limit']==2

# Required inventory tool, unchanged. Its historical filename heuristic is
# corrected in the new snapshot by explicit CHECK5 build metadata below.
audit=module('patch_inventory',ROOT/'scripts/audit-patch-inventory.py')
inventory=r/'patch-inventory-final.json';assert not inventory.exists()
audit.carrier_snapshot(w/'build.json',proof,inventory)
inv=read(inventory);inv['sources'][0]=audit.ref(ROOT/proof['builder_source'])
inv['check5_delta']=delta
for entry in inv['entries']:
 if entry.get('patch',{}).get('address')=='0xfffffff00769d230':
  entry['category']='observation';entry['rationale']='Publish successful scoped ip_new_thread, bounded phase9; native task_clear_return_wait retained. Prior artificial hold remains retired.'
inv['counts']=dict(collections.Counter(x['category'] for x in inv['entries']))
inv['inherited_inventory']=dict(path='reports/ufs-check-4-r1/patch-inventory-final.json',sha256=sha((ROOT/'reports/ufs-check-4-r1/patch-inventory-final.json').read_bytes()))
inv['observer_changes']=[dict(site='0xfffffff00769d230',category='observation',change='publish new exec thread before native release, successful scope only'),dict(site='0xfffffff00767356c',category='observation',change='remove old caller target overwrite; retain native replay and exec marker')]
inv['new_hooks']=0;inv['new_control_stops']=0;save(inventory,inv)

source_names=['scripts/build-ufs-check5-r1.py','scripts/test-ufs-check5-r1.py','scripts/qualify-ufs-check5-package.py',str(SOURCE.relative_to(ROOT)),
 'package/kernel-mainline/ExecEl0Target-staging.S','scripts/exec_carrier_model.py','scripts/test-exec-native-helpers.py','scripts/test-exec-native-continuation.py',
 'scripts/build_xnu_boot_package.py','scripts/flush_trace_inputs.py','scripts/nuwa_launch_context.py','scripts/usb_ramdisk_package.py','package/ufs-r1/Status-r2.S']
sources={path:sha((ROOT/path).read_bytes()) for path in source_names}
result=dict(candidate='UFS-CHECK-5 r1',offline_qualified=True,deployable=False,consumed=False,device_executed=False,device_root_cause_confirmed=False,
 image_path=str(Path(proof['image_path']).relative_to(ROOT)),image_sha256=proof['image_sha256'],image_bytes=len(image),kernel_sha256=proof['kernel_sha256'],
 kernel_reproduced=True,reproduction=str(a.reproduce),all_bytes_outside_declared_ranges_unchanged=True,delta=delta,container=container,files=files,fsck=fsck,launch=launch,
 tests=tests,new_machine_cases=73,layout=read(w/'layout-tests.json'),patch_inventory=dict(path=str(inventory.relative_to(ROOT)),sha256=sha(inventory.read_bytes())),sources=sources,
 reused=dict(qualification=str(priorfile.relative_to(ROOT)),sha256=sha(priorfile.read_bytes()),sources=prior['sources'],supporting_reports=prior['supporting_reports'],
 rationale='Seven CI objects, all linked chunks, native instructions outside existing observer callers, targets, policies, bootstrap, PMGR and UFS ledger bytes unchanged. Observer compiler reproduced CHECK4 exactly; changed observer and its callers tested anew.',
 checks=['NativeUfs CI/host/QEMU and authentication/root policy','bootstrap and native launchdsuffix','legacy retirement and FSCompression prefix cleanup','linked UFS ledger and native polling'],
 boundary='Historical reports retain CHECK4 hashes. They are component reuse, not a claim that CHECK5 ran those whole-kernel tests or QEMU booted XNU/APFS.'),
 scope='Offline-only actual ARM64 observer/native path instruction models and shipped package checks. Scheduling, filesystem IO, VM loader and signature services retain explicit fixture boundaries. No device or EL0 user execution.',
 remaining=['fresh recording and recovery agreement plus nuwa/A preflight','physical post-namei exec/EL0 evidence','SystemOS/Data/services/graphics and interactive SpringBoard'])
save(output,result)
candidate=dict(candidate=result['candidate'],offline_qualified=True,image_path=str(Path(proof['image_path']).relative_to(ROOT)),image_sha256=proof['image_sha256'],image_bytes=len(image),kernel_sha256=proof['kernel_sha256'],
 consumed=False,device_executed=False,deployable=False,ready_for_next_trial_preflight=True,qualification=str(output.relative_to(ROOT)),patch_inventory=str(inventory.relative_to(ROOT)),
 supersedes='UFS-CHECK-4 r1 (frozen and unconsumed)',fresh_recording_confirmation_required=True,fresh_recovery_confirmation_required=True,fresh_device_preflight_required=True,
 slot_unbootable_and_retry_check_required=True,previous_recovery='reports/ufs-check-3-r1/trial/postcondition.json',media_directory='../Media-nuwa/UFS-CHECK-5-r1/original',
 goal='Continue native exec with correctly scoped new-thread EL0 boundary observation; device stall root cause remains unknown')
save(r/'candidate.json',candidate)
save(r/'superseded-offline-artifacts.json',dict(selected=candidate['image_path'],selected_sha256=candidate['image_sha256'],not_for_trial=[
 dict(path='out/ufs-check-5-r1',reason='incomplete builder attempt; missing entry alias rejected, no package'),
 dict(path='out/ufs-check-5-r1-clean',reason='integration test rejected retained old-thread overwrite; do not deploy',image_sha256='d0a70ab28e5ae8373787611427c76e1d8467a018470c60bb6e9feaf99924fa89'),
 dict(path='out/ufs-check-5-r1-reproduce',reason='independent kernel reproduction only, no package'),
 dict(path='out/ufs-check-4-r1-clean',reason='frozen prior candidate superseded by CHECK5; historical files unchanged')]))
print('PASS CHECK5 final qualification',proof['image_sha256'],len(image))
