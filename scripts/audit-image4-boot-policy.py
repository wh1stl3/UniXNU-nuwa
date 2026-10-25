"""Audit the preserved AppleImage4 boolean policy consumer against the shipped ADT.
Fixtures change only an in-memory property; no shipped ADT, kernel, policy or device is changed.
"""
import argparse,gc,importlib.util,json,struct,sys,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'out/python-tools'),str(R/'scripts')]
import unicorn as U
from unicorn.arm64_const import *
s=importlib.util.spec_from_file_location('b',R/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
ENTRY=0xfffffff0046e9fe0;STACK=0xf00000;TREE=0xe00000;KEY='mix-n-match-prevention-status'
def append_property(blob,value):
 found=0
 def read(at):
  nonlocal found
  count,children=struct.unpack_from('<II',blob,at);at+=8;props=[];name=None
  for _ in range(count):
   begin=at;key=blob[at:at+32].split(b'\0')[0].decode();n=struct.unpack_from('<I',blob,at+32)[0]&0x7fffffff;at+=36;v=blob[at:at+n];at+=B.align(n,4);props.append(blob[begin:at])
   if key=='name':name=v.split(b'\0')[0].decode()
   if key==KEY:raise ValueError('Fixture expects the currently missing property')
  kids=[]
  for _ in range(children):raw,at=read(at);kids.append(raw)
  if name=='chosen':props.append(KEY.encode().ljust(32,b'\0')+struct.pack('<I',len(value))+value+bytes((-len(value))%4));count+=1;found+=1
  return struct.pack('<II',count,children)+b''.join(props)+b''.join(kids),at
 result,end=read(0);assert found==1 and not any(blob[end:]);return result

def execute(raw,m,adt):
 base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments']);u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(base,B.align(end-base));u.mem_map(STACK,0x10000);u.mem_map(TREE,B.align(len(adt)));u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
 for s in m['segments']:
  if s['filesize']:u.mem_write(s['va'],raw[s['fileoff']:s['fileoff']+s['filesize']])
 u.mem_write(TREE,adt);u.reg_write(UC_ARM64_REG_SP,STACK+0x8000);u.reg_write(UC_ARM64_REG_LR,STACK);u.reg_write(UC_ARM64_REG_X0,TREE);u.reg_write(UC_ARM64_REG_X1,len(adt));u.emu_start(m['symbols']['_SecureDTInit'],STACK,count=100000)
 out=STACK+0x1000;u.mem_write(out,b'\xa5');bad=[];events=[]
 u.hook_add(U.UC_HOOK_MEM_INVALID,lambda u,a,p,s,v,d:bad.append([a,hex(p)]) or False)
 def watch(u,p,s,d):
  if p==m['symbols']['_SecureDTGetProperty']:
   at=u.reg_read(UC_ARM64_REG_X1);buf=bytes(u.mem_read(at,80));events.append(buf.split(b'\0')[0].decode())
 u.hook_add(U.UC_HOOK_CODE,watch)
 for reg,val in ((UC_ARM64_REG_X0,0),(UC_ARM64_REG_X1,0),(UC_ARM64_REG_X2,12),(UC_ARM64_REG_X3,out),(UC_ARM64_REG_SP,STACK+0x8000),(UC_ARM64_REG_LR,STACK)):u.reg_write(reg,val)
 u.emu_start(ENTRY,STACK,count=1000000)
 assert u.reg_read(UC_ARM64_REG_PC)==STACK and not bad
 return dict(errno=u.reg_read(UC_ARM64_REG_X0),allow_mix_n_match=bytes(u.mem_read(out,1))[0],property_reads=events,adt_sha256=B.sha(adt))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();raw=B.INPUT.read_bytes();assert B.sha(raw)==B.EXPECTED;m=B.macho(raw);adt=a.adt.read_bytes();cases={};checks=[]
 variants=[('shipped-missing',adt,2,0xa5),('prevention-one',append_property(adt,struct.pack('<I',1)),0,0),('prevention-zero',append_property(adt,struct.pack('<I',0)),0,1),('empty-property',append_property(adt,b''),0,1),('oversized-property',append_property(adt,bytes(8)),84,0xa5)]
 for name,tree,errno,allow in variants:
  result=execute(raw,m,tree);assert result['errno']==errno and result['allow_mix_n_match']==allow,(name,result);assert KEY in result['property_reads'];cases[name]=result;checks.append(dict(name=name+' matches real consumer return and boolean semantics',passed=True));gc.collect()
 report=dict(scope=__doc__,input_sha256=B.sha(raw),adt_sha256=B.sha(adt),consumer=hex(ENTRY),property='/chosen/'+KEY,checks=checks,cases=cases,policy_selected=False,shipped_files_modified=False,device_accessed=False,limitations=['Native SecureDT fallback in an isolated instruction model; IOKit runtime-provider route not executed','Zero/empty cases are negative policy fixtures, not proposed shipping values','A readable property does not establish fusing, chain-of-trust or manifest authenticity'])
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(checks=len(checks),passed=True,shipped_errno=cases['shipped-missing']['errno'])))
if __name__=='__main__':main()
