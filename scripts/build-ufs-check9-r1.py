"""WSL-only CHECK9 zero-draw control candidate. No device access.

The observer source is a byte-identical copy of CHECK5. The ONLY build-time
difference is the body of the appended `draw` helper: it is replaced by one
`ret` plus NOP padding of exactly the original instruction length, and the
font bitmap is preserved verbatim. Consequently every hook, every repair
patch (coarse_release_before stlr / phase_record gate), the inherited x30
defect, every bl draw callsite, and every symbol address stay byte-identical
to CHECK5. No framebuffer write and no `dsb sy` execute on the boot path.

This is the control for observer self-harm: if boot progresses past the
CHECK5/6/7/8 stall with the draw writes removed, the previous verdicts must
be re-evaluated. If the stall is unchanged, framebuffer writes are excluded
and the next suspect is hook control-flow / the inherited x30 defect.
"""
import argparse, copy, hashlib, importlib.util, json, os, struct, subprocess, sys, zlib
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    from pip._vendor import tomli as tomllib
    sys.modules['tomllib'] = tomllib
import flush_trace_inputs as trace
import nuwa_launch_context as context
import usb_ramdisk_package as transport

ROOT = trace.R
PARENT = ROOT/'out/ufs-check-4-r1-clean'
CHECK5 = ROOT/'out/ufs-check-5-r1-qualified'
KERNEL_SHA = '551a0cf621b5fca221be267ae25aba142d5aaa904cccdd5310dfb53b88474ec3'
IMAGE_SHA = '0a37f98ea65c14f80cb446aff89cff0e51184f983e723e50705a7ec701514257'
SOURCE = ROOT/'package/kernel-mainline/CoarseStages-ufs-check9-r1.S'
CHECK5_SOURCE = ROOT/'package/kernel-mainline/CoarseStages-ufs-check5-r1.S'
STATUS = ROOT/'package/ufs-r1/Status-r2.S'
RET = bytes.fromhex('c0035fd6')   # ret
NOP = bytes.fromhex('1f2003d5')   # nop


def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(path.read_bytes())
def save(path, value): path.write_text(json.dumps(value, indent=2)+'\n')
def native_path(value):
    value = str(value).replace('\\','/')
    return Path('/mnt/'+value[0].lower()+value[2:]) if len(value)>2 and value[1]==':' else Path(value)
def run(*args): return subprocess.check_output([str(x) for x in args], stderr=subprocess.STDOUT)
def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def compile_code(text, work):
    work.mkdir(parents=True, exist_ok=False);(work/'trace.S').write_text(text)
    run('/usr/bin/clang','--target=aarch64-none-elf','-c',work/'trace.S','-o',work/'trace.o')
    run('/usr/bin/ld.lld','-Ttext='+hex(trace.START),'-e','coarse_root_wait',work/'trace.o','-o',work/'trace.elf')
    run('/usr/bin/llvm-objcopy','-O','binary','--only-section=.text',work/'trace.elf',work/'trace.bin')
    sy={s[2]:int(s[0],16) for line in run('/usr/bin/llvm-nm','--defined-only',work/'trace.elf').decode().splitlines() if len(s:=line.split())==3}
    return (work/'trace.bin').read_bytes(), sy


