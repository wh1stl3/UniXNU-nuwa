"""Execute actual carrier AMFI loadModule with original trust modules.
DT, memory allocation and initialization environment remain explicit fixtures; no device claim.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as trace
sys.path.insert(0,str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();w=a.work;assert not a.output.exists()
raw=(w/'kernel.macho').read_bytes();proof=json.loads((w/'kernel-proof.json').read_bytes());assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=trace.builder();m=B.macho(raw);sym=m['symbols'];payload=(w/'kernel.macho.trustcache').read_bytes();assert len(payload)==67764
count,*offsets=struct.unpack('<III',payload[:12]);assert count==2
integrity_path=trace.R/'reports/desktop-readiness/2026-11-02-payload-code-integrity-r1/audit.json'
integrity=json.loads(integrity_path.read_bytes())
assert integrity['passed'] and integrity['all_selected_original_trust_covered']
cache=next(v for v in integrity['records'] if v['path'].endswith('/dyld_shared_cache_arm64'))
assert cache['directories'][0]['cdhash']=='2e6af99c2bbd9042f6b658b58739b6265cb3c46d'
assert cache['directories'][0]['original_trust_matches']==[{'module':'SystemOS','attributes':'000000'}]
registration={}
for va,size in ((0xfffffff004700404,8),(0xfffffff00470046c,8),(0xfffffff00471802c,12),(0xfffffff005cb58f8,8)):
 off=B.backed(m,va,size);registration[hex(va)]=raw[off:off+size].hex()
assert int.from_bytes(bytes.fromhex(registration['0xfffffff005cb58f8']),'little')==sym['_amfi_interface_register']
stack=0x20010000;amfi=0xfffffff005cb69a0;img4=0x20004000;range_ptr=0x20005000;tc=0x30000000;callback=0xfffffff00470a1c4;sentinel=0x50002000
cases=[]
for case in ('both-return-success','engineering-disabled','first-error','second-error','property-absent'):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);pages=set()
 def mapping(addr,n,fixture=False):
  for page in range(addr&~4095,(addr+n+4095)&~4095,4096):
   if page in pages:continue
   s=next((s for s in m['segments'] if s['va']<=page<s['va']+s['size']),None)
   assert fixture or s is not None,('unexpected memory',hex(page))
   u.mem_map(page,4096);pages.add(page)
   if s and page-s['va']<s['filesize']:
    size=min(4096,s['filesize']-(page-s['va']));off=s['fileoff']+page-s['va'];u.mem_write(page,raw[off:off+size])
 def read(addr,n):mapping(addr,n);return bytes(u.mem_read(addr,n))
 def write(addr,data):mapping(addr,len(data));u.mem_write(addr,data)
 def string(addr):return read(addr,128).split(b'\0')[0]
 def fault(uc,access,addr,n,value,data):mapping(addr,n);return True
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
 mapping(0x20000000,0x20000,True);mapping(tc,0x20000,True);mapping(sentinel,4096,True)
 write(sym['_amfi'],struct.pack('<Q',amfi));write(sym['_img4if'],struct.pack('<Q',img4));assert struct.unpack('<I',read(amfi+0x118,4))[0]==3;assert struct.unpack('<Q',read(amfi+0x120,8))[0]==callback;write(img4+0x190,struct.pack('<Q',0x20006000))
 write(range_ptr,struct.pack('<QQ',0x60000000,len(payload)));write(tc,payload)
 if case in ('first-error','second-error'):write(tc+offsets[case=='second-error'],struct.pack('<I',0xffffffff))
 known={sym[n]:n for n in ('_lck_rw_init','_SecureDTLookupEntry','_SecureDTGetProperty','_phystokv','_printf','_kalloc_type_impl_internal','_panic')}
 cold={v:k for k,v in sym.items() if k.startswith('_load_static_trust_cache.cold.')}
 records=[];panicked=False;done=False;init=False
 def ret(v=0):u.reg_write(UC_ARM64_REG_X0,v);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 def hook(uc,pc,size,data):
  if pc==sentinel:
   state['done']=True;uc.emu_stop();return
  x=[uc.reg_read(r) for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4)]
  if pc in cold or pc==sym['_panic']:state['panic']=True;uc.emu_stop();return
  if records and pc==records[-1].get('return_pc'):
   records[-1]['native_return']=x[0]
  if pc==callback:
   index=len(records);assert index<2
   expected_index=0 if x[1]==0 else 1
   assert (x[1],x[3],x[4])==(expected_index,tc+offsets[expected_index],len(payload)-offsets[expected_index])
   records.append(dict(index=expected_index,type=x[1],offset=x[3]-tc,available=x[4],return_pc=uc.reg_read(UC_ARM64_REG_LR)))
   return
  name=known.get(pc)
  if name=='_lck_rw_init':state['init']=True;uc.emu_stop()
  elif name=='_SecureDTLookupEntry':assert string(x[1])==b'chosen/memory-map';write(x[2],struct.pack('<Q',0x20008000));ret(1)
  elif name=='_SecureDTGetProperty':
   assert string(x[1])==b'TrustCache'
   if case!='property-absent':write(x[2],struct.pack('<Q',range_ptr));write(x[3],struct.pack('<I',16))
   ret(0xffffffff if case=='property-absent' else 1)
  elif name=='_phystokv':assert x[0]==0x60000000;ret(tc)
  elif name=='_printf':ret()
  elif name=='_kalloc_type_impl_internal':ret(0x2000a000)
 state={'init':False,'panic':False,'done':False}
 u.hook_add(U.UC_HOOK_CODE,hook);u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_LR,sentinel)
 u.emu_start(sym['_trust_cache_runtime_init'],0,count=2000);assert state['init'] and not state['panic']
 runtime=struct.unpack('<Q',read(sym['_trust_cache_rt'],8))[0]
 assert read(runtime+8,3)==b'\0\1\0'
 if case=='engineering-disabled':write(runtime+9,b'\0')
 u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_LR,sentinel);
 try:u.emu_start(sym['_load_static_trust_cache'],0,count=10000)
 except U.UcError:
  print('MODEL FAILURE',case,hex(u.reg_read(UC_ARM64_REG_PC)),[hex(u.reg_read(r)) for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X19)]);raise
 expected={'both-return-success':[0,1],'engineering-disabled':[0],'first-error':[0],'second-error':[0,1],'property-absent':[]}[case]
 assert [r['type'] for r in records]==expected,(case,records)
 assert state['panic']==(case=='first-error') and state['done']==(case!='first-error'),(case,state)
 loaded=read(sym['_trust_cache_static_loaded'],1)[0]
 assert loaded==(0 if case in ('first-error','property-absent') else 1)
 engineering=struct.unpack('<Q',read(runtime+0x18,8))[0]
 assert bool(engineering)==(case=='both-return-success'),(case,hex(engineering),records)
 for rec in records:
  bad=(case=='first-error' and rec['index']==0) or (case=='second-error' and rec['index']==1)
  assert (rec['native_return'] & 0xff00 != 0)==bad,(case,rec)
 queries=[]
 if case!='first-error':
  query=struct.unpack('<Q',read(amfi+0x130,8))[0]
  get_type=struct.unpack('<Q',read(amfi+0x140,8))[0]
  for label,digest in [('SystemOS-main-cache',bytes.fromhex('2e6af99c2bbd9042f6b658b58739b6265cb3c46d')),('absent-control',bytes([255])*20)]:
   write(0x2000b000,digest);write(0x2000b100,bytes(64))
   state['done']=False
   for reg,value in ((UC_ARM64_REG_X0,runtime),(UC_ARM64_REG_X1,0),(UC_ARM64_REG_X2,0x2000b000),(UC_ARM64_REG_X3,0x2000b100),(UC_ARM64_REG_SP,stack),(UC_ARM64_REG_LR,sentinel)):u.reg_write(reg,value)
   u.emu_start(query,0,count=100000);assert state['done']
   result=u.reg_read(UC_ARM64_REG_W0);found=(result&0xff00)==0
   assert found==(label=='SystemOS-main-cache' and case=='both-return-success'),(case,label,hex(result))
   module_type=None;type_return=None
   if found:
    state['done']=False
    for reg,value in ((UC_ARM64_REG_X0,0x2000b100),(UC_ARM64_REG_X1,0x2000b200),(UC_ARM64_REG_SP,stack),(UC_ARM64_REG_LR,sentinel)):u.reg_write(reg,value)
    u.emu_start(get_type,0,count=10000);assert state['done'] and (u.reg_read(UC_ARM64_REG_W0)&0xff00)==0,(state,hex(u.reg_read(UC_ARM64_REG_W0)))
    type_return=u.reg_read(UC_ARM64_REG_W0)
    module_type=read(0x2000b200,1)[0];assert module_type==1
   queries.append(dict(name=label,cdhash=digest.hex(),native_return=result,found=found,module_type=module_type,type_native_return=type_return))
 cases.append(dict(name=case,module_calls=records,panic=state['panic'],static_loaded_flag=loaded,engineering_list_nonempty=bool(engineering),queries=queries))
report=dict(passed=True,kernel_sha256=proof['kernel_sha256'],payload_sha256=hashlib.sha256(payload).hexdigest(),cases=cases,second_static_supported=False,existing_engineering_dispatch=True,actual_amfi_load_module_executed=True,device_amfi_acceptance=False,device_accessed=False,amfi_table=hex(amfi),load_module=hex(callback),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Actual runtime init, static loader and carrier AMFI loadModule. DT, physical translation, lock initialization and allocator are fixtures. Invalid version negatives mutate only emulated memory. Native return, engineering list and actual query/type lookup checked; no device or full signing/pager acceptance.')
report.update(registration_binding=registration,integrity_report_sha256=hashlib.sha256(integrity_path.read_bytes()).hexdigest(),unicorn_version=U.__version__)
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases),'actual AMFI loadModule cases; device acceptance remains unproven')

