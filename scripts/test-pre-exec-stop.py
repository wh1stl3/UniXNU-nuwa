"""Execute the sole pre-init-exec halt and show no exec target runs."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transparency',ROOT/'scripts/test-probe-transparency.py')
T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)
from unicorn.arm64_const import *
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    b=json.loads(a.build.read_text());raw=(ROOT/b['candidate']['path']).read_bytes();assert T.B.sha(raw)==b['candidate']['sha256']
    site=0xfffffff00769d5f4;stop=int(b['root_mount_diagnostic']['stop'],16)
    patch=next(p for p in b['patches'] if p.get('va')==hex(site));m=T.B.macho(raw);checks=[]
    for name,value,video in [('first',0,True),('nonzero-argument',5,True),('no-video',0,False)]:
        case=dict(flag=0,video=video,nzcv=0xa0000000,x0=value,native_pc=site)
        u,_,_=T.machine(raw,b,patch,case);u.reg_write(UC_ARM64_REG_X0,value)
        seen=[]
        def watch(u,pc,s,d):
            assert pc!=m['symbols']['___mac_execve'],'Real first exec must not execute'
            if pc==stop:seen.append(pc);u.emu_stop()
        u.hook_add(T.U.UC_HOOK_CODE,watch)
        word=int.from_bytes(bytes.fromhex(patch['after']),'little');imm=word&0x3ffffff
        if imm&(1<<25):imm-=1<<26
        u.emu_start(site+imm*4,0,count=2000000)
        assert seen==[stop] and u.reg_read(UC_ARM64_REG_X0)==value
        assert u.reg_read(UC_ARM64_REG_SP)==T.STACK+0x8000-176
        idx=218;x=832+idx%10*48;y=256+idx//10*24
        pixel=struct.unpack('<I',u.mem_read(T.FB+y*T.ROW+x*4,4))[0]
        assert pixel==(0xffff40ff if video else 0)
        checks.append(dict(name=name,passed=True,incoming_x0=value,stop=hex(stop),exec_entered=False))
    a.output.write_bytes(json.dumps(dict(scope=__doc__,candidate_sha256=T.B.sha(raw),checks=checks,userspace_entered=False),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
