"""Repackage byte-identical qualified kernel with native release-launchd selection."""
import argparse,importlib.util,json,hashlib,struct,zlib,tomllib
from pathlib import Path
import build_xnu_boot_package as package
import flush_trace_inputs as trace
import nuwa_launch_context as context
import usb_ramdisk_package as transport
import ufs_carrier_object_link as overlay
R=trace.R
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();w=a.work.resolve();assert w.is_relative_to(R/'out');w.mkdir(exist_ok=False)
qpath=R/'reports/ufs-check-2-r1/offline-qualification.json';q=json.loads(qpath.read_bytes());assert q['offline_qualified']
for n,h in q['sources'].items():assert package.sha((R/n).read_bytes())==h,n
old=R/'out/ufs-check-2-r1-final';kernel=(old/'kernel.macho').read_bytes();assert package.sha(kernel)==q['kernel_sha256']
release_path=R/'reports/ufs-check-3-r1/init-release-tests.json';release=json.loads(release_path.read_bytes());assert release['passed'] and release['kernel_sha256']==q['kernel_sha256'] and len(release['tests'])==8
spec=importlib.util.spec_from_file_location('previous_builder',R/'scripts/build-ufs-check2-r1.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
(w/'kernel.macho').write_bytes(kernel);proof=json.loads((old/'kernel-proof.json').read_bytes());(w/'kernel-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
package.UNIXNU_TOML=package.UNIXNU_TOML.replace('NUWA XNU FIRST ENTRY - ANALYSIS BUILD','NUWA UFS-CHECK-3 r1').replace('args = "-v"','args = "-v native-ufs-root=1 launchdsuffix=release"')
builder.make_package(w,w/'kernel.macho',proof)
oldname=Path(proof['image_path']);newname=w/'boot-ufs-check-3-r1.img';oldname.rename(newname);proof.update(image_path=str(newname),candidate='UFS-CHECK-3 r1',kernel_reused_byte_identically=True,observer_source='package/kernel-mainline/CoarseStages-ufs-check2-r1.S');(w/'build.json').write_text(json.dumps(proof,indent=2)+'\n')
image=newname.read_bytes();assert package.sha(image)==proof['image_sha256'];fw,envlen=struct.unpack_from('<II',image,8);off=4096+((fw+4095)&~4095);env=image[off:off+envlen];assert env[:16]==transport.MAGIC;version,header,length,crc=struct.unpack_from('<IIQI',env,16);fat=env[header:];assert (version,header,length)==(1,64,67108864) and zlib.crc32(fat)==crc
back=w/'readback';back.mkdir();fatpath=back/'shipped.fat';fatpath.write_bytes(fat)
for name in ('kernel.macho','kernel.macho.adt','unixnu.toml'):
 overlay.run('mcopy','-i',overlay.linux(fatpath),'::/EFI/UniXNU/'+('' if name=='unixnu.toml' else 'Payloads/')+name,overlay.linux(back/name));assert (back/name).read_bytes()==(w/'fat'/name).read_bytes()
assert (back/'kernel.macho').read_bytes()==kernel
oldcfg=tomllib.loads((old/'fat/unixnu.toml').read_text());cfg=tomllib.loads((back/'unixnu.toml').read_text());assert len(cfg['entry'])==1 and cfg['entry'][0]['args']=='-v native-ufs-root=1 launchdsuffix=release'
# No other semantic configuration changes beyond title and argument selection.
def normalize(value):
 if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
 if isinstance(value,list):return [normalize(v) for v in value]
 if isinstance(value,str):return value.replace('UFS-CHECK-3','UFS-CHECK-2').replace(' launchdsuffix=release','')
 return value
assert normalize(cfg)==oldcfg
adt=(back/'kernel.macho.adt').read_bytes();tree=context.parse(adt);chosen=context.properties(context.find(tree,'/chosen'));assert chosen['root-matching']==(R/'out/ufs-root-chain-r2/chosen-root-matching.bin').read_bytes();assert 'RAMDisk' not in context.properties(context.find(tree,'/chosen/memory-map'))
fd=transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd';shim=transport.ARTIFACT/'shim/shim.bin';launch=context.validate(adt,back/'kernel.macho',fd,shim,(w/'launch/nonce.bin').read_bytes(),(w/'launch/launch-manifest.json').read_bytes());container=transport.inspect_container(image,transport.STOCK.read_bytes()[:4096],shim.read_bytes()+fd.read_bytes(),env,3);fsck=overlay.run('fsck.fat','-n',overlay.linux(fatpath)).decode()
report=dict(candidate='UFS-CHECK-3 r1',offline_qualified=True,consumed=False,device_executed=False,image_path=str(newname),image_sha256=proof['image_sha256'],image_bytes=len(image),kernel_sha256=q['kernel_sha256'],kernel_identical_to_qualified_parent=True,parent_qualification=str(qpath),parent_qualification_sha256=package.sha(qpath.read_bytes()),reused_evidence='All kernel/driver/ABI/QEMU tests inherited by exact kernel and unchanged source binding; no rerun claimed.',new_native_model=release,container=container,launch=launch,fsck=fsck,args=cfg['entry'][0]['args'],sources={n:package.sha((R/n).read_bytes()) for n in ('scripts/build-ufs-check3-r1.py','scripts/test-init-release-carrier.py')},release_model_sha256=package.sha(release_path.read_bytes()),success_continues_native_flow=True,extra_runtime_hooks=0,scope='Offline package readback. Release-only selection uses native branch. No device or root modifications.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(offline_qualified=True,image_path=str(newname),sha256=proof['image_sha256'])))
