"""Scoped native APFS read call/return observations; no native path changes."""
import struct
import read_dispatch_sites as PREVIOUS
ENTRY=PREVIOUS.ENTRY
END=0xfffffff0051a5df8
# Fixed-input range; every direct/indirect call within the observed handler.
CALL_OFFSETS=(0x30,0x3c,0x48,0x4c,0x58,0x7c,0xd4,0x144,0x160,0x180,0x19c,0x1a4,
 0x1e4,0x234,0x24c,0x280,0x290,0x2a8,0x2b8,0x2c0,0x330,0x35c,0x364,0x374,0x37c,
 0x3b0,0x3ec,0x424,0x42c,0x440,0x44c,0x454,0x464,0x478,0x484,0x49c,0x4c8,0x4ec,
 0x518,0x520,0x538,0x54c,0x550,0x558,0x560,0x580,0x594)

def points():
 out=[dict(site=ENTRY+4,id=277,phase='context',pair=None)]
 for n,off in enumerate(CALL_OFFSETS):
  for after in (0,1):out.append(dict(site=ENTRY+off+after*4,id=278+2*n+after,phase='continuation' if after else 'call',pair=n))
 out.append(dict(site=0xfffffff0051a5978,id=278+2*len(CALL_OFFSETS),phase='context',pair=None))
 return out

def add_sites(add,raw,m,backed):
 PREVIOUS.add_sites(add,raw,m,backed)
 found=[]
 for pc in range(ENTRY,END,4):
  word=struct.unpack_from('<I',raw,backed(m,pc))[0]
  if word&0xfc000000==0x94000000 or word&0xfffffc1f==0xd63f0000:found.append(pc-ENTRY)
 if tuple(found)!=CALL_OFFSETS:raise ValueError('Native read call set changed')
 for point in points():add(point['site'],'observed_apfs_read',hex(point['site']),'context' if point['pair'] is None else point['phase'])

def scope(done,outer=False):
 code=PREVIOUS.scope(done)
 if not outer:
  code=code.replace('    cmp x29, x10', '    ldr x11, [x29]\n    cmp x11, x10')
 code+=f'''    ldr x10, [x9, #56]
    LOADABS x11, {ENTRY:#x}
    cmp x10, x11
    b.ne {done}
'''
 code+=('    mov x10, x30\n' if outer else '    ldr x10, [x29, #8]\n')
 code+=f'''    LOADABS x11, {PREVIOUS.DISPATCH+4:#x}
    cmp x10, x11
    b.ne {done}
'''
 return code

def observe(site):
 source=PREVIOUS.observe(site)
 if site==PREVIOUS.PREVIOUS.FIRST:
  source+='    adr x9, probe_read_body_state\n    str xzr, [x9]\n'
  for p in points():
   i=p['id'];source+=f'    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n    DENSE_ONCE {i}, 0\n    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n'
  return source+'    mov x23, #0\n    HEXROW_VAL 1792\n    mov x23, #-1\n    HEXROW_VAL 1824\n'
 selected=[p for p in points() if p['site']==site]
 if not selected:return source
 done=f'.Lbody_done_{site:x}'
 source+=scope(done,selected[0]['pair'] is None)
 for p in selected:
  skip=f'.Lbody_skip_{p["id"]}'
  if p['pair'] is not None:
   source+='    adr x12, probe_read_body_state\n    ldr x13, [x12]\n'
   if p['phase']=='call':source+=f'    orr x13, x13, #{1<<p["pair"]:#x}\n    str x13, [x12]\n'
   else:source+=f'    tbz x13, #{p["pair"]}, {skip}\n    bic x13, x13, #{1<<p["pair"]:#x}\n    str x13, [x12]\n    mov x23, x0\n    HEXROW_VAL 1824\n'
  source+=f'    LOADABS x23, {site:#x}\n    HEXROW_VAL 1792\n    DENSE_ONCE {p["id"]}, '+('0xff40c0ff' if p['phase']=='call' else '0xff40ff80')+'\n'+skip+':\n'
 return source+done+':\n'
