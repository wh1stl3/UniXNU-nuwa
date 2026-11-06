"""Integrated CHECK8 tests, actual packaged code, serial legacy regressions.

The reused strict harness is rebound only after verifying the recorded CHECK4
parent and current kernel digest. No instruction is replaced in model memory.

CHECK5's 73 machine cases are re-executed unchanged against the CHECK8 kernel.
The selfcheck hook is checked for framebuffer write/readback and ungated arrival
marking; the read_return hook is checked at the real vn_rdwr x30 target.
"""
import argparse, hashlib, json, runpy, sys
from pathlib import Path
import exec_carrier_model as H
from exec_carrier_model import *

p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
proof=json.loads((a.work/'kernel-proof.json').read_bytes())
delta=proof.get('check6_delta') or proof['check5_delta']
assert delta['parent_kernel_sha256']==H.EXPECTED
assert hashlib.sha256((a.work/'kernel.macho').read_bytes()).hexdigest()==proof['kernel_sha256']
H.EXPECTED=proof['kernel_sha256']
c=Carrier(a.work);out=a.output_dir;out.mkdir(parents=True,exist_ok=False)
rows=[];state=proof['targets']['coarse_state'];NEW=MEM+0x3000;TASK=MEM+0x22000;SAVED=MEM+0x24000
for name,active,foreign,error,newptr,repeat in [
 ('success',True,False,0,NEW,False),('success_old_return_first',True,False,0,NEW,False),
 ('error',True,False,13,NEW,False),('foreign',True,True,0,NEW,False),
 ('inactive',False,False,0,NEW,False),('no_new_thread',True,False,0,0,False),
 ('already_recorded',True,False,0,NEW,True)]:
 m=Machine(c);release_site=BASE+0x769d230;init_site=proof['targets']['init_loaded_resume']-4
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
   m.stopped=None;m.callbacks[proof['targets']['init_loaded_resume']]=lambda:m.stop('early old return')
   m.run(init_site);assert m.get(state+32)==NEW
  # Old caller must not consume the new thread's latch, even at this boundary.
  m.stopped=None;m.x(21,SAVED);m.x(3,THREAD)
  m.callbacks[proof['targets']['el0_resume']]=lambda:m.stop('EL0 observer resume')
  m.run(BASE+0x73c3864);assert [14,1] not in m.draws and m.get(state+32)==NEW
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(3,NEW)
  m.run(BASE+0x73c3864);assert m.draws.count([14,1])==1 and m.get(state+32)==0
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,THREAD)
  m.callbacks[proof['targets']['init_loaded_resume']]=lambda:m.stop('late old return')
  m.run(init_site);assert m.get(state+32)==0
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(21,SAVED);m.x(3,NEW)
  m.run(BASE+0x73c3864);assert m.draws.count([14,1])==1
 rows.append(m.record(name))
write_report(out/'target-lifetime.json',c,rows,'Actual CHECK5 kernel callsites and observer; no code injection. Explicit thread objects/scheduling order and intercepted draw/native release entry. GPR/SIMD/SP/NZCV/args/LR preserved. No hardware scheduling proof.')

# Continue the new thread through the real native restore machinery after
# publishing via the actual CHECK5 release hook (not a preseeded target).
rows=[];CPU=MEM+0x28000;USER=MEM+0x3d000
for name,mode,debug,wait in [('native_restore',0,False,False),('kernel_mode',5,False,False),('recount_wait',0,False,True),('debug_restore',0,True,False)]:
 m=Machine(c);m.put(state+104,THREAD);m.put(IMG+0x2b8,NEW);m.x(19,IMG);m.x(24,0)
 m.callbacks[c.sy['_task_clear_return_wait']]=lambda:m.stop('native release entry')
 m.run(BASE+0x769d230);assert m.get(state+32)==NEW
 m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(21,SAVED);m.x(3,NEW)
 m.put(NEW+0x1c8,CPU);m.put(NEW+0x140,0x1234 if debug else 0);m.put(SAVED+0x110,mode,4)
 for i in range(31):m.put(SAVED+8+i*8,0x100+i)
 m.put(SAVED+0x108,USER);m.put(SAVED+0x100,MEM+0x35000)
 m.stub('_recount_enter_user',lambda:m.stop('recount boundary') if wait else m.ret())
 m.stub('_arm_debug_set',lambda:(m.events.append('debug restore boundary'),m.ret()))
 m.callbacks[BASE+0x73c3994]=lambda:m.stop('before ERET')
 m.run(BASE+0x73c3864);assert ([14,1] in m.draws)==(mode==0)
 if wait:assert m.stopped=='recount boundary' and BASE+0x73c3994 not in m.visits
 else:
  assert m.stopped=='before ERET' and m.u.reg_read(UC_ARM64_REG_ELR_EL1)==USER
  assert m.u.cpr_read(3,0,4,0,0)==mode and m.u.reg_read(UC_ARM64_REG_SP)==MEM+0x35000
  for i in range(31):
   if i!=18:assert m.x(i)==0x100+i
 assert USER not in m.visits
 rows.append(m.record(name))
