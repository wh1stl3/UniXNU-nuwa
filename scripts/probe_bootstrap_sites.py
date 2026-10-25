"""Dense, fixed-input call/return edge instrumentation; no native calls skipped."""
import struct
FUNCTIONS=('_kernel_bootstrap','_vm_mem_bootstrap','_vm_page_bootstrap','_pmap_startup')
SKIP={'_printf','_kprintf','_kernel_debug_string_early','_panic','_Assert','_PE_parse_boot_argn','_PE_i_can_has_debugger'}
def signed(v,b):return v-(1<<b) if v&(1<<(b-1)) else v
def plan_legacy(raw,m,backed):
    symbols=m['symbols'];reverse={v:k for k,v in symbols.items()};edges=[];sites={}
    for fn in FUNCTIONS:
        start=symbols[fn];end=min(v for v in symbols.values() if v>start)
        for pc in range(start,end,4):
            word=struct.unpack_from('<I',raw,backed(m,pc))[0]
            if word&0xfc000000!=0x94000000:continue
            target=(pc+signed(word&0x3ffffff,26)*4)&((1<<64)-1);callee=reverse.get(target,hex(target))
            if callee in SKIP or 'ubsan' in callee or 'invalid' in callee:continue
            for phase,site in (('call',pc),('continuation',pc+4)):
                index=len(edges)
                if index>=160:raise ValueError('Dense panel capacity exceeded')
                edge=dict(id=index,function=fn,callee=callee,phase=phase,call=hex(pc),site=hex(site),x=832+(index%10)*48,y=256+(index//10)*32,color=('0xff40c0ff' if phase=='call' else '0xff40ff80'))
                edges.append(edge);sites.setdefault(site,[]).append(edge)
    return edges,sites

# Revision25 focuses on execution AFTER the already observed first-thread edge.
NEXT_FUNCTIONS=('_load_context','_thread_continue','_kernel_bootstrap_thread','_bsd_utaskbootstrap')
BSD_MILESTONES={'_throttle_init','_kauth_init','_fdt_init','_mac_policy_initbsd',
 '_bsd_bufferinit','_IOKitInitializeTime','_vfsinit','_OSKextLoadKextWithIdentifier',
 '_IOKitBSDInit','_net_init_run','_IOFindBSDRoot','_vfs_mountroot','_IOSecureBSDRoot',
 '_imageboot_setup','_IOSetImageBoot','_devfs_kernel_mount','_bsd_utaskbootstrap'}
ENTRY_FUNCTIONS=('_load_context','_machine_load_context','_thread_continue',
 '_call_continuation','_kernel_bootstrap_thread','_PE_init_iokit','_bsd_init',
 '_IOFindBSDRoot','_vfs_mountroot','_bsd_utaskbootstrap')
def plan_next(raw,m,backed,revision=25):
    symbols=m['symbols'];reverse={v:k for k,v in symbols.items()};edges=[];sites={}
    def add(site,fn,callee,phase,call=None):
        index=len(edges)+(4 if revision>=29 and len(edges)>=178 else 0)
        if index>=220:raise ValueError('Next-phase panel capacity exceeded')
        color={'call':'0xff40c0ff','continuation':'0xff40ff80','entry':'0xffffff00','context':'0xffff40ff'}[phase]
        e=dict(id=index,function=fn,callee=callee,phase=phase,call=hex(call if call is not None else site),site=hex(site),x=832+(index%10)*48,y=256+(index//10)*24,color=color)
        edges.append(e);sites.setdefault(site,[]).append(e)
    for fn in ENTRY_FUNCTIONS:add(symbols[fn],fn,fn,'entry')
    machine=symbols['_machine_load_context']
    for off,word,meaning in ((0x5c,0xfd403828,'post-SP restore before D8'),(0x8c,0xd65f03c0,'before context RET')):
        site=machine+off
        if int.from_bytes(raw[backed(m,site):backed(m,site)+4],'little')!=word:raise ValueError('Machine context checkpoint changed')
        add(site,'_machine_load_context',meaning,'context')
    for fn in (*NEXT_FUNCTIONS,'_bsd_init'):
        start=symbols[fn];end=min(v for v in symbols.values() if v>start)
        for pc in range(start,end,4):
            word=struct.unpack_from('<I',raw,backed(m,pc))[0]
            if word&0xfc000000==0x94000000:
                target=pc+signed(word&0x3ffffff,26)*4;callee=reverse.get(target,hex(target))
                # This unsymbolized helper only obtains startup log labels.
                if target==0xfffffff00729f29c or callee in SKIP or '_early_random'==callee or 'ubsan' in callee or 'cold.' in callee:continue
                if fn=='_bsd_init' and callee not in BSD_MILESTONES:continue
            elif word&0xfffffc1f==0xd63f0000:
                if fn=='_bsd_init':continue
                callee='indirect_x'+str((word>>5)&31)
            else:continue
            add(pc,fn,callee,'call',pc);add(pc+4,fn,callee,'continuation',pc)
    if revision>=29:
        # Keep legacy 0..177 and pthread 178..181 unchanged. Pin each real BL
        # and expose the two different native waits instead of skipping either.
        root_calls=(0xfffffff0078e3374,0xfffffff0078e33b4,
                    0xfffffff0078e349c,0xfffffff0078e34b4,
                    0xfffffff0078e34e0,0xfffffff0078e34ec,
                    0xfffffff0078e3644,0xfffffff0078e36a8,
                    0xfffffff0078e3708,0xfffffff0078e37a8,
                    0xfffffff0078e381c,0xfffffff0078e3a3c,
                    0xfffffff0078e3d94,0xfffffff0078e3e94,
                    0xfffffff0078e3ea8)
        for pc in root_calls:
            word=struct.unpack_from('<I',raw,backed(m,pc))[0]
            if word&0xfc000000!=0x94000000:raise ValueError('Root checkpoint no longer a native BL')
            target=pc+signed(word&0x3ffffff,26)*4;callee=reverse.get(target)
            if callee is None:raise ValueError('Root checkpoint target has no pinned symbol')
            add(pc,'_IOFindBSDRoot',callee,'call',pc)
            add(pc+4,'_IOFindBSDRoot',callee,'continuation',pc)
    return edges,sites

def plan(raw,m,backed,revision=24):
    return plan_next(raw,m,backed,revision) if revision>=25 else plan_legacy(raw,m,backed)

def relocate(word,pc,label):
    resume=pc+4;tail=f'    b {label}_resume\n';defs={label+'_resume':resume}
    if word&0x7c000000==0x14000000:
        target=pc+signed(word&0x3ffffff,26)*4;defs[label+'_target']=target
        code=''
        if word&(1<<31):code=f'    adrp x30, {label}_resume\n    add x30, x30, :lo12:{label}_resume\n'
        return code+f'    b {label}_target\n',defs
    if word&0xfffffc1f==0xd63f0000:
        reg=(word>>5)&31
        if reg==30:raise ValueError('BLR x30 requires an explicit trampoline')
        return f'    adrp x30, {label}_resume\n    add x30, x30, :lo12:{label}_resume\n    br x{reg}\n',defs
    if word&0x1f000000==0x10000000:
        delta=signed(((word>>29)&3)|(((word>>5)&0x7ffff)<<2),21)
        value=((pc&~4095)+(delta<<12)) if word&(1<<31) else pc+delta
        reg=word&31
        if reg==31:raise ValueError('Unexpected ADR destination')
        return ''.join(f'    mov{("z" if shift==0 else "k")} x{reg}, #{(value>>shift)&65535}, lsl #{shift}\n' for shift in (0,16,32,48))+tail,defs
    if word&0x7e000000 in (0x34000000,0x36000000) or word&0xff000010==0x54000000:
        tb=word&0x7e000000==0x36000000;bits=14 if tb else 19;mask=((1<<bits)-1)<<5
        target=pc+signed((word>>5)&((1<<bits)-1),bits)*4;defs[label+'_target']=target
        inverse=((word&~mask)|(2<<5))^(1 if word&0xff000010==0x54000000 else (1<<24))
        return f'    .inst {inverse:#x}\n    b {label}_target\n'+tail,defs
    if word&0x3b000000==0x18000000:raise ValueError('Literal load needs explicit relocation')
    return f'    .inst {word:#x}\n'+tail,defs

def generate(raw,m,backed,revision=24):
    edges,sites=plan(raw,m,backed,revision);source=[];constants={};hooks=[]
    for site,markers in sorted(sites.items()):
        label=f'probe_dense_{site&0xffffffff:x}';word=struct.unpack_from('<I',raw,backed(m,site))[0]
        code,defs=relocate(word,site,'original_'+label);constants.update(defs)
        source += [f'.global {label}',label+':','    PROBE_SAVE']
        source += [f'    DENSE_ONCE {e["id"]}, {e["color"]}' for e in markers]
        if revision>=25:
            if site==m['symbols']['_load_context']:source += ['    DISPLAY_INIT',f'    DISPLAY_CHECK {markers[0]["id"]}']
            if site in (m['symbols']['_machine_load_context'],m['symbols']['_kernel_bootstrap_thread'],m['symbols']['_bsd_init']):source += [f'    DISPLAY_CHECK {markers[0]["id"]}']
            if site==m['symbols']['_kernel_bootstrap_thread']:source += ['    RESTORE_NATIVE_VECTORS']
        if revision>=28 and site==m['symbols']['_bsd_init']:
            source += ['    stp x29, x30, [sp, #-16]!', '    bl pthread_load_before_bsd', '    ldp x29, x30, [sp], #16']
        source += ['    PROBE_RESTORE',f'.global {label}_replay',label+'_replay:',code]
        hooks.append((site,label))
    return '\n'.join(source)+'\n',constants,hooks,edges
