"""Dense, fixed-input call/return edge instrumentation; no native calls skipped."""
import struct
FUNCTIONS=('_kernel_bootstrap','_vm_mem_bootstrap','_vm_page_bootstrap','_pmap_startup')
SKIP={'_printf','_kprintf','_kernel_debug_string_early','_panic','_Assert','_PE_parse_boot_argn','_PE_i_can_has_debugger'}
def signed(v,b):return v-(1<<b) if v&(1<<(b-1)) else v
def plan(raw,m,backed):
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

def relocate(word,pc,label):
    resume=pc+4;tail=f'    b {label}_resume\n';defs={label+'_resume':resume}
    if word&0x7c000000==0x14000000:
        target=pc+signed(word&0x3ffffff,26)*4;defs[label+'_target']=target
        code=''
        if word&(1<<31):code=f'    adrp x30, {label}_resume\n    add x30, x30, :lo12:{label}_resume\n'
        return code+f'    b {label}_target\n',defs
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

def generate(raw,m,backed):
    edges,sites=plan(raw,m,backed);source=[];constants={};hooks=[]
    for site,markers in sorted(sites.items()):
        label=f'probe_dense_{site&0xffffffff:x}';word=struct.unpack_from('<I',raw,backed(m,site))[0]
        code,defs=relocate(word,site,'original_'+label);constants.update(defs)
        source += [f'.global {label}',label+':','    PROBE_SAVE']
        source += [f'    DENSE_ONCE {e["id"]}, {e["color"]}' for e in markers]
        source += ['    PROBE_RESTORE',f'.global {label}_replay',label+'_replay:',code]
        hooks.append((site,label))
    return '\n'.join(source)+'\n',constants,hooks,edges
