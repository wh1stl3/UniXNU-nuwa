"""Audit exact PROBE20 root inputs and native selection branches; no device action."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'out/python-tools')]
import nuwa_launch_context as C
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
spec=importlib.util.spec_from_file_location('B',ROOT/'scripts/build-kernel-entry-probe.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
SOURCE=Path('D:/Code/PortingiOS/common/sources/xnu-ios16-full/iokit/bsddev/IOKitBSDInit.cpp')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    package=json.loads((ROOT/'reports/xnu-first-entry/entry-probe-20.json').read_text())
    build=json.loads((ROOT/package['entry_probe']['build']['path']).read_text())
    adt=(ROOT/'out/pthread-mainline-v28/launch/kernel.macho.adt').read_bytes()
    assert C.sha256(adt)==package['read_file_sha256']
    tree=C.parse(adt);chosen=C.properties(C.find(tree,'/chosen'));mem=C.properties(C.find(tree,'/chosen/memory-map'))
    args=package['fat_detail']['config']['entry'][0]['args']
    raw=B.INPUT.read_bytes();assert B.sha(raw)==B.EXPECTED
    m=B.macho(raw);syms=m['symbols'];pc=syms['_bsd_init'];end=min(v for v in syms.values() if v>pc)
    ins=list(Cs(CS_ARCH_ARM64,CS_MODE_ARM).disasm(raw[B.backed(m,pc):B.backed(m,end-4)+4],pc))
    pthread=[i.address for i in ins if i.mnemonic=='bl' and i.op_str==hex(syms['_pthread_init']).replace('0x','#0x')]
    root_call=next(int(e['site'],16) for e in build['dense_bootstrap']['edges'] if e['callee']=='_IOFindBSDRoot' and e['phase']=='call')
    assert len(pthread)==1 and pthread[0]<root_call
    keys=('root-matching','boot-uuid','rootpath','rootdev','boot-args')
    source=SOURCE.read_text();checks=[]
    def check(name,value):
        assert value,name
        checks.append(dict(name=name,passed=True))
    check('Shipped menu contains verbose flag only',args=='-v')
    check('Exact shipped ADT has no explicit root selector',all(k not in chosen for k in keys))
    check('Exact shipped memory-map has no root RAMDisk',all(k not in mem for k in ('RAMDisk','PackedRAMDisk','RAMDiskExtents')))
    check('Native pthread initializer call precedes observed root call',pthread[0]<root_call)
    check('Native root fallback matches Apple_HFS IOMedia', 'serviceMatching( "IOMedia" )' in source and 'withCStringNoCopy("Apple_HFS")' in source)
    check('Native root waits for matching service and retains missing-root error','service = IOService::waitForService( matching, &t );' in source and 'panic("Failed to mount root device")' in source)
    # Binding to fixed source content prevents claiming a similarly named port
    # implements the exact behavior used for the interpretation.
    check('Pinned native root source unchanged',C.sha256(SOURCE.read_bytes())=='ccee70ea15e2fdf143360feb4c4abb647def98eb647434aa1dd2d32f54cc7363')
    report=dict(scope=__doc__,checks=checks,package='reports/xnu-first-entry/entry-probe-20.json',candidate_sha256=build['candidate']['sha256'],adt_sha256=C.sha256(adt),chosen_root_keys={k:chosen[k].hex() for k in keys if k in chosen},memory_map_keys=sorted(mem),native_pthread_init_call=hex(pthread[0]),native_root_call=hex(root_call),source=dict(path=str(SOURCE),sha256=C.sha256(SOURCE.read_bytes()),commit='1b191cb58250d0705d8a51287127505aa4bc0789',license='APSL-2.0'),interpretation='Observed root entry is after pthread initialization. With -v only, no root selector or RAMDisk, native fallback seeks Apple_HFS IOMedia. Missing usable root provider is the leading cause; exact position inside IOFindBSDRoot and timer/wakeup health are not observed.',device_accessed=False,root_mounted=False)
    a.output.write_bytes(json.dumps(report,indent=2).encode()+b'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
