"""Execute the deliberate post-mount halt; no root result or userspace simulated."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transparency',ROOT/'scripts/test-probe-transparency.py')
T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)
from unicorn.arm64_const import *
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    b=json.loads(a.build.read_text());raw=(ROOT/b['candidate']['path']).read_bytes();assert T.B.sha(raw)==b['candidate']['sha256']
    mode=b['root_mount_diagnostic'];site=int(mode['site'],16);stop=int(mode['stop'],16)
    assert site==0xfffffff0076730e8 and mode['hook']=='probe_dense_76730e8'
    patch=next(p for p in b['patches'] if p.get('va')==hex(site));checks=[]
    for name,value,video in [('success',0,True),('error',5,True),('no-video',0,False)]:
        case=dict(flag=0,video=video,nzcv=0xa0000000,x0=value,native_pc=site)
        u,_,_=T.machine(raw,b,patch,case);u.reg_write(UC_ARM64_REG_X0,value)
        seen=[];u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,s,d:(seen.append(pc),u.emu_stop()) if pc==stop else None)
        word=int.from_bytes(bytes.fromhex(patch['after']),'little');imm=word&0x3ffffff
        if imm&(1<<25):imm-=1<<26
        u.emu_start(site+imm*4,0,count=2000000)
        assert seen==[stop] and u.reg_read(UC_ARM64_REG_X0)==value
        assert u.reg_read(UC_ARM64_REG_SP)==T.STACK+0x8000-176
        for idx in (212,213):
            x=832+(idx%10)*48;y=256+(idx//10)*24
            pixel=struct.unpack('<I',u.mem_read(T.FB+y*T.ROW+x*4,4))[0]
            wanted=(0xff40ff80 if idx==212 else 0xffff0000) if video and idx==(212 if value==0 else 213) else 0
            assert pixel==wanted,(name,idx,hex(pixel),hex(wanted))
        checks.append(dict(name=name,passed=True,actual_return=value,stop=hex(stop)))
    a.output.write_bytes(json.dumps(dict(scope=__doc__,candidate_sha256=T.B.sha(raw),checks=checks,actual_root_mount_executed=False,userspace_entered=False),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
