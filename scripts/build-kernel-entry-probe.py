"""Build a hash-pinned diagnostic kernel; preserve board, firmware and donor bytes."""
import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho'
EXPECTED='1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6'


def sha(data): return hashlib.sha256(data).hexdigest()
def align(n,a=4096): return (n+a-1)&-a
def macho(raw):
    if struct.unpack_from('<4I',raw)!=(0xfeedfacf,0x100000c,0,2):raise ValueError('Unexpected Mach-O')
    count,size=struct.unpack_from('<II',raw,16); cursor=32;segments=[];symbols={};entry=None
    for _ in range(count):
        cmd,length=struct.unpack_from('<II',raw,cursor)
        if length<8 or cursor+length>32+size:raise ValueError('Command bounds')
        if cmd==0x19:
            name=raw[cursor+8:cursor+24].split(b'\0')[0].decode();va,vm,off,fs=struct.unpack_from('<4Q',raw,cursor+24)
            segments.append(dict(name=name,va=va,size=vm,fileoff=off,filesize=fs,command_offset=cursor))
        if cmd==5:entry=struct.unpack_from('<Q',raw,cursor+272)[0]
        if cmd==2:
            at,n,st,sz=struct.unpack_from('<4I',raw,cursor+8)
            for i in range(n):
                k,t,s,d,v=struct.unpack_from('<IBBHQ',raw,at+i*16)
                if k and v:symbols[raw[st+k:raw.index(b'\0',st+k,st+sz)].decode(errors='replace')]=v
        cursor+=length
    if cursor!=32+size or entry is None:raise ValueError('Missing entry or command tail')
    return dict(segments=segments,symbols=symbols,entry=entry,command_end=cursor,ncmds=count,cmdbytes=size)
def backed(m,va,n=4):
    s=next(s for s in m['segments'] if s['va']<=va and va+n<=s['va']+s['filesize'])
    return s['fileoff']+va-s['va']