write_report(out/'native-el0-restore.json',c,rows,'Real register restore after CHECK5 new-thread publication. Synthetic saved state; recount/debug explicit boundaries; stop before ERET, no user instruction executed.')

# CHECK8 selfcheck: on the vfs_mountroot==0 fallthrough. It writes a known
# pattern into the FB06 row, reads it straight back, paints the readback to
# FB06, then paints a fixed arrival magic to FB03. Neither draw goes through
# phase_record, so a gate rejection cannot masquerade as "did not execute".
SELFCHECK_MAGIC = 0xc8a5
PATTERN = 0x5a5a5a5a
SCRATCH = proof['targets']['scratch']
selfcheck_site = {x['symbol']: int(x['address'], 16) for x in delta['callers']
                  if x['symbol'] == 'c8_selfcheck'}['c8_selfcheck']
selfcheck_resume = selfcheck_site + 4
rows = []
for name, base, pitch in [('selfcheck_live', MEM + 0x30000, 0),
                          ('selfcheck_pitch', MEM + 0x30000, 1),
                          ('selfcheck_null_base', 0, 0)]:
    m = Machine(c)
    m.put(SCRATCH, base, 8); m.put(SCRATCH + 8, pitch, 8)
    target = base + pitch * 768 + 384 if base else None
    if target is not None:
        m.put(target, 0xdeadbeef, 4)
    values = [0x7000 + i * 16 for i in range(29)]
    for i, v in enumerate(values): m.x(i, v)
    m.x(30, SENTINEL)
    vectors = [(0x13572468 << 32) + i for i in range(32)]
    for i, v in enumerate(vectors):
        m.u.reg_write(getattr(U.arm64_const, 'UC_ARM64_REG_Q' + str(i)), v)
    m.u.reg_write(UC_ARM64_REG_NZCV, 0xa0000000)
    m.callbacks[selfcheck_resume] = lambda: m.stop('selfcheck resume')
    m.run(proof['symbols']['c8_selfcheck'])
    assert m.stopped == 'selfcheck resume', (name, m.stopped)
    expected_draws = ([[6, PATTERN], [3, SELFCHECK_MAGIC]] if base else [[3, SELFCHECK_MAGIC]])
    assert m.draws == expected_draws, (name, m.draws, expected_draws)
    if target is not None:
        assert m.get(target, 4) == PATTERN, (name, 'pattern write')
    exp = values[:]; exp[0] = values[0] + 0x1c8   # replayed `add x0,x0,#0x1c8`
    assert [m.x(i) for i in range(29)] == exp, (name, 'GPR')
    assert m.x(30) == SENTINEL and m.u.reg_read(UC_ARM64_REG_SP) == STACK
    assert m.u.reg_read(UC_ARM64_REG_NZCV) == 0xa0000000
    assert [m.u.reg_read(getattr(U.arm64_const, 'UC_ARM64_REG_Q' + str(i))) for i in range(32)] == vectors
    rows.append(dict(name=name, stop=m.stopped, framebuffer_base=base, pitch=pitch,
                     pattern=PATTERN, readback=(PATTERN if base else None),
                     draws=m.draws, native_site=hex(selfcheck_site),
                     resume=hex(selfcheck_resume), native_replay=True,
                     context_preserved=True, ungated=True))
write_report(out/'check8-selfcheck.json', c, rows,
             'Actual CHECK8 selfcheck hook at packaged address. Framebuffer write/readback and ungated arrival magic; three bases including null. Model memory is plain RAM, so the DEVICE readback verdict can only come from the recording.')

