"""Compile two staged observer replacements; test only in emulated memory.

No boot image, candidate, frozen observer source or kernel is modified.
"""
import argparse,subprocess,hashlib,sys
from pathlib import Path
from exec_carrier_model import *
sys.path.append(str(t.R/'out/python-tools'))
from elftools.elf.elffile import ELFFile
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
c=Carrier(a.work);out=a.output_dir;out.mkdir(parents=True,exist_ok=False)
source=t.R/'package/kernel-mainline/CoarseStages-ufs-check4-r1.S'
old=source.read_text();assert hashlib.sha256(source.read_bytes()).hexdigest()=='bb92130f8a8055f1cf68bcb8728633c3bdd2155d156c50fd5f06d94c6076b94f'
init=old.split('.global coarse_init_loaded\n')[1].split('.global coarse_el0\n')[0]
remove='    mrs x10,tpidr_el1\n    add x9,x9,#32\n    stlr x10,[x9]\n'
assert init.count(remove)==1
init=init.replace(remove,'    // Target was published before native FINAL_WAIT release.\n')
init=init.replace('coarse_init_loaded','staged_init_loaded').replace('.addr x9,coarse_state','ldr x9,=coarse_state').replace('.jump init_loaded_resume','b init_loaded_resume')
source_text=(t.R/'package/kernel-mainline/ExecEl0Target-staging.S').read_text()+'\n.global staged_init_loaded\n'+init
source_text+='\n'+ '\n'.join(f'.equ {k}, {v}' for k,v in dict(coarse_state=c.proof['targets']['coarse_state'],phase_record=c.proof['symbols']['phase_record'],native_release=c.sy['_task_clear_return_wait'],draw=c.proof['symbols']['draw'],init_loaded_resume=c.proof['targets']['init_loaded_resume']).items())+'\n'
asm=out/'observer.S';asm.write_text(source_text)
start=BASE+0x84e0000
commands=[['/usr/bin/clang','--target=aarch64-none-elf','-c',str(asm),'-o',str(out/'observer.o')],['/usr/bin/ld.lld','-Ttext='+hex(start),'-e','staged_release_before',str(out/'observer.o'),'-o',str(out/'observer.elf')]]
for cmd in commands:subprocess.run(cmd,check=True,capture_output=True)
with (out/'observer.elf').open('rb') as f:
 elf=ELFFile(f);code=elf.get_section_by_name('.text').data();sy={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
assert len(code)<4096
rows=[];state=c.proof['targets']['coarse_state'];NEW=MEM+0x3000;TASK=MEM+0x22000;SAVED=MEM+0x24000
for name,active,foreign,error,newptr,repeat in [
 ('success',True,False,0,NEW,False),('success_old_return_first',True,False,0,NEW,False),('error',True,False,13,NEW,False),
 ('foreign',True,True,0,NEW,False),('inactive',False,False,0,NEW,False),
 ('no_new_thread',True,False,0,0,False),('already_recorded',True,False,0,NEW,True)]:
 m=Machine(c);m.ensure(start);m.u.mem_write(start,code)
 release_site=BASE+0x769d230;init_site=c.proof['targets']['init_loaded_resume']-4
 for site,label in ((release_site,'staged_release_before'),(init_site,'staged_init_loaded')):
  m.ensure(site);m.u.mem_write(site,c.b.branch(site,sy[label]))
 m.put(state+104,THREAD if active else 0);m.put(state+256,(1<<9) if repeat else 0,4)
 m.put(IMG+0x2b8,newptr);m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,THREAD+16 if foreign else THREAD)
 values=[0x7000+i*16 for i in range(31)];values[0]=TASK;values[1]=2;values[19]=IMG;values[24]=error
 for i,v in enumerate(values):m.x(i,v)
 vectors=[(0x123456789abcdef0<<64)+i for i in range(32)]
 for i,v in enumerate(vectors):m.u.reg_write(getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i)),v)
 m.u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
 m.callbacks[c.sy['_task_clear_return_wait']]=lambda:m.stop('native release entry')
 m.run(release_site)
 expected=values[:];expected[30]=BASE+0x769d234
 assert [m.x(i) for i in range(31)]==expected
 assert [m.u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]==vectors
 assert m.u.reg_read(UC_ARM64_REG_SP)==STACK and m.u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
 armed=name.startswith('success');assert m.get(state+32)==(NEW if armed else 0)
 if armed:
  if name=='success_old_return_first':
   m.stopped=None
   m.callbacks[c.proof['targets']['init_loaded_resume']]=lambda:m.stop('early init observer resume')
   m.run(init_site);assert m.get(state+32)==NEW
  # New thread can run immediately after release, before the old caller returns.
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(21,SAVED);m.x(3,NEW)
  resume=c.proof['targets']['el0_resume'];m.callbacks[resume]=lambda:m.stop('EL0 observer resume')
  m.run(BASE+0x73c3864);assert [14,1] in m.draws and m.get(state+32)==0
  # Late/repeated old-thread init return must neither overwrite nor rearm the latch.
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,THREAD)
  m.callbacks[c.proof['targets']['init_loaded_resume']]=lambda:m.stop('init observer resume')
  m.run(init_site);assert m.get(state+32)==0
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(21,SAVED);m.x(3,NEW)
  m.run(BASE+0x73c3864);assert m.draws.count([14,1])==1
 rows.append(m.record(name))
write_report(out/'report.json',c,rows,'Staged replacement, emulated memory only. Before native FINAL_WAIT release publish ip_new_thread for successful scoped exec. Init return no longer overwrites target. GPR/SIMD/SP/NZCV/native arguments/LR preserved. New thread early arrival and late old return tested. No candidate or image produced; no scheduling/device proof.')
(out/'binding.json').write_text(json.dumps(dict(commands=commands,analysis_only=True,deployable=False,source_sha256=hashlib.sha256(asm.read_bytes()).hexdigest(),code_sha256=hashlib.sha256(code).hexdigest(),load_address=hex(start),bytes=len(code),symbols={k:hex(v) for k,v in sy.items() if k.startswith('staged_')},frozen_kernel_sha256=EXPECTED),indent=2)+'\n')
print('PASS',len(rows),'staged EL0 target repair cases; no image produced')
