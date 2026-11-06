"""Actual backboardd/launchd negative paths; OS/XPC APIs remain explicit boundaries."""
import argparse,hashlib,importlib.util,json,struct
from pathlib import Path
from types import SimpleNamespace
from exec_carrier_model import *
s=importlib.util.spec_from_file_location('service_code',t.R/'scripts/inspect-service-code.py');S=importlib.util.module_from_spec(s);s.loader.exec_module(S)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
parent=t.R/'reports/desktop-readiness/2026-11-03-offline-mainline-r1/core-consumers-r2.json';evidence=json.loads(parent.read_bytes());rows=[]
def carrier(name):
 record=next(x for x in evidence['binaries'] if x['path']==name);raw=(t.R/record['extracted']).read_bytes();assert hashlib.sha256(raw).hexdigest()==record['sha256']
 return SimpleNamespace(raw=raw,m={'segments':S.segments(raw)},sy={},proof={'symbols':{'draw':0xdeadbeef}}),record
c,binding=carrier('/usr/libexec/backboardd')
for name,connection in [('oscard_connection_null',0),('oscard_connection_created',MEM+0x20000)]:
 m=Machine(c)
 def create():
  assert m.x(1)==0 and m.x(2)==2
  m.events.append('xpc create com.apple.oscard flags=2');m.ret(connection)
 m.callbacks[0x100091dac]=create
 for address,label,value in [(0x100091ddc,'set handler',0),(0x100091d94,'activate',0),(0x100091df4,'create dictionary',MEM+0x21000),(0x100091dd0,'send message',0),(0x100091a1c,'release object',0)]:
  m.callbacks[address]=lambda l=label,v=value:(m.events.append(l),m.ret(v))
 m.callbacks[0x100091a04]=lambda:m.ret(m.x(0))
 m.run(0x10000a7ec);assert m.stopped=='return' and m.x(0)==connection and m.u.reg_read(UC_ARM64_REG_SP)==STACK
 assert ('send message' in m.events)==bool(connection)
 rows.append(dict(binary=binding['path'],sha256=binding['sha256'],**m.record(name)))
c,binding=carrier('/sbin/launchd')
for name,fd in [('utmpx_create_error',-1),('utmpx_create_success',7)]:
 m=Machine(c)
 def opening():assert m.x(1)==0x200 and m.get(STACK)==0o666;m.events.append('open O_CREAT utmpx boundary');m.ret(fd)
 m.callbacks[0x100051520]=opening
 m.callbacks[0x10003abb4]=lambda:(m.events.append('close wrapper boundary'),m.ret())
 m.callbacks[0x1000519e8]=lambda:(m.events.append('post-utmpx API boundary'),m.ret())
 m.callbacks[0x1000403c8]=lambda:m.stop('launch configuration continuation')
 m.run(0x100040398);assert m.stopped=='launch configuration continuation'
 assert ('close wrapper boundary' in m.events)==(fd>=0)
 rows.append(dict(binary=binding['path'],sha256=binding['sha256'],**m.record(name)))
a.output.write_text(json.dumps(dict(passed=True,cases=rows,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),
 scope='Actual standalone instructions; explicit XPC/file API returns, no services run. oscard helper null returns without send; utmpx open failure continues locally. Does not prove every caller tolerates missing oscard or all later Data failures.',device_accessed=False),indent=2)+'\n')
print('PASS 4 actual service failure paths')
