"""Audit exact native read boundaries against fixed public XNU source and input."""
import argparse,hashlib,importlib.util,json,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'out/python-tools'))
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
from read_boundary_sites import CALLS
spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
SOURCE=Path('D:/Code/PortingiOS/common/sources/xnu-ios16-full')
COMMIT='1b191cb58250d0705d8a51287127505aa4bc0789'
SOURCE_SHA='ea24edd54bb7428d77ba880b1150b17cbbb6cca4518977536153f585552a6b9b'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not a.output.resolve().is_relative_to(ROOT/'reports'):raise ValueError('Output must be under reports')
    report=json.loads(a.build.read_text());raw=B.INPUT.read_bytes();assert B.sha(raw)==B.EXPECTED
    m=B.macho(raw);source=(SOURCE/'bsd/vfs/vfs_vnops.c').read_bytes();assert B.sha(source)==SOURCE_SHA
    cmd=['git','-C',str(SOURCE),'rev-parse','HEAD'];head=subprocess.check_output(cmd,text=True).strip();assert head==COMMIT
    d=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    def disasm(start,n):
        return [dict(pc=hex(i.address),bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str) for i in d.disasm(raw[B.backed(m,start):B.backed(m,start)+n],start)]
    sites=[]
    for i,(pc,fn,callee) in enumerate(CALLS):
        patch=next(p for p in report['patches'] if p.get('va')==hex(pc))
        assert patch['before']==raw[B.backed(m,pc):B.backed(m,pc)+4].hex()
        sites.append(dict(call_id=266+2*i,return_id=267+2*i,function=fn,callee=callee,call=hex(pc),continuation=hex(pc+4),native_instructions=disasm(pc,8)))
    # The MAC denial conditional reaches exactly the VNOP_READ continuation.
    branch_pc=0xfffffff007466ad0;w=struct.unpack_from('<I',raw,B.backed(m,branch_pc))[0]
    assert w&0xff00001f==0x35000000
    imm=(w>>5)&0x7ffff
    if imm&(1<<18):imm-=1<<19
    target=branch_pc+imm*4;assert target==CALLS[2][0]+4
    current=m['symbols']['_current_thread'];assert raw[B.backed(m,current):B.backed(m,current)+8].hex()=='80d038d5c0035fd6'
    out=dict(scope=__doc__,level='static-only',candidate_sha256=report['candidate']['sha256'],input_sha256=B.EXPECTED,source=dict(repository='https://github.com/apple-oss-distributions/xnu',commit=head,version='xnu-8796.141.3',license='APSL-2.0',path='bsd/vfs/vfs_vnops.c',sha256=SOURCE_SHA,lines=[951,1031],url='https://github.com/apple-oss-distributions/xnu/blob/'+head+'/bsd/vfs/vfs_vnops.c'),source_command=cmd,sites=sites,shared_return_join=dict(mac_denial_branch=disasm(branch_pc,4),target=hex(target),requires_paired_call=True),thread_identity=disasm(current,8),frame_geometry=dict(probe_save=176,vn_rdwr=dict(allocation=64,fp_from_sp=48,saved_lr_from_fp=8),vn_rdwr_64=dict(allocation=176,fp_from_sp=160),VNOP_READ=dict(allocation=112,fp_from_sp=96)),native_read_path=disasm(0xfffffff007466aa4,132),device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(static_checks_passed=True,sites=len(sites),shared_join=hex(target))))
if __name__=='__main__':main()