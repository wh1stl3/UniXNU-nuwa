"""Inspect software-generated bootstrap translations; never run on the phone."""
from pathlib import Path
import importlib.util,sys,struct,json
sys.path.insert(0,'out/python-tools')
import unicorn as U
from unicorn.arm64_const import *
spec=importlib.util.spec_from_file_location('test',Path(__file__).resolve().parent/'test-kernel-entry-probe.py');test=importlib.util.module_from_spec(spec);sys.modules[spec.name]=test;spec.loader.exec_module(test)
# Read TCR through the generic architectural system-register interface.
original_hook=U.Uc.emu_stop
snap=[]
def capture(uc):
 try:
  tcr=uc.cpr_read(3,0,2,0,2)
  t0=uc.reg_read(UC_ARM64_REG_TTBR0_EL1);t1=uc.reg_read(UC_ARM64_REG_TTBR1_EL1)
  s=dict(tcr=hex(tcr),ttbr0=hex(t0),ttbr1=hex(t1),sp=hex(uc.reg_read(UC_ARM64_REG_SP)),lr=hex(uc.reg_read(UC_ARM64_REG_X30)),vbar=hex(uc.reg_read(UC_ARM64_REG_VBAR_EL1)))
  def walk(va):
   table=(t1 if va>>63 else t0)&0x0000fffffffff000;rows=[]
   for level,shift in ((1,30),(2,21),(3,12)):
    indexbits=(64-((tcr>>16)&63 if va>>63 else tcr&63)-30) if level==1 else 9; at=table+((va>>shift)&((1<<indexbits)-1))*8;desc=struct.unpack('<Q',uc.mem_read(at,8))[0];rows.append(dict(level=level,address=hex(at),descriptor=hex(desc)))
    if not desc&1:return dict(va=hex(va),mapped=False,rows=rows)
    if level==3 or not desc&2:return dict(va=hex(va),mapped=True,pa=hex((desc&0x0000fffffffff000&~((1<<shift)-1))|(va&((1<<shift)-1))),rows=rows)
    table=desc&0x0000fffffffff000
  m=test.B.macho((test.ROOT/'out/kernel-entry-probe-03/kernel-entry-probe.macho').read_bytes());base=min(x['va'] for x in m['segments'] if x['size']);f=m['symbols']['_start_first_cpu']
  s['walks']=[walk(x) for x in (test.PA+f+0x318-base,uc.reg_read(UC_ARM64_REG_X30),uc.reg_read(UC_ARM64_REG_SP)-8,uc.reg_read(UC_ARM64_REG_VBAR_EL1),test.ARGS+base-test.PA)]
  snap.append(s)
 except Exception as e:snap.append(dict(error=str(e)))
 return original_hook(uc)
U.Uc.emu_stop=capture
build=json.loads((test.ROOT/'reports/kernel-entry-probe/2026-10-24/build-v3.json').read_text());raw=(test.ROOT/build['candidate']['path']).read_bytes();test.run(raw,build)
result=dict(scope='Software-generated bootstrap page-table walk before MMU; not hardware MMU behavior',candidate_sha256=build['candidate']['sha256'],snapshots=snap)
(test.ROOT/'reports/kernel-entry-probe/2026-10-24/pre-mmu-pagewalk.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
