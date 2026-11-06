"""Extend frozen DiagnosticLaunch.v1 with measured real APFS and a mount-only policy."""
import argparse,hashlib,json,struct
from pathlib import Path
import nuwa_launch_context as C
ROOT=C.ROOT
PAYLOAD_SHA='d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a'
ARGS='-v rd=md0'
POLICY=dict(boot_arguments=ARGS,halt_after='vfs_mountroot return',halt_site='0xfffffff0076730e8',restore_userspace_allowed=False)
def validate(adt,kernel,fd,shim,ramdisk,nonce=None):
    proof=C.validate(adt,kernel,fd,shim,nonce=nonce)
    raw=Path(ramdisk).read_bytes()
    if C.sha256(raw)!=PAYLOAD_SHA or len(raw)!=106954752 or raw[32:36]!=b'NXSB':raise ValueError('Pinned real restore APFS differs')
    if int.from_bytes(raw[36:40],'little')!=4096 or int.from_bytes(raw[40:48],'little')*4096!=len(raw):raise ValueError('APFS container geometry differs')
    chosen=C.properties(C.find(C.parse(adt),'/chosen'));manifest=json.loads(chosen[C.CONTEXT_KEY])
    if manifest.get('root_mount_diagnostic')!=POLICY or manifest.get('root_producer_sha256')!=C.sha256(Path(__file__).read_bytes()):raise ValueError('Root policy/producer differs')
    if proof['components'].get('root_ramdisk')!=C.measurement(ramdisk):raise ValueError('Actual RAMDisk not measured')
    mmap=C.properties(C.find(C.parse(adt),'/chosen/memory-map'))
    if mmap.get('RAMDisk')!=bytes(16) or 'PackedRAMDisk' in mmap:raise ValueError('Exact loader RAMDisk placeholder required')
    return dict(candidate_sha256=proof['components']['kernel']['sha256'],adt_sha256=proof['adt_sha256'],manifest_sha384=proof['manifest_sha384'],ramdisk=dict(path=Path(ramdisk).resolve().relative_to(ROOT).as_posix(),**C.measurement(ramdisk)),policy=POLICY,producer_sha256=C.sha256(Path(__file__).read_bytes()),kernel_path=Path(kernel).resolve().relative_to(ROOT).as_posix(),fd_path=Path(fd).resolve().relative_to(ROOT).as_posix(),shim_path=Path(shim).resolve().relative_to(ROOT).as_posix())
def validate_report(report):
    for key in ('kernel_path','fd_path','shim_path'):
        if not (ROOT/report[key]).resolve().is_relative_to(ROOT/'out'):raise ValueError('Root inputs outside local out')
    ramdisk=(ROOT/report['ramdisk']['path']).resolve()
    if not ramdisk.is_relative_to(ROOT/'out'):raise ValueError('Root image outside out')
    if C.measurement(ramdisk)!={k:report['ramdisk'][k] for k in ('bytes','sha256')} or report.get('policy')!=POLICY or report.get('producer_sha256')!=C.sha256(Path(__file__).read_bytes()):raise ValueError('Root launch report changed')
    adt_path=(ROOT/report['adt_path']).resolve()
    if not adt_path.is_relative_to(ROOT/'out'):raise ValueError('Root ADT outside out')
    actual=validate(adt_path.read_bytes(),ROOT/report['kernel_path'],ROOT/report['fd_path'],ROOT/report['shim_path'],ramdisk)
    actual['adt_path']=report['adt_path']
    if actual!=report:raise ValueError('Root proof does not match actual inputs')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('base-adt','kernel','fd','shim','ramdisk','work','output','root-output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    C.create(a.base_adt,a.kernel,a.fd,a.shim,a.work)
    path=a.work/'kernel.macho.adt';tree=C.parse(path.read_bytes());chosen=C.find(tree,'/chosen');values=C.properties(chosen)
    manifest=json.loads(values[C.CONTEXT_KEY]);manifest['components']['root_ramdisk']=C.measurement(a.ramdisk);manifest['root_mount_diagnostic']=POLICY;manifest['root_producer_sha256']=C.sha256(Path(__file__).read_bytes());mb=C.canonical(manifest)
    chosen['properties']=[(k,f,mb if k==C.CONTEXT_KEY else hashlib.sha384(mb).digest() if k==C.HASH_KEY else v) for k,f,v in chosen['properties']]
    adt=C.encode(tree);path.write_bytes(adt);(a.work/'launch-manifest.json').write_bytes(mb)
    proof=C.validate(adt,a.kernel,a.fd,a.shim,nonce=(a.work/'nonce.bin').read_bytes(),manifest_bytes=mb)
    root=validate(adt,a.kernel,a.fd,a.shim,a.ramdisk,nonce=(a.work/'nonce.bin').read_bytes())
    root['adt_path']=path.resolve().relative_to(ROOT).as_posix()
    for dest,obj in ((a.output,proof),(a.root_output,root)):
        dest=dest.resolve()
        if not dest.is_relative_to(ROOT/'reports') or dest.exists():raise ValueError('Fresh report path required')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(json.dumps(obj,indent=2).encode()+b'\n')
    print(json.dumps(dict(adt_sha256=proof['adt_sha256'],root_ramdisk_sha256=PAYLOAD_SHA)))
if __name__=='__main__':main()
