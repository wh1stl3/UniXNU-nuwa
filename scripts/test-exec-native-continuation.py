"""Native post-namei caller, activation fallback, signature and cleanup continuity.

Starts with explicitly constructed native frames at the already observed namei
return. VM image loading and task switching remain external contracts, never a
claim of a loaded launchd. No frozen carrier or qualification files are written.
"""
import argparse
from pathlib import Path
from exec_carrier_model import *

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
c=Carrier(a.work);rows=[]
TASK,OLDTASK,UTHREAD,RO,SPACE,REASON= [MEM+x for x in (0x20000,0x22000,0x24000,0x26000,0x28000,0x2a000)]
NEWTHREAD=MEM+0x3000

cases=[
 dict(name='process_wait',flags=0x40,stop='scheduler boundary'),
 dict(name='process_committed',flags=0x60,error=11,phase=7),
 dict(name='getattr_wait',getattr_error=None,stop='filesystem getattr boundary'),
 dict(name='getattr_ioerror',getattr_error=5,error=5,phase=2),
 dict(name='mode_denied',mode=0,error=13,phase=7),
 dict(name='empty_file',size=0,error=8,phase=7),
 dict(name='read_wait',read=None,stop='file read boundary'),
 dict(name='read_ioerror',read=5,error=5,phase=6),
 dict(name='unknown_format',format='invalid',error=8,phase=7),
 dict(name='short_read_invalid',format='invalid',residual=4090,error=8,phase=7),
 dict(name='swapped_mach',format='swapped',error=86,phase=7),
 dict(name='mach_loader_boundary',format='mach',loader=None,stop='Mach loader boundary'),
 dict(name='mach_loader_bad_object',format='mach',loader=2,mapped_errno=88,stop='task switch with terminated exec copy'),
 dict(name='mach_loader_io',format='mach',loader=9,mapped_errno=5,stop='task switch with terminated exec copy'),
 dict(name='mach_loader_decrypt',format='mach',loader=10,mapped_errno=80,stop='task switch with terminated exec copy'),
 dict(name='success_contract',error=0),
 dict(name='wait_wake_success_contract',flags=0x40,sleep='wake',error=0),
 dict(name='signature_launch_denied',signature=13,error=13,phase=8),
 dict(name='signature_launch_wait',signature=None,stop='launch constraints boundary'),
 dict(name='release_wait',release_wait=True,stop='final release ipc lock boundary'),
]
for case in cases:
 m=environment(c,flags=case.get('flags',0),sleep=case.get('sleep','stop'),
     getattr_error=case.get('getattr_error',0),size=case.get('size',4096),mode=case.get('mode',0o755))
 # Stack snapshots correspond to actual prologues: activate 0xa0, exec 0x70,
 # load_init_program_at_path 0xa0. Return paths execute their real epilogues.
 outer=STACK-0x70; act=outer-0xa0
 saved={0x80:PROC,0x88:IMG,0x70:OLDTASK,0x78:UTHREAD,0x60:0,0x68:TASK,0x90:outer+0x60,0x98:BASE+0x769cfac}
 for off,val in saved.items():m.put(act+off,val)
 m.put(outer+0x60,STACK+0x90);m.put(outer+0x68,BASE+0x769d5f8)
 m.put(STACK+0x58,m.get(BASE+0x7abd760));m.put(STACK+0x98,SENTINEL)
 m.u.reg_write(UC_ARM64_REG_SP,act);m.x(29,act+0x90)
 for reg,val in [(0,0),(19,IMG),(20,PROC),(21,NDP),(26,MEM+0x17080)]:m.x(reg,val)
 m.put(MEM+0x17080,12,4);m.put(IMG+0x2b8,NEWTHREAD);m.put(NEWTHREAD+0x420,RO)
 m.put(RO,NEWTHREAD);m.put(RO+0x10,PROC);m.put(RO+0x20,TASK);m.put(CTX,NEWTHREAD)
 m.put(UTHREAD+0x60,IMG);m.put(TASK+0x328,SPACE);m.put(TASK+0x70,NEWTHREAD);m.put(TASK+0x412,1,1)
 m.put(PROC+0x18,RO+0x100);m.put(RO+0x100,PROC)
 m.put(IMG+0x48,0x100,4)  # native __mac_execve sets IMGPF_EXEC before activation
 m.put(c.proof['targets']['coarse_state']+96,1,4)
 m.put(BASE+0x7af0ce0,0,4);m.put(BASE+0x7a7d62c,0,4);m.put(BASE+0x7a7f4a0,0)
 m.stub('_zone_require_ro',lambda:m.ret())
 del m.callbacks[c.sy['_get_bsdthreadtask_info']]
 # Model only the facilities below the native functions under investigation.
 def event(name,result=0):m.events.append(name);m.ret(result)
 m.stub('_mac_vnode_check_exec',lambda:event('MAC exec boundary'))
 m.stub('_vnode_authorize',lambda:event('authorization boundary'))
 def read():
  assert m.x(0)==0 and m.x(1)==VNODE and m.x(2)==HEADER and m.x(3)==4096
  m.events.append('header read boundary')
  if case.get('read',0) is None:m.stop('file read boundary');return
  m.put(m.get(m.u.reg_read(UC_ARM64_REG_SP)),case.get('residual',0),4)
  m.u.mem_write(HEADER,b'\xa5'*4096)
  m.put(HEADER,0xcffaedfe if case.get('format')=='swapped' else 0,4)
  if case.get('format')=='mach':
   for off,value in ((0,0xfeedfacf),(4,0x100000c),(8,0),(12,2)):m.put(HEADER+off,value,4)
  m.ret(case.get('read',0))
 m.stub('_vn_rdwr',read)
 if 'format' not in case:
  m.stub('_exec_mach_imgact',lambda:event('VM/image activation success contract',0))
 def loader():
  assert m.x(0)==IMG and m.x(1)==HEADER and m.x(2)==NEWTHREAD
  m.events.append('Mach loader boundary')
  if case.get('loader') is None:m.stop('Mach loader boundary')
  else:m.ret(case['loader'])
 m.stub('_cpu_subtype',lambda:m.ret(1))
 m.stub('_validate_potential_simulator_binary',lambda:m.ret(0))
 m.stub('_exec_extract_strings',lambda:event('argument extraction boundary'))
 m.stub('_load_machfile',loader)
 m.stub('_os_reason_create',lambda:m.ret(REASON))
 m.stub('_os_reason_free',lambda:event('reason free'))
 m.stub('_set_proc_name',lambda:event('process name boundary'))
 m.stub('_kauth_cred_proc_ref',lambda:m.ret(MEM+0x17000))
 m.stub('_kauth_cred_unref',lambda:event('credential unref'))
 m.stub('_kauth_authorize_fileop_has_listeners',lambda:m.ret(0))
 m.stub('_nameidone',lambda:event('nameidone'))
 def free():
  assert m.x(1) in (NDP,IMG);event('free '+('nameidata' if m.x(1)==NDP else 'image params'))
 m.stub('_kfree_type_impl_internal',free)
 m.stub('_current_proc',lambda:m.ret(PROC))
 def switch():
  if 'terminate exec copy' in m.events:m.stop('task switch with terminated exec copy')
  else:m.switched=True;event('task switch contract',PROC)
 m.switched=False
 m.stub('_proc_exec_switch_task',switch)
 def terminate():
  assert m.x(0) in (TASK,OLDTASK)
  event('terminate exec copy' if m.x(0)==TASK else 'terminate old task')
 m.stub('_task_terminate_internal',terminate)
 m.callbacks[BASE+0x7698774]=lambda:m.events.append('loader mapped errno '+str(m.x(0)))
 for name in ('_ipc_task_enable','_exec_resettextvp','_task_bank_init','_proc_footprint_entitlement_hacks','_thread_affinity_exec','_proc_inherit_task_role','_task_set_main_thread_qos','_proc_apply_jit_and_vm_policies','_dtrace_thread_didexec','_task_transfer_turnstile_watchports','_task_deallocate_grp','_proc_rele','_proc_knote'):
  m.stub(name,lambda name=name:event(name))
 m.stub('_vnode_put',lambda:event('vnode put'))
 m.stub('_task_is_exec_copy',lambda:m.ret(int(not m.switched)))
 m.stub('_task_did_exec',lambda:m.ret(int(m.switched)))
 def deallocate():
  assert m.x(0)==NEWTHREAD and m.get(TASK+0x70)==0 and not m.get(TASK+0x412,1)&1
  event('thread deallocate after final wait clear')
 m.stub('_thread_deallocate',deallocate)
 m.stub('_proc_task',lambda:m.ret(TASK));m.stub('_get_task_map',lambda:m.ret(MEM+0x2c000))
 m.stub('_vm_map_cs_enforcement_set',lambda:event('VM signing policy boundary'))
 def ro_mut():
  assert m.x(0)==5 and m.x(1)==RO+0x100 and m.x(2)==0x1c and m.x(4)==4
  m.put(m.x(1)+m.x(2),m.get(m.x(3),4),4);m.ret()
 m.stub('_zalloc_ro_mut',ro_mut)
 def constraints():
  m.events.append('launch constraints boundary')
  value=case.get('signature',0)
  if value is None:m.stop('launch constraints boundary');return
  if value:m.put(m.x(2),REASON)
  m.ret(value)
 m.stub('_mac_proc_check_launch_constraints',constraints)
 m.stub('_task_get_special_port',lambda:m.ret(5))
 m.stub('_proc_get_task_raw',lambda:m.ret(TASK));m.stub('_proc_platform',lambda:m.ret(2));m.stub('_proc_sdk',lambda:m.ret(0))
 m.stub('_machine_task_process_signature',lambda:event('machine signature boundary'))
 m.stub('_thread_process_signature',lambda:event('thread signature boundary'))
 m.stub('_proc_csflags_set',lambda:event('CS_KILLED boundary'))
 m.stub('_psignal_with_reason',lambda:event('native SIGKILL request'))
 def space_lock():
  assert m.x(0)==SPACE
  if case.get('release_wait'):m.stop('final release ipc lock boundary')
  else:event('ipc lock')
 m.stub('_ipc_space_lock',space_lock);m.stub('_ipc_space_unlock',lambda:event('ipc unlock'))
 m.stub('_thread_wakeup_prim',lambda:event('exec wait wakeup'))
 try:m.run(BASE+0x769bdd8)
 except Exception:
  failure=a.output.with_name(a.output.stem+'-'+case['name']+'-failure.json')
  failure.parent.mkdir(parents=True,exist_ok=True)
  failure.write_text(json.dumps(dict(case=case,recent=m.recent,events=m.events,draws=m.draws),indent=2)+'\n');raise
 if 'stop' in case:assert m.stopped==case['stop'],(case,m.stopped)
 else:
  assert m.stopped=='return' and m.x(0)==case['error'],(case,m.record(case['name']))
  assert [13,case['error']] in m.draws
  if case['error']:
   assert [17,case['error']] in m.draws and [20,0xe0000000+case['phase']] in m.draws,(case,m.draws)
  else:assert not any(row in (17,20) for row,v in m.draws)
  assert not m.locked and m.get(IMG+0x2b8)==0 and m.get(UTHREAD+0x60)==0
  assert m.events.count('free nameidata')==1 and m.events.count('free image params')==1
  assert m.events.count('vnode put')==1 and m.events.count('credential unref')==(2 if case.get('format')=='invalid' else 1),(case,m.events)
  assert m.get(PROC+0x458,4)&0x60==(0x60 if case['name']=='process_committed' else 0)
  assert ('terminate old task' in m.events)==m.switched
  assert ('terminate exec copy' in m.events)==(not m.switched)
 if case.get('residual'):
  assert m.u.mem_read(HEADER+4096-case['residual'],case['residual'])==bytes(case['residual'])
 if case.get('format')=='invalid':
  assert all(c.sy[s] in m.visits for s in ('_exec_mach_imgact','_exec_fat_imgact','_exec_shell_imgact','_bzero') if s!='_bzero' or case.get('residual'))
 if case.get('signature')==13:assert 'native SIGKILL request' in m.events
 if case.get('loader'):
  assert 'loader mapped errno '+str(case['mapped_errno']) in m.events
  assert 'native SIGKILL request' in m.events and 'terminate exec copy' in m.events
  assert [18,0xa0000007] in m.draws and not any(row in (17,20) for row,v in m.draws)
 row=m.record(case['name']);row['boundary_inputs']=case;rows.append(row)
write_report(a.output,c,rows,'Native namei continuation, real proc/vnode machinery, header residual zero-fill, actual invalid/swapped format rejection, activation epilogue, outer exec branches, real process_signature and task_clear_return_wait, native helper epilogue and result hook. Native frames explicitly initialized. VM image success, task switch, authorization, I/O, signing facilities and resource APIs are contract fixtures; no real Mach-O load, AMFI acceptance, scheduling or device success.')
print('PASS',len(rows),'native continuous paths')
