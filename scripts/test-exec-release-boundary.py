"""Verify continuous exec observations and the conditional restore-release boundary."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transparency',ROOT/'scripts/test-probe-transparency.py')
T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)
from unicorn.arm64_const import *
NAMES={'inactive-pass','uncommitted-pass','foreign-task-pass','wrong-flag-pass','committed-hold','committed-no-video','first-exec-continues','error-return-continues'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    b=json.loads(a.build.read_text());raw=(ROOT/b['candidate']['path']).read_bytes();assert T.B.sha(raw)==b['candidate']['sha256']
    m=T.B.macho(raw);state=int(b['exec_trace']['state'],16);hold=int(b['root_mount_diagnostic']['stop'],16);checks=[]
    task=T.STACK+0x2000
    for name,active,committed,match,flag,video in [('inactive-pass',0,1,True,2,True),('uncommitted-pass',1,0,True,2,True),('foreign-task-pass',1,1,False,2,True),('wrong-flag-pass',1,1,True,1,True),('committed-hold',1,1,True,2,True),('committed-no-video',1,1,True,2,False),('first-exec-continues',0,0,True,2,True),('error-return-continues',1,0,True,2,True)]:
        site=0xfffffff00769d5f4 if name=='first-exec-continues' else 0xfffffff00769d5f8 if name=='error-return-continues' else 0xfffffff00769d230
        patch=next(x for x in b['patches'] if x.get('va')==hex(site))
        case=dict(flag=0,video=video,nzcv=0xa0000000,x0=2 if name=='error-return-continues' else task,native_pc=site)
        u,_,_=T.machine(raw,b,patch,case);u.reg_write(UC_ARM64_REG_X1,flag)
        u.mem_write(state,struct.pack('<10Q',active,committed,0,0,0,0,0,0,0,task if match else task+0x100))
        should_hold=name in ('committed-hold','committed-no-video')
        target=hold if should_hold else m['symbols']['___mac_execve'] if name=='first-exec-continues' else site+4 if name=='error-return-continues' else m['symbols']['_task_clear_return_wait']
        visited=[]
        def watch(u,pc,size,data):
            if should_hold:assert pc!=m['symbols']['_task_clear_return_wait'],'Guard must not release the task'
            if pc==target:visited.append(pc);u.emu_stop()
        u.hook_add(T.U.UC_HOOK_CODE,watch)
        word=int.from_bytes(bytes.fromhex(patch['after']),'little');imm=word&0x3ffffff
        if imm&(1<<25):imm-=1<<26
        u.emu_start(site+imm*4,0,count=2000000)
        assert visited==[target],(name,hex(u.reg_read(UC_ARM64_REG_PC)))
        assert u.reg_read(UC_ARM64_REG_X0)==case['x0'] and u.reg_read(UC_ARM64_REG_X1)==flag
        assert u.reg_read(UC_ARM64_REG_SP)==T.STACK+0x8000-(176 if should_hold else 0)
        fields=struct.unpack('<10Q',u.mem_read(state,80))
        if name=='first-exec-continues':assert fields[:2]==(1,0) and fields[2:6]==(2**64-1,)*4
        if name=='error-return-continues':assert fields[:2]==(0,0) and fields[4]==2
        pixel=struct.unpack('<I',u.mem_read(T.FB+472*T.ROW+1368*4,4))[0]
        assert pixel==(0xffff40ff if should_hold and video else 0),(name,hex(pixel))
        checks.append(dict(name=name,passed=True,held=should_hold,target=hex(target)))
    if b['probe_revision']>=33:
        spec=importlib.util.spec_from_file_location('reader',ROOT/'scripts/test-probe-read-sites.py')
        reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
        for name,site,row in [('inactive-activation-result',0xfffffff00769cfac,1440),('inactive-exec-result',0xfffffff00769d5f8,1536),('repeat-retains-result',0xfffffff00769d5f4,1440),('inactive-switch-rearms',0xfffffff00769d0d8,0)]:
            patch=next(x for x in b['patches'] if x.get('va')==hex(site))
            # Seed a stopped machine, then execute the real patched hook anew.
            case=dict(flag=0,video=True,nzcv=0,x0=2,native_pc=site)
            u,_,_=T.machine(raw,b,patch,case)
            u.mem_write(state,bytes(96));u.reg_write(UC_ARM64_REG_X0,2)
            if name=='repeat-retains-result':
                u.mem_write(state+80,struct.pack('<Q',1))
                rectangle=T.FB+reader.data_y(row)*T.ROW+256*4
                u.mem_write(rectangle,b'\x5a'*1920)
                before=bytes(u.mem_read(rectangle,1920))
            target=m['symbols']['_proc_exec_switch_task'] if name=='inactive-switch-rearms' else m['symbols']['___mac_execve'] if name=='repeat-retains-result' else site+4
            h=u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,size,data:u.emu_stop() if pc==target else None)
            word=int.from_bytes(bytes.fromhex(patch['after']),'little');imm=word&0x3ffffff
            if imm&(1<<25):imm-=1<<26
            u.emu_start(site+imm*4,0,count=2000000);u.hook_del(h)
            assert u.reg_read(UC_ARM64_REG_PC)==target and u.reg_read(UC_ARM64_REG_X0)==2
            if name=='repeat-retains-result':
                assert bytes(u.mem_read(rectangle,1920))==before
                assert reader.decode(u,1408)=='0000000000000002'
            elif name=='inactive-switch-rearms':
                fields=struct.unpack('<12Q',u.mem_read(state,96));assert fields[0]==1 and fields[9]==u.reg_read(UC_ARM64_REG_X3)
            else:assert reader.decode(u,row)=='0000000000000002'
            checks.append(dict(name=name,passed=True,held=False,target=hex(target)))
    if b['probe_revision']>=34:
        for name,error,prior in [('path-first-error',2,0),('path-zero-return',0,0),('path-keeps-first-error',13,240)]:
            site=0xfffffff00769bdd8
            patch=next(x for x in b['patches'] if x.get('va')==hex(site))
            u,_,_=T.machine(raw,b,patch,dict(flag=0,video=True,nzcv=0,x0=error,native_pc=site))
            u.mem_write(state,bytes(96));u.mem_write(state+88,struct.pack('<Q',prior))
            target=int(b['probe']['symbols']['probe_dense_769bdd8_replay'],16)
            h=u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,size,data:u.emu_stop() if pc==target else None)
            word=int.from_bytes(bytes.fromhex(patch['after']),'little');imm=word&0x3ffffff
            if imm&(1<<25):imm-=1<<26
            u.emu_start(site+imm*4,0,count=2000000);u.hook_del(h)
            assert u.reg_read(UC_ARM64_REG_PC)==target and u.reg_read(UC_ARM64_REG_X0)==error
            first=struct.unpack('<Q',u.mem_read(state+88,8))[0]
            assert first==(242 if name=='path-first-error' else prior)
            if name=='path-first-error':
                assert reader.decode(u,1472)=='00000000000000F2' and reader.decode(u,1600)=='0000000000000002'
            else:assert reader.decode(u,1472)=='?'*16 and reader.decode(u,1600)=='?'*16
            checks.append(dict(name=name,passed=True,held=False,first_failure_stage=first))
    a.output.write_bytes(json.dumps(dict(scope=__doc__,candidate_sha256=T.B.sha(raw),checks=checks,exec_body_executed=False,restore_userspace_released=False),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
