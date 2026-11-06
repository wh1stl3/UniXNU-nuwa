"""Scoped cache progress, prefetch, cleanup and native read continuation."""
import hashlib,struct
from pathlib import Path
import resource_chain_sites as H
import cluster_gate_diagnostics as G
BASE=0xfffffff007000000
# Existing native sites only. Preserve the nine caller/gate tiles and add seven
# once-per-header checkpoints along native cache-miss/fallback execution.
TILE_OFFSETS = (0x43914c, 0x439150, 0x4344d4, 0x4349e4, 0x4349e8,
                0x46e538, 0x46e54c, 0x46e550, 0x46e570, 0x43530c,
                0x435310, 0x435330, 0x435334, 0x46e574, 0x46e590, 0x4357f8)
assert len(TILE_OFFSETS) == len(set(TILE_OFFSETS)) == 16

# Keep code size and state layout: only replace the first drawing instruction.
SUPPRESSED_LIVE_TILE=0x46e550
def live_tile(p):return tile_selected(p) and p['offset']!=SUPPRESSED_LIVE_TILE

def tile_selected(p): return p['offset'] in TILE_OFFSETS

SPECS=(
 dict(name='clusterext',entry=0x43871c,ret=0x4388dc,frame=0x50,lr=0xfffffff00519c4a0-BASE,parent='read',parent_bit=4,parent_lr=0xfffffff00519cd54,
      calls=(0x438890,0x438858,0x4388b8,0x4387cc,0x4387f8)),
 dict(name='clustercopy',entry=0x4388e0,ret=0x4399f0,frame=0x180,lr=0x438894,parent='clusterext',parent_bit=0,parent_lr=0xfffffff00519c4a0,
      calls=(0x438c34,0x438e74,0x43914c,0x4391c8,0x439400,0x439454,0x4394ec,0x439ad0,0x439b64,0x439ba8,0x438d70,0x438bdc,0x438c7c,0x439a94,0x439ae4,0x439af4,0x4399cc)),
 dict(name='ubccopy',entry=0x43cb58,ret=0x43cc74,frame=0x70,lr=0x438c38,parent='clustercopy',parent_bit=0,parent_lr=BASE+0x438894,
      calls=(0x43cb8c,0x43cc1c)),
 dict(name='vmcopy',entry=0x3005cc,ret=0x300c98,frame=0x1a0,lr=0x43cc20,parent='ubccopy',parent_bit=1,parent_lr=BASE+0x438c38,
      calls=(0x300638,0x300650,0x300700,0x300728,0x300734,0x300760,0x300804,0x300870,0x300924,0x300a14,0x300a5c,0x300a84,0x300a9c,0x300ab4,0x300b38,0x300b80,0x300b88,0x300bb4,0x300c08,0x300c54,0x300c5c)),
 dict(name='uplrequest',entry=0x6fa0c0,ret=0x6fa1f8,extra_ret=0x6fa1e4,frame=0x10,lr=0x438e78,parent='clustercopy',parent_bit=1,parent_lr=BASE+0x438894,
      calls=(0x6fa1b8,)),
 dict(name='clusterio',entry=0x4344d4,ret=0x4357f8,frame=0x110,lr=0x439150,parent='clustercopy',parent_bit=2,parent_lr=BASE+0x438894,
      calls=(0x4349e4,0x434a5c,0x4351e4,0x43530c,0x435330,0x43561c,0x4357d4)),
 dict(name='strategy',entry=0x46e538,ret=0x46e590,frame=0x20,lr=0x435310,parent='clusterio',parent_bit=3,parent_lr=BASE+0x439150,calls=(0x46e54c,0x46e570)),
)
def catalog_points():
 result=[]
 for spec in SPECS:
  rows={spec['entry']:dict(offset=spec['entry'],phase='entry',calls=[],returns=[]),spec['ret']:dict(offset=spec['ret'],phase='return',calls=[],returns=[])}
  if 'extra_ret' in spec:rows[spec['extra_ret']]=dict(offset=spec['extra_ret'],phase='return',calls=[],returns=[])
  if spec['name']=='clustercopy':
   samples={
    0x4389b0:('x21','native max_io_size after minimum and page rounding'),
    0x438a7c:('x24','initial native io_req_size'),
    0x438b38:('x19','native streaming loop remaining io_size'),
    0x438c1c:('x20','requested cache copy bytes before call'),
    0x438c3c:('request_residual','requested bytes high32, returned residual low32; not errno'),
    0x438c4c:('x8','native error OR residual branch predicate'),
    0x438cd0:('x0','native cache helper error before fallback branch'),
    0x438e18:('x19','native _PAGE_SHIFT_CONST just loaded; not mutable _page_shift'),
    0x439a00:('x19','remaining io_size at cache-stream completion'),
    0x439a80:('x0','native status entering cleanup'),
   }
   for offset,(value,meaning) in samples.items():
    rows[offset]=dict(offset=offset,phase='body',calls=[],returns=[],value=value,meaning=meaning)
  if spec['name']=='vmcopy':
   for offset,value,meaning in ((0x300710,'x8','native page flags before busy/cleaning test'),(0x3006a0,'x22','remaining VM copy request before page batch'),(0x300c78,'x27','VM copy result before epilogue')):
    rows[offset]=dict(offset=offset,phase='body',calls=[],returns=[],value=value,meaning=meaning)
  for bit,offset in enumerate(spec['calls']):
   for after in (False,True):
    p=rows.setdefault(offset+4*after,dict(offset=offset+4*after,phase='body',calls=[],returns=[]))
    p['returns' if after else 'calls'].append(bit)
  if spec['name']=='strategy':rows[0x46e570]['value']='x8'
  for offset,p in sorted(rows.items()):result.append(dict(p,site=BASE+offset,id=700+len(result),group=spec['name']))
 return result
