"""Read the current package's Data-provider evidence without changing its inputs."""
import argparse, hashlib, importlib.util, json
from pathlib import Path
import read_dispatch_audit as A
ROOT=A.ROOT
spec=importlib.util.spec_from_file_location('adt_reader',ROOT/'scripts/check-nuwa-adt.py')
ADT=importlib.util.module_from_spec(spec); spec.loader.exec_module(ADT)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cli=argparse.ArgumentParser(description=__doc__); cli.add_argument('--output',type=Path,required=True); a=cli.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(ROOT/'reports'): raise ValueError('Fresh reports output required')
    kernel=ROOT/'out/kernel-entry-probe-49-resource-r4/kernel-entry-probe.macho'; raw=kernel.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='8757bc0c38449099e3d10b8fcd69ec0cbd830c263f99c77bce2ff191848e4418': raise ValueError('Current kernel changed')
    image=A.B.macho(raw); names=sorted(k for k in image['symbols'] if 'NativeRamBlock' in k or 'native_ram_block' in k or 'native_ufs_store' in k)
    adt=ROOT/'out/exec-mainline-v49-resource/launch/kernel.macho.adt'; blob=adt.read_bytes()
    if hashlib.sha256(blob).hexdigest()!='82b5219204cd30f79d520e1710c5b63d105e19f4337f16ef87cdc1603da00a57': raise ValueError('Current ADT changed')
    nodes=ADT.decode(blob); memory=nodes['/device-tree/chosen/memory-map']['properties']; chosen=nodes['/device-tree/chosen']['properties']
    ranges={key:dict(bytes=len(memory[key]),zero_placeholder=not any(memory[key])) for key in ('RAMDisk','PackedRAMDisk') if key in memory}
    package=ROOT/'reports/xnu-first-entry/entry-probe-41.json'; info=json.loads(package.read_bytes()); root=info['root_ramdisk']
    legacy=Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU/drivers/NativeRamBlock')
    snapshot=[dict(path=str(legacy/name),sha256=sha(legacy/name)) for name in ('SparseDisk.h','NativeRamBlock.cpp','Test/sparse.cpp')]
    profile=ROOT/'config/kernel-merged-profile.json'; profile_data=json.loads(profile.read_bytes())
    public_manifest=ROOT/'reports/desktop-readiness/2026-10-27-data-linux-r1/public-ramblock.json'; public=json.loads(public_manifest.read_bytes())
    comparisons=[]
    for key,local in (('SparseDisk.h',legacy/'SparseDisk.h'),('NativeRamBlock.cpp',legacy/'NativeRamBlock.cpp')):
        reference=next(v for v in public if v['url'].endswith('/'+key))
        comparisons.append(dict(file=key,local_sha256=sha(local),public_sha256=reference['sha256'],same_bytes=sha(local)==reference['sha256']))
    report=dict(current_kernel=dict(path=str(kernel.relative_to(ROOT)),sha256=sha(kernel),symbol_count=len(image['symbols']),ramblock_related_symbols=names,
                                   identity_strings={s.decode():raw.count(s) for s in (b'NativeRamBlock',b'native_ram_block')},scope='Named symbol/string evidence only; no runtime provider qualification'),
                current_adt=dict(path=str(adt.relative_to(ROOT)),sha256=sha(adt),memory_map=ranges,ephemeral_storage_present='ephemeral-storage' in chosen),
                current_root=dict(**root,scope='Current initrd is the restore root, not the new Data candidate'),
                local_readonly_snapshot=snapshot,configured_module_revision=profile_data['modules']['drivers/NativeRamBlock'],public_comparison=comparisons,
                local_git_metadata=dict(status='Stopped: Git dubious ownership; no safe.directory override or metadata workaround',revision_confirmed=False),
                parents=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in (package,profile,public_manifest)],
                sources=[dict(path='scripts/'+name,sha256=sha(ROOT/'scripts'/name)) for name in ('audit-data-provider.py','check-nuwa-adt.py','read_dispatch_audit.py','build-kernel-entry-probe.py')],
                device_accessed=False,kernel_modified=False,board_modified=False,release_guard_changed=False,
                integration_pending=['Qualified iOS16 IOBlockStorageDevice/provider ABI, archive/link and initialization','Data volume UUID consumer and APFS mount path','Separate full root publication from current rd=md0 restore initrd','Fresh loader ownership/range and mutable page memory budget; no board memory change inferred'])
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    print(json.dumps(dict(symbols=len(image['symbols']),ramblock_named_symbols=len(names),memory_map=ranges,local_matches_public=[c['same_bytes'] for c in comparisons])))


if __name__=='__main__': main()
