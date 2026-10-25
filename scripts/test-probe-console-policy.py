"""Exercise native DT lookup and the bounded missing-pram console policy.
Not a hardware test; this is not a general binary implementation of DT panic buffers.
"""
import argparse,importlib.util,json,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
spec=importlib.util.spec_from_file_location('b',ROOT/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
FB=0xb8000000;ROW=5760;STACK=0xf00000;TREE=0xe00000

def node(name,children=()):
 value=name.encode()+b'\0';prop=b'name'+bytes(28)+struct.pack('<I',len(value))+value+bytes((-len(value))%4)
 return struct.pack('<II',1,len(children))+prop+b''.join(children)

def run(build,adt,stop_init=False):
 raw=(ROOT/build['candidate']['path']).read_bytes();assert B.sha(raw)==build['candidate']['sha256'];m=B.macho(raw);base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments']);syms=m['symbols'];ps=build['probe']['symbols']
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(base,B.align(end-base));u.mem_map(FB,0x1200000);u.mem_map(STACK,0x10000);u.mem_map(TREE,B.align(len(adt)))
 for s in m['segments']:
  if s['filesize']:u.mem_write(s['va'],raw[s['fileoff']:s['fileoff']+s['filesize']])
 u.mem_write(TREE,adt);u.mem_write(int(ps['probe_scratch'],16),struct.pack('<QQ',FB,ROW));u.reg_write(UC_ARM64_REG_SP,STACK+0x8000);u.reg_write(UC_ARM64_REG_LR,STACK);u.reg_write(UC_ARM64_REG_X0,TREE);u.reg_write(UC_ARM64_REG_X1,len(adt))
 u.emu_start(syms['_SecureDTInit'],STACK,count=100000)
 regs=[getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)) for i in range(19,30)]
 for i,reg in enumerate(regs):u.reg_write(reg,0x11220000+i*0x100)
 initial=[u.reg_read(reg) for reg in regs];u.reg_write(UC_ARM64_REG_SP,STACK+0x8000);u.reg_write(UC_ARM64_REG_LR,STACK)
 reads=[];bad=[];events=[];halt=int(ps.get('probe_console_policy_stop','0'),16)
 def code(u,pc,size,_):
  if pc in (syms['_PE_create_console'],syms['_initialize_screen'],syms['_ml_io_map_wcomb'],halt):events.append(hex(pc))
  if pc==halt or (stop_init and pc==syms['_initialize_screen']):u.emu_stop()
 def access(u,kind,addr,size,value,_):
  if 0x3c0fc000<=addr<0x3c100000:reads.append(dict(kind=kind,address=hex(addr),size=size))
 def invalid(u,kind,addr,size,value,_):bad.append(dict(kind=kind,address=hex(addr),pc=hex(u.reg_read(UC_ARM64_REG_PC))));return False
 u.hook_add(U.UC_HOOK_CODE,code);u.hook_add(U.UC_HOOK_MEM_READ|U.UC_HOOK_MEM_WRITE,access);u.hook_add(U.UC_HOOK_MEM_INVALID,invalid)
 error=None
 try:u.emu_start(syms['_PE_create_console'],STACK,count=5000000)
 except U.UcError as e:error=str(e)
 status=struct.unpack('<Q',u.mem_read(int(ps['probe_console_status'],16),8))[0] if 'probe_console_status' in ps else None
 globals_={n:bytes(u.mem_read(syms[n],nbytes)).hex() for n,nbytes in [('_gPanicBase',8),('_gPanicSize',4),('_panic_info',8),('_panic_text_len',1)]}
 return dict(error=error,pc=hex(u.reg_read(UC_ARM64_REG_PC)),status=status,events=events,bcm_accesses=reads,bad_memory=bad,panic_globals=globals_,callee_saved_preserved=initial==[u.reg_read(reg) for reg in regs],sp=hex(u.reg_read(UC_ARM64_REG_SP)))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--adt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--negative-build',type=Path,required=True);a=p.parse_args();build=json.loads(a.build.read_text());results={};checks=[]
 adt=a.adt.read_bytes()
 for name,tree in [('shipped-missing-pram',adt),('minimal-missing-pram',node('device-tree')),('present-pram',node('device-tree',[node('pram')]))]:
  r=run(build,tree,stop_init=True);results[name]=r
  assert not r['bcm_accesses'] and not r['bad_memory'] and r['error'] is None,r
  assert all(int(x,16)==0 for x in r['panic_globals'].values()),r
  if name=='present-pram':assert r['status']==2 and r['pc']==build['probe']['symbols']['probe_console_policy_stop'],r
  else:assert r['status']==1 and r['pc']==hex(B.macho((ROOT/build['candidate']['path']).read_bytes())['symbols']['_initialize_screen']) and r['callee_saved_preserved'] and r['sp']=='0xf08000',r
  checks.append(dict(name=name+' uses native DT lookup without BCM access',passed=True))
 m=B.macho((ROOT/build['candidate']['path']).read_bytes())
 assert hex(m['symbols']['_initialize_screen']) in results['shipped-missing-pram']['events']
 checks.append(dict(name='Missing-pram path retains native screen initialization entry',passed=True))
 assert hex(m['symbols']['_initialize_screen']) not in results['present-pram']['events']
 checks.append(dict(name='Present-pram policy stops explicitly before console and old log access',passed=True))
 negative_path=a.output.with_name('console-negative.json')
 subprocess.run([sys.executable,'-B',str(ROOT/'scripts/test-probe-transition.py'),'--build',str(a.negative_build),'--adt',str(a.adt),'--case','normal','--output',str(negative_path)],check=True)
 negative=json.loads(negative_path.read_text())
 assert negative['error']=='Invalid memory read (UC_ERR_READ_UNMAPPED)' and negative['bad_memory'][0]['address']=='0x3c0fc000',negative
 results['v22-negative']=negative;checks.append(dict(name='Old candidate still reads unmapped BCM panic region',passed=True))
 out=dict(scope=__doc__,candidate_sha256=build['candidate']['sha256'],adt_sha256=B.sha(adt),checks=checks,cases=results)
 a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