# Preserve catalog IDs/coordinates; only these points emit native hooks.
# Entry/RET and ancestry calls stay paired. VM interior samples/calls are gone.
def points():
 keep_calls={'clusterext':{0},'clustercopy':{0,1,2},'ubccopy':{0,1},'vmcopy':set(),'uplrequest':set(),'clusterio':{0,3,4},'strategy':{0,1}}
 return [p for p in catalog_points() if p['phase'] in ('entry','return') or tile_selected(p) or G.selected(p) or p['offset']==0x300c78 or any(bit in keep_calls[p['group']] for bit in p['calls']+p['returns'])]

def removed_points():
 active={p['site'] for p in points()}
 return [p for p in catalog_points() if p['site'] not in active]

def spec_for(p):return next(s for s in SPECS if s['name']==p['group'])
def state_name(group):return 'probe_resource_'+group+'_state'
def geometry(p):
 if p['group']=='strategy':return (8+(p['id']-832)*36,1030)
 index=p['id']-700
 return 8+(index%6)*36,800+(index//6)*10

def show_hex(p):return p['offset']==0x46e570 or p['phase']=='return' and p['group'] in ('clusterext','clustercopy')

def stamp(p,clear=False):
 if not tile_selected(p):return ''
 x,y=geometry(p);label=f'.Lcluster_tile_{p["id"]}_{int(clear)}'
 color=0 if clear else 0xffff40ff if p['phase']=='entry' else 0xffffffff if p['phase']=='return' or p['returns'] else 0xffffc040 if p['calls'] else 0xff00ffff
 prefix=f'''    adr x9, probe_scratch
    ldp x10, x11, [x9]
    cbz x10, {label}_done
'''
 if not clear and p['offset']==SUPPRESSED_LIVE_TILE:
  prefix=prefix.replace('    adr x9, probe_scratch',f'    b {label}_done',1)
 if not clear:
  prefix+=f'    adr x9, probe_cluster_tile_seen\n    ldrb w12, [x9, #{TILE_OFFSETS.index(p["offset"])}]\n    cbnz w12, {label}_done\n'
 return prefix+f'''
    mov x12, #{y}
    madd x10, x11, x12, x10
    add x10, x10, #{x*4}
    LOADABS x13, {color:#x}
    mov x14, #6
{label}_row:
    mov x15, x10
    mov x16, #24
{label}_pixel:
    str w13, [x15], #4
    subs x16, x16, #1
    b.ne {label}_pixel
    add x10, x10, x11
    subs x14, x14, #1
    b.ne {label}_row
'''+(f'    mov w12, #1\n    strb w12, [x9, #{TILE_OFFSETS.index(p["offset"])}]\n' if not clear else '')+f'''
{label}_done:
'''

def plan():
 return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),specs=[dict(s,calls=list(s['calls'])) for s in SPECS],state_bytes=32*len(SPECS)+len(G.OFFSETS)*G.SLOT_BYTES+16,cache_progress_revision=56,removed_native_sites=[p['site'] for p in removed_points()],vm_copy_observation="entry-return-result-only",new_grid_rectangles=len(TILE_OFFSETS),tile_offsets=list(TILE_OFFSETS),native_policy_changed=False,
  rectangles=[dict(id=p['id'],site=p['site'],x=geometry(p)[0],y=geometry(p)[1],width=24,height=6,hex_published=show_hex(p)) for p in points() if tile_selected(p)],
  gate_diagnostics=dict(enabled=G.ENABLED,reserved_unused_state_bytes=288,source_sha256=hashlib.sha256(Path(G.__file__).read_bytes()).hexdigest(),symbol=G.SYMBOL,slot_bytes=G.SLOT_BYTES,offsets=list(G.OFFSETS),caller_entry=G.CALLER_ENTRY,caller_lrs=list(G.CALLER_LRS),caller_bits=[14,15,16,17],reason_bits=[[i,name] for i,name in enumerate(G.REASONS)],passed_bit=8,reached_bit=9,wide_control_bits=[10,11],strict_control_bits=[12,13],rectangles=[dict(site=p['site'],x=x,y=y,width=w,height=h) for p in points() if G.ENABLED and G.selected(p) for x,y,w,h in G.rectangles(p,geometry)],scope='Active read thread only; no writes for inactive read or foreign thread. Wide control is unattributed; strict scope unchanged. Sticky bits reset per header, not order or counts; no bit proves deadlock or stack corruption.'),
  suppressed_live_tile=SUPPRESSED_LIVE_TILE,suppression_policy='Only 746E550 live tile bypassed; reset and reserved machine code/layout unchanged; native pairing remains',
  render_policy='PROBE54 removes native hooks outside retained ancestry, cache boundary and IO observations. Stable catalog IDs retain PROBE53 coordinates. Sixteen IO tiles remain; nine old gate diagnostic record/render bodies are retired. Their 288-byte inert reservation preserves layout. Unhooked sites execute original instructions; no policy change.',
  scope='active read thread, paired parent call, exact parent frame chain and saved LR, paired child returns',
  fields={'A03A_at_746E570':'buf_vnode result x20','A03B_at_746E570':'native v_op table x9 saved by PROBE_SAVE','A03C_at_746E570':'signed vnop_strategy_desc index','A03D':'last scoped attribute/lookup/read checkpoint; not stopped PC','A03E':'native x0 unless per-point value says otherwise; 7438C3C packs request high32 and residual low32, not errno'},
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
 value=p.get('value','x0')
 if value=='request_residual':
  s+='    mov w15, w8\n    mov w16, w20\n    orr x15, x15, x16, lsl #32\n'
  value='x15'
 s+=f'    adr x9, probe_result_state\n    LOADABS x10, {site:#x}\n    stp x10, {value}, [x9, #32]\n'
 # At this exact call: x20 is buf_vnode result, saved native x9 is v_op.
 # Read only the already-mapped static descriptor; never dereference target.
 if p['offset']==0x46e570:
  s+='    str x20, [x9, #8]\n    ldr x10, [sp]\n    str x10, [x9, #16]\n    LOADABS x10, 0xfffffff0079feca8\n    ldrsw x10, [x10]\n    str x10, [x9, #24]\n'
 offsets=(8,16,24,32,40) if p['offset']==0x46e570 else (32,40)
 return G.instrument(p,geometry,s+stamp(p)+(H.H.W.R.R.draw(offsets) if show_hex(p) else '')+done+':\n')
def reset():
 return '    adr x14, probe_cluster_tile_seen\n    stp xzr, xzr, [x14]\n'+''.join(f'    adr x14, {state_name(s["name"])}\n    stp xzr, xzr, [x14]\n    stp xzr, xzr, [x14, #16]\n' for s in SPECS)+''.join(stamp(p,True) for p in points())+G.reset(points(),geometry)
def transform(template):
 needle='.balign 4096\n.global probe_zero';assert template.count(needle)==1
 data=''.join(f'.global {state_name(s["name"])}\n{state_name(s["name"])}:\n    .zero 32\n' for s in SPECS)
 return template.replace(needle,data+G.data()+'.balign 8\n.global probe_cluster_tile_seen\nprobe_cluster_tile_seen:\n    .zero 16\n'+needle)
