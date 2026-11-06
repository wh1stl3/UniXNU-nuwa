"""Execute CHECK5 Image4 AES caller; crypto and descriptors remain explicit fixtures."""
import argparse,hashlib,json,sys
from pathlib import Path
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
import exec_carrier_model as H
from exec_carrier_model import *
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified');rows=[]
for name in ('raw_boundary','native_domain_boundary','unsupported','wait','short_buffer','provider_absent'):
 m=Machine(c);SELF=MEM+0x10000;AES=SELF+0x100;SVT=SELF+0x1000;AVT=SVT+0x1000;DESC=SELF+0x4000;SRC=DESC+0x1000;DST=SRC+0x1000;DOMAIN=DST+0x1000;BUF=DOMAIN+0x1000;VT=BUF+0x1000;CALL=VT+0x1000
 m.put(SELF,SVT);m.put(SELF+0x90,AES);m.put(AES,AVT)
 m.put(0xfffffff006a116d0,0 if name=='provider_absent' else SELF);m.put(0xfffffff006a116c8,DESC)
 m.put(0xfffffff005cab920,DESC+0x100);m.put(DESC+0x100,0x1234)
 if name=='raw_boundary':m.put(DOMAIN+0x38,0,4)
 else:DOMAIN=0xfffffff005caec60
 for obj in (SRC,DST):m.put(obj,VT)
 for table,offset,fn in ((SVT,0x20,lambda:m.ret()),(VT,0x148,lambda:m.ret(BUF)),(VT,0xd8,lambda:m.ret())):
  m.put(table+offset,CALL);m.callbacks[CALL]=fn;CALL+=4
 for addr in (0xfffffff0046f9fc8,0xfffffff0046f9fd4):m.callbacks[addr]=lambda:m.ret()
 allocated=[]
 def alloc():
  result=(SRC,DST)[len(allocated)];allocated.append(result);m.ret(result)
 m.callbacks[0xfffffff0046f9d10]=alloc
 observed={}
 def aes():
  key=m.x(6);sp=m.u.reg_read(UC_ARM64_REG_SP)
  observed.update(bits=m.get(key,4),selector=m.get(key+36,4),key_hex=bytes(m.u.mem_read(key+4,32)).hex(),length=m.x(3),operation=m.x(5),iv_hex=bytes(m.u.mem_read(m.x(4),16)).hex(),stack_args=[m.get(sp+i*8) for i in range(3)])
  assert m.x(0)==AES and m.x(1)==SRC and m.x(2)==DST and m.x(7)==0
  assert observed['bits']==128 and observed['length']==16 and observed['operation']==0
  assert observed['selector']==(0 if name=='raw_boundary' else 2212)
  assert observed['iv_hex']=='00'*16 and observed['key_hex']=='00'*32 and observed['stack_args']==[0,0,0]
  if name=='unsupported':m.ret(0xe00002c7)
  else:m.stop('AES wait boundary' if name=='wait' else 'AES call boundary')
 m.put(AVT+0x550,CALL);m.callbacks[CALL]=aes
 m.callbacks[0xfffffff0046fa028]=lambda:m.stop('native panic')
 m.callbacks[0xfffffff0046f9960]=lambda:m.stop('native missing-provider panic boundary')
 m.x(0,BUF+0x100);m.x(1,BUF+0x200);m.x(2,15 if name=='short_buffer' else 16);m.x(3,DOMAIN)
 try:m.run(0xfffffff0046ef3e0)
 except Exception:print(name,m.recent);raise
 expected={'unsupported':'native panic','short_buffer':'native panic','provider_absent':'native missing-provider panic boundary','wait':'AES wait boundary'}.get(name,'AES call boundary')
 assert m.stopped==expected,(name,m.stopped)
 if name=='unsupported':assert m.get(m.u.reg_read(UC_ARM64_REG_SP))==0xe00002c7
 if name in ('short_buffer','provider_absent'):assert not observed and not allocated
 row=m.record(name);row['aes_arguments']=observed;rows.append(row)
write_report(a.output,c,rows,'Actual Image4 AES caller from entry through argument construction, descriptor preparation and native error branches. Synthetic raw domain selector 0 and immutable actual domain 0 selector 2212, service objects, descriptor allocation/virtuals, locks and crypto are fixtures. No runtime active-domain selection, AES encryption, hardware key or provider publication proven; wait stops at selected callback.')
r=json.loads(a.output.read_bytes());r['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native AES caller cases')