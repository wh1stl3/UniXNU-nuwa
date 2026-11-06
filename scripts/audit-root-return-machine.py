"""Check the pinned PROBE58 mount-return machine code without changing a kernel."""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
R = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R/'out/python-tools'), str(R/'scripts')]
import capstone
import unicorn as U
from unicorn import arm64_const as A

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists(): raise SystemExit('Existing report refused')
    spec=importlib.util.spec_from_file_location('builder',R/'scripts/build-kernel-entry-probe.py')
    B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
    p=R/'reports/kernel-entry-probe/2026-10-30-probe58-milestones-r1/build.json'
    j=json.loads(p.read_bytes()); raw=(R/j['candidate']['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==j['candidate']['sha256']
    m=B.macho(raw)
    def get(va,n):
        for s in m['segments']:
            if s['va']<=va and va+n<=s['va']+s['filesize']:
                o=s['fileoff']+va-s['va'];return raw[o:o+n]
        raise ValueError(hex(va))
    cs=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
    hook=int(j['probe']['symbols']['probe_dense_76730e8'],16)
    replay=int(j['probe']['symbols']['probe_dense_76730e8_replay'],16)
    assert get(0xfffffff0076730e4,4).hex()=='a641f797'
    assert get(replay,12).hex()=='400000351b9ac617109ac617'
    assert get(0xfffffff007673110,4).hex()=='dcffff17'
    suppressed=[c for c in j['lean_observation']['changes'] if c.get('function')=='probe_dense_76730e8']
    assert len(suppressed)==4
    for c in suppressed: assert get(int(c['va'],16),4).hex()==c['after']
    cases=[]
    for value in (0,1,5,0xffffffff,0x100000000):
        u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
        page=hook & ~4095; u.mem_map(page,4096);u.mem_write(hook,get(hook,replay+12-hook))
        u.mem_map(0xfffffff007673000,4096);u.mem_write(0xfffffff007673000,get(0xfffffff007673000,4096))
        u.mem_map(0x100000,0x4000);u.reg_write(A.UC_ARM64_REG_SP,0x102000)
        regs=[getattr(A,f'UC_ARM64_REG_X{i}') for i in range(31)]
        before=[value]+[0x200000+i*32 for i in range(1,31)]
        for r,v in zip(regs,before):u.reg_write(r,v)
        u.reg_write(A.UC_ARM64_REG_NZCV,0xa0000000)
        target=0xfffffff007673114 if value & 0xffffffff == 0 else 0xfffffff0076730ec
        u.emu_start(hook,target,count=100)
        passed=(u.reg_read(A.UC_ARM64_REG_PC)==target and [u.reg_read(r) for r in regs]==before and u.reg_read(A.UC_ARM64_REG_SP)==0x102000 and u.reg_read(A.UC_ARM64_REG_NZCV)==0xa0000000)
        cases.append(dict(x0=hex(value),target=hex(target),passed=passed))
        assert passed
    ranges=[]
    for va,n in ((0xfffffff007673080,0x100),(0xfffffff00744377c,0xa0),(hook,replay+12-hook)):
        ranges.append(dict(start=hex(va),instructions=[dict(va=hex(i.address),bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str) for i in cs.disasm(get(va,n),va)]))
    start=m['symbols']['_vfs_mountroot']
    end=min(v for v in m['symbols'].values() if v>start)
    reverse={v:k for k,v in m['symbols'].items()}
    calls=[]
    for i in cs.disasm(get(start,end-start),start):
        if i.mnemonic in ('bl','blr'):
            target=int(i.op_str[1:],16) if i.mnemonic=='bl' else None
            calls.append(dict(site=hex(i.address),instruction=i.mnemonic+' '+i.op_str,target_symbol=reverse.get(target),indirect=i.mnemonic=='blr'))
    result=dict(scope='Actual PROBE58 static disassembly and isolated return-hook emulation, not hardware execution',kernel_sha256=hashlib.sha256(raw).hexdigest(),build_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),cases=cases,suppressed_return_rendering=suppressed,ranges=ranges,passed=True,limitations=['Does not execute vfs_mountroot or APFS','Does not prove actual return value, IRQ timing or runtime reachability'])
    result['mount_function_calls']=calls
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=len(cases),report=str(args.output))))

if __name__=='__main__': main()
