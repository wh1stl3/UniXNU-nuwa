"""Execute actual vector-slot entries; test capture and first-thread native VBAR handoff."""
import argparse,gc,importlib.util,json,struct,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'out/python-tools')]
import unicorn as U
from unicorn.arm64_const import *
s=importlib.util.spec_from_file_location('transparency',R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T);B=T.B
s=importlib.util.spec_from_file_location('entry',R/'scripts/test-kernel-entry-probe.py');E=importlib.util.module_from_spec(s);sys.modules[s.name]=E;s.loader.exec_module(E)
def slot(b,index):
 raw=(R/b['candidate']['path']).read_bytes();m=B.macho(raw);seg=next(s for s in m['segments'] if s['name']=='__NUWA_PROBE');u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(seg['va'],B.align(seg['size']));u.mem_write(seg['va'],raw[seg['fileoff']:seg['fileoff']+seg['filesize']]);dest=int(b['probe']['symbols']['probe_exception'],16);seen=[];intr=[]
 u.hook_add(U.UC_HOOK_CODE,lambda u,p,s,d:(seen.append(p),u.emu_stop()) if p==dest else None);u.hook_add(U.UC_HOOK_INTR,lambda u,n,d:(intr.append(n),u.emu_stop()));u.emu_start(seg['va']+index*128,0,count=8)
 return dict(reached=bool(seen),interrupts=intr,pc=hex(u.reg_read(UC_ARM64_REG_PC)),first_word=raw[seg['fileoff']+index*128:seg['fileoff']+index*128+4].hex())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--negative-build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();b=json.loads(a.build.read_text());old=json.loads(a.negative_build.read_text());checks=[];positive=[];negative=[]
 for i in range(16):
  good=slot(b,i);bad=slot(old,i);assert good['reached'] and not good['interrupts'],(i,good);assert not bad['reached'] and bad['interrupts'],(i,bad);positive.append(good);negative.append(bad);gc.collect()
 checks += [dict(name='All sixteen actual vector entries branch to the reporter',passed=True),dict(name='Old PROBE17 vector entries trap before the reporter',passed=True)]
 raw=(R/b['candidate']['path']).read_bytes();native=B.macho(raw)['symbols']['_ExceptionVectorsBase'];cont=E.run_continuous(raw,b);assert cont['reached'] and cont['error'] is None and cont['native_vbar_snapshot']==hex(native),cont
 checks.append(dict(name='Real cold path captures the pinned native VBAR before override',passed=True))
 m=B.macho(raw);site=m['symbols']['_kernel_bootstrap_thread'];patch=next(p for p in b['patches'] if p['va']==hex(site));case=dict(flag=0,video=True,nzcv=0,x0=1,native_pc=site+4);u,state,writes=T.machine(raw,b,patch,case);ps=b['probe']['symbols'];status=int(ps['probe_vector_status'],16)
 assert u.cpr_read(3,0,12,0,0)==native and struct.unpack('<Q',u.mem_read(status,8))[0]==1
 checks.append(dict(name='First-thread entry restores native VBAR before services and IRQ enable',passed=True))
 u.mem_write(int(ps['probe_native_vectors'],16),struct.pack('<Q',0x12345000));u.cpr_write(3,0,12,0,0,int(ps['probe_vectors'],16));reject=int(ps['probe_native_vector_reject'],16);u.hook_add(U.UC_HOOK_CODE,lambda u,p,s,d:u.emu_stop() if p==reject else None);u.emu_start(site,0,count=2000000)
 assert u.reg_read(UC_ARM64_REG_PC)==reject and u.cpr_read(3,0,12,0,0)==int(ps['probe_vectors'],16) and struct.unpack('<Q',u.mem_read(status,8))[0]==2
 checks.append(dict(name='Unexpected saved VBAR is rejected without unsafe handoff',passed=True))
 a.output.write_text(json.dumps(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,native_vbar=hex(native),positive=positive,negative=negative,cold_snapshot=cont['native_vbar_snapshot'],scope=__doc__,limitations=['Model execution; no hardware IRQ delivery or interrupt controller validation']),indent=2)+'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
