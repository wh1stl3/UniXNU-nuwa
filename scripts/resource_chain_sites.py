"""Scoped continuation through APFS attributes, resource vnode lookup and read."""
import hashlib,struct
from pathlib import Path
import resource_handler_sites as H
BASE=0xfffffff005190000
SPECS=(
 dict(name='attribute',entry=0xcc48,ret=0xd2ac,frame=0x100,lr=0xcc14,parent='handler',parent_bit=7,parent_lr=H.W.AFTER,
      calls=(0xcc94,0xcd18,0xcd50,0xcd7c,0xce88,0xcec4,0xcff4,0xd07c,0xd0fc,0xd274,0xd288)),
 dict(name='lookup',entry=0xd350,ret=0xd6a8,frame=0xb0,lr=0xcd1c,parent='attribute',parent_bit=1,parent_lr=BASE+0xcc14,
      calls=(0xd3a8,0xd3bc,0xd420,0xd45c,0xd474,0xd480,0xd5b0,0xd5cc,0xd650,0xd668)),
 dict(name='read',entry=0xc2a4,ret=0xc848,frame=0x130,lr=0xcd54,parent='attribute',parent_bit=2,parent_lr=BASE+0xcc14,
      calls=(0xc388,0xc390,0xc3dc,0xc3fc,0xc49c,0xc58c,0xc6b0,0xc738,0xc75c,0xc778)),
)
def points():
 result=[]
 for spec in SPECS:
  rows={spec['entry']:dict(offset=spec['entry'],phase='entry',calls=[],returns=[]),spec['ret']:dict(offset=spec['ret'],phase='return',calls=[],returns=[])}
  for bit,offset in enumerate(spec['calls']):
   for after in (False,True):
    p=rows.setdefault(offset+4*after,dict(offset=offset+4*after,phase='body',calls=[],returns=[]))
    p['returns' if after else 'calls'].append(bit)
  for offset,p in sorted(rows.items()):result.append(dict(p,site=BASE+offset,id=632+len(result),group=spec['name']))
 return result
def spec_for(p):return next(s for s in SPECS if s['name']==p['group'])
def state_name(group):return 'probe_resource_'+group+'_state'
def plan():
 return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),specs=[dict(s,calls=list(s['calls'])) for s in SPECS],state_bytes=96,new_grid_rectangles=0,native_policy_changed=False,
  scope='active read thread, paired parent call, exact parent frame chain and saved LR, paired child returns',
  fields={'A03D':'last scoped attribute/lookup/read checkpoint; not stopped PC','A03E':'raw native x0 at checkpoint, not always errno'},
  limitations=['Selected significant calls, not every instruction','Native locks, errors, IO and exec boundary unchanged'])
def add_sites(add,raw,m,backed):
 for p in points():
  word=struct.unpack_from('<I',raw,backed(m,p['site']))[0]
  if p['calls']:assert word&0xfc000000==0x94000000 or word&0xfffffc1f==0xd63f0000
  if p['phase']=='return':assert word==0xd65f03c0
  add(p['site'],'resource-chain',hex(p['site']),'context')
def observe(site):
 p=next((p for p in points() if p['site']==site),None)
 if p is None:return ''
 spec=spec_for(p);done=f'.Lresource_chain_done_{p["id"]}'
 s=f'''    adr x9, probe_read_state
    ldr x10, [x9]
    cbz x10, {done}
    mrs x10, tpidr_el1
    ldr x11, [x9, #8]
    cmp x10, x11
    b.ne {done}
    adr x9, {state_name(spec['parent'])}
    ldr x10, [x9, #8]
    cbz x10, {done}
    ldr x10, [x9, #16]
    tbz x10, #{spec['parent_bit']}, {done}
'''
 s+=('    mov x12, x29\n    mov x13, x30\n' if p['phase'] in ('entry','return') else '    ldr x12, [x29]\n    ldr x13, [x29, #8]\n')
 s+=f'''    LOADABS x10, {BASE+spec['lr']:#x}
    cmp x13, x10
    b.ne {done}
    ldr x10, [x9]
    ldr x11, [x12]
    cmp x10, x11
    b.ne {done}
    ldr x11, [x12, #8]
    LOADABS x10, {spec['parent_lr']:#x}
    cmp x10, x11
    b.ne {done}
    adr x14, {state_name(spec['name'])}
'''
 if p['phase']=='entry':s+='    str x12, [x14]\n    mov x10, #1\n    str x10, [x14, #8]\n    stp xzr, xzr, [x14, #16]\n'
 else:s+=f'    ldr x10, [x14, #8]\n    cbz x10, {done}\n    ldr x10, [x14]\n    cmp x10, x12\n    b.ne {done}\n'
 s+='    ldr x10, [x14, #16]\n'
 for bit in p['returns']:s+=f'    tbz x10, #{bit}, {done}\n    bic x10, x10, #{1<<bit}\n'
 for bit in p['calls']:s+=f'    orr x10, x10, #{1<<bit}\n'
 s+='    str x10, [x14, #16]\n    ldr x10, [x14, #24]\n    add x10, x10, #1\n    str x10, [x14, #24]\n'
 if p['phase']=='return':s+='    str xzr, [x14, #8]\n'
 s+=f'    adr x9, probe_result_state\n    LOADABS x10, {site:#x}\n    stp x10, x0, [x9, #32]\n'
 return s+H.W.R.R.draw((32,40))+done+':\n'
def reset():
 return ''.join(f'    adr x14, {state_name(s["name"])}\n    stp xzr, xzr, [x14]\n    stp xzr, xzr, [x14, #16]\n' for s in SPECS)
def transform(template):
 needle='.balign 4096\n.global probe_zero';assert template.count(needle)==1
 data=''.join(f'.global {state_name(s["name"])}\n{state_name(s["name"])}:\n    .zero 32\n' for s in SPECS)
 return template.replace(needle,data+needle)
