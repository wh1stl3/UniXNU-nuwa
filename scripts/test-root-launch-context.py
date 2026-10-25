"""Reject mutated real-root inputs and relaxed mount-only policy after resealing."""
import argparse,copy,json
from pathlib import Path
from unittest.mock import patch
import nuwa_launch_context as C
import nuwa_root_launch_context as R
NAMES={'actual-root','corrupt-root','missing-root-measurement','userspace-allowed','wrong-arguments','wrong-producer','nonzero-placeholder'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=json.loads(a.build.with_name('root-launch.json').read_text());adt=(C.ROOT/root['adt_path']).read_bytes()
    kernel=C.ROOT/root['kernel_path'];fd=C.ROOT/root['fd_path'];shim=C.ROOT/root['shim_path'];ramdisk=C.ROOT/root['ramdisk']['path'];checks=[]
    R.validate_report(root);R.validate(adt,kernel,fd,shim,ramdisk);checks.append(dict(name='actual-root',passed=True))
    original=Path.read_bytes;bad=bytearray(original(ramdisk));bad[-1]^=1
    with patch.object(Path,'read_bytes',lambda p:bytes(bad) if p.resolve()==ramdisk.resolve() else original(p)):
        try:R.validate(adt,kernel,fd,shim,ramdisk)
        except ValueError:checks.append(dict(name='corrupt-root',passed=True))
        else:raise AssertionError('corrupt real image')
    for mode in ('missing-root-measurement','userspace-allowed','wrong-arguments','wrong-producer','nonzero-placeholder'):
        tree=C.parse(adt);chosen=C.find(tree,'/chosen');manifest=json.loads(C.properties(chosen)[C.CONTEXT_KEY])
        if mode=='missing-root-measurement':del manifest['components']['root_ramdisk']
        if mode=='userspace-allowed':manifest['root_mount_diagnostic']['restore_userspace_allowed']=True
        if mode=='wrong-arguments':manifest['root_mount_diagnostic']['boot_arguments']='-v'
        if mode=='wrong-producer':manifest['root_producer_sha256']='0'*64
        if mode=='nonzero-placeholder':
            mem=C.find(tree,'/chosen/memory-map');mem['properties']=[(k,f,b'\1'+bytes(15) if k=='RAMDisk' else v) for k,f,v in mem['properties']]
        mb=C.canonical(manifest)
        chosen['properties']=[(k,f,mb if k==C.CONTEXT_KEY else R.hashlib.sha384(mb).digest() if k==C.HASH_KEY else v) for k,f,v in chosen['properties']]
        try:R.validate(C.encode(tree),kernel,fd,shim,ramdisk)
        except ValueError:checks.append(dict(name=mode,passed=True))
        else:raise AssertionError(mode)
    assert {c['name'] for c in checks}==NAMES
    a.output.write_bytes(json.dumps(dict(candidate_sha256=root['candidate_sha256'],checks=checks,device_accessed=False),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
