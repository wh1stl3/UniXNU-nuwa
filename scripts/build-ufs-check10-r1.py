"""WSL-only CHECK10 observer: witness the REAL _vn_rdwr RET.

Inherits CHECK8 verbatim (CHECK5 prefix, all repair patches, c8_selfcheck and
c8_read_return, the full draw implementation). One hook is appended at the
_vn_rdwr epilogue 0x74669c8, immediately before the untouched native RET at
0x74669cc. At that point 0x74669c0 has already restored x30 from the stack,
so the captured value is the real return landing address of the call.

No control-flow change, no repair patch removed, no inherited observation
removed. Single-variable control against the consumed CHECK8 candidate.

No device access.
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
KERNEL_SHA = '551a0cf621b5fca221be267ae25aba142d5aaa904cccdd5310dfb53b88474ec3'
IMAGE_SHA = '0a37f98ea65c14f80cb446aff89cff0e51184f983e723e50705a7ec701514257'
SOURCE = ROOT/'package/kernel-mainline/CoarseStages-ufs-check10-r1.S'
CHECK8_SOURCE = ROOT/'package/kernel-mainline/CoarseStages-ufs-check8-r1.S'
CHECK8_KERNEL = ROOT/'out/ufs-check-8-r1/kernel.macho'
CHECK8_KERNEL_SHA = None  # bound from CHECK8 kernel-proof.json at build time

# CHECK8's two sites are inherited verbatim. The third is the new witness.
# 0x74669c8 is 'add sp,sp,#64' in the _vn_rdwr epilogue; 0x74669cc is RET.
PATCHES = (
    (0xfffffff007673118, '00200791', 'c8_selfcheck',   'c8_selfcheck_resume',   0xfffffff00767311c),
    (0xfffffff00769bfa4, '480340b9', 'c8_read_return', 'c8_read_return_resume', 0xfffffff00769bfa8),
    (0xfffffff0074669c8, 'ff030191', 'c10_vn_rdwr_ret','c10_vn_rdwr_ret_resume',0xfffffff0074669cc),
)
# DECIMAL field IDs. draw maps N -> 0xFB00+N; screen FBxx is HEX.
# 3/6/7 come from CHECK8; 21/22/23 are new and must have exactly one writer.
FIELD_IDS = (3, 6, 7, 21, 22, 23)
NEW_FIELD_IDS = (21, 22, 23)
RET_MAGIC = 0xC10A55AA

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
    prior=read(PARENT/'kernel-proof.json'); b=trace.builder();m=b.macho(raw)
    check8_proof=read(ROOT/'out/ufs-check-8-r1/kernel-proof.json')
    assert sha(CHECK8_KERNEL.read_bytes())==check8_proof['kernel_sha256']
    compiler=module('check4_compiler',ROOT/'scripts/build-ufs-check4-r1.py')
    trace.compile_code=compile_code
    oldcode,oldsy=compiler.compile_observer(work/'parent-reproduction',prior['targets'])
    off=b.backed(m,trace.START,len(oldcode))
    assert oldsy==prior['symbols'] and oldcode==raw[off:off+len(oldcode)]
    compiler.SOURCE=SOURCE
    check5=(compiler.ROOT/'package/kernel-mainline/CoarseStages-ufs-check5-r1.S').read_text()
    check8=CHECK8_SOURCE.read_text()
    source_text=SOURCE.read_text()
    assert source_text.startswith(check8), 'check10 must extend check8 verbatim'
    assert check8.startswith(check5), 'check8 must extend check5 verbatim'
    # No inherited observer line may be deleted or rewritten: the prefix also
    # carries repair patches (coarse_release_before publishes ip_new_thread).
    prefix_sha=sha(check5.encode());check8_sha=sha(check8.encode())
    assert len(source_text)>len(check8)
    for fb in FIELD_IDS:
        assert f'mov w0,#{fb}\n' not in check5, f'ID {fb} already has an inherited writer'
        assert source_text.count(f'mov w0,#{fb}\n') == 1, f'ID {fb} must have exactly one writer'
    assert 'c7_' not in source_text, 'CHECK7 observer body leaked into CHECK10'
    assert 'movz x30,#49044' in check5, 'inherited read_before x30 constant missing'
    # 49044 decimal == 0xBF94. The CHECK8 source comment and its build
    # script string both claim 0xBFA4 (49060); that is a DOCUMENTATION error,
    # not a machine-code difference. Verify the encoded immediate below.
    assert 'movz x30,#49044' in check5, 'read_before x30 constant changed'
    x30 = 49044
    assert x30==0xBF94 and x30!=0xBFA4, ('x30 low half must be 0xBF94 (49044 decimal)',hex(x30))
    # New field IDs must be absent from the CHECK8 prefix (no inherited writer).
    for fb in NEW_FIELD_IDS:
        assert f'mov w0,#{fb}\n' not in check8, f'new ID {fb} collides with check8'
    targets=dict(prior['targets'])
    for _pc,_before,_hook,resume,raddr in PATCHES:targets[resume]=raddr
    code,sy=compiler.compile_observer(work,targets)
    # Bind the x30 constant to the actual encoded instruction, not to any
    # comment: 9e f2 97 d2 == movz x30,#49044 == movz x30,#0xBF94.
    assert code.count(bytes.fromhex('9ef297d2'))==1, 'movz x30,#0xBF94 must be encoded exactly once'
    # Every exit hook must end with the native instruction it replaces, replayed
    # verbatim, immediately before its resume branch.
    for _pc,_before,_hook,_resume,_raddr in PATCHES:
        start=sy[_hook]-trace.START;end=start
        while True:
            word=struct.unpack_from('<I',code,end)[0];end+=4
            if word&0xfc000000==0x14000000:break
        replay=code[end-8:end-4]
        assert replay.hex()==_before,('hook must replay the native instruction verbatim',_hook,replay.hex(),_before)
    # The new hook must restore x30 from its own frame and then replay the
    # native stack adjustment, leaving the original RET untouched.
    ret_at=b.backed(m,0xfffffff0074669cc,4)
    assert raw[ret_at:ret_at+4].hex()=='c0035fd6', 'native RET changed'
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
    for pc,before,hook,resume,raddr in PATCHES:
        at=b.backed(m,pc,4)
        assert raw[at:at+4].hex()==before,(hex(pc),'exit site changed',raw[at:at+4].hex())
        after=b.branch(pc,sy[hook])
        out[at:at+4]=after
        role={'c8_selfcheck':'framebuffer_selfcheck','c8_read_return':'vn_rdwr_return'}.get(hook,'vn_rdwr_ret_witness')
        patches.append(dict(address=hex(pc),file_offset=at,before=before,after=after.hex(),symbol=hook,role=role))
    assert any(x['symbol']=='coarse_release_before' for x in patches)
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
    # Single-variable control against the consumed CHECK8 kernel: outside the
    # cave, the ONLY changed word may be the new witness site 0x74669c8.
    c8=CHECK8_KERNEL.read_bytes()
    cave_lo,cave_hi=off,off+max(len(oldcode),len(code),check8_proof['code_bytes'])
    outside=[]
    for at in range(0,min(len(c8),len(out)),4):
        if cave_lo<=at<cave_hi:continue
        if c8[at:at+4]!=out[at:at+4]:outside.append((at,c8[at:at+4].hex(),out[at:at+4].hex()))
    new_site_off=b.backed(m,0xfffffff0074669c8,4)
    assert [x[0] for x in outside]==[new_site_off],('unexpected CHECK8->CHECK10 outside-cave diff',outside[:10])
    assert outside[0][1]=='ff030191', 'CHECK8 must carry the native epilogue instruction'
    # Non-observational inherited patches. These are part of the boot contract,
    # not probes. Never strip them.
    repair_patches=dict(
        coarse_release_before=dict(address='0xfffffff00769d230',effect='stlr x17,[x16] publishes ip_new_thread before FINAL_WAIT release'),
        phase_record=dict(address=hex(sy['phase_record']),effect='thread-scoped gate and coarse_state+256 phase bitmap'),
        inherited_observer_prefix_sha256=prefix_sha,
        check8_observer_prefix_sha256=check8_sha,
        field_ids_unoccupied_in_prefix=list(FIELD_IDS))
    repair_patches['inherited_read_return_chain_defect']=dict(
        x30_installed_by_coarse_read_before='0xfffffff00769bf94',
        coarse_read_after_patched_at='0xfffffff00769bf94',
        consequence='RET lands on 0x769bf94 -> coarse_read_after -> 0x84d9be4 cbz w0; success b 0x769bf98, error b 0x769c144. This chain IS reachable.',
        correction='CHECK8 source comment and build-ufs-check8-r1.py string claim x30=0x769bfa4; the encoded movz #49044 is 0xBF94. The offline-audit README value 0x769bf94 is correct. Archived CHECK8 artifacts are not rewritten.',
        check8_fb07_caveat='c8_read_return was patched at 0x769bfa4, which is the resid!=0 short-read path; 0x769bf9c cbz w23 skips it on a normal resid==0 return. A blank FB07 therefore does NOT witness a missing vn_rdwr return.',
        witness='c10_vn_rdwr_ret reads x30 after the native ldp x29,x30,[sp,#48] in the _vn_rdwr epilogue')
    proof=copy.deepcopy(prior)
    proof.update(parent_build=str(native_path(prior['parent_build'])),kernel_sha256=sha(out),source_sha256=sha(SOURCE.read_bytes()),
        observer_source=str(SOURCE.relative_to(ROOT)),builder_source='scripts/build-ufs-check10-r1.py',code_bytes=len(code),symbols=sy,changes=fullchanges,
        objects=[dict(path=str(native_path(x['path'])),sha256=x['sha256']) for x in prior['objects']],
        repair_patches=repair_patches,
        check5_delta=dict(parent_kernel_sha256=KERNEL_SHA,parent_image_sha256=IMAGE_SHA,callers=patches,incoming_branches=incoming,
            observer_file_offset=off,old_code_bytes=len(oldcode),new_code_bytes=len(code),allowed_file_ranges=allowed,
            all_bytes_outside_declared_ranges_unchanged=True,ci_objects_reused_byte_identically=True,
            purpose='Witness the real _vn_rdwr RET: capture w0 and x30 at the epilogue before the untouched native ret. CHECK8 FB07 was sited on the resid!=0 short-read path and its blank value is inconclusive; CHECK10 settles whether the read returned at all. CHECK8 source verbatim, all repair patches retained, inherited x30 constant 0xBF94 preserved.'))
    proof['check10_delta']=dict(
        baseline='CHECK8 (consumed)',
        baseline_kernel_sha256=check8_proof['kernel_sha256'],
        baseline_source_sha256=sha(CHECK8_SOURCE.read_bytes()),
        source_prefix_verbatim=True,
        new_hook='c10_vn_rdwr_ret',
        new_patch_site='0xfffffff0074669c8',
        new_patch_before='ff030191',
        native_ret_preserved_at='0xfffffff0074669cc',
        native_ret_bytes='c0035fd6',
        outside_cave_diff_word_count=len(outside),
        outside_cave_only_diff=[dict(file_offset=at,before=x,after=y) for at,x,y in outside],
        new_field_ids_decimal=list(NEW_FIELD_IDS),
        encoding_formula='draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N; N is DECIMAL, screen suffix is HEX',
        new_field_labels={str(n):'0x%04X'%(0xFB00+n) for n in NEW_FIELD_IDS},
        arrival_magic=hex(RET_MAGIC),
        control_flow_changed=False,
        repair_patches_removed=0,
        inherited_observations_removed=0)
    (work/'kernel.macho').write_bytes(out);save(work/'kernel-proof.json',proof)
    return proof

def package(work, proof):
    fd=transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd';shim=transport.ARTIFACT/'shim/shim.bin'
    stock=native_path(transport.STOCK).read_bytes()
    assert [sha(p.read_bytes()) for p in (fd,shim)]==[transport.FD_SHA,transport.SHIM_SHA] and sha(stock)==transport.STOCK_SHA
    base=work/'base.adt';base.write_bytes((PARENT/'base.adt').read_bytes())
    launch=context.create(base,work/'kernel.macho',fd,shim,work/'launch')
    staging=work/'fat';staging.mkdir();fatpath=work/'payload.fat'
    menu=(PARENT/'fat/unixnu.toml').read_text().replace('UFS-CHECK-4 r1','UFS-CHECK-10 r1')
    assert 'UFS-CHECK-10 r1' in menu
    run('mformat','-C','-F','-T','131072','-v','NUWAXNU','-N','584E5558','-i',fatpath,'::')
    for d in ('::/EFI','::/EFI/UniXNU','::/EFI/UniXNU/Payloads'):run('mmd','-i',fatpath,d)
    for name,data,dest in [('unixnu.toml',menu.encode(),'::/EFI/UniXNU/unixnu.toml'),('kernel.macho',(work/'kernel.macho').read_bytes(),'::/EFI/UniXNU/Payloads/kernel.macho'),('kernel.macho.adt',(work/'launch/kernel.macho.adt').read_bytes(),'::/EFI/UniXNU/Payloads/kernel.macho.adt')]:
        p=staging/name;p.write_bytes(data);os.utime(p,(315532800,315532800));run('mcopy','-m','-i',fatpath,p,dest)
        back=staging/('readback-'+name);run('mcopy','-i',fatpath,dest,back);assert back.read_bytes()==data
    fat=fatpath.read_bytes();envelope=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat))+fat
    fw=shim.read_bytes()+fd.read_bytes();image=transport.compose(stock[:4096],fw,envelope,3)
    transport.inspect_container(image,stock[:4096],fw,envelope,3)
    path=work/'boot-ufs-check-10-r1.img';path.write_bytes(image)
    proof.update(image_path=str(path),image_sha256=sha(image),image_bytes=len(image),launch=launch)
    save(work/'build.json',proof);print(path,sha(image))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--kernel-only',action='store_true');a=p.parse_args()
    proof=build(a.work.resolve())
    if not a.kernel_only:package(a.work.resolve(),proof)