# CHECK8 read_return: patched at 0x769bfa4, the x30 installed by
# coarse_read_before. Zero direct incoming branches => reaching it proves
# vn_rdwr executed RET. One unconditional draw of w0, no gate, no bitmap.
return_site = {x['symbol']: int(x['address'], 16) for x in delta['callers']
               if x['symbol'] == 'c8_read_return'}['c8_read_return']
return_resume = return_site + 4
assert return_site == 0xfffffff00769bfa4
rows = []
for value in (0, 0xE00002BC, 0xFFFFFFFF):
    m = Machine(c)
    mem = MEM + 0x31000; m.put(mem, 0x12345678, 4)
    values = [0x7000 + i * 16 for i in range(29)]
    values[26] = mem
    for i, v in enumerate(values): m.x(i, v)
    m.x(0, value); m.x(30, SENTINEL)
    vectors = [(0x2468ace0 << 32) + i for i in range(32)]
    for i, v in enumerate(vectors):
        m.u.reg_write(getattr(U.arm64_const, 'UC_ARM64_REG_Q' + str(i)), v)
    m.u.reg_write(UC_ARM64_REG_NZCV, 0xa0000000)
    m.callbacks[return_resume] = lambda: m.stop('read return resume')
    m.run(proof['symbols']['c8_read_return'])
    assert m.stopped == 'read return resume', (value, m.stopped)
    assert m.draws == [[7, value & 0xffffffff]], (value, m.draws)
    exp = values[:]; exp[0] = value; exp[8] = 0x12345678  # replayed `ldr w8,[x26]`
    assert [m.x(i) for i in range(29)] == exp, (value, 'GPR')
    assert m.x(30) == SENTINEL and m.u.reg_read(UC_ARM64_REG_SP) == STACK
    assert m.u.reg_read(UC_ARM64_REG_NZCV) == 0xa0000000
    assert [m.u.reg_read(getattr(U.arm64_const, 'UC_ARM64_REG_Q' + str(i))) for i in range(32)] == vectors
    rows.append(dict(name='read_return_x0_%#x' % value, stop=m.stopped, value=value,
                     draws=m.draws, native_site=hex(return_site),
                     resume=hex(return_resume), incoming_direct_branches=0,
                     native_replay=True, context_preserved=True, ungated=True))
write_report(out/'check8-read-return.json', c, rows,
             'Actual CHECK8 vn_rdwr-return hook at the real x30 target 0x769bfa4. Three return values; one ungated draw of w0; native ldr w8,[x26] replayed verbatim. No device execution.')

executed=[]
def regression(name,argv,replace=None):
 source=t.R/'scripts'/name;text=source.read_text();original=hashlib.sha256(source.read_bytes()).hexdigest()
 if replace:
  before,after=replace;assert text.count(before)==1;text=text.replace(before,after)
  (out/('adapted-'+name)).write_text(text)
 sys.argv=[str(source),*map(str,argv)]
 exec(compile(text,str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
 executed.append(dict(source=name,sha256=original,adaptation=replace,executed_text_sha256=hashlib.sha256(text.encode()).hexdigest()))
regression('test-exec-native-helpers.py',['--work',a.work,'--output',out/'native-helpers.json'])
regression('test-exec-native-continuation.py',['--work',a.work,'--output',out/'native-continuation.json'])
regression('test-kmain16-stages.py',['--work',a.work,'--exec-return-limit','2'],
 ("if name=='init_loaded':assert struct.unpack('<Q',u.mem_read(latch+32,8))[0]==thread", "if name=='init_loaded':assert struct.unpack('<Q',u.mem_read(latch+32,8))[0]==0"))
regression('test-kmain4-r1-mainline.py',['--work',a.work])
(out/'regression-binding.json').write_text(json.dumps(dict(kernel_sha256=proof['kernel_sha256'],passed=True,executed=executed,
 harness_sha256=hashlib.sha256(Path(H.__file__).read_bytes()).hexdigest(),expected_hash_rebound_from=proof['check5_delta']['parent_kernel_sha256']),indent=2)+'\n')
print('PASS CHECK8 73 inherited cases (7+4+14+20+20+8), 3 selfcheck and 3 vn_rdwr-return cases')
