"""Execute retired diagnostic sites: strict pairing survives, no old log writes."""
import argparse, importlib.util, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('flow',ROOT/'scripts/test-read-flow.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
C=M.CLUSTER_CHECKS;P=C.P

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--build',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    a=cli.parse_args();assert not a.output.exists() and not P.G.ENABLED
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes()
    assert M.B.sha(raw)==b['candidate']['sha256']
    original=M.B.INPUT.read_bytes();om=M.B.macho(original);checks=[]
    for p in P.points():
        if not P.G.selected(p):continue
        for mode in C.MODES:
            C.execute(M,raw,b,p,mode,original,om)
            u,m,sy,_,_=C.setup(M,raw,b,p,mode)
            at=sy[P.G.SYMBOL];sentinel=b'\xa5'*(9*32)
            u.mem_write(at,sentinel);writes=[]
            replay=sy['probe_dense_'+format(p['site']&0xffffffff,'x')+'_replay']
            u.hook_add(M.T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==replay else None)
            u.hook_add(M.T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:writes.append((pos,n)) if M.T.FB<=pos<M.T.FB+0x1200000 else None)
            u.emu_start(p['site'],0,count=3000000)
            assert bytes(u.mem_read(at,len(sentinel)))==sentinel and not writes
            checks.append(dict(name=hex(p['site'])+':'+mode,passed=True))
    assert len(checks)==108
    a.output.write_text(json.dumps(dict(candidate_sha256=M.B.sha(raw),source_sha256=M.B.sha(Path(__file__).read_bytes()),checks=checks,device_accessed=False,retired_slots=9,reserved_unused_state_bytes=288),indent=2)+'\n')
    print('108 retired diagnostic and strict-scope cases passed')

if __name__=='__main__':main()
