"""Exercise the real first-exec hook with an explicit OSKext API boundary model.

The lifecycle and decompressor bodies are outside this model. No model table
writes are present in the delivered helper; actual registration needs hardware.
"""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transparency',ROOT/'scripts/test-probe-transparency.py')
T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)
from unicorn.arm64_const import *

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    b=json.loads(a.build.read_text());raw=(ROOT/b['candidate']['path']).read_bytes();assert T.B.sha(raw)==b['candidate']['sha256']
    m=T.B.macho(raw);site=0xfffffff00769d5f4;patch=next(x for x in b['patches'] if x.get('va')==hex(site));slot=m['symbols']['_decompressors']+32;table=T.STACK+0x4300;loader=m['symbols']['_OSKextLoadKextWithIdentifier'];checks=[]
    for mode in ('registered','load-success','load-failure','load-empty'):
        for video in (True,False):
            case=dict(flag=0,video=video,nzcv=0xa0000000,x0=1,seed_simd=True)
            ref,expected,_=T.machine(raw,b,patch,case,True)
            expected['fpcr']=ref.reg_read(UC_ARM64_REG_FPCR);expected['fpsr']=ref.reg_read(UC_ARM64_REG_FPSR)
            case['native_pc']=site;u,_,_=T.machine(raw,b,patch,case)
            u.mem_write(slot,struct.pack('<Q',table if mode=='registered' else 0));calls=[];native_table_writes=[]
            def watch(u,pc,size,data):
                if pc==expected['pc']:u.emu_stop()
                if pc==loader:
                    bundle=b'com.apple.AppleFSCompression.AppleFSCompressionTypeZlib\0'
                    assert bytes(u.mem_read(u.reg_read(UC_ARM64_REG_X0),len(bundle)))==bundle
                    calls.append(pc);resume=u.reg_read(UC_ARM64_REG_LR)
                    for i in range(19):u.reg_write(T.REGS[i],0x55550000+i)
                    for i in range(32):u.reg_write(getattr(T,f'UC_ARM64_REG_Q{i}'),0xdeadbeef+i)
                    u.reg_write(UC_ARM64_REG_NZCV,0x50000000);u.reg_write(UC_ARM64_REG_FPCR,0x400000);u.reg_write(UC_ARM64_REG_FPSR,1)
                    if mode=='load-success':u.mem_write(slot,struct.pack('<Q',table))
                    u.reg_write(UC_ARM64_REG_X0,0xe00002c0 if mode=='load-failure' else 0)
                    u.reg_write(UC_ARM64_REG_PC,resume)
            u.hook_add(T.U.UC_HOOK_CODE,watch)
            u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,ac,ad,sz,v,d:native_table_writes.append(ad) if slot<=ad<slot+8 else None)
            word=int.from_bytes(bytes.fromhex(patch['after']),'little');imm=word&0x3ffffff
            if imm&(1<<25):imm-=1<<26
            u.emu_start(site+imm*4,0,count=2000000)
            actual=dict(registers=[u.reg_read(x) for x in T.REGS],sp=u.reg_read(UC_ARM64_REG_SP),nzcv=u.reg_read(UC_ARM64_REG_NZCV),simd=[u.reg_read(getattr(T,f'UC_ARM64_REG_Q{i}')) for i in range(32)],tpidr_el1=u.reg_read(UC_ARM64_REG_TPIDR_EL1),pc=u.reg_read(UC_ARM64_REG_PC),bad=[])
            actual['fpcr']=u.reg_read(UC_ARM64_REG_FPCR);actual['fpsr']=u.reg_read(UC_ARM64_REG_FPSR)
            assert actual==expected,(mode,video,'native context changed')
            status=struct.unpack('<3Q',u.mem_read(int(b['fscompression_startup']['status'],16),24))
            wanted=(0xe00002c0 if mode=='load-failure' else 0,table if mode in ('registered','load-success') else 0,int(mode!='registered'))
            assert status==wanted and len(calls)==int(mode!='registered') and not native_table_writes,(mode,status,wanted,native_table_writes)
            checks.append(dict(name=mode+': '+('video' if video else 'no-video'),passed=True,loader_calls=len(calls),status=[hex(x) for x in status],native_table_writes=native_table_writes))
    a.output.write_bytes(json.dumps(dict(scope=__doc__,candidate_sha256=b['candidate']['sha256'],source_sha256=b['fscompression_startup']['source_sha256'],checks=checks,os_kext_lifecycle_executed=False,decompressor_body_executed=False,device_accessed=False),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
