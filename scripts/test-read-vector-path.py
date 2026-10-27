"""Execute native post-allocation vector preparation up to the decode call.

Supplied allocation/vector fixtures do not model heap allocation or APFS IO.
"""
import argparse, importlib.util, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('vector_result_model',ROOT/'scripts/test-read-result.py')
M=importlib.util.module_from_spec(s);sys.modules[s.name]=M;s.loader.exec_module(M)
T=M.T;B=M.B;P=M.P

def run(raw,b,original,om,length,native):
    u,_,sy,_=M.setup(raw,b,P.CONTINUATION,'normal')
    cb=T.STACK+0xf000;allocation=T.STACK+0x6000;vector=T.STACK+0x7000;dest=T.STACK+0x1000
    values={0:allocation,20:vector,21:1,24:40,25:0,27:length,28:0,29:cb}
    for reg,value in values.items():u.reg_write(getattr(T,'UC_ARM64_REG_X'+str(reg)),value)
    u.reg_write(T.UC_ARM64_REG_SP,cb-0xf0)
    u.mem_write(vector,struct.pack('<QQ',dest,length))
    u.mem_write(allocation,bytes(40))
    if native:
        for patch in b['patches']:
            if patch['va'] is None:continue
            pc=int(patch['va'],16) if isinstance(patch['va'],str) else patch['va']
            if P.F.CALLBACK<=pc<P.F.CALLBACK+0x480:
                at=B.backed(om,pc);u.mem_write(pc,original[at:at+4])
    stop=P.PREVIOUS.DECODE
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(P.CONTINUATION,0,count=12000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop,hex(u.reg_read(T.UC_ARM64_REG_PC))
    args=[u.reg_read(getattr(T,'UC_ARM64_REG_X'+str(i))) for i in range(6)]
    assert args==[cb-0xa0,0,length,1,allocation+8,cb-0x60],args
    assert struct.unpack('<3Q',u.mem_read(allocation,24))==(40,dest,length)
    return M.M.snapshot(u),bytes(u.mem_read(allocation,40)),args

def resource_prefix(raw,b,original,om,offset,length,native):
    import read_resource_sites as Q
    u,m,sy=M.M.setup(raw,b,Q.D.DECODE+0x1bc,'normal')
    cb=T.STACK+0xf000;ctx=T.STACK+0x5000;buffer=T.STACK+0x6000;error=T.STACK+0x7000;meta=T.STACK+0x8000;uio=T.STACK+0x8300
    u.reg_write(T.UC_ARM64_REG_LR,Q.PARENTS[2][0])
    u.mem_write(sy['probe_result_state'],struct.pack('<8Q',cb,40,1,1,0,0,0,1))
    u.mem_write(ctx,struct.pack('<Q',meta));u.mem_write(meta,struct.pack('<QQ',meta+0x100,meta+0x200))
    for n,v in enumerate((ctx,buffer,length,offset,error)):u.reg_write(getattr(T,'UC_ARM64_REG_X'+str(n)),v)
    if native:
        for p in Q.points():
            at=B.backed(om,p['site']);u.mem_write(p['site'],original[at:at+4])
    targets={m['symbols'][name] for name in ('_uio_create','_uio_addiov','_VNOP_GETXATTR')}
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc in targets else None)
    u.emu_start(Q.ENTRY,0,count=3000000);assert u.reg_read(T.UC_ARM64_REG_PC)==m['symbols']['_uio_create']
    args=lambda n:[u.reg_read(getattr(T,'UC_ARM64_REG_X'+str(i))) for i in range(n)]
    assert args(4)==[1,offset,2,0]
    u.reg_write(T.UC_ARM64_REG_X0,uio);u.emu_start(u.reg_read(T.UC_ARM64_REG_LR),0,count=3000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==m['symbols']['_uio_addiov'] and args(3)==[uio,buffer,length]
    u.reg_write(T.UC_ARM64_REG_X0,0);u.emu_start(u.reg_read(T.UC_ARM64_REG_LR),0,count=3000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==m['symbols']['_VNOP_GETXATTR']
    sp=u.reg_read(T.UC_ARM64_REG_SP)
    assert args(6)==[meta+0x100,0xfffffff0043fd4a5,uio,sp+0x38,0x20,meta+0x200]
    assert struct.unpack('<Q',u.mem_read(sp+0x38,8))[0]==length
    return M.M.snapshot(u),args(6)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    assert not a.output.exists();b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes()
    assert B.sha(raw)==b['candidate']['sha256'];original=B.INPUT.read_bytes();assert B.sha(original)==B.EXPECTED;om=B.macho(original)
    checks=[]
    for length in (1,512,4096,16384,65536):
        actual=run(raw,b,original,om,length,False);reference=run(raw,b,original,om,length,True)
        assert actual==reference
        checks.append(dict(name='offset0-one-vector-'+str(length),passed=True,decode_arguments=[hex(v) for v in actual[2]]))
    for offset,length in ((264,8),(336,23707),(384,33021)):
        assert resource_prefix(raw,b,original,om,offset,length,False)==resource_prefix(raw,b,original,om,offset,length,True)
        checks.append(dict(name=f'resource-request-{offset}-{length}',passed=True))
    u,m,sy,_=M.setup(raw,b,P.REQUEST,'normal');u.mem_write(sy['probe_resource_state'],b'\xa5'*32)
    stop=m['symbols']['_vn_rdwr'];u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(P.F.DECOMP.PREVIOUS.FIRST,0,count=4000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop and bytes(u.mem_read(sy['probe_resource_state'],32))==bytes(32)
    checks.append(dict(name='resource-header-reset',passed=True))
    evidence=[]
    for rel in ('reports/kernel-entry-probe/2026-10-27-v45-preparation/type4-native.json','reports/kernel-entry-probe/2026-10-27-v46-preparation/allocation-decode-native.json'):
        path=ROOT/rel;doc=json.loads(path.read_bytes());functions=doc.get('functions',[doc]);count=0
        for f in functions:
            for ins in f['instructions']:
                pc=int(ins['pc'],16);at=B.backed(om,pc);expected=bytes.fromhex(ins['bytes'])
                assert original[at:at+len(expected)]==expected;count+=1
        evidence.append(dict(path=rel,sha256=B.sha(path.read_bytes()),instructions_matched=count))
    a.output.write_bytes(json.dumps(dict(candidate_sha256=B.sha(raw),input_sha256=B.sha(original),test_sha256=B.sha(Path(__file__).read_bytes()),checks=checks,disassembly_binding=evidence,device_accessed=False,limitations=['Unicorn execution with supplied nonnull allocation, zero offset, one vector; no allocator or resource IO executed','Vector path stops before decode; resource prefix supplies uio_create/addiov returns and stops before VNOP_GETXATTR body','No decompression or EL0 runtime claim']),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))

if __name__=='__main__':main()
