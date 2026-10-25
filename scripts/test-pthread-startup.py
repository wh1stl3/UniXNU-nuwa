"""Execute BSD hook with an explicit OSKext API boundary model.

The real donor kmod and native registration execute. OSKext lifecycle and
pthread initializer body are outside this isolated model and need hardware.
"""
import argparse, json, struct, sys
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
spec=importlib.util.spec_from_file_location('transparency',ROOT/'scripts/test-probe-transparency.py')
T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=json.loads(a.build.read_text());raw=(ROOT/report['candidate']['path']).read_bytes()
    assert T.B.sha(raw)==report['candidate']['sha256'] and report['probe_revision']==28
    audit=json.loads((ROOT/'reports/kernel-entry-probe/2026-10-25-v27/pthread-registration.json').read_text())
    patch=next(x for x in report['patches'] if x.get('va')=='0xfffffff0076729e0')
    m=T.B.macho(raw);syms=m['symbols'];checks=[]
    for mode in ('registered','load-success','load-failure'):
        for video in ('video','no-video'):
            case=dict(flag=0,video=video=='video',nzcv=0xa0000000,x0=1,seed_simd=True)
            # Reuse exact candidate mappings and the actual native first instruction.
            ref,expected,_=T.machine(raw,report,patch,case,True)
            expected['fpcr']=ref.reg_read(UC_ARM64_REG_FPCR);expected['fpsr']=ref.reg_read(UC_ARM64_REG_FPSR)
            case['native_pc']=expected['pc']
            # machine() executes immediately; construct the same machine by stopping
            # at the hook site, then add boundary interception before resuming.
            site=int(patch['va'],16);case['native_pc']=site
            u,_,_=T.machine(raw,report,patch,case)
            target=syms['_pthread_functions'];table=int(audit['functions_table'],16)
            u.mem_write(target,struct.pack('<Q',table if mode=='registered' else 0))
            calls=[];bad=[]
            def watch(u,pc,size,data):
                if pc==expected['pc']:u.emu_stop()
                if pc==syms['_OSKextLoadKextWithIdentifier']:
                    assert bytes(u.mem_read(u.reg_read(UC_ARM64_REG_X0),22)).split(b'\0')[0]==b'com.apple.kec.pthread'
                    calls.append(pc)
                    for i in range(19):u.reg_write(T.REGS[i],0x55550000+i)
                    for i in range(32):u.reg_write(getattr(T,f'UC_ARM64_REG_Q{i}'),0xdeadbeef+i)
                    u.reg_write(UC_ARM64_REG_NZCV,0x50000000)
                    u.reg_write(UC_ARM64_REG_FPCR,0x400000);u.reg_write(UC_ARM64_REG_FPSR,1)
                    if mode=='load-success':
                        # Explicit OSKext boundary substitution, absent from shipped code.
                        u.reg_write(UC_ARM64_REG_X0,0);u.reg_write(UC_ARM64_REG_X1,0)
                        u.reg_write(UC_ARM64_REG_PC,int(audit['module_start'],16))
                    else:
                        u.reg_write(UC_ARM64_REG_X0,0xe00002c0)
                        u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
            # Leave the initial stop-at-site hook installed and resume at the
            # decoded target of the actual BSD entry branch.
            u.hook_add(U.UC_HOOK_CODE,watch)
            u.hook_add(U.UC_HOOK_MEM_INVALID,lambda u,ac,ad,sz,v,d:bad.append(hex(ad)) or False)
            word=int.from_bytes(bytes.fromhex(patch['after']),'little');imm=word&0x3ffffff
            if imm&(1<<25):imm-=1<<26
            u.emu_start(site+imm*4,0,count=2000000)
            actual=dict(registers=[u.reg_read(x) for x in T.REGS],sp=u.reg_read(UC_ARM64_REG_SP),nzcv=u.reg_read(UC_ARM64_REG_NZCV),simd=[u.reg_read(getattr(T,f'UC_ARM64_REG_Q{i}')) for i in range(32)],tpidr_el1=u.reg_read(UC_ARM64_REG_TPIDR_EL1),pc=u.reg_read(UC_ARM64_REG_PC),bad=bad)
            actual['fpcr']=u.reg_read(UC_ARM64_REG_FPCR);actual['fpsr']=u.reg_read(UC_ARM64_REG_FPSR)
            assert actual==expected,(mode,video,actual,expected)
            status=struct.unpack('<QQQ',u.mem_read(int(report['probe']['symbols']['probe_pthread_load_status'],16),24))
            assert len(calls)==(mode!='registered')
            assert status==((0xe00002c0 if mode=='load-failure' else 0),0 if mode=='load-failure' else table,int(mode!='registered')),status
            # Actual native wrapper retains NULL rejection, or dispatches to donor init.
            stop=int(audit['pthread_init_target'],16) if mode!='load-failure' else syms['_panic']
            u.hook_add(U.UC_HOOK_CODE,lambda u,pc,s,d:u.emu_stop() if pc==stop else None)
            u.reg_write(UC_ARM64_REG_LR,T.STACK);u.reg_write(UC_ARM64_REG_SP,T.STACK+0x8000)
            u.emu_start(syms['_pthread_init'],0,count=100000)
            assert u.reg_read(UC_ARM64_REG_PC)==stop
            checks.append(dict(name=mode+': '+video,passed=True,loader_calls=len(calls),status=[hex(x) for x in status]))
    a.output.write_bytes(json.dumps(dict(scope=__doc__,candidate_sha256=T.B.sha(raw),prelink_sha256=report['pthread_startup']['prelink_sha256'],source_sha256=report['pthread_startup']['source_sha256'],checks=checks,os_kext_lifecycle_executed=False,pthread_initializer_body_executed=False,device_accessed=False),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
