"""Execute native iOS16 trust-cache dispatch with explicit AMFI/DT fixtures.
This verifies module routing and error handling, never AMFI acceptance.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as trace
sys.path.insert(0,str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work
raw=(w/'kernel.macho').read_bytes();proof=json.loads((w/'kernel-proof.json').read_bytes());assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=trace.builder();m=B.macho(raw);sym=m['symbols'];payload=(w/'kernel.macho.trustcache').read_bytes();assert len(payload)==67764
count,*offsets=struct.unpack('<III',payload[:12]);assert count==2
stack=0x20010000;amfi=0x20003000;img4=0x20004000;range_ptr=0x20005000;tc=0x30000000;callback=0x50001000;sentinel=0x50002000
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
 mapping(0x20000000,0x20000,True);mapping(tc,0x20000,True);mapping(callback,0x2000,True)
 write(sym['_amfi'],struct.pack('<Q',amfi));write(sym['_img4if'],struct.pack('<Q',img4));write(amfi+0x118,struct.pack('<I',3));write(amfi+0x120,struct.pack('<Q',callback));write(img4+0x190,struct.pack('<Q',0x20006000))
 write(range_ptr,struct.pack('<QQ',0x60000000,len(payload)));write(tc,payload)
 known={sym[n]:n for n in ('_lck_rw_init','_SecureDTLookupEntry','_SecureDTGetProperty','_phystokv','_printf','_kalloc_type_impl_internal','_panic')}
 cold={v:k for k,v in sym.items() if k.startswith('_load_static_trust_cache.cold.')}
 records=[];panicked=False;done=False;init=False
 def ret(v=0):u.reg_write(UC_ARM64_REG_X0,v);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 def hook(uc,pc,size,data):
  if pc==sentinel:
   state['done']=True;uc.emu_stop();return
  x=[uc.reg_read(r) for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4)]
  if pc in cold or pc==sym['_panic']:state['panic']=True;uc.emu_stop();return
  if pc==callback:
   index=len(records);assert index<2
   expected_index=0 if x[1]==0 else 1
   assert (x[1],x[3],x[4])==(expected_index,tc+offsets[expected_index],len(payload)-offsets[expected_index])
   error=(case=='first-error' and expected_index==0) or (case=='second-error' and expected_index==1)
   records.append(dict(index=expected_index,type=x[1],offset=x[3]-tc,available=x[4],fixture_error=int(error)))
   ret(0x100 if error else 0);return
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
 cases.append(dict(name=case,module_calls=records,panic=state['panic'],static_loaded_flag=loaded))
report=dict(passed=True,kernel_sha256=proof['kernel_sha256'],payload_sha256=hashlib.sha256(payload).hexdigest(),cases=cases,second_static_supported=False,existing_engineering_dispatch=True,amfi_acceptance=False,device_accessed=False,scope='Genuine native runtime initialization and static loader instructions; explicit DT, physical translation, allocator and AMFI loadModule fixtures. A static-loaded flag does not prove acceptance of the second module.')
(w/'trust-dispatch-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases),'native trust-cache dispatch cases; AMFI is a fixture')
