"""Differential native cluster_io call/prologue and strict entry ancestry.

Stops before cluster_io body dependencies; no simulated IO completion claim.
"""
import argparse, importlib.util, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('io_entry_model',ROOT/'scripts/test-read-flow.py')
M=importlib.util.module_from_spec(spec);sys.modules[spec.name]=M;spec.loader.exec_module(M)
C,T,P=M.CLUSTER_CHECKS,M.T,M.CLUSTER_CHECKS.P

def run(raw,b,original,om,mode,native):
    caller=next(p for p in P.points() if p['offset']==0x43914c)
    entry=next(p for p in P.points() if p['offset']==0x4344d4)
    u,m,sy,_,_=C.setup(M,raw,b,caller,mode)
    fp=u.reg_read(T.UC_ARM64_REG_X29)
    if native:
        for p in (caller,entry):
            at=M.B.backed(om,p['site']);u.mem_write(p['site'],original[at:at+4])
    stop=P.BASE+0x4344f4
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(caller['site'],0,count=3000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop
    assert u.reg_read(T.UC_ARM64_REG_LR)==P.BASE+0x439150
    if not native:
        own=struct.unpack('<4Q',u.mem_read(sy[P.state_name('clusterio')],32))
        assert own==(fp,1,0,1),own
        for point,color in ((caller,0xffffc040),(entry,0xffff40ff)):
            x,y=P.geometry(point)
            expected=0 if mode=='no-video' else color
            for yy in range(y,y+6):
                assert bytes(u.mem_read(T.FB+yy*T.ROW+x*4,96))==struct.pack('<I',expected)*24
    return M.D.snapshot(u)

def main():
    c=argparse.ArgumentParser(description=__doc__);c.add_argument('--build',type=Path,required=True);c.add_argument('--output',type=Path,required=True);a=c.parse_args()
    assert not a.output.exists();b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes()
    assert M.B.sha(raw)==b['candidate']['sha256']
    if b.get('lean_observation'):
        import lean_probe_inputs as L
        L.verify_bytes(b,raw)
        assert b['read_flow']==L.read(L.BASE/'build.json')['read_flow']
    else:assert b['read_flow']==M.P.plan()
    original=M.B.INPUT.read_bytes();assert M.B.sha(original)==M.B.EXPECTED;om=M.B.macho(original)
    checks=[]
    for mode in ('normal','no-video'):
        assert run(raw,b,original,om,mode,False)==run(raw,b,original,om,mode,True)
        checks.append(dict(name='native-call-prologue:'+mode,passed=True))
    a.output.write_bytes(json.dumps(dict(candidate_sha256=M.B.sha(raw),source_sha256=M.B.sha(Path(__file__).read_bytes()),checks=checks,scope=__doc__,device_accessed=False),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
