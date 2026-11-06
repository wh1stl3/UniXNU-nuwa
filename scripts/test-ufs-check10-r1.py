"""Integrated CHECK10 tests, actual packaged code, serial legacy regressions.

The reused strict harness is rebound only after verifying the recorded CHECK4
parent and current kernel digest. No instruction is replaced in model memory.

CHECK5's 73 machine cases are re-executed unchanged against the CHECK10 kernel.
CHECK8's selfcheck and read_return cases are inherited unchanged, and the new
c10_vn_rdwr_ret witness is executed for real from the packaged cave.
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

# Inherited CHECK8 read_return: patched at 0x769bfa4. CORRECTION: the x30
# constant installed by coarse_read_before is movz #49044 == 0xBF94, so the
# real RET target is 0x769bf94, not 0x769bfa4. 0x769bfa4 is the resid!=0
# short-read path (0x769bf9c cbz w23 skips it when resid==0). These inherited
# cases still verify the hook's own behaviour, but the blank FB07 on device
# no longer witnesses a missing return. CHECK10 adds the real RET witness.
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
# ===== CHECK10: the real _vn_rdwr RET witness, executed from the packaged cave =====
d10 = proof['check10_delta']
assert d10['baseline'] == 'CHECK8 (consumed)' and d10['source_prefix_verbatim'] is True
assert d10['outside_cave_diff_word_count'] == 1 and d10['control_flow_changed'] is False
assert d10['repair_patches_removed'] == 0 and d10['inherited_observations_removed'] == 0
assert d10['new_field_labels'] == {'21': '0xFB15', '22': '0xFB16', '23': '0xFB17'}
assert 49044 == 0xBF94 and 49044 != 0xBFA4, 'x30 immediate arithmetic'
raw10 = (a.work / 'kernel.macho').read_bytes()
witness_patch = [x for x in delta['callers'] if x['symbol'] == 'c10_vn_rdwr_ret']
assert len(witness_patch) == 1
wp = witness_patch[0]
assert int(wp['address'], 16) == 0xfffffff0074669c8
assert raw10[wp['file_offset']:wp['file_offset'] + 4].hex() == wp['after']
assert wp['before'] == 'ff030191'
assert raw10[wp['file_offset'] + 4:wp['file_offset'] + 8].hex() == 'c0035fd6', 'native RET preserved'
# The real RET target is 0x769bf94 (movz #49044 == 0xBF94); 0x769bfa4 is
# the resid!=0 short-read path where CHECK8's FB07 hook was sited.
assert proof['repair_patches']['inherited_read_return_chain_defect']['x30_installed_by_coarse_read_before'] == '0xfffffff00769bf94'
assert 'c8_read_return' in [x['symbol'] for x in delta['callers']]

WITNESS_MAGIC = 0xc10a55aa
witness_resume = 0xfffffff0074669cc
rows = []
for name, retval, lr in [('ret_zero', 0, 0x0769bf94),
                         ('ret_error', 0xe00002bc, 0x0769bf94),
                         ('ret_unexpected_lr', 0, 0xdeadbeef)]:
    m = Machine(c)
    values = [0x7000 + i * 16 for i in range(29)]
    for i, v in enumerate(values): m.x(i, v)
    m.x(0, retval); m.x(30, lr)
    vectors = [(0x13572468 << 32) + i for i in range(32)]
    for i, v in enumerate(vectors):
        m.u.reg_write(getattr(U.arm64_const, 'UC_ARM64_REG_Q' + str(i)), v)
    m.u.reg_write(UC_ARM64_REG_NZCV, 0xa0000000)
    m.callbacks[witness_resume] = lambda: m.stop('native ret reached')
    m.run(proof['symbols']['c10_vn_rdwr_ret'])
    assert m.stopped == 'native ret reached', (name, m.stopped)
    assert m.draws == [[21, WITNESS_MAGIC], [22, retval & 0xffffffff],
                       [23, lr & 0xffffffff]], (name, m.draws)
    exp = values[:]; exp[0] = retval
    assert [m.x(i) for i in range(29)] == exp, (name, 'GPR')
    assert m.x(30) == lr, (name, 'x30 restored')
    assert m.u.reg_read(UC_ARM64_REG_SP) == STACK + 64, (name, 'native stack replay')
    assert m.u.reg_read(UC_ARM64_REG_NZCV) == 0xa0000000
    assert [m.u.reg_read(getattr(U.arm64_const, 'UC_ARM64_REG_Q' + str(i))) for i in range(32)] == vectors
    rows.append(dict(name=name, stop=m.stopped, return_value=hex(retval),
                     x30_low32=hex(lr), draws=m.draws, native_site=wp['address'],
                     resume=hex(witness_resume), native_replay=True,
                     context_preserved=True, ungated=True))
write_report(out / 'check10-ret-witness.json', c, rows,
             'Actual CHECK10 hook executed from the packaged cave at the _vn_rdwr epilogue. Three draws carry arrival magic, w0 and the low 32 bits of the restored x30; full GPR/SIMD/NZCV preserved, native add sp,sp,#64 replayed, control resumes at the untouched native RET. Unicorn only, no device.')

(out / 'check10-byte-binding.json').write_text(json.dumps(dict(
    kernel_sha256=proof['kernel_sha256'], baseline_kernel_sha256=d10['baseline_kernel_sha256'],
    outside_cave_diff_word_count=d10['outside_cave_diff_word_count'],
    outside_cave_only_diff=d10['outside_cave_only_diff'],
    new_patch_site=wp['address'], new_patch_before=wp['before'], new_patch_after=wp['after'],
    native_ret_bytes='c0035fd6', x30_immediate_decimal=49044, x30_low_half='0xBF94',
    check8_fb07_site='0xfffffff00769bfa4 (resid!=0 short-read path, not the RET target)',
    passed=True), indent=2) + '\n')

(out/'regression-binding.json').write_text(json.dumps(dict(kernel_sha256=proof['kernel_sha256'],passed=True,executed=executed,
 harness_sha256=hashlib.sha256(Path(H.__file__).read_bytes()).hexdigest(),expected_hash_rebound_from=proof['check5_delta']['parent_kernel_sha256']),indent=2)+'\n')
print('PASS CHECK10 73 inherited + 3 selfcheck + 3 read_return + 3 ret-witness cases, plus byte-level single-variable bindings')
