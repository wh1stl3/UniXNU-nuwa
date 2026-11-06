"""Reviewed retirement manifest: native instruction restoration, never guessed NOPs."""
import json,hashlib,re,importlib.util
from pathlib import Path
import flush_trace_inputs as t
EVENTS=[('getattr_before',0x769be7c),('getattr_after',0x769be80),('mac_after',0x769bf04),('authorize_after',0x769bf2c),('read_before',0x769bf90),('read_after',0x769bf94),('activate_after',0x769cfac),('signature_after',0x769d110),('release_before',0x769d230)]
# These generated observers add only bounded framebuffer tiles to state snapshots.
TILES={0x74344d4,0x74349e4,0x74349e8,0x743530c,0x7435310,0x7435330,0x7435334,0x74357f8,0x743914c,0x7439150,0x746e538,0x746e54c,0x746e550,0x746e570,0x746e574,0x746e590}
MANUAL=TILES|{0x769bf90,0x73c73e0,0x769d230}
KEEP_FUNCTIONAL={0x729f098:'display initialization',0x76729e0:'pthread actual OSKext lifecycle',0x769d5f4:'FSCompression actual OSKext lifecycle',0x7944b18:'restore native exception vectors'}
def plan(raw,macho,parent):
 a_path=t.R/'reports/ufs-check-4-r1/legacy-source-audit.json';a=json.loads(a_path.read_bytes());src=t.R/'out/kernel-entry-probe-61-init-bridge-r2/probe.S';assert hashlib.sha256(src.read_bytes()).hexdigest()==a['assembly_sha256'];assert hashlib.sha256((t.BASE/'build.json').read_bytes()).hexdigest()==a['parent_build_sha256']
 b=t.builder();changes=[];targets={};by_site={int(x['va'],16):x for x in parent['patches'] if x.get('va')};syms={k:int(v,16) for k,v in parent['probe']['symbols'].items()}
 for row in a['rows']:
  x=row['patch'];address=int(x['va'],16);low=address&0xfffffff
  if not row['source_effects_only_diagnostic'] and low not in MANUAL:continue
  assert low not in KEEP_FUNCTIONAL
  off=b.backed(macho,address,4);assert raw[off:off+4].hex()==x['after'];assert x['before']!=x['after']
  changes.append(dict(address=hex(address),before=x['after'],after=x['before'],reason='retire legacy diagnostic body: '+x['reason'],source_body_sha256=row['body_sha256'],method='source CFG diagnostic-only' if row['source_effects_only_diagnostic'] else 'manual bounded tiles/state' if low!=0x769d230 else 'user-requested removal of restore-era final-wait self-loop'))
 # Five early drawing-only entry points: restore exact displaced instruction.
 assembly=src.read_text()
 for low,label in [(0x73c7378,'probe_mmu_on'),(0x729e804,'probe_kernel_bootstrap'),(0x5194248,'probe_cpu_base'),(0x5194278,'probe_arm_vm'),(0x5194290,'probe_pmap')]:
  address=0xfffffff000000000+low;x=by_site[address];start=assembly.index('\n'+label+':');end=assembly.index('\n.global ',start+1);body=assembly[start:end]
  allowed=[line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith('//')]
  assert all(line==label+':' or line in ('PROBE_SAVE','PROBE_RESTORE','.inst original_mmu_on_word') or line.startswith('BAND_ONCE ') for line in allowed),body
  assert raw[b.backed(macho,address,4):][:4].hex()==x['after']
  changes.append(dict(address=hex(address),before=x['after'],after=x['before'],reason='retire early drawing-only hook: '+label,source_body_sha256=hashlib.sha256(body.encode()).hexdigest(),method='explicit source stencil; exact original instruction restored'))
 # Mixed FSCompression wrapper: preserve register frame and real load helper,
 # bypass obsolete exec-state initialization/HEX prefix whose consumers retired.
 start=syms['probe_dense_769d5f4'];end=syms['probe_dense_769d5f4_replay'];helper=0xfffffff0084e65dc;calls=[]
 for pc in range(start,end,4):
  word=int.from_bytes(raw[b.backed(macho,pc,4):][:4],'little')
  if word&0xfc000000!=0x94000000:continue
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
  if pc+4*imm==helper:calls.append(pc)
 assert len(calls)==1
 call=calls[0];prefix=start+52
 assert raw[b.backed(macho,start,4):][:4].hex()=='ffc302d1'
 assert raw[b.backed(macho,prefix-8,8):][:8].hex()=='09423bd5e95300f9'
 assert raw[b.backed(macho,call-4,4):][:4].hex()=='fd7bbfa9'
 changes.append(dict(address=hex(prefix),before=raw[b.backed(macho,prefix,4):][:4].hex(),after=b.branch(prefix,call-4).hex(),reason='retire unused exec-state prefix; preserve FSCompression load and saved-register frame',method='exact call target and save frame validation'))
 # Existing compact hooks can still tail-jump into legacy replay, never observation bodies.
 for key,site in [('exec_entry_old',0x769ce3c),('exec_namei_target',0x769bdd8)]:targets[key]=syms['probe_dense_'+format(site,'x')+'_replay']
 for name,site in EVENTS:
  address=0xfffffff000000000+site
  if name in ('getattr_before','read_before','release_before'):
   x=by_site.get(address);word=int.from_bytes(bytes.fromhex(x['before']) if x else raw[b.backed(macho,address):][:4],'little');assert word&0xfc000000==0x94000000
   imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;targets['phase_'+name+'_resume']=address+4*imm
  else:targets['phase_'+name+'_resume']=syms['probe_dense_'+format(site,'x')+'_replay']
 assert targets['phase_release_before_resume']==macho['symbols']['_task_clear_return_wait']
 assert targets['phase_getattr_before_resume']==macho['symbols']['_vnode_getattr']
 assert targets['phase_read_before_resume']==macho['symbols']['_vn_rdwr']
 return dict(changes=changes,targets=targets,source_audit_sha256=hashlib.sha256(a_path.read_bytes()).hexdigest(),retained_functional={hex(k):v for k,v in KEEP_FUNCTIONAL.items()},scope='All 505 inherited dense sites reviewed: diagnostic-state/render bodies restored; four functional mixed helpers retained. Surviving current hooks target native replay. No native authentication/errno/timeout changes.')
