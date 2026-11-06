"""Pinned native exec and dyld lookup observations; preserve the first failure per attempt."""
import hashlib,struct
from pathlib import Path
import exec_trace_v33 as V33
if hashlib.sha256(Path(V33.__file__).read_bytes()).hexdigest()!='ee47349c7143d12578b9b0874c1aa31528afe4948ac3932e320ea2c59827d2c3':raise ValueError('Frozen v33 observations changed')
CALLS=((0xfffffff00769bd74,'_exec_activate_image','_exec_save_path'),
       (0xfffffff00769bdd4,'_exec_activate_image','_namei'),
       (0xfffffff00769be7c,'_exec_activate_image','_vnode_getattr'),
       (0xfffffff00769bf00,'_exec_activate_image','_mac_vnode_check_exec'),
       (0xfffffff00769bf28,'_exec_activate_image','_vnode_authorize'),
       (0xfffffff00769bf90,'_exec_activate_image','_vn_rdwr'),
       (0xfffffff00769bfe0,'_exec_activate_image','_exec_mach_imgact'),
       (0xfffffff00769c0dc,'_exec_activate_image','_namei'),
       (0xfffffff007698764,'_exec_mach_imgact','_load_machfile'),
       (0xfffffff0077300a4,'_load_dylinker','_namei'),
       (0xfffffff007730120,'_load_dylinker','_vnode_authorize'),
       (0xfffffff0077301a4,'_load_dylinker','_vn_rdwr'))
def add_sites(add,raw,m,backed):
    V33.add_sites(add,raw,m,backed)
    for pc,fn,target in CALLS:
        word=struct.unpack_from('<I',raw,backed(m,pc))[0];imm=word&0x3ffffff
        if imm&(1<<25):imm-=1<<26
        if word&0xfc000000!=0x94000000 or pc+imm*4!=m['symbols'][target]:raise ValueError('Pinned exec-path call changed')
        add(pc,fn,target,'call',pc);add(pc+4,fn,target,'continuation',pc)
def observe(site):
    source=V33.observe(site)
    if site==V33.V32.FIRST:
        source+='    adr x9, probe_exec_state\n    str xzr, [x9, #88]\n'
    record=next(((240+2*i,fn,target) for i,(pc,fn,target) in enumerate(CALLS) if site==pc+4),None)
    if record:
        stage,fn,target=record;done=f'.Lexec_path_done_{site:x}'
        source+=f'''    cbz w0, {done}
    adr x9, probe_exec_state
    ldr x10, [x9, #88]
    cbnz x10, {done}
    mov x10, #{stage}
    str x10, [x9, #88]
    mov x23, x10
    HEXROW_VAL 1472
    mov w23, w0
    HEXROW_VAL 1600
{done}:
'''
    return source
