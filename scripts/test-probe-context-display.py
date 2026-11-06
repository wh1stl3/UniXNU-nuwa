"""Paired native machine context restore plus non-destructive framebuffer readback tests."""
import argparse,gc,importlib.util,json,struct,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'out/python-tools')]
import unicorn as U
from unicorn.arm64_const import *
s=importlib.util.spec_from_file_location('transparency',R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T);B=T.B
TH=0x200000;CPU=TH+0x2000;CTX=TH+0x4000;NEWSP=T.STACK+0xc000
REGS=[getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}') for i in range(31)];QREGS=[getattr(sys.modules[__name__],f'UC_ARM64_REG_Q{i}') for i in range(32)]
def context(build,reference,video,flag,fpcr,first_stack=False):
 ctx_addr=NEWSP if first_stack else CTX
 raw=(R/build['candidate']['path']).read_bytes();m=B.macho(raw);base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments']);native=B.macho(B.INPUT.read_bytes())
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(base,B.align(end-base));u.mem_map(TH,0x10000);u.mem_map(T.STACK,0x10000);u.mem_map(T.FB,0x1200000)
 src=B.INPUT.read_bytes() if reference else raw
 for seg in (native if reference else m)['segments']:
  if seg['filesize']:u.mem_write(seg['va'],src[seg['fileoff']:seg['fileoff']+seg['filesize']])
 ps=build['probe']['symbols'];u.mem_write(int(ps['probe_scratch'],16),struct.pack('<QQ',T.FB if video else 0,T.ROW));u.mem_write(int(ps['probe_flags'],16),bytes([flag])*4096)
 for reg,val in ((UC_ARM64_REG_X0,TH),(UC_ARM64_REG_SP,T.STACK+0x8000),(UC_ARM64_REG_CPACR_EL1,3<<20),(UC_ARM64_REG_NZCV,0xa0000000)):u.reg_write(reg,val)
 for i,reg in enumerate(QREGS):u.reg_write(reg,((i+1)<<96)|((i+2)<<64)|(i+3))
 for off,val in ((0x1c8,CPU),(0x148,0x12345678),(0x4d0,0x123),(0x158,ctx_addr)):u.mem_write(TH+off,struct.pack('<Q',val))
 u.mem_write(CPU,struct.pack('<h',0));target=m['symbols']['_thread_continue']
 restored=[0x440000+i for i in range(12)];restored[-1]=target
 u.mem_write(ctx_addr,struct.pack('<12Q',*restored));u.mem_write(ctx_addr+0x60,struct.pack('<Q',NEWSP));u.mem_write(ctx_addr+0x70,struct.pack('<8Q',*[0x880000+i for i in range(8)]));u.mem_write(ctx_addr+0xb0,struct.pack('<I',fpcr))
 bad=[];u.hook_add(U.UC_HOOK_MEM_INVALID,lambda u,a,p,s,v,d:bad.append([a,hex(p)]) or False);u.hook_add(U.UC_HOOK_CODE,lambda u,p,s,d:u.emu_stop() if p==target else None)
 u.emu_start(m['symbols']['_machine_load_context'],0,count=2000000)
 out=dict(gprs=[u.reg_read(x) for x in REGS],simd=[u.reg_read(x) for x in QREGS],sp=u.reg_read(UC_ARM64_REG_SP),nzcv=u.reg_read(UC_ARM64_REG_NZCV),pc=u.reg_read(UC_ARM64_REG_PC),fpcr=u.reg_read(UC_ARM64_REG_FPCR),tpidr=[u.reg_read(x) for x in (UC_ARM64_REG_TPIDR_EL1,UC_ARM64_REG_TPIDR_EL0,UC_ARM64_REG_TPIDRRO_EL0)],cpu_thread=bytes(u.mem_read(CPU+0x30,8)).hex(),caller_stack=bytes(u.mem_read(NEWSP,0x4000)).hex(),bad=bad)
 assert out['pc']==target and out['sp']==NEWSP and not bad,out
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();b=json.loads(a.build.read_text());checks=[];records={}
 for name,video,flag,fpcr in (('fresh',True,0,0),('repeat',True,1,0),('no-video',False,0,0),('FPCR-change',True,0,1<<22),('first-stack-layout',True,0,0)):
  native=context(b,True,video,flag,fpcr,name=='first-stack-layout');probe=context(b,False,video,flag,fpcr,name=='first-stack-layout');assert native==probe,name
  checks.append(dict(name='Machine context restore preserves GPR SIMD SP system registers: '+name,passed=True));records[name]=dict(pc=hex(probe['pc']),sp=hex(probe['sp']),fpcr=hex(probe['fpcr']),tpidr=[hex(x) for x in probe['tpidr']]);gc.collect()
 raw=(R/b['candidate']['path']).read_bytes();m=B.macho(raw);site=m['symbols']['_load_context'];patch=next(p for p in b['patches'] if p['va']==hex(site));case=dict(flag=0,video=True,nzcv=0,x0=1,native_pc=site+4)
 u,state,writes=T.machine(raw,b,patch,case);status=int(b['probe']['symbols']['probe_display_status'],16)
 def bar():return b''.join(bytes(u.mem_read(T.FB+(224+y)*T.ROW+832*4,384*4)) for y in range(16))
 expected=(struct.pack('<I',0xffffffff)*192+struct.pack('<I',0xff00ffff)*192)*16
 assert bar()==expected and struct.unpack('<QQ',u.mem_read(status,16))==(0,0)
 checks.append(dict(name='Calibration band writes exact white and cyan pixels',passed=True))
 checks.append(dict(name='Immediate display readback reports zero mismatches',passed=True))
 def execute(fn):
  pc=m['symbols'][fn];u.hook_add(U.UC_HOOK_CODE,lambda u,p,s,d:u.emu_stop() if p==pc+4 else None);u.emu_start(pc,0,count=2000000);assert u.reg_read(UC_ARM64_REG_PC)==pc+4
 u.mem_write(T.FB+224*T.ROW+832*4,struct.pack('<I',0));before=bar();execute('_kernel_bootstrap_thread');assert struct.unpack('<QQ',u.mem_read(status,16))==(1,4) and bar()==before
 checks.append(dict(name='Readback detects one changed pixel without repainting',passed=True))
 u.mem_write(T.FB+224*T.ROW+832*4,b'\0'*(384*4));before=bar();execute('_bsd_init');assert struct.unpack('<QQ',u.mem_read(status,16))==(384,6) and bar()==before
 checks.append(dict(name='Readback detects one changed row without repainting',passed=True))
 case['video']=False;empty,_,writes=T.machine(raw,b,patch,case);assert not any(T.FB<=p<T.FB+0x1200000 for p,n in writes)
 checks.append(dict(name='Missing framebuffer keeps native control flow without display writes',passed=True))
 out=dict(scope=__doc__,candidate_sha256=b['candidate']['sha256'],checks=checks,context=records,synthetic_layout=dict(thread=hex(TH),cpu=hex(CPU),saved_context=hex(CTX),new_sp=hex(NEWSP)),limitations=['Synthetic register/stack fixture, not full scheduler execution or hardware scanout'])
 a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