def build(work):
    assert work.resolve().is_relative_to(ROOT/'out')
    work.mkdir(parents=True,exist_ok=False)
    raw=(PARENT/'kernel.macho').read_bytes();assert sha(raw)==KERNEL_SHA
    assert sha((PARENT/'boot-ufs-check-4-r1.img').read_bytes())==IMAGE_SHA
    # CHECK9 source must be a byte-identical copy of CHECK5: no hook removed,
    # no repair patch removed, no rewrite of any inherited line.
    assert SOURCE.read_bytes()==CHECK5_SOURCE.read_bytes(), 'CHECK9 source must equal CHECK5 byte-for-byte'
    check5_proof=read(CHECK5/'kernel-proof.json')
    check5_kernel=(CHECK5/'kernel.macho').read_bytes()
    assert sha(check5_kernel)==check5_proof['kernel_sha256']
    prior=read(PARENT/'kernel-proof.json'); b=trace.builder();m=b.macho(raw)
    compiler=module('check4_compiler',ROOT/'scripts/build-ufs-check4-r1.py')
    trace.compile_code=compile_code

    # 1. Reproduce the CHECK4 parent observer with the untouched compiler.
    oldcode,oldsy=compiler.compile_observer(work/'parent-reproduction',prior['targets'])
    off=b.backed(m,trace.START,len(oldcode))
    assert oldsy==prior['symbols'] and oldcode==raw[off:off+len(oldcode)]

    # 2. Baseline: same source, ORIGINAL draw. This is the reference image for
    #    every byte-level assertion below. It must reproduce CHECK5 exactly.
    compiler.SOURCE=SOURCE
    baseline,base_sy=compiler.compile_observer(work/'baseline',prior['targets'])
    assert base_sy==check5_proof['symbols'], 'baseline symbols must equal CHECK5'
    assert len(baseline)==check5_proof['code_bytes']
    baseline_kernel=bytearray(raw);baseline_kernel[off:off+len(baseline)]=baseline
    # Caller branches are recomputed below; compare the cave only here.
    assert baseline==check5_kernel[off:off+len(baseline)], 'baseline cave must equal CHECK5 cave'

    draw_at=base_sy['draw']-trace.START
    font_at=base_sy['font']-trace.START
    body_len=font_at-draw_at
    assert body_len%4==0 and body_len>=4
    nops=body_len//4-1

    # 3. Zero-draw: replace ONLY the draw body with ret + NOP padding, keep the
    #    font bitmap verbatim so the total length and all symbol addresses are
    #    unchanged. The compiler reads the display from compiler.ROOT.
    status=STATUS.read_text()
    font_text='font:'+status.split('\ndraw:\n',1)[1].split('font:',1)[1]
    override='    ret\n    .rept %d\n    nop\n    .endr\n'%nops+font_text
    fake=work/'zero-draw-display';(fake/'package/ufs-r1').mkdir(parents=True)
    (fake/'package/ufs-r1/Status-r2.S').write_text('\ndraw:\n'+override)
    compiler.ROOT=fake
    code,sy=compiler.compile_observer(work/'zero-draw',prior['targets'])

    # 4. The control's single-variable guarantee.
    # Only the local labels that lived INSIDE the original draw body may
    # disappear; every externally referenced symbol must keep its address.
    draw_local={'digit','draw_done','pixel_row','pixel_column'} | {
        k for k,v in base_sy.items() if k.startswith('fixup_') and draw_at<=v-trace.START<font_at}
    assert not (set(sy)-set(base_sy)), ('unexpected new symbol',set(sy)-set(base_sy))
    assert set(base_sy)-set(sy)==draw_local, ('non-draw symbol lost',set(base_sy)-set(sy)^draw_local)
    assert all(sy[k]==v for k,v in base_sy.items() if k in sy), 'symbol address moved'
    assert len(code)==len(baseline)
    assert code[:draw_at]==baseline[:draw_at], 'all observer bodies before draw must be byte-identical'
    assert code[font_at:]==baseline[font_at:], 'font bitmap and everything after draw must be byte-identical'
    body=code[draw_at:font_at]
    assert body[:4]==RET and body[4:]==NOP*nops, ('draw body must be ret + nops',body[:8].hex())
    draw_hex=body.hex()

    out=bytearray(raw);out[off:off+len(code)]=code
    entries={v:k for k,v in oldsy.items() if not k.startswith(('fixup_','$'))}
    patches=[];fullchanges=copy.deepcopy(prior['changes'])
    for change in fullchanges:
        address=int(change['address'],16);at=b.backed(m,address,4);word=int.from_bytes(raw[at:at+4],'little')
        if word&0x7c000000!=0x14000000: continue
        imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
        target=address+imm*4
        if not trace.START<=target<trace.START+len(oldcode):continue
        assert target in entries,(hex(address),hex(target))
        label=entries[target];after=b.branch(address,sy[label])
        if word&0x80000000:after=struct.pack('<I',int.from_bytes(after,'little')|0x80000000)
        out[at:at+4]=after
        patches.append(dict(address=hex(address),file_offset=at,before=raw[at:at+4].hex(),after=after.hex(),symbol=label))
        change['after']=after.hex()
    assert any(x['symbol']=='coarse_release_before' for x in patches)
    # Exhaustively check aligned direct branches into this cave.
    recorded={int(x['address'],16) for x in patches}; incoming=[]
    for seg in m['segments']:
        if not seg['filesize']:continue
        for at in range(seg['fileoff'],seg['fileoff']+seg['filesize']-3,4):
            address=seg['va']+at-seg['fileoff']
            if trace.START<=address<trace.START+max(len(oldcode),len(code)):continue
            word=struct.unpack_from('<I',raw,at)[0]
            if word&0x7c000000!=0x14000000:continue
            imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
            if trace.START<=address+4*imm<trace.START+len(oldcode):
                assert address in recorded,('unrecorded incoming branch',hex(address),hex(address+4*imm))
                incoming.append(hex(address))
    allowed=[(off,off+max(len(oldcode),len(code)))]+[(p['file_offset'],p['file_offset']+4) for p in patches]
    check=bytearray(out)
    for start,end in allowed:check[start:end]=raw[start:end]
    assert check==raw

    # 5. Whole-kernel differential against the qualified CHECK5 image: the only
    #    differing bytes in the ENTIRE kernel must be inside the draw body.
    diff=[i for i,(x,y) in enumerate(zip(out,check5_kernel)) if x!=y]
    assert len(out)==len(check5_kernel)
    lo,hi=off+draw_at,off+font_at
    assert all(lo<=i<hi for i in diff),('unexpected difference outside draw body',len(diff),[hex(i) for i in diff[:8]])
    assert len(diff)>0, 'zero-draw candidate is identical to CHECK5: draw was not replaced'
    # code[:draw_at] equality already covers every bl draw callsite.

    repair_patches=dict(
        coarse_release_before=dict(symbol_address=hex(sy['coarse_release_before']),
            effect='stlr x17,[x16] publishes ip_new_thread before native FINAL_WAIT release',
            preserved='byte-identical to CHECK5 (asserted by code[:draw_at] equality)'),
        phase_record=dict(symbol_address=hex(sy['phase_record']),
            effect='thread-scoped gate and coarse_state+256 phase bitmap',
            preserved='byte-identical to CHECK5'),
        inherited_read_return_chain_defect=dict(
            x30_installed_by_coarse_read_before='0xfffffff00769bfa4',
            coarse_read_after_patched_at='0xfffffff00769bf94',
            consequence='phase 6 hook structurally unreachable; deliberately preserved so CHECK9 shares the CHECK5/6/7/8 execution path'),
        observer_source_sha256=sha(SOURCE.read_bytes()),
        check5_observer_source_sha256=sha(CHECK5_SOURCE.read_bytes()))
    proof=copy.deepcopy(prior)
    proof.update(parent_build=str(native_path(prior['parent_build'])),kernel_sha256=sha(out),source_sha256=sha(SOURCE.read_bytes()),
        observer_source=str(SOURCE.relative_to(ROOT)),builder_source='scripts/build-ufs-check9-r1.py',code_bytes=len(code),symbols=sy,changes=fullchanges,
        objects=[dict(path=str(native_path(x['path'])),sha256=x['sha256']) for x in prior['objects']],
        repair_patches=repair_patches,
        check5_delta=dict(parent_kernel_sha256=KERNEL_SHA,parent_image_sha256=IMAGE_SHA,callers=patches,incoming_branches=incoming,
            observer_file_offset=off,old_code_bytes=len(oldcode),new_code_bytes=len(code),allowed_file_ranges=allowed,
            all_bytes_outside_declared_ranges_unchanged=True,ci_objects_reused_byte_identically=True,
            purpose='ZERO-DRAW CONTROL: observer source equals CHECK5 byte-for-byte; only the draw body is replaced by ret+nops. No framebuffer write, no dsb sy. Tests whether observer screen writes cause the boot stall.'),
        check9_delta=dict(
            baseline_code_sha256=sha(baseline),zero_draw_code_sha256=sha(code),
            baseline_code_equals_check5_cave=True,
            symbol_addresses_identical_to_baseline=True,
            symbol_table_note='all external/referenced symbols keep their CHECK5 address; only local labels inside the removed draw body disappear',
            draw_local_labels_removed=sorted(draw_local),
            draw_symbol=hex(sy['draw']),font_symbol=hex(sy['font']),
            draw_body_instructions=body_len//4,draw_body_bytes=body_len,draw_body_hex=draw_hex,
            draw_body_pattern='ret + %d nop'%nops,font_bitmap_preserved_verbatim=True,
            observer_bytes_before_draw_unchanged=True,observer_bytes_after_font_unchanged=True,
            whole_kernel_diff_vs_check5=dict(total_bytes=len(diff),all_within_draw_body=True,
                file_range=[lo,hi],offsets=diff[:64]),
            qualified_check5_kernel_sha256=check5_proof['kernel_sha256'],
            framebuffer_writes_on_boot_path=0,dsb_sy_on_boot_path=0,
            control_question='With screen writes removed, does boot progress past the CHECK5/6/7/8 stall?',
            verdict_matrix=dict(
                progresses='observer framebuffer writes are the stall cause; re-evaluate all prior root-cause verdicts',
                unchanged='framebuffer writes excluded; next suspect is hook control flow / inherited x30 defect / genuine UFS read hang')))
    (work/'kernel.macho').write_bytes(out);save(work/'kernel-proof.json',proof)
    (work/'zero-draw-display.S').write_text('\ndraw:\n'+override)
    return proof


