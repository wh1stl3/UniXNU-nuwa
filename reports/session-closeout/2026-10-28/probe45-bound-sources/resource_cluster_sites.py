"""Scoped continuation through APFS attributes, resource vnode lookup and read."""
import hashlib,struct
from pathlib import Path
import resource_chain_sites as H
BASE=0xfffffff007000000
SPECS=(
 dict(name='clusterext',entry=0x43871c,ret=0x4388dc,frame=0x50,lr=0xfffffff00519c4a0-BASE,parent='read',parent_bit=4,parent_lr=0xfffffff00519cd54,
      calls=(0x438890,0x438858,0x4388b8,0x4387cc,0x4387f8)),
 dict(name='clustercopy',entry=0x4388e0,ret=0x4399f0,frame=0x180,lr=0x438894,parent='clusterext',parent_bit=0,parent_lr=0xfffffff00519c4a0,
      calls=(0x438c34,0x438e74,0x43914c,0x4391c8,0x439400,0x439454,0x4394ec,0x439ad0,0x439b64,0x439ba8,0x438d70)),
 dict(name='ubccopy',entry=0x43cb58,ret=0x43cc74,frame=0x60,lr=0x438c38,parent='clustercopy',parent_bit=0,parent_lr=BASE+0x438894,
      calls=(0x43cb8c,0x43cc1c)),
 dict(name='uplrequest',entry=0x6fa0c0,ret=0x6fa1f8,extra_ret=0x6fa1e4,frame=0x10,lr=0x438e78,parent='clustercopy',parent_bit=1,parent_lr=BASE+0x438894,
      calls=(0x6fa1b8,)),
 dict(name='clusterio',entry=0x4344d4,ret=0x4357f8,frame=0x110,lr=0x439150,parent='clustercopy',parent_bit=2,parent_lr=BASE+0x438894,
      calls=(0x4349e4,0x434a5c,0x4351e4,0x43530c,0x435330,0x43561c,0x4357d4)),
)
def points():
 result=[]
 for spec in SPECS:
  rows={spec['entry']:dict(offset=spec['entry'],phase='entry',calls=[],returns=[]),spec['ret']:dict(offset=spec['ret'],phase='return',calls=[],returns=[])}
  if 'extra_ret' in spec:rows[spec['extra_ret']]=dict(offset=spec['extra_ret'],phase='return',calls=[],returns=[])
  if spec['name']=='clustercopy':rows[0x438e18]=dict(offset=0x438e18,phase='body',calls=[],returns=[],value='x19',meaning='native page_shift just loaded')
  for bit,offset in enumerate(spec['calls']):
   for after in (False,True):
    p=rows.setdefault(offset+4*after,dict(offset=offset+4*after,phase='body',calls=[],returns=[]))
    p['returns' if after else 'calls'].append(bit)
  for offset,p in sorted(rows.items()):result.append(dict(p,site=BASE+offset,id=700+len(result),group=spec['name']))
 return result
def spec_for(p):return next(s for s in SPECS if s['name']==p['group'])
def state_name(group):return 'probe_resource_'+group+'_state'
def plan():
 return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),specs=[dict(s,calls=list(s['calls'])) for s in SPECS],state_bytes=160,new_grid_rectangles=0,native_policy_changed=False,
  scope='active read thread, paired parent call, exact parent frame chain and saved LR, paired child returns',
  fields={'A03D':'last scoped attribute/lookup/read checkpoint; not stopped PC','A03E':'raw native register at checkpoint; x19 only at page_shift checkpoint, not always errno'},
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
 spec=spec_for(p);done=f'.Lresource_cluster_done_{p["id"]}'
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
 s+=f'    adr x9, probe_result_state\n    LOADABS x10, {site:#x}\n    stp x10, {p.get("value","x0")}, [x9, #32]\n'
 return s+H.H.W.R.R.draw((32,40))+done+':\n'
def reset():
 return ''.join(f'    adr x14, {state_name(s["name"])}\n    stp xzr, xzr, [x14]\n    stp xzr, xzr, [x14, #16]\n' for s in SPECS)
def transform(template):
 needle='.balign 4096\n.global probe_zero';assert template.count(needle)==1
 data=''.join(f'.global {state_name(s["name"])}\n{state_name(s["name"])}:\n    .zero 32\n' for s in SPECS)
 return template.replace(needle,data+needle)
