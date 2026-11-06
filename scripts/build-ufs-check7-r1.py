"""WSL-only CHECK7 observer: pure-memory exit records plus one snapshot painter.

Inherits CHECK5 verbatim (all repair patches preserved). Three exit hooks write
only to coarse_state; one snapshot hook paints FB03/FB06/FB07 once, after the
vfs_mountroot return where framebuffer is known live. No device access.

Recompile the complete observer at its existing address and relocate only its
existing direct callers. Preserve every other kernel byte and all CI objects.
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
SOURCE = ROOT/'package/kernel-mainline/CoarseStages-ufs-check7-r1.S'

# CHECK6 adds exit observers inside _vfs_mountroot so the single returned errno
# can be attributed to one of the four source-level returns. Each site records
# the native x0 into a dedicated FB field; the fields are mutually exclusive.
#   FB11 <- (*mountroot)() return (only reached when mountroot != NULL)
#   FB13 <- bdevvp() failure errno (only reached when bdevvp != 0)
#   FB14 <- (*vfc_mountroot)() return (only reached when that hook exists)
EXITS = (
    (0xfffffff0074437f0, '680340b9', 'c7_mountroot_ret', 'c7_mountroot_resume', 0xfffffff0074437f4),
    (0xfffffff00744382c, 'f30300aa', 'c7_bdevvp_fail',   'c7_bdevvp_resume',   0xfffffff007443830),
    (0xfffffff007443910, 'f80300aa', 'c7_vfcmount_ret',  'c7_vfcmount_resume', 0xfffffff007443914),
)
# The snapshot hook replaces the native instruction at coarse_mount_return+4.
# It runs exactly once per vfs_mountroot return, after all three exit records exist.
SNAPSHOT = (0xfffffff0076730ec, 'f80300aa', 'c7_snapshot', 'c7_snapshot_resume', 0xfffffff0076730f0)
PATCHES = EXITS + (SNAPSHOT,)
# FB03/FB06/FB07 have no writer in the inherited CHECK5 observer. CHECK6 used
# FB11/FB13/FB14, which are shared with coarse_init_entry/init_loaded/exec.
FIELD_IDS = (3, 6, 7)
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
    compiler=module('check4_compiler',ROOT/'scripts/build-ufs-check4-r1.py')
    trace.compile_code=compile_code
    # Reproduce the original observer with the same compiler before substitution.
    oldcode,oldsy=compiler.compile_observer(work/'parent-reproduction',prior['targets'])
    off=b.backed(m,trace.START,len(oldcode))
    assert oldsy==prior['symbols'] and oldcode==raw[off:off+len(oldcode)]
    compiler.SOURCE=SOURCE
    check5=(compiler.ROOT/'package/kernel-mainline/CoarseStages-ufs-check5-r1.S').read_text()
    assert SOURCE.read_text().startswith(check5), 'check7 must extend check5 verbatim'
    # No inherited observer line may be deleted or rewritten: the prefix also
    # carries repair patches (coarse_release_before publishes ip_new_thread).
    prefix_sha=sha(check5.encode());assert len(SOURCE.read_text())>len(check5)
    for fb in FIELD_IDS:
        assert f'mov w0,#{fb}\n' not in check5, f'FB{fb:02d} already has an inherited writer'
    targets=dict(prior['targets'])
    for _pc,_before,_hook,resume,raddr in PATCHES:targets[resume]=raddr
    code,sy=compiler.compile_observer(work,targets)
    # Every exit hook must end with the native instruction it replaces, replayed
    # verbatim, immediately before its resume branch. A hand-written replay that
    # differs in even one immediate silently changes kernel semantics.
    for _pc,_before,_hook,_resume,_raddr in PATCHES:
        start=sy[_hook]-trace.START;end=start
        while True:
            word=struct.unpack_from('<I',code,end)[0];end+=4
            if word&0xfc000000==0x14000000:break
        replay=code[end-8:end-4]
        assert replay.hex()==_before,('hook must replay the native instruction verbatim',_hook,replay.hex(),_before)
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
        patches.append(dict(address=hex(pc),file_offset=at,before=before,after=after.hex(),symbol=hook,role='snapshot' if hook=='c7_snapshot' else 'exit'))
    assert any(x['symbol']=='coarse_release_before' for x in patches)
    # Exhaustively check aligned direct branches into this cave, including
    # retained legacy bodies. Unrecorded incoming references fail closed.
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
    # Non-observational inherited patches. These are part of the boot contract,
    # not probes: coarse_release_before publishes ip_new_thread via stlr, and
    # phase_record maintains the scoped phase bitmap. Never strip them.
    repair_patches=dict(
        coarse_release_before=dict(address='0xfffffff00769d230',effect='stlr x17,[x16] publishes ip_new_thread before FINAL_WAIT release'),
        phase_record=dict(address='dynamic',effect='thread-scoped gate and coarse_state+256 phase bitmap'),
        inherited_observer_prefix_sha256=prefix_sha,
        field_ids_unoccupied_in_prefix=list(FIELD_IDS))
    repair_patches['phase_record']['address']=hex(sy['phase_record'])
    repair_patches['coarse_release_before']['address']='0xfffffff00769d230'
    repair_patches['inherited_branch_to_mount_return_resume']='0xfffffff0076730ec (nonzero vfs_mountroot return; CHECK7 snapshot hook replaces the native mov x24,x0 here)'
    proof=copy.deepcopy(prior)
    proof.update(parent_build=str(native_path(prior['parent_build'])),kernel_sha256=sha(out),source_sha256=sha(SOURCE.read_bytes()),
        observer_source=str(SOURCE.relative_to(ROOT)),builder_source='scripts/build-ufs-check7-r1.py',code_bytes=len(code),symbols=sy,changes=fullchanges,
        objects=[dict(path=str(native_path(x['path'])),sha256=x['sha256']) for x in prior['objects']],
        repair_patches=repair_patches,
        check5_delta=dict(parent_kernel_sha256=KERNEL_SHA,parent_image_sha256=IMAGE_SHA,callers=patches,incoming_branches=incoming,
            observer_file_offset=off,old_code_bytes=len(oldcode),new_code_bytes=len(code),allowed_file_ranges=allowed,
            all_bytes_outside_declared_ranges_unchanged=True,ci_objects_reused_byte_identically=True,
            purpose='Pure-memory exit attribution: three vfs_mountroot exits record x0+magic; one snapshot paints FB03/FB06/FB07 once. CHECK5 prefix verbatim, all repair patches retained.'))
    (work/'kernel.macho').write_bytes(out);save(work/'kernel-proof.json',proof)
    return proof

def package(work, proof):
    fd=transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd';shim=transport.ARTIFACT/'shim/shim.bin'
    stock=native_path(transport.STOCK).read_bytes()
    assert [sha(p.read_bytes()) for p in (fd,shim)]==[transport.FD_SHA,transport.SHIM_SHA] and sha(stock)==transport.STOCK_SHA
    base=work/'base.adt';base.write_bytes((PARENT/'base.adt').read_bytes())
    launch=context.create(base,work/'kernel.macho',fd,shim,work/'launch')
    staging=work/'fat';staging.mkdir();fatpath=work/'payload.fat'
    menu=(PARENT/'fat/unixnu.toml').read_text().replace('UFS-CHECK-4 r1','UFS-CHECK-7 r1')
    assert 'UFS-CHECK-7 r1' in menu
    run('mformat','-C','-F','-T','131072','-v','NUWAXNU','-N','584E5558','-i',fatpath,'::')
    for d in ('::/EFI','::/EFI/UniXNU','::/EFI/UniXNU/Payloads'):run('mmd','-i',fatpath,d)
    for name,data,dest in [('unixnu.toml',menu.encode(),'::/EFI/UniXNU/unixnu.toml'),('kernel.macho',(work/'kernel.macho').read_bytes(),'::/EFI/UniXNU/Payloads/kernel.macho'),('kernel.macho.adt',(work/'launch/kernel.macho.adt').read_bytes(),'::/EFI/UniXNU/Payloads/kernel.macho.adt')]:
        p=staging/name;p.write_bytes(data);os.utime(p,(315532800,315532800));run('mcopy','-m','-i',fatpath,p,dest)
        back=staging/('readback-'+name);run('mcopy','-i',fatpath,dest,back);assert back.read_bytes()==data
    fat=fatpath.read_bytes();envelope=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat))+fat
    fw=shim.read_bytes()+fd.read_bytes();image=transport.compose(stock[:4096],fw,envelope,3)
    transport.inspect_container(image,stock[:4096],fw,envelope,3)
    path=work/'boot-ufs-check-7-r1.img';path.write_bytes(image)
    proof.update(image_path=str(path),image_sha256=sha(image),image_bytes=len(image),launch=launch)
    save(work/'build.json',proof);print(path,sha(image))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--kernel-only',action='store_true');a=p.parse_args()
    proof=build(a.work.resolve())
    if not a.kernel_only:package(a.work.resolve(),proof)
