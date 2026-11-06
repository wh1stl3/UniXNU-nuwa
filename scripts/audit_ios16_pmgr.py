"""Exact iOS16 original nub ABI. Fail closed on carrier drift."""
import hashlib,json,struct
import flush_trace_inputs as trace

def audit(raw, output):
 B=trace.builder();m=B.macho(raw);symbols=m['symbols'];checks=[]
 def read(va,n):return raw[B.backed(m,va,n):][:n]
 def ptr(va):return int.from_bytes(read(va,8),'little')
 def words(va, expected):
  assert read(va,len(expected)*4)==struct.pack('<'+'I'*len(expected),*expected),hex(va)
  checks.append(dict(address=hex(va),bytes=read(va,len(expected)*4).hex()))
 def stub(va):
  w,a,b=struct.unpack('<3I',read(va,12))
  assert w&0x9f00001f==0x90000010 and a&0xffc003ff==0xf9400210 and b==0xd61f0200
  imm=((w>>5)&0x7ffff)*4+((w>>29)&3)
  if imm&(1<<20):imm-=1<<21
  slot=(va&~4095)+(imm<<12)+((a>>10)&4095)*8
  return ptr(slot)
 table=0xfffffff005ca5058
 methods={21:('__ZN9IOService4initEP12OSDictionary','pmgr_init'),84:('__ZN9IOService15registerServiceEj','pmgr_register'),86:('__ZN9IOService5startEPS_','pmgr_start'),87:('__ZN9IOService4stopEPS_','pmgr_stop_service'),108:('__ZN9IOService6attachEPS_','pmgr_attach'),109:('__ZN9IOService6detachEPS_','pmgr_detach_service'),5:('__ZNK8OSObject7releaseEv','pmgr_release_object')}
 targets={}
 for index,(symbol,label) in methods.items():
  assert ptr(table+index*8)==symbols[symbol],(index,symbol)
  targets[label]=symbols[symbol]
 for symbol,label in [('__ZN11OSMetaClass18allocClassWithNameEPKc','pmgr_alloc'),('__ZN9IOService11getPlatformEv','pmgr_platform'),('__ZN9IOService15serviceMatchingEPKcP12OSDictionary','pmgr_matching'),('__ZN9IOService22waitForMatchingServiceEP12OSDictionaryy','pmgr_wait')]:targets[label]=symbols[symbol]
 assert stub(0xfffffff004717f90)==targets['pmgr_matching']
 assert stub(0xfffffff004717f9c)==targets['pmgr_wait']
 assert stub(0xfffffff004717ea0)==symbols['__ZN15OSMetaClassBase12safeMetaCastEPKS_PK11OSMetaClass']
 targets.update(pmgr_vtable=table,pmgr_read=stub(0xfffffff004717e34),pmgr_write=stub(0xfffffff004717e40),pmgr_amfi_resume=0xfffffff0046fe7a8)
 words(targets['pmgr_read'],[0xf9404400,0xb4000080,0xf9400008,0xf944e101,0xd61f0020,0x12800000,0xd65f03c0])
 words(targets['pmgr_write'],[0xf9404400,0xb4000080,0xf9400008,0xf944e502,0xd61f0040,0xd65f03c0])
 words(0xfffffff0046830fc,[0x5280e803]) # class size 0x740
 words(0xfffffff0046831fc,[0x5280e801]) # allocator size 0x740
 words(0xfffffff0046fe764,[0xd2958001,0xf2bf8461,0xf2c000c1]) # 30 billion ns
 words(0xfffffff0046fe794,[0x321e0015,0xaa1403e0,0xaa1503e1])
 assert ptr(table+7*8)==0xfffffff0046831a8
 assert read(0xfffffff003dfbacf,13)==b'ApplePMGRNub\0'
 report=dict(passed=True,carrier_sha256=hashlib.sha256(raw).hexdigest(),class_size=0x740,vtable=hex(table),provider_offset=0x88,read_slot=312,write_slot=313,timeout_ns=30000000000,targets={k:hex(v) for k,v in targets.items()},instruction_contracts=checks,scope='Static original ABI; runtime class identity and null provider checked before publication; no power hardware support')
 output.write_text(json.dumps(report,indent=2)+'\n')
 return targets