def branch(pc,target):
    delta=target-pc
    if delta%4 or not -(1<<27)<=delta<(1<<27):raise ValueError('Branch out of reach')
    return struct.pack('<I',0x14000000|((delta//4)&0x3ffffff))
def linux(p):return '/mnt/d/'+p.resolve().as_posix().split(':/',1)[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    work=a.work.resolve();output=a.output.resolve()
    if not work.is_relative_to(ROOT/'out') or work.exists() or not output.is_relative_to(ROOT/'reports') or output.exists():raise ValueError('Fresh out and reports required')
    raw=INPUT.read_bytes()
    if sha(raw)!=EXPECTED:raise ValueError('Input kernel changed')
    m=macho(raw);symbols=m['symbols'];entry=m['entry'];first=symbols['_start_first_cpu'];low=symbols['_LowExceptionVectorBase']
    if raw[backed(m,entry):backed(m,entry)+4]!=branch(entry,first):raise ValueError('Entry branch changed')
    # These exact instruction sites are in the fixed CI40015845083 native text.
    tables=first+0x22c;mmu=first+0x308;bcm=first+0x2d0
    # The SCTLR write itself and the isb that follows it are located by encoding,
    # not by a hardcoded offset, so a different native build fails instead of
    # silently hooking an unrelated instruction.
    msr=first+0x318;isb_site=msr+4
    if struct.unpack_from('<I',raw,backed(m,msr))[0]!=0xd5181000:raise ValueError('Expected msr sctlr_el1, x0 after the MMU band site')
    if struct.unpack_from('<I',raw,backed(m,isb_site))[0]!=0xd5033fdf:raise ValueError('Expected isb after the SCTLR write')
    if '_arm_init' not in symbols:raise ValueError('_arm_init symbol missing')
    arm_init=symbols['_arm_init']
    # C-entry markers past arm_init: located by symbol, validated by instruction word.
    for name in ('_current_percpu_base','_arm_vm_init','_pmap_bootstrap','_kernel_bootstrap'):
        if name not in symbols:raise ValueError(name+' symbol missing')
    expected={tables:0xd5033b9f,mmu:0xf2e00000,bcm:0xb9000001}
    for va,word in expected.items():
        if struct.unpack_from('<I',raw,backed(m,va))[0]!=word:raise ValueError(f'Unexpected instruction at {va:#x}')
    codeva=align(max(s['va']+s['size'] for s in m['segments']));fileoff=align(len(raw));work.mkdir(parents=True)
    template=(ROOT/'package/entry-probe/entry-probe.S').read_text(encoding='utf-8-sig')
    for name in ('_current_percpu_base','_arm_vm_init','_pmap_bootstrap','_kernel_bootstrap',
                 '_panic','_panic_trap_to_debugger','_panic_with_options','_early_random',
                 '_SecureDTLookupEntry','_pe_arm_get_soc_base_phys','_ml_parse_cpu_topology',
                 '_cpu_bootstrap','_machine_startup'):
        if not (0xfffffff007000000<=symbols[name]<0xfffffff008000000):raise ValueError(name+' outside the kernel text')
    # Fixed offsets inside arm_vm_init, pinned by instruction word like the start.s sites.
    avm_bases=symbols['_arm_vm_init']+0x54
    avm_memcheck=symbols['_arm_vm_init']+0xa4
    avm_physmap=symbols['_arm_vm_init']+0x108
    avm_slide=symbols['_arm_vm_init']+0x130
    constants=dict(original_first_cpu=first,original_tables_word=expected[tables],original_tables_resume=tables+4,original_mmu_word=expected[mmu],original_mmu_resume=mmu+4,
                   original_mmu_on_word=0xd5033fdf,original_mmu_on_resume=isb_site+4,
                   original_arm_init_word=struct.unpack_from('<I',raw,backed(m,arm_init))[0],original_arm_init_resume=arm_init+4,
                   original_cpu_base_word=struct.unpack_from('<I',raw,backed(m,symbols['_current_percpu_base']))[0],
                   original_cpu_base_resume=symbols['_current_percpu_base']+4,
                   original_arm_vm_word=struct.unpack_from('<I',raw,backed(m,symbols['_arm_vm_init']))[0],
                   original_arm_vm_resume=symbols['_arm_vm_init']+4,
                   original_pmap_word=struct.unpack_from('<I',raw,backed(m,symbols['_pmap_bootstrap']))[0],
                   original_pmap_resume=symbols['_pmap_bootstrap']+4,
                   original_kernel_bootstrap_word=struct.unpack_from('<I',raw,backed(m,symbols['_kernel_bootstrap']))[0],
                   original_kernel_bootstrap_resume=symbols['_kernel_bootstrap']+4,
                   original_avm_bases_word=struct.unpack_from('<I',raw,backed(m,avm_bases))[0],
                   original_avm_bases_resume=avm_bases+4,
                   original_avm_memcheck_word=struct.unpack_from('<I',raw,backed(m,avm_memcheck))[0],
                   original_avm_memcheck_resume=avm_memcheck+4,
                   original_panic_word=struct.unpack_from('<I',raw,backed(m,symbols['_panic']))[0],
                   original_panic_resume=symbols['_panic']+4,
                   original_panic_trap_word=struct.unpack_from('<I',raw,backed(m,symbols['_panic_trap_to_debugger']))[0],
                   original_panic_trap_resume=symbols['_panic_trap_to_debugger']+4,
                   original_avm_physmap_word=struct.unpack_from('<I',raw,backed(m,avm_physmap))[0],
                   original_avm_physmap_resume=avm_physmap+4,
                   original_avm_slide_word=struct.unpack_from('<I',raw,backed(m,avm_slide))[0],
                   original_avm_slide_resume=avm_slide+4,
                   original_early_random_word=struct.unpack_from('<I',raw,backed(m,symbols['_early_random']))[0],
                   original_early_random_resume=symbols['_early_random']+4,
                   original_dt_lookup_word=struct.unpack_from('<I',raw,backed(m,symbols['_SecureDTLookupEntry']))[0],
                   original_dt_lookup_resume=symbols['_SecureDTLookupEntry']+4,
                   original_soc_base_word=struct.unpack_from('<I',raw,backed(m,symbols['_pe_arm_get_soc_base_phys']))[0],
                   original_soc_base_resume=symbols['_pe_arm_get_soc_base_phys']+4,
                   original_cpu_topo_word=struct.unpack_from('<I',raw,backed(m,symbols['_ml_parse_cpu_topology']))[0],
                   original_cpu_topo_resume=symbols['_ml_parse_cpu_topology']+4,
                   original_cpu_bootstrap_word=struct.unpack_from('<I',raw,backed(m,symbols['_cpu_bootstrap']))[0],
                   original_cpu_bootstrap_resume=symbols['_cpu_bootstrap']+4,
                   original_machine_startup_word=struct.unpack_from('<I',raw,backed(m,symbols['_machine_startup']))[0],
                   original_machine_startup_resume=symbols['_machine_startup']+4,
                   original_panic_options_word=struct.unpack_from('<I',raw,backed(m,symbols['_panic_with_options']))[0],
                   original_panic_options_resume=symbols['_panic_with_options']+4)
    source='\n'.join(f'.equ {k}, {v:#x}' for k,v in constants.items() if k.endswith('_word'))+'\n'+template
    (work/'probe.S').write_text(source,encoding='utf-8',newline='\n')
    commands=[]
    for argv in (['clang','--target=aarch64-none-elf','-c',linux(work/'probe.S'),'-o',linux(work/'probe.o')],
                 ['ld.lld','-Ttext='+hex(codeva),'--entry=probe_entry',*[f'--defsym={k}={v:#x}' for k,v in constants.items() if not k.endswith('_word')],linux(work/'probe.o'),'-o',linux(work/'probe.elf')],
                 ['llvm-objcopy','-O','binary','--only-section=.text',linux(work/'probe.elf'),linux(work/'probe.bin')]):
        cmd=['wsl','-d','Ubuntu-22.04','--',*argv];r=subprocess.run(cmd,capture_output=True,text=True);commands.append(dict(argv=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));r.check_returncode()
    nm=subprocess.check_output(['wsl','-d','Ubuntu-22.04','--','llvm-nm','--defined-only',linux(work/'probe.elf')],text=True)
    hooks={name:int(addr,16) for addr,kind,name in re.findall(r'^([0-9a-fA-F]+)\s+(\S)\s+(\S+)$',nm,re.M)}
    code=(work/'probe.bin').read_bytes()
    # The zeroed per-CPU page starts at the assembler's probe_zero label, so its
    # address comes from the linked symbol table, never from a computed guess.
    zero_offset=hooks['probe_zero']-codeva
    if zero_offset%4096:raise ValueError('probe_zero must be page aligned')
    payload=code+b'\0'*(-len(code)%4096)
    payload+=b'\0'*4096
    if len(payload)<zero_offset+4096:raise ValueError('Probe extent too small for the per-CPU page')
    command=struct.pack('<II16s4Q4I',0x19,72,b'__NUWA_PROBE',codeva,len(payload),fileoff,len(payload),5,5,0,0)
    cursor=m['command_end']
    # Verify actual first section backing, not merely a zero-looking span.
    first_section=min(struct.unpack_from('<I',raw,s['command_offset']+72+80*i+48)[0] for s in m['segments'] for i in range(struct.unpack_from('<I',raw,s['command_offset']+64)[0]) if struct.unpack_from('<I',raw,s['command_offset']+72+80*i+48)[0])
    if cursor+72>first_section or raw[cursor:cursor+72]!=b'\0'*72:raise ValueError('No unused load-command padding')
    candidate=bytearray(raw);patches=[]
    def patch(off,new,reason,va=None):
        patches.append(dict(file_offset=off,va=hex(va) if va else None,before=bytes(candidate[off:off+len(new)]).hex(),after=new.hex(),reason=reason))
        candidate[off:off+len(new)]=new
    patch(16,struct.pack('<II',m['ncmds']+1,m['cmdbytes']+72),'Add one bounded RX diagnostic segment')
    patch(cursor,command,'Use verified zero load-command padding')
    sites=((entry,'probe_entry'),(tables,'probe_tables'),(mmu,'probe_mmu'),(isb_site,'probe_mmu_on'),
           (arm_init,'probe_arm_init'),(symbols['_current_percpu_base'],'probe_cpu_base'),
           (symbols['_arm_vm_init'],'probe_arm_vm'),(symbols['_pmap_bootstrap'],'probe_pmap'),
           (symbols['_kernel_bootstrap'],'probe_kernel_bootstrap'),
           (avm_bases,'probe_avm_bases'),(avm_memcheck,'probe_avm_memcheck'),
           (avm_physmap,'probe_avm_physmap'),(avm_slide,'probe_avm_slide'),
           (symbols['_early_random'],'probe_early_random'),
           (symbols['_SecureDTLookupEntry'],'probe_dt_lookup'),
           (symbols['_pe_arm_get_soc_base_phys'],'probe_soc_base'),
           (symbols['_ml_parse_cpu_topology'],'probe_cpu_topo'),
           (symbols['_cpu_bootstrap'],'probe_cpu_bootstrap'),
           (symbols['_machine_startup'],'probe_machine_startup'),
           (symbols['_panic'],'probe_panic'),
           (symbols['_panic_with_options'],'probe_panic_options'),
           (symbols['_panic_trap_to_debugger'],'probe_panic_trap'))
    for va,name in sites:patch(backed(m,va),branch(va,hooks[name]),name,va)
    patch(backed(m,bcm),struct.pack('<I',0xd503201f),'Suppress BCM2837-only MMIO write; no native timer activation',bcm)
    for index in range(16):
        va=low+index*128;off=backed(m,va)
        if raw[off:off+4]!=struct.pack('<I',0x14000000):raise ValueError('Early vector is not the expected self loop')
        patch(off,branch(va,hooks['probe_fault']),'Capture early exception ESR/ELR/FAR',va)
    candidate.extend(b'\0'*(fileoff-len(candidate)));candidate.extend(payload)
    after=macho(candidate)
    if after['entry']!=entry or len(after['segments'])!=len(m['segments'])+1:raise ValueError('Entry or segment count changed')
    allowed=set(i for item in patches for i in range(item['file_offset'],item['file_offset']+len(bytes.fromhex(item['after']))))
    changed={i for i,(x,y) in enumerate(zip(raw,candidate)) if x!=y}
    if not changed<=allowed:raise ValueError('Unrecorded original byte mutation')
    preserved=[]
    for seg in m['segments']:
        if seg['name'].startswith(('__PRELINK','__PLK')) and seg['filesize']:
            off=seg['fileoff'];n=seg['filesize']
            if raw[off:off+n]!=candidate[off:off+n]:raise ValueError('Donor or prelink segment changed')
            preserved.append(dict(name=seg['name'],sha256=sha(raw[off:off+n]),bytes=n))
    target=work/'kernel-entry-probe.macho';target.write_bytes(candidate)
    report=dict(scope='Diagnostic binary instrumentation of fixed analysis prelink; not runtime qualification',input_sha256=EXPECTED,candidate=dict(path=target.relative_to(ROOT).as_posix(),sha256=sha(candidate),bytes=len(candidate)),probe=dict(va=hex(codeva),file_offset=fileoff,code_bytes=len(code),segment_bytes=len(payload),sha256=sha(payload),symbols={k:hex(v) for k,v in hooks.items() if k.startswith(('probe_','fault_stop','exception_stop'))}),patches=patches,original_changed_bytes=len(changed),preserved_donor_segments=preserved,commands=commands,source_sha256=sha(template.encode()),loadable=False,runtime_qualified=False,device_accessed=False,probe_zero=hex(hooks['probe_zero']),probe_flags=hex(hooks['probe_flags']),screen=dict(bands=[dict(stage=1,y=256,color='blue',means='XNU __start branch and diagnostic entry executed'),dict(stage=2,y=352,color='yellow',means='Bootstrap page tables generated; before translation control setup'),dict(stage=3,y=448,color='magenta',means='Passed BCM block with invalid write suppressed; before enabling MMU'),dict(stage=4,y=736,color='cyan',means='msr sctlr_el1 executed and the following fetch was translated (V=P identity)'),dict(stage=5,y=832,color='white',means='arm_init entered at the KVA: TTBR1 fetch and translation are live')],fault=dict(y=544,color='red',hex_rows=dict(ESR_EL1=608,ELR_EL1=640,FAR_EL1=672)),post_mmu_mapping=dict(l1_slot=2,virtual='0x80000000',physical='0x80000000',size='0x40000000',descriptor='0x6000008000040d',attributes='Device-nGnRnE (MAIR index 3), AF, PXN|UXN, installed only if the slot is invalid',source='probe_mmu stub before the SCTLR write',scratch='framebuffer base and line stride copied from boot_args into probe_scratch'),limitations=['Bands do not prove arm_init returned, arm_vm_init, kext start or iOS','Cyan and white depend on the diagnostic 1 GiB device mapping installed pre-MMU; if the L1 slot were occupied nothing is drawn and no mapping is changed','Fault logger active only through physical early vector; x20 must still be boot_args','Exact video ABI and MMIO/cache effects need nuwa trial']))
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report['candidate']))
if __name__=='__main__':main()