def package(work, proof):
    fd=transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd';shim=transport.ARTIFACT/'shim/shim.bin'
    stock=native_path(transport.STOCK).read_bytes()
    assert [sha(p.read_bytes()) for p in (fd,shim)]==[transport.FD_SHA,transport.SHIM_SHA] and sha(stock)==transport.STOCK_SHA
    base=work/'base.adt';base.write_bytes((PARENT/'base.adt').read_bytes())
    launch=context.create(base,work/'kernel.macho',fd,shim,work/'launch')
    staging=work/'fat';staging.mkdir();fatpath=work/'payload.fat'
    menu=(PARENT/'fat/unixnu.toml').read_text().replace('UFS-CHECK-4 r1','UFS-CHECK-9 r1')
    assert 'UFS-CHECK-9 r1' in menu
    run('mformat','-C','-F','-T','131072','-v','NUWAXNU','-N','584E5558','-i',fatpath,'::')
    for d in ('::/EFI','::/EFI/UniXNU','::/EFI/UniXNU/Payloads'):run('mmd','-i',fatpath,d)
    for name,data,dest in [('unixnu.toml',menu.encode(),'::/EFI/UniXNU/unixnu.toml'),('kernel.macho',(work/'kernel.macho').read_bytes(),'::/EFI/UniXNU/Payloads/kernel.macho'),('kernel.macho.adt',(work/'launch/kernel.macho.adt').read_bytes(),'::/EFI/UniXNU/Payloads/kernel.macho.adt')]:
        p=staging/name;p.write_bytes(data);os.utime(p,(315532800,315532800));run('mcopy','-m','-i',fatpath,p,dest)
        back=staging/('readback-'+name);run('mcopy','-i',fatpath,dest,back);assert back.read_bytes()==data
    fat=fatpath.read_bytes();envelope=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat))+fat
    fw=shim.read_bytes()+fd.read_bytes();image=transport.compose(stock[:4096],fw,envelope,3)
    transport.inspect_container(image,stock[:4096],fw,envelope,3)
    path=work/'boot-ufs-check-9-r1.img';path.write_bytes(image)
    proof.update(image_path=str(path),image_sha256=sha(image),image_bytes=len(image),launch=launch)
    save(work/'build.json',proof);print(path,sha(image))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--kernel-only',action='store_true');a=p.parse_args()
    proof=build(a.work.resolve())
    if not a.kernel_only:package(a.work.resolve(),proof)
